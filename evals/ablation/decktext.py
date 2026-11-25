"""Turn a deck into the plain text a reader sees, for the judge and the figure checks.

Both conditions go through the same function. It drops what a reader does not see by default
(scripts, styles, the hidden template guidance and its reading list, the navigation rail) and
the brand mark, so the judge is not told which condition made a deck. It keeps every slide's
words and figures. Illustrative samples stay in, wrapped in markers, so the judge sees them as a
reader would and the figure check can count them apart from data.

Standard library only.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

# Elements whose text a reader does not see by default, or that only name the tool.
HIDDEN_CLASSES = {"guide", "rail", "brand"}
HIDDEN_TAGS = {"script", "style", "details", "nav", "head", "template", "noscript"}
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "source", "wbr", "col", "area", "base", "embed", "track", "param"}
BLOCK_TAGS = {"div", "p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "br", "table", "ul", "ol", "dt", "dd", "header", "footer", "article"}
CELL_TAGS = {"td", "th"}
SAMPLE_START = "[ILLUSTRATIVE SAMPLE, greyed out on the slide]"
SAMPLE_END = "[END OF ILLUSTRATIVE SAMPLE]"


class _Text(HTMLParser):
    def __init__(self, drop_ids: frozenset[str] = frozenset()) -> None:
        super().__init__(convert_charrefs=True)
        self.drop_ids = drop_ids
        self.stack: list[tuple[str, bool, bool]] = []  # (tag, hides, is_sample)
        self.out: list[str] = []

    def hidden(self) -> bool:
        return any(h for _, h, _ in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        hides = tag in HIDDEN_TAGS or bool(classes & HIDDEN_CLASSES) or (a.get("id") or "") in self.drop_ids
        sample = "sample" in classes
        if tag in BLOCK_TAGS or tag in CELL_TAGS:
            self.out.append("\n" if tag in BLOCK_TAGS else " | ")
        if sample and not self.hidden():
            self.out.append(f"\n{SAMPLE_START}\n")
        if tag not in VOID_TAGS:
            self.stack.append((tag, hides, sample))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        # Pop to the matching tag; tolerate unclosed children.
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                closing = self.stack[i:]
                del self.stack[i:]
                if any(s for _, _, s in closing) and not self.hidden():
                    self.out.append(f"\n{SAMPLE_END}\n")
                break
        if tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden():
            self.out.append(data)


def html_to_text(html: str, drop_ids: frozenset[str] = frozenset()) -> str:
    """Visible text of an HTML deck. drop_ids removes whole elements by id, for a counterfactual run only."""
    p = _Text(drop_ids)
    p.feed(html)
    p.close()
    text = "".join(p.out)
    text = re.sub(r"\bDacard\b", "", text).replace("Show template guidance", "").replace("Made with the Product & Technology Leader Report by", "")
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def deck_text(path: Path, drop_ids: frozenset[str] = frozenset()) -> str:
    """Plain text of one deck file: HTML is reduced to visible text; Markdown and text pass through."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        return html_to_text(raw, drop_ids)
    return raw.strip()


def split_samples(text: str) -> tuple[str, str]:
    """Return (text outside illustrative samples, text inside them)."""
    inside: list[str] = []
    outside: list[str] = []
    pos = 0
    while True:
        i = text.find(SAMPLE_START, pos)
        if i < 0:
            outside.append(text[pos:])
            break
        j = text.find(SAMPLE_END, i)
        j = len(text) if j < 0 else j
        outside.append(text[pos:i])
        inside.append(text[i + len(SAMPLE_START) : j])
        pos = j + len(SAMPLE_END)
    return "".join(outside), "\n".join(inside)
