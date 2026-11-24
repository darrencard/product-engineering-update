#!/usr/bin/env python3
"""Write a Markdown summary of the update, ready to post to Linear as a document or project update.

Usage:
  python3 scripts/summary.py run/deck.json --out run/summary.md                  # the full deck
  python3 scripts/summary.py run/deck.json --out run/staff.md --cut S            # one cut: L or S
  python3 scripts/summary.py run/deck.json --out run/board.md --cut B --signed-off-by "Name"
  python3 scripts/summary.py run/deck.json --out run/summary.md --link https://example.com/update.html

The summary lists each slide's title, the ledger rows it cites, the slides that show gaps, and the
cited ledger rows with their source and window. It adds nothing the deck does not say.

It refuses, like render.py, when validate.py finds errors, and it refuses the board cut without
--signed-off-by naming the person who said yes. It writes a file and prints where; it never posts.
The agent shows the file to the person and posts it through the Linear connector only after they
confirm. The board cut is never posted automatically, not even by a scheduled run.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]
CUT_NAMES = {"L": "Leadership", "B": "Board", "S": "Staff"}
GAP_TITLE = "is not reported this period"


def plain(text: str) -> str:
    """Text safe to post as Markdown: deck markup is kept to safe links, ledger marks become IDs, and nothing can
    become an image, raw HTML or a mention of someone in the workspace."""
    text = re.sub(r"\[\[(L\d+)\]\]", r" (\1)", text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"!(?=\[)", "", text)
    text = re.sub(r"@(?=\w)", "@\u200b", text)
    return validate.MARKDOWN_LINK.sub(lambda m: m.group(0) if validate.is_safe_link(m.group(2)) else m.group(1), text)


def slides_in(deck: Json, cut: str | None) -> list[Json]:
    core = [s for s in deck["slides"] if s["kind"] == "slide"]
    return [s for s in core if cut in s["audiences"]] if cut else core


def build(deck: Json, cut: str | None, signed_off_by: str | None, link: str | None) -> str:
    """The summary as Markdown. Refuses a deck with validator errors, and a board cut with no named sign-off."""
    report = validate.check(deck)
    if not report["ok"]:
        raise SystemExit(f"summary: the deck has {len(report['errors'])} validator error(s). Run validate.py and fix them first.")
    if cut is not None and cut not in CUT_NAMES:
        raise SystemExit(f"summary: --cut must be one of {', '.join(CUT_NAMES)}.")
    if cut == "B" and not (signed_off_by or "").strip():
        raise SystemExit("summary: the board cut needs --signed-off-by with the name of the person who said yes. Nothing was written.")
    if link and not validate.is_safe_link(link):
        raise SystemExit(f"summary: --link must start with https://, http:// or mailto:, got {link[:80]!r}.")
    meta = deck["meta"]
    slides = slides_in(deck, cut)
    shown = [s for s in slides if GAP_TITLE not in s["title"]]
    gaps = [s for s in slides if GAP_TITLE in s["title"]]
    lines = [
        f"# {plain(meta['company'])} product & engineering update, {plain(meta['period'])}",
        "",
        f"{CUT_NAMES.get(cut or '', 'Full deck')}. Data as of {meta['as_of']}. {len(shown)} of {len(slides)} slides show data.",
    ]
    if cut == "B":
        lines.append(f"Signed off by {plain(signed_off_by.strip())}.")  # type: ignore[union-attr]
    if link:
        lines.append(f"The full update: [open it]({link}).")
    lines += ["", "## What the update says", ""]
    cited: list[str] = []
    for s in shown:
        refs = sorted(set(validate.ledger_refs(s)))
        cited += refs
        # Slide 8's title counts metrics that moved; posted alone it could read as cause, so the caveat travels with it.
        caveat = " Moved means the metric went the right way, not that the commitment caused it." if s["id"] == "08" else ""
        lines.append(f"- **{plain(s['nav'])}.** {plain(s['title'])}{caveat}" + (f" Ledger: {', '.join(refs)}." if refs else ""))
    if gaps:
        lines += ["", "## Not reported this period", ""]
        lines += [f"- **{plain(s['nav'])}.** The data is missing." for s in gaps]
    rows = [r for r in deck["ledger"] if r["id"] in set(cited)]
    if rows:
        lines += ["", "## Ledger rows cited", "", "| ID | Claim | Source | Window | Confidence |", "|---|---|---|---|---|"]
        for r in rows:
            source = plain(r["source_system"])
            where = r.get("query_or_url")
            if isinstance(where, str) and validate.is_safe_link(where):
                source = f"[{source}]({where})"
            cells = [r["id"], plain(r["claim"]), source, plain(r.get("window") or ""), r["confidence"]]
            lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    lines += ["", "Status words: landed, watch, stalled. Every figure has a row in the evidence ledger. A slide without its data says so."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Write a Markdown summary of the update for Linear.")
    ap.add_argument("deck")
    ap.add_argument("--out", required=True, help="the Markdown file to write")
    ap.add_argument("--cut", help="summarise one audience's cut: L, B or S")
    ap.add_argument("--signed-off-by", help="the person who said yes; required for the board cut")
    ap.add_argument("--link", help="where the rendered update can be opened, if it is shared somewhere")
    args = ap.parse_args()
    text = build(validate.read_deck(Path(args.deck), tool="summary"), args.cut, args.signed_off_by, args.link)
    out = Path(args.out)
    out.write_text(text, encoding="utf-8")
    print(f"summary: wrote {out}. Show it to the person; post it to Linear only after they confirm.")
    if args.cut == "B":
        print("summary: this is the board cut. Never post it automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
