#!/usr/bin/env python3
"""Turn a Mixpanel query result into the analytics source.

Usage:
  python3 scripts/from_mixpanel.py --chart insights.json --metric "Signups" --series "Signed up" \\
      --period "2026-Q2=2026-04-01..2026-06-30" --period "2026-Q3=2026-07-01..2026-09-30" \\
      --aggregate sum --project "Acme" --run run

Input, saved as it stands, either:
  - the Query API's insights result (GET /api/query/insights): {"series": {"<event>": {"<ISO date>": n}}}
  - its segmentation result (GET /api/query/segmentation, in maintenance mode): {"data": {"values":
    {"<event>": {"YYYY-MM-DD": n}}}}
Pick one series with --series when there are several. Each period's value is the sum, mean or last
of its daily values, as --aggregate says.

This script reads a file and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_mixpanel"


def main() -> int:
    args = convert.analytics_args("Turn a Mixpanel query result into the analytics source.").parse_args()
    by_label: dict[str, dict[str, float]] = {}
    for path in args.chart:
        data = convert.load_json(Path(path), TOOL)
        found = data.get("series") if isinstance(data, dict) and isinstance(data.get("series"), dict) else ((data or {}).get("data") or {}).get("values")
        if not isinstance(found, dict):
            raise convert.fail(TOOL, f"{path} holds no series (insights) or data.values (segmentation), as Mixpanel returns them.")
        for label, points in found.items():
            if isinstance(points, dict):
                by_label.setdefault(str(label), {}).update(points)
    rows = convert.series_rows(by_label, TOOL, args)
    what = f"Mixpanel query result, {args.aggregate} of daily values per period"
    out = convert.write(
        "analytics",
        rows,
        f"Mixpanel ({args.project})",
        what,
        collect.retrieved_date(args.retrieved_at, args.chart[0]),
        Path(args.chart[0]).name,
        args.run,
        keep_other="metric",
    )
    print(f"{TOOL}: {len(rows)} period value(s) for {args.metric}, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
