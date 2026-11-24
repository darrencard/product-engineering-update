#!/usr/bin/env python3
"""Turn raw PostHog results into the analytics source, with no retyping.

Usage, one of:
  python3 scripts/from_posthog.py --query results.json --run run
      a HogQL query result ({"columns": [...], "results": [[...], ...]}) whose query returns
      one row per metric and period, with columns named metric, period and value
      (and optionally definition). Write the query so the period column holds the intake's
      period labels, for example '2026-Q3'.

  python3 scripts/from_posthog.py --insight trend.json --metric "Weekly active dispatchers" \\
      --period "2026-Q2=2026-04-01..2026-06-30" --period "2026-Q3=2026-07-01..2026-09-30" \\
      --aggregate mean --run run
      a trends insight result ({"result": [{"label", "days": [...], "data": [...]}, ...]}).
      Each period's value is the sum, mean or last of the daily values inside it, as --aggregate
      says. --series picks one series by label when the insight has several.

Shapes are PostHog's documented query API and insight API responses. This script reads files
and writes a file. It makes no network calls. If an analytics file already exists, its rows for
other metrics are kept.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]
NEEDED = ("metric", "period", "value")


def fail(message: str) -> SystemExit:
    return SystemExit(f"from_posthog: {message}")


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise fail(f"cannot read {path} ({e}). Save PostHog's response as it stands, as UTF-8 JSON.") from None


def query_rows(data: Any) -> list[Json]:
    if not isinstance(data, dict) or not isinstance(data.get("columns"), list) or not isinstance(data.get("results"), list):
        raise fail("a query result needs PostHog's columns and results lists.")
    columns = [str(c).lower() for c in data["columns"]]
    missing = [c for c in NEEDED if c not in columns]
    if missing:
        raise fail(f"the query returns no {', '.join(missing)} column. Name its columns metric, period and value.")
    at = {c: columns.index(c) for c in (*NEEDED, "definition") if c in columns}
    return [{c: row[i] for c, i in at.items()} for row in data["results"] if isinstance(row, list)]


def window(text: str) -> tuple[str, datetime.date, datetime.date]:
    try:
        label, span = text.split("=", 1)
        start, end = span.split("..", 1)
        return label.strip(), datetime.date.fromisoformat(start.strip()), datetime.date.fromisoformat(end.strip())
    except ValueError:
        raise fail(f'--period takes LABEL=YYYY-MM-DD..YYYY-MM-DD, for example "2026-Q3=2026-07-01..2026-09-30". Got {text!r}.') from None


def insight_rows(data: Any, metric: str, series: str | None, periods: list[str], aggregate: str) -> list[Json]:
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, list) or not result:
        raise fail("an insight result needs PostHog's result list of series.")
    if series is None and len(result) > 1:
        raise fail(f"the insight has {len(result)} series ({', '.join(str(s.get('label')) for s in result)}). Pick one with --series.")
    picked = next((s for s in result if series is None or s.get("label") == series), None)
    if picked is None:
        raise fail(f'the insight has no series named "{series}".')
    days, values = picked.get("days") or [], picked.get("data") or []
    if len(days) != len(values):
        raise fail("the series' days and data differ in length. Export the insight again.")
    rows = []
    for text in periods:
        label, start, end = window(text)
        inside = [v for d, v in zip(days, values) if start <= datetime.date.fromisoformat(str(d)[:10]) <= end]
        if not inside:
            raise fail(f"the insight holds no days inside {label}. Widen its date range in PostHog and export again.")
        value = sum(inside) if aggregate == "sum" else statistics.mean(inside) if aggregate == "mean" else inside[-1]
        rows.append({"metric": metric, "period": label, "value": value})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw PostHog results into the analytics source.")
    given = ap.add_mutually_exclusive_group(required=True)
    given.add_argument("--query", help="a HogQL query result with metric, period and value columns")
    given.add_argument("--insight", help="a trends insight result")
    ap.add_argument("--metric", help="insight: the metric's name, as the intake names it")
    ap.add_argument("--series", help="insight: the series label to use, when there are several")
    ap.add_argument("--period", action="append", default=[], help="insight: LABEL=START..END; repeat for each period")
    ap.add_argument("--aggregate", choices=["sum", "mean", "last"], help="insight: how the daily values in a period become one")
    ap.add_argument("--definition", help="insight: what the metric counts, in one plain-English sentence")
    ap.add_argument("--project", default="PostHog", help="the PostHog project, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    origin = args.query or args.insight
    if args.query:
        rows, what = query_rows(load(Path(args.query))), "PostHog query API (HogQL)"
    else:
        if not (args.metric and args.period and args.aggregate):
            raise fail("--insight needs --metric, at least one --period and --aggregate. The script does not choose them.")
        rows = insight_rows(load(Path(args.insight)), args.metric, args.series, args.period, args.aggregate)
        rows = [{**r, "definition": args.definition or ""} for r in rows]
        what = f"PostHog trends insight, {args.aggregate} of daily values per period"
    out = Path(args.run) / "data" / "analytics.json"
    if out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        names = {r["metric"] for r in rows}
        rows = [r for r in existing["rows"] if r["metric"] not in names] + rows
    data = collect.collect("analytics", rows, f"PostHog ({args.project})", what, collect.retrieved_date(args.retrieved_at, origin), Path(origin).name)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    metrics = sorted({r["metric"] for r in data["rows"]})
    print(f"from_posthog: {len(data['rows'])} rows for {len(metrics)} metric(s) ({', '.join(metrics)}), written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
