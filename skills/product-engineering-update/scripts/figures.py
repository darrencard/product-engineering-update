#!/usr/bin/env python3
"""The figures a deck may print: every number the pipeline computed, and nothing else.

draft.py writes run/figures.json next to run/deck.json: every figure in its own draft, in the
ledger and in the intake. Claude may then rewrite titles and text, cut slides or reorder them,
but validate.py blocks any printed figure that is not on that list (rule figure-not-computed).
The wording can change between runs; the numbers cannot.

A figure is read with the rounding its printing implies, so "$10.9M" matches 10,910,000 and
"22%" matches 21.8. Dates, years, quarters, ledger references and bare counts of 20 or less
are not figures.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

Json = dict[str, Any]

SCALE = {"k": 1e3, "K": 1e3, "M": 1e6, "m": 1e6, "B": 1e9, "bn": 1e9}
UNITS = r"%|pp|K|M|B|bn|k|h|hours?|days?|d|weeks?|mins?|minutes?"
FIGURE = re.compile(rf"(?<![\w.])(-|−|\+)?(\$)?(\d{{1,3}}(?:,\d{{3}})+|\d+)(\.\d+)?\s?({UNITS})?(?![\w])")
NOT_FIGURES = (
    r"\[\[[^\]]*\]\]",  # ledger references
    r"\bL\d{2,}\b",  # ledger IDs in prose
    r"\b\d{4}-\d{2}-\d{2}\b",  # ISO dates
    r"\b\d{4}-Q[1-4]\b|\bQ[1-4](?:\s\d{4})?\b",  # quarters
    r"\b\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:\s\d{4})?\b",  # 4 Nov 2026
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s\d{1,2}(?:,?\s\d{4})?\b",  # Nov 4, 2026
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s\d{4}\b",  # Nov 2026
    r"\b(?:19|20)\d{2}\b",  # years
    r"\bv?\d+\.\d+\.\d+\b",  # versions
    r"\b[A-Z]+-\d+\b",  # tracker keys, R-999
)


def extract(text: str) -> list[Json]:
    """Every figure printed in a text, with its value and the rounding its printing allows."""
    for pattern in NOT_FIGURES:
        text = re.sub(pattern, " ", text)
    found = []
    for m in FIGURE.finditer(text):
        sign, dollar, whole, frac, unit = m.groups()
        unit = unit or ""
        if not dollar and not unit and not frac and int(whole.replace(",", "")) <= 20:
            continue  # small bare counts: "3 bets", slide numbers
        value = float(whole.replace(",", "") + (frac or ""))
        if sign in ("-", "−"):
            value = -value
        scale = SCALE.get(unit, 1.0)
        decimals = len(frac) - 1 if frac else 0
        found.append(
            {"printed": m.group(0).strip(), "value": value * scale, "tol": 0.5 * 10 ** (-decimals) * scale + 1e-9, "kind": kind_of(unit, bool(dollar))}
        )
    return found


KINDS = ("pct", "money", "time", "count")


def kind_of(unit: str, dollar: bool = False) -> str:
    """A figure's kind, so a made-up percentage cannot pass by matching a count or a dollar amount."""
    if dollar or unit == "$":
        return "money"
    if unit in ("%", "pp"):
        return "pct"
    if unit and unit[0] in "hdwm" and unit not in ("m",):
        return "time"
    return "count"


def numbers(obj: Any, raw_kinds: tuple[str, ...] = ("count", "pct")) -> list[tuple[str, float]]:
    """(kind, value) for every number in a JSON value. A figure printed in a string carries its own
    kind; a raw number (an intake target such as 50) may stand for a count or a percentage."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [(k, float(obj)) for k in raw_kinds]
    if isinstance(obj, str):
        return [(f["kind"], f["value"]) for f in extract(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in numbers(v, raw_kinds)]
    if isinstance(obj, list):
        return [n for v in obj for n in numbers(v, raw_kinds)]
    return []


def shown(slide: Json) -> Any:
    """What a reader sees on a slide: its title and blocks, without illustrative samples."""
    return [slide.get("title"), slide.get("kicker"), [b for b in slide.get("blocks", []) if b.get("type") != "sample"]]


def pool(deck: Json, intake: Json) -> dict[str, list[float]]:
    """The figures a deck may print, by kind: those in the pipeline's draft, its ledger and the intake."""
    values = numbers([shown(s) for s in deck["slides"]], ("count",)) + numbers(intake)
    for row in deck.get("ledger") or []:
        values += numbers(row.get("claim"))
        if isinstance(row.get("value"), (int, float)):
            values.append((kind_of(row.get("unit") or ""), float(row["value"])))
    values += [("pct", v * 100) for k, v in values if k in ("count", "pct") and 0 < abs(v) < 1]  # a share stored as a fraction
    return {k: sorted({round(v, 6) for kind, v in values if kind == k}) for k in KINDS}


def matches(figure: Json, allowed: dict[str, list[float]]) -> bool:
    return any(abs(abs(figure["value"]) - abs(p)) <= figure["tol"] for p in allowed.get(figure["kind"], []))


def write(run: Path, deck: Json, intake: Json) -> Path:
    allowed = pool(deck, intake)
    path = run / "figures.json"
    body = {"note": "Written by draft.py. Every figure the deck may print. Do not edit: run draft.py again.", "figures": allowed}
    body["sha256"] = hashlib.sha256(json.dumps(allowed).encode()).hexdigest()
    path.write_text(json.dumps(body) + "\n", encoding="utf-8")
    return path


def load(deck_path: Path) -> dict[str, list[float]] | None:
    """The allowed figures written beside a deck, or None when there are none (a deck written by hand)."""
    path = deck_path.parent / "figures.json"
    if not path.exists():
        return None
    body = json.loads(path.read_text(encoding="utf-8"))
    allowed = body.get("figures")
    if not isinstance(allowed, dict) or hashlib.sha256(json.dumps(allowed).encode()).hexdigest() != body.get("sha256"):
        raise SystemExit(f"figures: {path} was changed by hand. Run draft.py again to rewrite it; never edit it.")
    return allowed


def unmatched(deck: Json, allowed: dict[str, list[float]]) -> list[tuple[str, str]]:
    """(slide ID, printed figure) for every figure on a slide that the pipeline did not compute."""
    out = []
    for s in deck["slides"]:
        if s["kind"] == "appendix":
            continue
        for text in strings(shown(s)):
            out += [(s["id"], f["printed"]) for f in extract(text) if not matches(f, allowed)]
    return out


def strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [t for v in obj.values() for t in strings(v)]
    if isinstance(obj, list):
        return [t for v in obj for t in strings(v)]
    return []
