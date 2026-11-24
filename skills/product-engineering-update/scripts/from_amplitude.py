#!/usr/bin/env python3
"""Turn an Amplitude chart result into the analytics source.

Usage:
  python3 scripts/from_amplitude.py --chart segmentation.json --metric "Weekly active dispatchers" \\
      --period "2026-Q2=2026-04-01..2026-06-30" --period "2026-Q3=2026-07-01..2026-09-30" \\
      --aggregate mean --project "Acme web" --run run

Input: the Dashboard REST API's event segmentation result (GET /api/2/events/segmentation), saved as it
stands: {"data": {"series": [[...]], "seriesLabels": [...], "xValues": ["YYYY-MM-DD", ...]}}. Each
series is one group's values in xValues order. Pick one with --series when there are several. Each
period's value is the sum, mean or last of its daily values, as --aggregate says.

This script reads a file and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_amplitude"


def main() -> int:
    args = convert.analytics_args("Turn an Amplitude chart result into the analytics source.").parse_args()
    by_label: dict[str, dict[str, float]] = {}
    for path in args.chart:
        data = (convert.load_json(Path(path), TOOL) or {}).get("data") or {}
        series, labels, days = data.get("series"), data.get("seriesLabels") or [], data.get("xValues")
        if not isinstance(series, list) or not isinstance(days, list):
            raise convert.fail(TOOL, f"{path} holds no data.series and data.xValues, as event segmentation returns them.")
        for i, values in enumerate(series):
            label = str(labels[i]) if i < len(labels) else f"series {i + 1}"
            if len(values) != len(days):
                raise convert.fail(TOOL, f"series {label} has {len(values)} values for {len(days)} days. Export the chart again.")
            by_label.setdefault(label, {}).update(dict(zip(days, values)))
    rows = convert.series_rows(by_label, TOOL, args)
    what = f"Amplitude event segmentation, {args.aggregate} of daily values per period"
    out = convert.write(
        "analytics",
        rows,
        f"Amplitude ({args.project})",
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
