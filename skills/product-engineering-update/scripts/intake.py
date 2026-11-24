#!/usr/bin/env python3
"""Build and check intake.json, the record of the interview.

Usage:
  python3 scripts/intake.py init run/intake.json        # write an empty intake
  python3 scripts/intake.py check run/intake.json       # list what is still Unknown, by slide
  python3 scripts/intake.py suggest run/intake.json     # suggested healthy ranges to put to the user
  python3 scripts/intake.py accept run/intake.json "Deploys per week" [--range "3+"]
                                                        # record a range the user said yes to, as suggested or edited
  python3 scripts/intake.py import run/intake.json --decisions log.md --risks risks.csv --stopped stop.md
                                                        # read the team's own decision log, risk register and stop list
  python3 scripts/intake.py propose run/intake.json drafted.json
                                                        # hold answers drafted from documents, each with its source and quote
  python3 scripts/intake.py confirm run/intake.json --by "Name" [--field F ...] [--edit F=JSON]
                                                        # apply the proposals the user said yes to

Anything the person does not supply stays null. Null means Unknown: the deck
shows a data_needed block for it. Never fill a null with a guess.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

Json = dict[str, Any]

EMPTY: Json = {
    "company": None,
    "author": None,
    "period": {"label": None, "start": None, "end": None},
    "as_of": None,
    # Who owns a gap when nobody else is named, and when it is due. Used on data_needed blocks.
    "gap_owner": None,
    "gap_due": None,
    "objectives": [],  # [{"name": "Grow ARR to $50M", "target": "$50M", "owner": "CEO"}]
    "strategy": {"diagnosis": None, "policy": None, "actions": [], "non_goals": []},
    "product_lines": [],  # [{"name": "...", "stage": "Explore|Expand|Sustain", "objective": "..."}]
    "investment_plan": {},  # {"New capabilities": 35, "Keep the lights on": 15}  percent of capacity, by work type
    "rd_lines": [],  # finance lines that count as R&D spend, for R&D as a share of revenue: ["R&D payroll", "Cloud"]
    "north_star": {"metric": None, "definition": None, "target": None, "owner": None},
    # Each input: {"metric": "Activation", "definition": "Accounts with a first automated load inside 14 days",
    #              "unit": "%", "target": 50, "target_display": "50%", "higher_is_better": true, "owner": "..."}
    "inputs": [],
    "delivery_ranges": {},  # {"Deploys per week": "35+", "Change failure rate": "under 3.5%"}  healthy ranges, never single points
    "ai_features": None,  # [{"name": "Dispatch Agent", "eval_set": "v14"}]  [] means none in production; null means not asked yet
    "bets": [],  # [{"bet", "commitment", "appetite", "expected", "confidence", "stop_rule", "objective", "cause", "owner"}]
    "risks": [],  # [{"risk", "likelihood", "impact", "mitigation", "due"}]
    "stopped": [],  # [{"what", "why"}]
    "decisions": [],  # [{"ask", "options", "recommendation", "deadline"}]
    "connected": [],  # source keys that have data: "tracker", "billing", ...
    # When two sources disagree on a figure, the user names the one that owns it: {"ARR": "billing"}. Never fill this in for them.
    "source_of_truth": {},
    # Where each healthy range came from, when the user accepted it from a suggestion:
    # {"Deploys per week": {"suggested": "1+", "accepted": "1+", "edited": false, "source": "..."}}
    "range_sources": {},
    # Answers confirmed from a drafted proposal: {"strategy.diagnosis": {"evidence": [{"source", "quote"}], "confirmed_by", "edited"}}
    "provenance": {},
}

# A quote is short evidence, not a copy of the document.
MAX_QUOTE = 400

SUGGESTIONS = Path(__file__).resolve().parent.parent / "assets" / "suggested_ranges.json"

# Which slide goes without data when a field is Unknown.
FIELD_SLIDES = [
    ("strategy.diagnosis", "02"),
    ("strategy.policy", "02"),
    ("strategy.actions", "02"),
    ("strategy.non_goals", "02"),
    ("objectives", "03"),
    ("bets", "03"),
    ("product_lines", "04"),
    ("investment_plan", "05"),
    ("delivery_ranges", "09"),
    ("north_star.metric", "11"),
    ("north_star.target", "11"),
    ("inputs", "11"),
    ("risks", "14"),
    ("stopped", "15"),
    ("bets", "16"),
    ("decisions", "18"),
]
REQUIRED = ["company", "period.label", "period.start", "period.end", "as_of", "gap_owner", "gap_due"]
DATE_FIELDS = ("period.start", "period.end", "as_of")
# What every bet must state before the run starts; validate.py blocks a deck whose bets lack them.
BET_FIELDS = ("appetite", "confidence", "stop_rule")


def get(d: object, path: str) -> Any:
    """The value at a dotted path such as "period.start", or None when any step is missing."""
    for key in path.split("."):
        d = d.get(key) if isinstance(d, dict) else None
    return d


def is_unknown(v: object) -> bool:
    return v is None or v == "" or v == [] or v == {}


def is_date(v: object) -> bool:
    if not isinstance(v, str):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def check(intake: Json) -> tuple[list[str], list[tuple[str, str]]]:
    """Return (blocking, unknown): fields the run cannot start without, and fields that will show as data needed."""
    blocking = [p for p in REQUIRED if is_unknown(get(intake, p))]
    for p in DATE_FIELDS:
        v = get(intake, p)
        if v and not is_date(v):
            blocking.append(f"{p} (must be YYYY-MM-DD, got {v!r})")
    unknown = [(p, slide) for p, slide in FIELD_SLIDES if is_unknown(get(intake, p))]
    # A metric with no definition still shows, but a reader outside the team cannot tell what it counts.
    if get(intake, "north_star.metric") and is_unknown(get(intake, "north_star.definition")):
        unknown.append(("north_star.definition", "11"))
    for i, metric in enumerate(intake.get("inputs") or []):
        if isinstance(metric, dict) and metric.get("metric") and is_unknown(metric.get("definition")):
            unknown.append((f'inputs[{i}].definition ("{metric["metric"]}")', "11"))
    for bet in intake.get("bets") or []:
        name = bet.get("bet", "?")
        for field in BET_FIELDS:
            if is_unknown(bet.get(field)):
                blocking.append(f'bet "{name}" has no {field}')
        if is_unknown(bet.get("cause")):
            blocking.append(f'bet "{name}" states no cause linking it to an objective')
    return blocking, unknown


def read_intake(path: Path) -> Json:
    """Load the intake, or exit with one line that says what to do about it."""
    try:
        intake = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"intake: {path} does not exist. Run `intake.py init {path}` to write an empty one.") from None
    except UnicodeDecodeError:
        raise SystemExit(f"intake: {path} is not UTF-8 text. Save it as UTF-8 JSON, then run this again.") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"intake: {path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). Fix the file, then run this again.") from None
    except OSError as e:
        raise SystemExit(f"intake: cannot read {path} ({e.strerror}). Check the path and its permissions, then run this again.") from None
    bets = intake.get("bets") if isinstance(intake, dict) else None
    if not isinstance(intake, dict) or not isinstance(bets or [], list) or not all(isinstance(bet, dict) for bet in bets or []):
        raise SystemExit(f"intake: {path} is not an intake: it must be a JSON object, and bets a list of objects. Start again from `intake.py init`.")
    return intake


def load_suggestions(path: Path = SUGGESTIONS) -> Json:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"intake: cannot read the suggested ranges in {path} ({e}). Reinstall the skill.") from None


def citation(source: Json) -> str:
    return f"{source['title']} ({source['publisher']}, {source['published']})"


def suggest(intake: Json, suggestions: Json) -> list[str]:
    """The suggestions to put to the user, one line each, for metrics that have no range yet. Nothing is applied."""
    have = intake.get("delivery_ranges") or {}
    lines = []
    for metric, s in suggestions["ranges"].items():
        if metric in have:
            continue
        lines.append(f'suggest   {metric}: "{s["range"]}"  ({s["basis"]}; {citation(suggestions["source"])})')
    for metric, reason in suggestions.get("no_suggestion", {}).items():
        if metric not in have:
            lines.append(f"no source {metric}: {reason}")
    return lines


def accept(intake: Json, suggestions: Json, metric: str, edited: str | None) -> Json:
    """Record a range the user said yes to. The intake keeps what was suggested, what was accepted and the source."""
    s = suggestions["ranges"].get(metric)
    if s is None and edited is None:
        raise SystemExit(f'intake: there is no suggested range for "{metric}". Ask the user for one and pass it with --range.')
    final = edited or s["range"]
    intake.setdefault("delivery_ranges", {})[metric] = final
    if s is not None:
        intake.setdefault("range_sources", {})[metric] = {
            "suggested": s["range"],
            "accepted": final,
            "edited": final != s["range"],
            "source": citation(suggestions["source"]),
        }
    return intake


def init(path: Path) -> int:
    if path.exists():
        raise SystemExit(f"intake: {path} already exists. It holds interview answers, so it is not overwritten. Edit it, or delete it first.")
    try:
        path.write_text(json.dumps(EMPTY, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"intake: cannot write {path} ({e.strerror}). Create the run folder first, then run this again.") from None
    print(f"intake: wrote {path}. Fill it from the interview. Leave anything not supplied as null.")
    return 0


# What each kept document must hold, by column name. A document without these columns is refused,
# never read by guessing: the first column names the item and must be filled in every row.
IMPORTS = {
    "decisions": ("ask", "options", "recommendation", "deadline"),
    "risks": ("risk", "likelihood", "impact", "mitigation", "due"),
    "stopped": ("what", "why"),
}


def markdown_tables(text: str) -> list[list[list[str]]]:
    """Every pipe table in a Markdown file, as rows of cells, without the separator row."""
    tables, current = [], []
    for line in text.splitlines() + [""]:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", stripped.strip("|"))]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    return tables


def read_table(path: Path, columns: tuple[str, ...]) -> list[Json]:
    """The rows of the first table in a CSV or Markdown file that has every named column."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise SystemExit(f"intake: cannot read {path} ({e}). Save it as UTF-8 CSV or Markdown.") from None
    tables = markdown_tables(text) if path.suffix.lower() in (".md", ".markdown") else [list(csv.reader(io.StringIO(text)))]
    for table in tables:
        if not table:
            continue
        header = [h.strip().lower() for h in table[0]]
        if all(c in header for c in columns):
            at = {c: header.index(c) for c in columns}
            rows = [{c: (r[i].strip() if i < len(r) else "") or None for c, i in at.items()} for r in table[1:] if any(x.strip() for x in r)]
            blank = [n for n, r in enumerate(rows, start=2) if not r[columns[0]]]
            if blank:
                raise SystemExit(f"intake: {path} has rows with no {columns[0]} (table rows {', '.join(map(str, blank))}). Fill them in or delete them.")
            return rows
    found = ", ".join(header for header in (" | ".join(t[0]) for t in tables if t)) or "no table"
    raise SystemExit(f"intake: {path} has no table with the columns {', '.join(columns)}. Found: {found}. Rename the columns; nothing was imported.")


def import_documents(intake: Json, files: dict[str, Path], replace: bool) -> tuple[Json, dict[str, list[Json]]]:
    """Read each kept document into the intake. A list the intake already holds is only replaced when asked."""
    read = {}
    for key, path in files.items():
        if intake.get(key) and not replace:
            raise SystemExit(f"intake: the intake already holds {len(intake[key])} {key}. Pass --replace to replace them with {path.name}.")
        read[key] = read_table(path, IMPORTS[key])
    for key, rows in read.items():
        intake[key] = rows
    return intake, read


def proposals_path(intake_path: Path) -> Path:
    """Proposals live beside the intake, apart from it, and never count as answers."""
    return intake_path.with_name("proposals.json")


def known_field(path: str) -> bool:
    """A field the intake has: a top-level key, or one level down such as strategy.diagnosis."""
    head, _, rest = path.partition(".")
    if head not in EMPTY or head in ("provenance", "range_sources", "source_of_truth"):
        return False
    return not rest or (isinstance(EMPTY[head], dict) and rest in EMPTY[head])


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def evidence_of(p: Json) -> list[Json]:
    """A proposal's evidence: its source and quote, or an evidence list when a value draws on several places."""
    return p["evidence"] if isinstance(p.get("evidence"), list) and p["evidence"] else [{"source": p.get("source"), "quote": p.get("quote")}]


def check_proposal(p: Any, base: Path) -> str | None:
    """Why a proposal is refused, or None. Every proposal names a known field, and each piece of its evidence
    a source and a short quote; a quote from a local file must appear in that file."""
    if not isinstance(p, dict):
        return "is not an object"
    field = p.get("field")
    if not isinstance(field, str) or not known_field(field):
        return f"names no intake field it can fill ({field!r})"
    if "value" not in p or p["value"] in (None, "", [], {}):
        return f"{field}: has no value"
    for e in evidence_of(p):
        why = check_evidence(field, e.get("source") if isinstance(e, dict) else None, e.get("quote") if isinstance(e, dict) else None, base)
        if why:
            return why
    return None


def check_evidence(field: str, source: Any, quote: Any, base: Path) -> str | None:
    if not isinstance(source, str) or not source.strip():
        return f"{field}: has no source. Name the file and heading or line, or the URL."
    if not isinstance(quote, str) or not quote.strip():
        return f"{field}: has no quote of the evidence."
    if len(quote) > MAX_QUOTE:
        return f"{field}: the quote is over {MAX_QUOTE} characters. Quote the evidence, not the document."
    if not re.match(r"https?://", source):
        file = Path(source.split("#", 1)[0].split(":", 1)[0]).expanduser()
        file = file if file.is_absolute() else base / file
        try:
            text = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return f"{field}: its source {source!r} cannot be read. Give a path that exists, or a URL."
        if squash(quote) not in squash(text):
            return f"{field}: its quote does not appear in {file.name}. Quote the document word for word."
    return None


def propose(intake_path: Path, drafted: Path) -> list[Json]:
    """Store drafted answers apart from the intake. A file with any proposal lacking a source or quote is refused whole."""
    try:
        data = json.loads(drafted.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise SystemExit(f"intake: cannot read the proposals in {drafted} ({e}).") from None
    items = data.get("proposals") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise SystemExit(f'intake: {drafted} holds no proposals. Write {{"proposals": [{{"field", "value", "source", "quote"}}]}}.')
    problems = [f"proposal {i}: {why}" for i, p in enumerate(items, start=1) if (why := check_proposal(p, drafted.parent))]
    if problems:
        raise SystemExit("intake: no proposals were stored, because:\n  " + "\n  ".join(problems))
    store = proposals_path(intake_path)
    held = json.loads(store.read_text(encoding="utf-8"))["proposals"] if store.exists() else []
    held = [h for h in held if h["status"] != "pending" or h["field"] not in {p["field"] for p in items}]
    new = [{"field": p["field"], "value": p["value"], "evidence": evidence_of(p), "status": "pending"} for p in items]
    store.write_text(json.dumps({"proposals": held + new}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new


def put(d: Json, path: str, value: Any) -> None:
    head, _, rest = path.partition(".")
    if rest:
        d.setdefault(head, {})[rest] = value
    else:
        d[head] = value


def confirm(intake_path: Path, intake: Json, by: str, fields: list[str], edits: dict[str, Any]) -> list[Json]:
    """Apply the pending proposals the user said yes to: the named fields, or all of them when none are named."""
    store = proposals_path(intake_path)
    if not store.exists():
        raise SystemExit(f"intake: there are no proposals beside {intake_path}. Run propose first.")
    data = json.loads(store.read_text(encoding="utf-8"))
    pending = [p for p in data["proposals"] if p["status"] == "pending"]
    unknown = [f for f in fields + list(edits) if f not in {p["field"] for p in pending}]
    if unknown:
        raise SystemExit(f"intake: no pending proposal for {', '.join(unknown)}. `intake.py check` lists them.")
    chosen = [p for p in pending if not fields or p["field"] in fields or p["field"] in edits]
    for p in chosen:
        value = edits.get(p["field"], p["value"])
        put(intake, p["field"], value)
        intake.setdefault("provenance", {})[p["field"]] = {
            "evidence": p["evidence"],
            "confirmed_by": by,
            "edited": p["field"] in edits,
        }
        p["status"] = "confirmed"
    store.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return chosen


def pending_proposals(intake_path: Path) -> list[Json]:
    store = proposals_path(intake_path)
    return [p for p in json.loads(store.read_text(encoding="utf-8"))["proposals"] if p["status"] == "pending"] if store.exists() else []


def write_intake(path: Path, intake: Json) -> None:
    path.write_text(json.dumps(intake, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and check the intake.")
    ap.add_argument("command", choices=["init", "check", "suggest", "accept", "import", "propose", "confirm"])
    ap.add_argument("path")
    ap.add_argument("metric", nargs="?", help="accept: the metric whose range the user said yes to; propose: the drafted proposals file")
    ap.add_argument("--range", help="accept: the range as the user edited it, if they changed the suggestion")
    ap.add_argument("--suggestions", default=str(SUGGESTIONS), help=argparse.SUPPRESS)
    ap.add_argument("--decisions", help="import: a decision log with columns ask, options, recommendation, deadline")
    ap.add_argument("--risks", help="import: a risk register with columns risk, likelihood, impact, mitigation, due")
    ap.add_argument("--stopped", help="import: a stop list with columns what, why")
    ap.add_argument("--replace", action="store_true", help="import: replace a list the intake already holds")
    ap.add_argument("--by", help="confirm: the name of the person who said yes")
    ap.add_argument("--field", action="append", default=[], help="confirm: a field to apply; repeat it. None named means all pending")
    ap.add_argument("--edit", action="append", default=[], metavar="FIELD=JSON", help="confirm: apply a proposal as the user edited it")
    args = ap.parse_args()
    path = Path(args.path)
    if args.command == "init":
        return init(path)
    if args.command == "suggest":
        lines = suggest(read_intake(path), load_suggestions(Path(args.suggestions)))
        for line in lines:
            print(line)
        print(
            "intake: put each suggestion to the user and ask them to accept or edit it. Never accept one for them."
            if any(x.startswith("suggest") for x in lines)
            else "intake: no suggestions left to offer."
        )
        return 0
    if args.command == "propose":
        if not args.metric:
            raise SystemExit("intake: propose needs the drafted file, for example propose run/intake.json drafted.json.")
        read_intake(path)
        stored = propose(path, Path(args.metric))
        print(f"intake: {len(stored)} proposal(s) stored in {proposals_path(path)}. None of them is an answer yet:")
        for p in stored:
            print(f"  - {p['field']}: {json.dumps(p['value'], ensure_ascii=False)[:120]}  (from {', '.join(e['source'] for e in p['evidence'])})")
        print("intake: show them to the user in one table with each source and quote, then run confirm with their name.")
        return 0
    if args.command == "confirm":
        if not (args.by or "").strip():
            raise SystemExit("intake: confirm needs --by with the name of the person who said yes.")
        edits = {}
        for e in args.edit:
            field, sep, raw = e.partition("=")
            if not sep:
                raise SystemExit(f'intake: --edit takes FIELD=VALUE, for example --edit "strategy.policy=Sell the judgment". Got {e!r}.')
            try:
                edits[field] = json.loads(raw)
            except json.JSONDecodeError:
                edits[field] = raw
        intake = read_intake(path)
        done = confirm(path, intake, args.by.strip(), args.field, edits)
        write_intake(path, intake)
        for p in done:
            where = ", ".join(e["source"] for e in p["evidence"])
            print(f"confirmed {p['field']}{' (edited)' if p['field'] in edits else ''}, by {args.by.strip()}, from {where}")
        return 0
    if args.command == "import":
        files = {k: Path(v) for k, v in (("decisions", args.decisions), ("risks", args.risks), ("stopped", args.stopped)) if v}
        if not files:
            raise SystemExit("intake: import needs --decisions, --risks or --stopped.")
        intake, read = import_documents(read_intake(path), files, args.replace)
        write_intake(path, intake)
        for key, rows in read.items():
            print(f"imported  {len(rows)} {key} from {files[key].name}:")
            for r in rows:
                print("  - " + "; ".join(f"{c}: {r[c] or 'not stated'}" for c in IMPORTS[key]))
        print("intake: confirm each imported row with the user. If any is wrong, fix the document and import again with --replace.")
        return 0
    if args.command == "accept":
        if not args.metric:
            raise SystemExit('intake: accept needs the metric name, for example accept run/intake.json "Deploys per week".')
        intake = accept(read_intake(path), load_suggestions(Path(args.suggestions)), args.metric, args.range)
        write_intake(path, intake)
        print(f'intake: "{args.metric}" range set to "{intake["delivery_ranges"][args.metric]}".')
        return 0
    blocking, unknown = check(read_intake(path))
    for p in pending_proposals(path):
        print(f"proposed  {p['field']}  (from {', '.join(e['source'] for e in p['evidence'])}; not an answer until confirmed)")
    for problem in blocking:
        print(f"BLOCKING  {problem}")
    for field, slide in unknown:
        effect = "will show the metric with no definition" if "definition" in field else "will show data needed"
        print(f"unknown   {field}  (slide {slide.lstrip('0')} {effect})")
    print(f"intake: {len(blocking)} blocking, {len(unknown)} unknown.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
