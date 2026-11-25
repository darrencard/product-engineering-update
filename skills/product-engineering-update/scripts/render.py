#!/usr/bin/env python3
"""Render a deck JSON to one self-contained HTML file, plus the ledger as CSV.

Usage:
  python3 scripts/render.py deck.json --out update.html
  python3 scripts/render.py deck.json --out board.html --cut B --signed-off-by "Name"

The output has inline CSS, JS and fonts and makes no network calls.
A render refuses to run when validate.py finds errors, and the board cut
(--cut B) also needs --signed-off-by, because a person signs what a board sees.

Standard library only. This file is a port of the site's renderer; the test
in evals/ holds the two to the same output.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

# validate.py sits beside this file. Python puts a script's own folder on sys.path, except in
# isolated mode (python3 -I), which sandboxes use. Naming the folder here makes both cases the same.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import validate  # noqa: E402  (must follow the path line above)

ASSETS = HERE.parent / "assets"
Json = dict[str, Any]
Table = tuple[list[Json], list[Any]]

GRID = {"2": "g2", "3": "g3", "4": "g4", "2:1": "g21"}
NOTE_STYLE = ' style="font-size:12.5px;margin:14px 0 0"'
# The space above a paragraph, in px, by what comes before it in a card.
PARAGRAPH_GAP = {"pv": 14, "table": 12, "p": 10}
LEDGER_FIELDS = ("id", "claim", "value", "unit", "source_system", "query_or_url", "window", "retrieved_at", "confidence", "owner", "stale")
# A spreadsheet runs a cell that starts with one of these as a formula, so a ledger claim could run code
# on the reader's machine. A leading apostrophe makes the cell plain text.
FORMULA_START = re.compile(r"\s*[=+\-@]")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def attr(s: str) -> str:
    return esc(s).replace('"', "&quot;")


def safe_link(target: str) -> str:
    """Return a link target unchanged when it is http, https or mailto. Refuse the render otherwise."""
    if not validate.is_safe_link(target):
        raise SystemExit(f'render: the link "{target}" is not allowed. {validate.LINK_HELP}. Fix the deck, then render again.')
    return target


def _anchor(found: re.Match[str]) -> str:
    label = found.group(1)
    href = safe_link(found.group(2)).replace('"', "&quot;")
    return f'<a href="{href}">{label}</a>'


def rich(text: str) -> str:
    """The deck's light markup: status marks, ledger references, bold, links."""
    t = esc(text)
    t = re.sub(r"\[\[status:(landed|watch|stalled)\]\]", r'<span class="st \1">\1</span>', t)
    t = re.sub(r"\[\[([A-Z]\d+)\]\]", r'<span class="led">\1</span>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return validate.MARKDOWN_LINK.sub(_anchor, t)


def style_attr(parts: Iterable[str]) -> str:
    s = ";".join(p for p in parts if p)
    return f' style="{s}"' if s else ""


def max_width(b: Json) -> str:
    return f"max-width:{num(b['max_width'])}px" if b.get("max_width") else ""


def num_class(column: Json) -> str:
    return ' class="num"' if column.get("align") == "num" else ""


def cell_class(column: Json) -> str:
    return ' class="mono"' if column.get("mono") else num_class(column)


def table_rows(columns: list[Json], rows: list[Any]) -> str:
    head = "".join(f"<th{num_class(c)}>{rich(c['label'])}</th>" for c in columns)
    body = []
    for r in rows:
        if isinstance(r, dict):
            body.append(f'<tr class="grp"><td colspan="{len(columns)}">{rich(r["group"])}</td></tr>')
            continue
        cells = [f"<td{cell_class(columns[i] if i < len(columns) else {})}>{cell_html(cell)}</td>" for i, cell in enumerate(r)]
        body.append(f"<tr>{''.join(cells)}</tr>")
    joined = "\n".join(body)
    return f"<table>\n<tr>{head}</tr>\n{joined}\n</table>"


def scorecard_as_table(b: Json) -> Table:
    labels = b["labels"]
    columns = [
        {"label": labels["metric"]},
        {"label": labels["prior"], "align": "num"},
        {"label": labels["actual"], "align": "num"},
        {"label": labels["target"], "align": "num"},
        {"label": labels["status"]},
    ] + [{"label": x} for x in labels.get("extra", [])]
    rows = [
        r if "group" in r else [metric_cell(r), r["prior"], actual_cell(r), r["target"], f"[[status:{r['status']}]]"] + r.get("extra", []) for r in b["rows"]
    ]
    return columns, rows


def metric_cell(r: Json) -> Any:
    """The metric's name, with its definition beneath it when the row carries one."""
    return {"text": r["metric"], "sub": r["definition"]} if r.get("definition") else r["metric"]


def actual_cell(r: Json) -> Any:
    """The figure, with what it covers beneath it when that is less than the reporting window."""
    return {"text": r["actual"], "sub": r["coverage"]} if r.get("coverage") else r["actual"]


def cell_html(cell: Any) -> str:
    """A table cell's content. A cell with a sub line shows it beneath, smaller and muted, so a reader sees what the figure counts."""
    if isinstance(cell, dict):
        return f'{rich(cell["text"])}<span class="t3" style="display:block;font-size:12px;line-height:1.4;margin-top:2px">{rich(cell["sub"])}</span>'
    return rich(cell)


def ledger_as_table(deck: Json) -> Table:
    columns = [{"label": "ID", "mono": True}, {"label": "Claim"}, {"label": "Source"}, {"label": "Window"}, {"label": "Confidence"}]
    return columns, [[r["id"], r["claim"], r["source_system"], r["window"], r["confidence"]] for r in deck["ledger"]]


def requirements(deck: Json, s: Json) -> list[Json]:
    """What a slide needs: its own requirements, then those of the slides it condenses."""
    by_id = {x["id"]: x for x in deck["slides"]}
    inherited = [r for sid in s.get("rolls_up", []) for r in by_id.get(sid, {}).get("requires", [])]
    return s.get("requires", []) + inherited


def sources_needed(deck: Json) -> list[tuple[Json, list[tuple[Json, Json]]]]:
    out = []
    for t in deck["meta"]["source_types"]:
        uses = [(s, r) for s in deck["slides"] for r in requirements(deck, s) if r["source"] == t["key"]]
        if uses:
            out.append((t, uses))
    return out


def required_by_cut(deck: Json) -> list[tuple[Json, list[Json]]]:
    out = []
    for a in deck["meta"]["audiences"]:
        slides = [s for s in deck["slides"] if s["kind"] == "slide" and a["key"] in s["audiences"]]
        keys = {r["source"] for s in slides for r in requirements(deck, s) if r["required"]}
        out.append((a, [t for t in deck["meta"]["source_types"] if t["key"] in keys]))
    return out


def short_id(slide_id: str) -> str:
    """Slide 03 reads as 3."""
    return re.sub(r"^0", "", slide_id)


def slide_label(s: Json) -> str:
    return f"Appendix {s['id']}" if s["kind"] == "appendix" else short_id(s["id"])


def unique(items: Iterable[str]) -> list[str]:
    """The items in their first-seen order, each once."""
    return list(dict.fromkeys(items))


def sources_as_table(deck: Json) -> Table:
    columns = [{"label": "Source"}, {"label": "Examples"}, {"label": "Feeds slides"}, {"label": "What it must hold"}, {"label": "CSV fallback"}]
    rows = []
    for t, uses in sources_needed(deck):
        feeds = ", ".join(unique(slide_label(s) for s, _ in uses))
        holds = ". ".join(unique(r["data"] for _, r in uses)) + "."
        rows.append([t["label"], ", ".join(t["examples"]), feeds, holds, t["csv"]])
    return columns, rows


def table_of(b: Json, deck: Json) -> str:
    kind = b["type"]
    if kind == "scorecard":
        columns, rows = scorecard_as_table(b)
    elif kind == "ledger":
        columns, rows = ledger_as_table(deck)
    elif kind == "sources_needed":
        columns, rows = sources_as_table(deck)
    else:
        columns, rows = b["columns"], b["rows"]
    return table_rows(columns, rows)


def plan_vs_actual(b: Json) -> str:
    lg = b["legend"]
    key = (
        f'<div class="key"><span><i></i>{rich(lg["plan"])}</span><span><i class="a"></i>{rich(lg["actual"])}</span>'
        f'<span><i class="o"></i>{rich(lg["over"])}</span></div>'
    )
    rows = []
    for r in b["rows"]:
        over = " over" if r.get("over") else ""
        rows.append(
            f'<span>{rich(r["label"])}</span><div class="track"><div class="b" style="width:{num(r["plan"] * 2)}%"></div>'
            f'<div class="b a{over}" style="width:{num(r["actual"] * 2)}%"></div></div><span class="v">{num(r["plan"])} / {num(r["actual"])}%</span>'
        )
    joined = "\n".join(rows)
    return f'{key}\n<div class="pv">\n{joined}\n</div>'


def num(n: float) -> str:
    """Print 20 as 20 and 20.5 as 20.5, the way JavaScript does."""
    return str(int(n)) if float(n) == int(n) else repr(float(n))


def paragraph(part: str | Json, prev: str) -> str:
    p = {"p": part} if isinstance(part, str) else part
    space = p.get("space", PARAGRAPH_GAP.get(prev))
    margin = f"margin-top:{num(space)}px" if space is not None and prev != "h3" else ""
    return f"<p{style_attr([margin, 'color:var(--t1)' if p.get('emphasis') else ''])}>{rich(p['p'])}</p>"


def card(c: Json, deck: Json, style: str = "") -> str:
    out = []
    if c.get("title"):
        out.append(f"<h3>{rich(c['title'])}</h3>")
    prev = "h3"
    for part in c["body"]:
        if isinstance(part, str) or "p" in part:
            out.append(paragraph(part, prev))
            prev = "p"
        elif "list" in part:
            items = "\n".join(f"<li>{rich(li)}</li>" for li in part["list"])
            out.append(f"<ul>{items}</ul>")
            prev = "ul"
        elif "cta" in part:
            cta = part["cta"]
            out.append(f'<p style="margin-top:12px"><a class="cta" href="{attr(safe_link(cta["href"]))}">{rich(cta["label"])}</a></p>')
            prev = "cta"
        elif part["type"] == "plan_vs_actual":
            out.append(plan_vs_actual(part))
            prev = "pv"
        else:
            out.append(table_of(part, deck))
            prev = "table"
    return f'<div class="card"{style}>{"".join(out)}</div>'


def data_needed(n: Json) -> str:
    return f'<div class="need"><b>{rich(n["label"])}</b><p>{rich(n["text"])} Owner is {rich(n["owner"])}. Due in {rich(n["due"])}.</p></div>'


def cards(b: Json, deck: Json, top: str) -> str:
    style = style_attr([top, max_width(b)])
    if b["columns"] == 1:
        return "\n".join(f"<div{style}>{data_needed(it)}</div>" if it.get("type") == "data_needed" else card(it, deck, style) for it in b["items"])
    items = []
    for it in b["items"]:
        if it.get("type") == "data_needed":
            items.append(data_needed(it))
        elif it.get("type") in ("table", "scorecard"):
            items.append(f'<div class="tablewrap">{table_of(it, deck)}</div>')
        else:
            items.append(card(it, deck))
    return grid(b, style, items)


def grid(b: Json, style: str, items: list[str]) -> str:
    joined = "\n".join(items)
    return f'<div class="grid {GRID[str(b["columns"])]}"{style}>\n{joined}\n</div>'


def tile(t: Json) -> str:
    note = f'<p style="margin-top:10px">{rich(t["note"])}</p>' if t.get("note") else ""
    return f'<div class="card"><div class="big">{rich(t["value"])}</div><div class="sub">{rich(t["label"])}</div>{note}</div>'


def tiles(b: Json, top: str) -> str:
    return grid(b, style_attr([top, max_width(b)]), [tile(t) for t in b["items"]])


def leaf(bet: Json) -> str:
    return (
        f'<div class="leaf"><div><small>Bet</small><b>{rich(bet["bet"])}</b>{rich(bet["owner"])}</div>'
        f"<div><small>Product outcome</small>{rich(bet['outcome'])}</div><div><small>Why we think it works</small>{rich(bet['cause'])}</div>"
        f"<div><small>Confidence</small>{rich(bet['confidence'])}</div></div>"
    )


def sources_block(b: Json, deck: Json, top: str) -> str:
    cuts = ", ".join(f"{esc(a['chip'])} {len(srcs)}" for a, srcs in required_by_cut(deck))
    return (
        f'<div class="tablewrap"{style_attr([top])}>{table_of(b, deck)}</div>\n'
        f'<p class="t2"{NOTE_STYLE}><b>Required sources by cut.</b> {cuts}, of {len(sources_needed(deck))} in all.'
        " The rest improve a slide but don’t block it.</p>"
    )


def block(b: Json, i: int, blocks: list[Json], deck: Json) -> str:
    prev = blocks[i - 1] if i else None
    after_lede = bool(prev) and prev["type"] == "text" and prev["variant"] == "lede"
    top = "margin-top:14px" if i > 0 and not after_lede else ""
    kind = b["type"]
    if kind == "text":
        return f'<p class="lede">{rich(b["text"])}</p>' if b["variant"] == "lede" else f'<p class="t2"{NOTE_STYLE}>{rich(b["text"])}</p>'
    if kind == "cards":
        return cards(b, deck, top)
    if kind == "tiles":
        return tiles(b, top)
    if kind in ("table", "scorecard", "ledger"):
        return f'<div class="tablewrap"{style_attr([top])}>{table_of(b, deck)}</div>'
    if kind == "sources_needed":
        return sources_block(b, deck, top)
    if kind == "tree":
        leaves = "\n".join(leaf(x) for x in b["bets"])
        return f'<div class="tree">\n<div class="obj">{rich(b["objective"])}</div>\n<div class="br">\n{leaves}\n</div>\n</div>'
    if kind == "strip":
        style = style_attr(["margin:0 0 14px" if i == 0 and len(blocks) > 1 else ""])
        return f'<div class="strip"{style}><b>{rich(b["label"])}</b> {rich(b["text"])}</div>'
    if kind == "steps":
        steps = "\n".join(f"<div><b>{rich(s['title'])}</b>{rich(s['text'])}</div>" for s in b["items"])
        return f'<div class="steps">\n{steps}\n</div>'
    if kind == "sample":
        inner = "\n".join(block(x, j, b["blocks"], deck) for j, x in enumerate(b["blocks"]))
        return (
            f'<div class="sample"{style_attr([top or "margin-top:14px", "border:1px dashed var(--line)", "border-radius:8px", "padding:14px"])}>'
            f'<div class="notice" style="padding:0 0 10px;border:0;background:none"><span class="ill">Illustrative</span><span>{rich(b["label"])}</span></div>'
            f'<div aria-hidden="true" style="opacity:.45;filter:grayscale(1);pointer-events:none">\n{inner}\n</div></div>'
        )
    if kind == "facts":
        return f'<div class="facts">{"".join(f"<span>{rich(f)}</span>" for f in b["items"])}</div>'
    raise SystemExit(f"render: unknown block type {kind!r}. Use a block type from assets/deck.schema.json, then render again.")


def guide(g: Json | list[Json]) -> str:
    if isinstance(g, list):
        pairs = g
    else:
        pairs = [{"label": "Question", "text": g["question"]}, {"label": "Needs", "text": g["needs"]}, {"label": "Rule", "text": g["rule"]}]
    rows = "\n".join(f"<dt>{rich(p['label'])}</dt><dd>{rich(p['text'])}</dd>" for p in pairs)
    return f'<div class="guide"><dl>\n{rows}\n</dl></div>'


def foot(s: Json) -> str:
    parts = []
    if "asof" in s:
        refs = "".join(f'<span class="led">{esc(r)}</span>' for r in s.get("ledger_refs", []))
        parts.append(f'<div class="asof">{rich(s["asof"])}{refs}</div>')
    if s.get("guide"):
        parts.append(guide(s["guide"]))
    if s.get("dig_deeper"):
        reading = "\n".join(f"<li>{rich(d)}</li>" for d in s["dig_deeper"])
        parts.append(f"<details><summary>Dig deeper</summary><ul>\n{reading}\n</ul></details>")
    if not parts:
        return ""
    joined = "\n".join(parts)
    return f'<div class="foot">\n{joined}\n</div>'


def slide_meta(s: Json, deck: Json) -> str:
    if s["kind"] == "cover":
        return "".join(f"<span>{rich(m)}</span>" for m in s.get("meta", []))
    if s["kind"] == "appendix":
        return f"<span>Appendix {esc(s['id'])}</span>"
    chips = "".join(f'<span class="aud">{esc(a["chip"])}</span>' for a in deck["meta"]["audiences"] if a["key"] in s["audiences"])
    return f"<span>{esc(s['id'])}</span><span>{rich(s.get('kicker', ''))}</span>{chips}"


def slide(s: Json, deck: Json) -> str:
    cover = s["kind"] == "cover"
    ill = '<span class="ill">Illustrative</span>' if s["illustrative"] else ""
    n = "" if re.fullmatch(r"\d\d", s["id"]) else f' data-n="{attr(short_id(s["id"]))}"'
    h = "h1" if cover else "h2"
    lines = [
        f'<section class="slide{" cover" if cover else ""}" id="s{attr(s["id"])}" data-aud="{"".join(s["audiences"])}"'
        f' data-act="{attr(s["act"])}" data-nav="{attr(s["nav"])}"{n}>',
        f'<div class="meta">{slide_meta(s, deck)}{ill}</div>',
        f"<{h}>{rich(s['title'])}</{h}>",
    ]
    lines += [x for x in (block(b, i, s["blocks"], deck) for i, b in enumerate(s["blocks"])) if x]
    f = foot(s)
    if f:
        lines.append(f)
    lines.append("</section>")
    return "\n".join(lines)


def render_body(deck: Json) -> str:
    m = deck["meta"]
    buttons = "\n".join(
        f'<button data-aud="{a["key"]}" aria-pressed="{"true" if i == 0 else "false"}">{esc(a["label"])}</button>' for i, a in enumerate(m["audiences"])
    )
    ill = '<span class="ill">Illustrative</span>' if m["notice"]["illustrative"] else ""
    lines = [
        '<div class="bar">',
        f'<div class="seg" role="group" aria-label="Audience">\n{buttons}\n</div>',
        '<span class="count" id="count"></span>',
        '<label><input type="checkbox" id="g"> Show template guidance</label>',
        "</div>",
        f'<div class="notice">{ill}<span>{rich(m["notice"]["text"])}</span></div>',
    ]
    lines += [slide(s, deck) for s in deck["slides"]]
    lines.append(
        '<footer class="slide" style="min-height:0;padding-top:28px;padding-bottom:40px;border:0" data-skip>\n'
        f'<p class="t3" style="font-size:11.5px;margin:0">{rich(m["footer"])}</p>\n</footer>'
    )
    return "\n".join(lines)


def render_deck(deck: Json, template: str | None = None) -> str:
    if template is None:
        path = ASSETS / "template.html"
        try:
            template = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise SystemExit(f"render: cannot read {path} ({e}). The skill's assets folder is incomplete; reinstall the skill.") from None
    m = deck["meta"]
    slots = (
        ("{{TITLE}}", esc(m["title"])),
        ("{{DESCRIPTION}}", attr(m["description"])),
        ("{{BRAND}}", esc(m["brand"])),
        ("{{PRODUCT}}", esc(m["product"])),
        ("{{BODY}}", render_body(deck)),
    )
    for key, value in slots:
        template = template.replace(key, value, 1)
    return template


def cut_deck(deck: Json, key: str) -> Json:
    """One audience's cut: its core slides, the cover and the appendices."""
    keys = [a["key"] for a in deck["meta"]["audiences"]]
    if key not in keys:
        raise SystemExit(f"render: --cut must be one of {', '.join(keys)}")
    out = dict(deck)
    out["slides"] = [s for s in deck["slides"] if s["kind"] != "slide" or key in s["audiences"]]
    out["meta"] = dict(deck["meta"], audiences=[a for a in deck["meta"]["audiences"] if a["key"] == key])
    if key == "B":
        out["slides"] = one_page_first(out["slides"])
        # A board reads the rows behind its own slides, not the whole working ledger.
        cited = {ref for s in out["slides"] for ref in validate.ledger_refs(s)}
        out["ledger"] = [r for r in deck["ledger"] if r["id"] in cited]
    return out


BOARD_DETAIL = "Appendix: the detail"


def one_page_first(slides: list[Json]) -> list[Json]:
    """The board cut reads as one page: slide 1's title, its open questions on the data, what happened and the
    decisions, with one line saying how many gaps there are and where the detail is. The gap list and the detail
    slides follow under "Appendix: the detail", then the ledger. Nothing is reworded, so every figure stays one the
    pipeline computed and validate.py checked."""
    one = next((s for s in slides if s.get("id") == "01"), None)
    detail = [s for s in slides if s["kind"] == "slide" and s.get("id") != "01"]
    if not one:
        return slides
    gap_blocks = [b for b in one["blocks"] if is_gap_list(b)]
    kept = [b for b in one["blocks"] if not is_gap_list(b)]
    pointer = []
    if gap_blocks:
        count = sum(len(part.get("list", [])) for b in gap_blocks for item in b["items"] for part in item.get("body", []) if isinstance(part, dict))
        pointer.append(f"{count} gaps and data notes, each with an owner and a date, are in the appendix.")
    if detail:
        pointer.append("The detail follows: " + ", ".join(s["nav"] for s in detail) + ".")
    page = dict(one, nav="The page", blocks=[*kept, *([{"type": "text", "variant": "note", "text": " ".join(pointer)}] if pointer else [])])
    gaps = (
        [
            dict(
                one,
                id="01g",
                nav="Gaps and data notes",
                act=BOARD_DETAIL,
                kicker=BOARD_DETAIL,
                title="Gaps and data notes, each with an owner and a date.",
                blocks=gap_blocks,
                ledger_refs=[],
            )
        ]
        if gap_blocks
        else []
    )
    out = []
    for s in slides:
        if s is one:
            out += [page, *gaps]
        elif s in detail:
            out.append(dict(s, act=BOARD_DETAIL, kicker=BOARD_DETAIL))
        else:
            out.append(s)
    return out


def is_gap_list(block: Json) -> bool:
    """Slide 1's card that lists every gap and data note (draft.py gap_register)."""
    return block.get("type") == "cards" and any(str(item.get("title", "")).startswith("Gaps and data notes") for item in block.get("items", []))


def sign_cover(deck: Json, signer: str) -> Json:
    """The board cut carries the name of the person who said yes, on its cover, so the sign-off travels with the file."""
    out = dict(deck)
    out["slides"] = [dict(s, meta=[*s.get("meta", []), f"Signed off by {signer}"]) if s["kind"] == "cover" else s for s in deck["slides"]]
    return out


def csv_cell(value: object) -> object:
    """A ledger value as a CSV cell. Text that a spreadsheet would run as a formula gets a leading apostrophe."""
    if value is None:
        return ""
    if isinstance(value, str) and FORMULA_START.match(value):
        return "'" + value
    return value


def write_ledger_csv(deck: Json, path: str | Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader()
        for r in deck["ledger"]:
            w.writerow({k: csv_cell(r.get(k)) for k in LEDGER_FIELDS})


def refuse_blocked(deck: Json, allowed: dict[str, list[float]] | None = None) -> None:
    """Stop the render when validate.py finds errors, after listing them."""
    errors = validate.check(deck, allowed=allowed)["errors"]
    if not errors:
        return
    for e in errors:
        print(f"  [{e['rule']}] slide {e['slide']}: {e['message']}", file=sys.stderr)
    raise SystemExit(f"render: {len(errors)} blocking problem(s). Fix them or downgrade the claim, then render again.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Render a deck JSON to one self-contained HTML file.")
    ap.add_argument("deck")
    ap.add_argument("--out", required=True, help="the HTML file to write")
    ap.add_argument("--cut", help="render one audience's cut: L, B or S")
    ap.add_argument("--signed-off-by", help="the person who reviewed the change list; required for the board cut")
    ap.add_argument("--skip-validate", action="store_true", help="for tests of the renderer only")
    args = ap.parse_args()
    deck = validate.read_deck(Path(args.deck), tool="render")
    if not args.skip_validate:
        refuse_blocked(deck, validate.figures.load(Path(args.deck)))
    signer = (args.signed_off_by or "").strip()
    if args.cut == "B" and not signer:
        raise SystemExit("render: the board cut needs --signed-off-by with a person's name. Show the change list (review.py) and get an explicit yes first.")
    shown = cut_deck(deck, args.cut) if args.cut else deck
    if args.cut == "B":
        shown = sign_cover(shown, signer)
    html = render_deck(shown)
    out = Path(args.out)
    ledger_path = out.with_name(out.stem + ".ledger.csv")
    try:
        out.write_text(html, encoding="utf-8")
        write_ledger_csv(shown, ledger_path)
    except OSError as e:
        raise SystemExit(f"render: cannot write {e.filename or out} ({e.strerror}). Check that the folder exists and is writable, then render again.") from None
    signed = f" Signed off by {signer}." if signer else ""
    print(f"render: wrote {out} ({len(html) // 1024} KB) and {ledger_path}.{signed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
