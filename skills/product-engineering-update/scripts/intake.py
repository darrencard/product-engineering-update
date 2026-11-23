#!/usr/bin/env python3
"""Build and check intake.json, the record of the interview.

Usage:
  python3 scripts/intake.py init run/intake.json        # write an empty intake
  python3 scripts/intake.py check run/intake.json       # list what is still Unknown, by slide

Anything the person does not supply stays null. Null means Unknown: the deck
shows a data_needed block for it. Never fill a null with a guess.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
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
    "inputs": [],  # [{"metric": "Activation", "target": 50, "target_display": "50%", "higher_is_better": true, "owner": "..."}]
    "delivery_ranges": {},  # {"Deploys per week": "35+", "Change failure rate": "under 3.5%"}  healthy ranges, never single points
    "ai_features": None,  # [{"name": "Dispatch Agent", "eval_set": "v14"}]  [] means none in production; null means not asked yet
    "bets": [],  # [{"bet", "commitment", "appetite", "expected", "confidence", "stop_rule", "objective", "cause", "owner"}]
    "risks": [],  # [{"risk", "likelihood", "impact", "mitigation", "due"}]
    "stopped": [],  # [{"what", "why"}]
    "decisions": [],  # [{"ask", "options", "recommendation", "deadline"}]
    "connected": [],  # source keys that have data: "tracker", "billing", ...
}

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


def init(path: Path) -> int:
    if path.exists():
        raise SystemExit(f"intake: {path} already exists. It holds interview answers, so it is not overwritten. Edit it, or delete it first.")
    try:
        path.write_text(json.dumps(EMPTY, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"intake: cannot write {path} ({e.strerror}). Create the run folder first, then run this again.") from None
    print(f"intake: wrote {path}. Fill it from the interview. Leave anything not supplied as null.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Build and check the intake.")
    ap.add_argument("command", choices=["init", "check"])
    ap.add_argument("path")
    args = ap.parse_args()
    path = Path(args.path)
    if args.command == "init":
        return init(path)
    blocking, unknown = check(read_intake(path))
    for problem in blocking:
        print(f"BLOCKING  {problem}")
    for field, slide in unknown:
        print(f"unknown   {field}  (slide {slide.lstrip('0')} will show data needed)")
    print(f"intake: {len(blocking)} blocking, {len(unknown)} unknown.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
