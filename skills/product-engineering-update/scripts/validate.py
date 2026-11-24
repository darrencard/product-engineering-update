#!/usr/bin/env python3
"""Check a deck before it renders. Errors block the render. Warnings do not.

Usage:
  python3 scripts/validate.py deck.json            # human-readable report, exit 1 on errors
  python3 scripts/validate.py deck.json --json     # the same report as JSON

Three layers:
  1. shape       the deck against assets/deck.schema.json
  2. references  ledger references, source keys, cuts, rollups
  3. claims      the overclaim rules (see RULES below)

To clear an error, fix the data or downgrade the claim. Never delete the rule,
and never replace a missing figure with prose: use a data_needed block.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
Json = dict[str, Any]

# The board reads at most this many core slides. More than 8 stops being a board cut.
MAX_BOARD_SLIDES = 8
# A figure is stale when it was retrieved more than one reporting quarter (92 days) before the deck's as_of date.
STALE_AFTER_DAYS = 92
# A long shape report repeats itself; the first 25 problems are enough to fix the file.
MAX_SHAPE_ERRORS = 25
# A sentence quoted in a finding is cut at this length so one finding stays one readable line.
QUOTE_CHARS = 140

RULES = {
    "shape": "The deck does not match the schema.",
    "reference": "A reference points at something that does not exist.",
    "no-ledger-row": "A slide shows figures and cites no ledger row.",
    "speed-without-quality": "A speed metric has no quality metric beside it on the same slide.",
    "productivity-without-baseline": "An AI productivity claim has no baseline and window.",
    "adoption-as-outcome": "An adoption or usage count sits in an outcome slot.",
    "stale-figure": "A figure is older than the reporting window and is not marked stale.",
    "bet-incomplete": "A bet has no stop rule, appetite or confidence.",
    "branch-without-cause": "A line-of-sight branch states no cause.",
    "point-target": "A delivery metric has a single-point target where it needs a range.",
    "banned-phrase": "The deck uses a banned phrase.",
    "missing-evidence": "A slide has neither its evidence block nor a data_needed block.",
    "placeholder-left": "A filled deck still holds a template title, or a gap with no real owner or date.",
    "unsafe-link": "A link is not http, https or mailto.",
    "board-cut-too-long": f"The board cut holds more than {MAX_BOARD_SLIDES} slides.",
    "sample-not-illustrative": "A sample block is not tagged illustrative.",
    "sample-beside-data": "A sample block sits on a slide that shows real data.",
    "sample-cites-ledger": "A sample block cites a ledger row, so it would pass for evidence.",
}

SPEED = re.compile(r"\b(deploys?|deployment frequency|lead time|cycle time|throughput|velocity|merge frequency|pull requests? merged|time to merge)\b", re.I)
QUALITY = re.compile(
    r"\b(change failure|failure rate|time to restore|restore|rework|defects?|incidents?|review time|rollbacks?|rolled back|followed by errors|escaped|bug)",
    re.I,
)
ADOPTION = re.compile(
    r"\b(adoption|feature usage|usage count|pilots? started|seats?|sign-?ups?|logins?|page ?views?|downloads?|prompts? sent|tokens? used|licen[cs]es?)\b", re.I
)
# Engineering and finance shorthand a board member outside the team may not know. In a title it warns:
# say what the number means instead (writing-rules.md). Tables keep the precise names.
JARGON = re.compile(
    r"\b(change failure rate|lead time|cycle time|keep the lights on|KTLO|capacity|ARR|NRR|GRR|MTTR|SLOs?|DORA|p9[059]|"
    r"throughput|velocity|story points|rework rate|evals?|eval pass rate|deploys?|PRs?|pull requests?|tech debt)\b",
    re.I,
)
PRODUCTIVITY = re.compile(r"(productiv|faster|speed-?up|time saved|hours saved|efficien)", re.I)
HAS_NUMBER = re.compile(r"\d+(\.\d+)?\s?(%|x\b|×)", re.I)
BASELINE = re.compile(
    r"(baseline|than (a|last|the prior) (year|quarter|month)|year ago|on Q\d|against|versus|\bvs\b|from .+ to |compared (with|to)|before)", re.I
)
RANGE = re.compile(r"(\bto\b|under|over|below|above|at least|at most|up to|between|<|>|\+|≤|≥|-)", re.I)
BANNED = [
    (re.compile(r"\b\d+x\b", re.I), 'a multiplier claim such as "10x"'),
    (re.compile(r"AI-powered", re.I), '"AI-powered"'),
]
FIGURE_BLOCKS = ("scorecard", "tiles", "plan_vs_actual")

# Links. The deck's light markup has one link form, [label](target), and cards can hold a cta href.
# The output is a file people open and forward, so a target is an allowlist, never a blocklist:
# javascript:, data:, file: and relative targets are all refused. render.py uses these same two patterns.
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
SAFE_LINK = re.compile(r"(?:https?://|mailto:)\S+")
LINK_HELP = "Links must start with http://, https:// or mailto:"

# What the blank template holds where a person has to write something.
BLANK_COMPANY = "[Company]"
PLACEHOLDER_TITLE = "Write the claim"
PLACEHOLDER_OWNERS = ("", "[owner]", "[date]")


class Finding(TypedDict):
    rule: str
    slide: str
    message: str


class Report(TypedDict):
    ok: bool
    errors: list[Finding]
    warnings: list[Finding]


@dataclass
class Findings:
    """Collects what the checks find, in the order they find it."""

    errors: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)

    def err(self, rule: str, slide: str, message: str) -> None:
        self.errors.append({"rule": rule, "slide": slide, "message": message})

    def warn(self, rule: str, slide: str, message: str) -> None:
        self.warnings.append({"rule": rule, "slide": slide, "message": message})

    def report(self) -> Report:
        return {"ok": not self.errors, "errors": self.errors, "warnings": self.warnings}


def is_safe_link(target: object) -> bool:
    """True when a link target is an http, https or mailto address."""
    return isinstance(target, str) and SAFE_LINK.fullmatch(target) is not None


# ---- layer 1: shape ---------------------------------------------------------


def _kind(v: object) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    return "object"


def _resolve(ref: str, root: Json) -> Json:
    node = root
    for key in ref.removeprefix("#/").split("/"):
        node = node[key]
    return node


def _one_of(value: object, options: list[Json], root: Json, at: str) -> list[str]:
    results = [validate_shape(value, option, root, at) for option in options]
    fits = sum(1 for r in results if not r)
    if fits == 1:
        return []
    if fits == 0:
        closest = min(results, key=len)
        return [f"{at}: fits none of the allowed shapes (closest: {closest[0]})"]
    return [f"{at}: fits {fits} shapes, expected 1"]


def validate_shape(value: object, s: Json, root: Json, at: str = "$") -> list[str]:
    """A small JSON Schema validator covering the keywords deck.schema.json uses."""
    if "$ref" in s:
        return validate_shape(value, _resolve(s["$ref"], root), root, at)
    if "oneOf" in s:
        return _one_of(value, s["oneOf"], root, at)
    if "const" in s and value != s["const"]:
        return [f"{at}: expected {json.dumps(s['const'])}"]
    if "enum" in s and value not in s["enum"]:
        return [f"{at}: {json.dumps(value)} is not one of {json.dumps(s['enum'])}"]
    if "type" in s:
        types = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if _kind(value) not in types:
            return [f"{at}: expected {' or '.join(types)}, got {_kind(value)}"]
    out: list[str] = []
    if isinstance(value, str):
        if "pattern" in s and not re.search(s["pattern"], value):
            out.append(f'{at}: "{value}" does not match {s["pattern"]}')
        if len(value) < s.get("minLength", 0):
            out.append(f"{at}: is empty")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in s and value < s["minimum"]:
            out.append(f"{at}: {value} is below {s['minimum']}")
        if "maximum" in s and value > s["maximum"]:
            out.append(f"{at}: {value} is above {s['maximum']}")
    if isinstance(value, list):
        if len(value) < s.get("minItems", 0):
            out.append(f"{at}: needs at least {s['minItems']} item(s)")
        if "items" in s:
            for i, v in enumerate(value):
                out += validate_shape(v, s["items"], root, f"{at}[{i}]")
    elif isinstance(value, dict):
        props = s.get("properties", {})
        for key in s.get("required", []):
            if key not in value:
                out.append(f'{at}: missing "{key}"')
        for key, v in value.items():
            if key in props:
                out += validate_shape(v, props[key], root, f"{at}.{key}")
            elif s.get("additionalProperties") is False:
                out.append(f'{at}: unknown field "{key}"')
    return out


# ---- helpers ----------------------------------------------------------------


def strings(node: object) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, list):
        return [s for x in node for s in strings(x)]
    if isinstance(node, dict):
        return [s for x in node.values() for s in strings(x)]
    return []


def walk_blocks(blocks: list[Json]) -> Iterator[Json]:
    """Every block on a slide, including the ones nested in cards."""
    for b in blocks:
        yield b
        if b.get("type") == "cards":
            for item in b["items"]:
                if item.get("type"):
                    yield item
                for part in item.get("body", []):
                    if isinstance(part, dict) and part.get("type"):
                        yield part


def real_blocks(blocks: list[Json]) -> list[Json]:
    """A slide's own blocks. A sample shows what the slide could look like; it is never the slide's evidence."""
    return [b for b in blocks if b.get("type") != "sample"]


def slide_text(s: Json) -> list[str]:
    """The claims a slide makes: its title and blocks. Guidance, reading and samples are not claims."""
    return [s.get("title", ""), s.get("asof", "")] + strings(real_blocks(s.get("blocks", [])))


def sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]


def ledger_refs(s: Json) -> list[str]:
    refs = list(s.get("ledger_refs", []))
    for t in slide_text(s):
        refs += re.findall(r"\[\[(L\d+)\]\]", t)
    return refs


def has_numeric_table(blocks: list[Json]) -> bool:
    return any(b.get("type") == "table" and b["rows"] and any(c.get("align") == "num" for c in b["columns"]) for b in walk_blocks(blocks))


def link_targets(node: object) -> Iterator[str]:
    """Every link target under a node: each cta href, and each [label](target) in any string."""
    if isinstance(node, str):
        for found in MARKDOWN_LINK.finditer(node):
            yield found.group(2)
    elif isinstance(node, list):
        for item in node:
            yield from link_targets(item)
    elif isinstance(node, dict):
        cta = node.get("cta")
        if isinstance(cta, dict) and isinstance(cta.get("href"), str):
            yield cta["href"]
        for item in node.values():
            yield from link_targets(item)


def blocks_of_type(node: object, kind: str) -> Iterator[Json]:
    """Every block of one type under a node, however deeply it is nested."""
    if isinstance(node, list):
        for item in node:
            yield from blocks_of_type(item, kind)
    elif isinstance(node, dict):
        if node.get("type") == kind:
            yield node
        for item in node.values():
            yield from blocks_of_type(item, kind)


def _is_slide(s: Json, audience: str) -> bool:
    return s["kind"] == "slide" and audience in s["audiences"]


def _cell(row: list[str], index: int) -> str:
    """A table cell as text; a row shorter than its header reads as empty there."""
    return str(row[index]) if index < len(row) else ""


def _load_asset(name: str) -> Any:
    path = ASSETS / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"validate: cannot read {path} ({e}). The skill's assets folder is incomplete; reinstall the skill.") from None


# ---- layer 2: references ----------------------------------------------------


def _check_references(deck: Json, found: Findings) -> None:
    slides = deck["slides"]
    by_id = {s["id"]: s for s in slides}
    ledger = {r["id"] for r in deck["ledger"]}
    source_keys = {t["key"] for t in deck["meta"]["source_types"]}
    if len(by_id) != len(slides):
        found.err("reference", "-", "two slides share an id")
    if len(ledger) != len(deck["ledger"]):
        found.err("reference", "-", "two ledger rows share an id")
    for s in slides:
        for ref in ledger_refs(s):
            if ref not in ledger:
                found.err("reference", s["id"], f"ledger reference {ref} has no row")
        for need in s.get("requires", []):
            if need["source"] not in source_keys:
                found.err("reference", s["id"], f'requires unknown source "{need["source"]}"')
        for sid in s.get("rolls_up", []):
            if sid not in by_id:
                found.err("reference", s["id"], f"rolls up slide {sid}, which does not exist")
    for a in deck["meta"]["audiences"]:
        want = [s["id"] for s in slides if _is_slide(s, a["key"])]
        got = deck["meta"]["cuts"].get(a["key"], [])
        if want != got:
            found.err("reference", "-", f"meta.cuts.{a['key']} lists {len(got)} slides, the slides themselves give {len(want)}")


def _check_board_cut(deck: Json, found: Findings) -> None:
    board = [s for s in deck["slides"] if _is_slide(s, "B")]
    if len(board) > MAX_BOARD_SLIDES:
        found.err("board-cut-too-long", "-", f"the board cut holds {len(board)} slides, the limit is {MAX_BOARD_SLIDES}")


def _check_stale(deck: Json, found: Findings) -> None:
    stamp = deck["meta"]["as_of"]
    try:
        as_of = datetime.date.fromisoformat(stamp)
    except ValueError:
        found.err("shape", "-", f'$.meta.as_of: "{stamp}" is not a real date. Use YYYY-MM-DD.')
        return
    for r in deck["ledger"]:
        got = r.get("retrieved_at")
        if not got:
            continue
        try:
            when = datetime.date.fromisoformat(got[:10])
        except ValueError:
            found.err("stale-figure", "-", f"{r['id']}: retrieved_at {got!r} is not a date (YYYY-MM-DD)")
            continue
        age = (as_of - when).days
        if age > STALE_AFTER_DAYS and not r.get("stale"):
            found.err(
                "stale-figure",
                "-",
                f"{r['id']} ({r['claim']}) was retrieved {age} days before {stamp}. Refresh it or set stale: true and say so on the slide.",
            )


def _check_links(deck: Json, found: Findings) -> None:
    """Every link in the deck, wherever it sits, because any string can reach the rendered page."""
    places = [("-", deck["meta"]), ("-", deck["ledger"])] + [(s["id"], s) for s in deck["slides"]]
    for slide, node in places:
        for target in link_targets(node):
            if not is_safe_link(target):
                found.err("unsafe-link", slide, f'the link "{target[:QUOTE_CHARS]}" is not allowed. {LINK_HELP}. Fix the link or remove it.')


def _check_placeholders(deck: Json, found: Findings) -> None:
    """A deck with a real company name is someone's draft, so nothing from the blank template may be left in it."""
    if deck["meta"]["company"] == BLANK_COMPANY:
        return
    for s in deck["slides"]:
        if s["title"].startswith(PLACEHOLDER_TITLE):
            found.err("placeholder-left", s["id"], f'the title is still the template\'s "{s["title"][:QUOTE_CHARS]}". Write the claim the slide makes.')
        leftover = re.search(
            r"\[(Company|Period|Author)\]|Fill in each slide from the sources it names", " ".join(strings([s.get("title", ""), s.get("meta", []), s["blocks"]]))
        )
        if leftover:
            found.err("placeholder-left", s["id"], f'still holds the blank template\'s text "{leftover.group(0)}". Replace it or remove it.')
        for gap in blocks_of_type(s["blocks"], "data_needed"):
            for name in ("owner", "due"):
                if gap[name].strip() in PLACEHOLDER_OWNERS:
                    found.err(
                        "placeholder-left",
                        s["id"],
                        f'the data needed block "{gap["label"]}" has no real {name} ("{gap[name]}"). Name the {"person" if name == "owner" else "date"}.',
                    )


# ---- layer 3: claims --------------------------------------------------------


def _check_scorecard(b: Json, sid: str, found: Findings) -> None:
    rows = [r for r in b["rows"] if "metric" in r]
    if b["target_kind"] != "range":
        for r in rows:
            if not r.get("definition"):
                found.warn(
                    "undefined-metric",
                    sid,
                    f'"{r["metric"]}" has no definition. Add one plain-English sentence to the intake (north_star.definition or the input\'s'
                    " definition) so a reader outside the team knows what it counts.",
                )
            if ADOPTION.search(r["metric"]):
                found.err(
                    "adoption-as-outcome",
                    sid,
                    f'"{r["metric"]}" is an adoption or usage count in an outcome slot.'
                    " Move it to an input slide or replace it with the outcome it should drive.",
                )
        return
    for r in rows:
        if not RANGE.search(r["target"]):
            found.err(
                "point-target",
                sid,
                f'"{r["metric"]}" has the target "{r["target"]}". Delivery metrics take a healthy range, for example "under 40h" or "80 to 90%".',
            )
    groups = [r["group"] for r in b["rows"] if "group" in r]
    speed = [r["metric"] for r in rows if SPEED.search(r["metric"])] or [g for g in groups if re.search("speed", g, re.I)]
    quality = [r["metric"] for r in rows if QUALITY.search(r["metric"])]
    if speed and not quality:
        found.err(
            "speed-without-quality",
            sid,
            f"shows {', '.join(speed[:3])} with no quality metric beside it. Add change failure rate, time to restore, review time or rework.",
        )


def _check_tree(b: Json, sid: str, found: Findings) -> None:
    for bet in b["bets"]:
        if not bet["cause"].strip():
            found.err("branch-without-cause", sid, f'"{bet["bet"]}" states no cause. Say why the bet should move the objective.')
        if not bet["confidence"].strip():
            found.err("bet-incomplete", sid, f'"{bet["bet"]}" states no confidence.')


def _check_bets_table(b: Json, sid: str, found: Findings) -> None:
    labels = [c["label"].lower() for c in b["columns"]]
    if not labels or labels[0] != "bet":
        return
    # column heading contains -> the name the finding uses
    for word, name in (("stop", "stop rule"), ("appetite", "appetite"), ("confidence", "confidence")):
        columns = [i for i, label in enumerate(labels) if word in label]
        if not columns:
            found.err("bet-incomplete", sid, f"the bets table has no {name} column.")
            continue
        for r in b["rows"]:
            if isinstance(r, list) and not _cell(r, columns[0]).strip():
                found.err("bet-incomplete", sid, f'"{_cell(r, 0)}" has no {name}.')


def _check_sentences(text: list[str], sid: str, found: Findings) -> None:
    """Productivity claims and banned phrases, sentence by sentence."""
    for t in text:
        for sentence in sentences(t):
            quote = sentence[:QUOTE_CHARS]
            if PRODUCTIVITY.search(sentence) and HAS_NUMBER.search(sentence) and not BASELINE.search(sentence):
                found.err(
                    "productivity-without-baseline",
                    sid,
                    f'no baseline or window in: "{quote}". State what it is measured against and over what period, or cut the number.',
                )
            for pattern, name in BANNED:
                if pattern.search(sentence):
                    found.err("banned-phrase", sid, f'uses {name} in: "{quote}"')


def _check_samples(s: Json, types: set[str], found: Findings) -> None:
    """A sample shows a reader what a gap would look like filled. It must never pass for the slide's own data."""
    sid = s["id"]
    for b in s["blocks"]:
        if b.get("type") != "sample":
            continue
        if b["illustrative"] is not True:
            found.err("sample-not-illustrative", sid, "has a sample block that is not tagged illustrative. Set illustrative to true.")
        if (types - {"cards", "data_needed", "text"}) or s.get("ledger_refs"):
            found.err("sample-beside-data", sid, "shows real data and a sample. A sample may only sit beside a data_needed block; remove it.")
        if any(re.search(r"\[\[L\d+\]\]", t) for t in strings(b["blocks"])):
            found.err("sample-cites-ledger", sid, "has a sample that cites a ledger row. Sample figures are made up and cite nothing.")
        _check_sentences(strings(b["blocks"]), sid, found)


def _check_slide(s: Json, deck: Json, contract: Json | None, found: Findings) -> None:
    sid = s["id"]
    own = real_blocks(s["blocks"])
    blocks = list(walk_blocks(own))
    types = {b["type"] for b in blocks if b.get("type")}
    text = slide_text(s)

    # a figure with no ledger row
    shows_figures = any(t in types for t in FIGURE_BLOCKS) or has_numeric_table(own)
    if shows_figures and not ledger_refs(s) and not s.get("rolls_up"):
        found.err("no-ledger-row", sid, "shows figures and cites no ledger row. Add the row and reference it, for example [[L01]] or ledger_refs.")

    # minimum evidence, or a data_needed block in its place
    if contract and not (set(contract["evidence_blocks"]) & types) and "data_needed" not in types:
        found.err(
            "missing-evidence",
            sid,
            f"needs one of {', '.join(contract['evidence_blocks'])}, or a data_needed block with an owner and a due date. Prose does not count.",
        )

    # What the slide shows, without its sources line: naming an incident tool as a source is not a quality metric.
    shown = " ".join(strings(own))
    for b in blocks:
        kind = b.get("type")
        if kind == "scorecard":
            _check_scorecard(b, sid, found)
        elif kind == "tiles":
            labels = " ".join(t["label"] for t in b["items"])
            if SPEED.search(labels) and not QUALITY.search(shown):
                found.err("speed-without-quality", sid, "shows a speed metric in a tile with no quality metric on the slide.")
        elif kind == "tree":
            _check_tree(b, sid, found)
        elif kind == "table":
            _check_bets_table(b, sid, found)
            # A plain table is no way round the pairing rule: a speed metric named in its first column needs a quality metric on the slide.
            named = " ".join(row[0] for row in b["rows"] if isinstance(row, list) and row)
            if SPEED.search(named) and not QUALITY.search(shown):
                found.err("speed-without-quality", sid, "shows a speed metric in a table with no quality metric on the slide.")

    _check_sentences(text, sid, found)
    _check_samples(s, types, found)
    jargon = sorted({m.group(0).lower() for m in JARGON.finditer(s.get("title", ""))})
    if jargon:
        found.warn("jargon-in-title", sid, f"the title uses {', '.join(jargon)}. Say what it means for a reader outside the team; keep the term in the table.")

    if s["illustrative"] is False and deck["meta"]["notice"]["illustrative"]:
        found.warn("illustrative", sid, "the deck is marked illustrative but this slide is not.")


def check(deck: Json, contracts: list[Json] | None = None, schema: Json | None = None) -> Report:
    """Return {"ok", "errors", "warnings"}; each finding has rule, slide and message."""
    found = Findings()
    if schema is None:
        schema = _load_asset("deck.schema.json")
    if contracts is None:
        contracts = _load_asset("contracts.json")
    shape = validate_shape(deck, schema, schema)
    if shape:
        for message in shape[:MAX_SHAPE_ERRORS]:
            found.err("shape", "-", message)
        return found.report()

    _check_references(deck, found)
    _check_board_cut(deck, found)
    _check_stale(deck, found)
    _check_links(deck, found)
    _check_placeholders(deck, found)

    contract_by_id = {c["id"]: c for c in contracts}
    for s in deck["slides"]:
        if s["kind"] == "slide":
            _check_slide(s, deck, contract_by_id.get(s["id"]), found)

    unknown = [r["id"] for r in deck["ledger"] if r["confidence"] == "Unknown"]
    if unknown:
        rows = ", ".join(unknown)
        found.warn(
            "unknown-rows", "-", f"{len(unknown)} ledger row(s) are Unknown: {rows}. Check that each shows as a data needed block and nowhere as a figure."
        )
    return found.report()


def read_deck(path: Path, tool: str = "validate") -> Json:
    """Load a deck file, or exit with one line that says what to do about it."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"{tool}: {path} does not exist. Check the path, or run draft.py to write the deck first.") from None
    except IsADirectoryError:
        raise SystemExit(f"{tool}: {path} is a folder. Pass the deck JSON file inside it.") from None
    except UnicodeDecodeError:
        raise SystemExit(f"{tool}: {path} is not UTF-8 text. Save the deck as UTF-8 JSON, then run this again.") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"{tool}: {path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). Fix the file, then run this again.") from None
    except OSError as e:
        raise SystemExit(f"{tool}: cannot read {path} ({e.strerror}). Check the file's permissions, then run this again.") from None


def main() -> int:
    ap = argparse.ArgumentParser(description="Check a deck before it renders.")
    ap.add_argument("deck")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    report = check(read_deck(Path(args.deck)))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for level, tag in (("errors", "ERROR  "), ("warnings", "warning")):
            for finding in report[level]:
                print(f"{tag} [{finding['rule']}] slide {finding['slide']}: {finding['message']}")
        verdict = "The deck can render." if report["ok"] else "Fix the data or downgrade the claim, then run this again."
        print(f"validate: {len(report['errors'])} error(s), {len(report['warnings'])} warning(s). {verdict}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
