#!/usr/bin/env python3
"""Shared helpers for the from_<system>.py converters. Not run on its own.

Every converter reads a system's own export, saved as it stands, maps only fields that exist, and
writes one of the sources collect.py defines. These helpers keep that the same everywhere: reading
pages, parsing the date forms systems use, naming periods, and writing through collect.collect so
the columns are checked the same way as a CSV.

Standard library only. Runs on Python 3.9 or later. It makes no network calls.
"""

from __future__ import annotations

import csv
import datetime
import io
import json
import statistics
from pathlib import Path
from typing import Any

import collect

Json = dict[str, Any]


class Refused(SystemExit):
    """A converter stopping with one line that says what to do."""


def fail(tool: str, message: str) -> Refused:
    return Refused(f"{tool}: {message}")


def load_json(path: Path, tool: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise fail(tool, f"cannot read {path} ({e}). Save the system's response as it stands, as UTF-8 JSON.") from None


def items(data: Any, *keys: str) -> list[Json] | None:
    """The list of records in a response: the first of `keys` that holds a list, or the response itself if it is a list.
    A dotted key walks into objects, so "data.values" or "result.records" work."""
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    for key in keys:
        node: Any = data
        for part in key.split("."):
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, list):
            return [x for x in node if isinstance(x, dict)]
    return None


def pages(paths: list[str], tool: str, *keys: str) -> list[Json]:
    """Every record across saved pages. A page with no list under any of `keys` is refused."""
    out: list[Json] = []
    for p in paths:
        found = items(load_json(Path(p), tool), *keys)
        if found is None:
            raise fail(tool, f"{p} holds no list under {', '.join(keys) or 'its top level'}, as the system returns it.")
        out += found
    return out


def read_csv(path: Path, tool: str) -> list[Json]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise fail(tool, f"cannot read {path} ({e}).") from None
    return list(csv.DictReader(io.StringIO(text)))


def when(value: Any) -> datetime.datetime | None:
    """A timestamp in any form systems use: ISO text, epoch seconds, or epoch milliseconds (as a number or a string)."""
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value)
    if isinstance(value, (int, float)):
        seconds = value / 1000 if abs(value) > 10**11 else value
        return datetime.datetime.fromtimestamp(seconds, tz=datetime.timezone.utc)
    try:
        parsed = datetime.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.datetime.fromisoformat(str(value).strip()[:10])
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)


def day(value: Any) -> datetime.date | None:
    moment = when(value)
    return moment.date() if moment else None


def period(text: str, tool: str) -> tuple[str, datetime.date, datetime.date]:
    """LABEL=YYYY-MM-DD..YYYY-MM-DD, as the intake names its periods."""
    try:
        label, span = text.split("=", 1)
        start, end = span.split("..", 1)
        return label.strip(), datetime.date.fromisoformat(start.strip()), datetime.date.fromisoformat(end.strip())
    except ValueError:
        raise fail(tool, f'--period takes LABEL=YYYY-MM-DD..YYYY-MM-DD, for example "2026-Q3=2026-07-01..2026-09-30". Got {text!r}.') from None


def inside(d: datetime.date | None, start: datetime.date, end: datetime.date) -> bool:
    return d is not None and start <= d <= end


def aggregate(values: list[float], how: str) -> float:
    """How a period's daily values become one: the user says which, the script never picks."""
    return float(sum(values)) if how == "sum" else float(statistics.mean(values)) if how == "mean" else float(values[-1])


def write(source: str, rows: list[Json], system: str, query: str, retrieved: str, origin: str, run: str, keep_other: str | None = None) -> Path:
    """Write a source through collect.collect, so the columns are checked as for a CSV. With keep_other naming a column,
    rows already in the file whose value in that column is not in the new rows are kept (one system's metrics beside another's)."""
    out = Path(run) / "data" / f"{source}.json"
    if keep_other and out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        names = {r[keep_other] for r in rows}
        rows = [r for r in existing["rows"] if r[keep_other] not in names] + rows
    data = collect.collect(source, rows, system, query, retrieved, origin)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out


def write_csv(path: Path, columns: tuple[str, ...], rows: list[Json]) -> None:
    """A file for the person to check and finish before it is imported. Cells a spreadsheet would run are neutralised."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for k, v in r.items()})


def pairs(values: list[str], flag: str, tool: str) -> dict[str, str]:
    out = {}
    for v in values:
        if "=" not in v:
            raise fail(tool, f"{flag} takes VALUE=NAME. Got {v!r}.")
        a, b = v.split("=", 1)
        out[a.strip()] = b.strip()
    return out
