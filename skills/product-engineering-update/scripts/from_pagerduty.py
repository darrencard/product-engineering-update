#!/usr/bin/env python3
"""Turn PagerDuty incidents into the incidents source: id, started_at, restored_at, severity.

Usage:
  python3 scripts/from_pagerduty.py --incidents incidents-*.json --severity-from priority \\
      --service "Checkout API" --account acme --run run

Input: GET /incidents (or the PagerDuty connector), saved as it stands, one file per page
({"incidents": [...], "offset", "more"}). An incident starts at created_at and is restored at
resolved_at; one not yet resolved is left out and counted. Severity is its urgency or its priority's
summary, as --severity-from says. --service keeps only the named services (repeat it), so on-call noise
from unrelated services stays out.

Time to restore uses every incident counted; DORA's failed deployment recovery time counts only
failures a deployment caused, so the slide's figure is time to restore, not that.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_pagerduty"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn PagerDuty incidents into the incidents source.")
    ap.add_argument("--incidents", nargs="+", required=True, help="incidents as PagerDuty returns them, one file per page")
    ap.add_argument("--severity-from", choices=["urgency", "priority"], default="urgency", help="what the severity column holds (default urgency)")
    ap.add_argument("--service", action="append", default=[], help="a service to keep; repeat it. Default: every service")
    ap.add_argument("--account", required=True, help="the PagerDuty account, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()
    rows, skipped = [], {"are not resolved": 0}
    keep = {s.lower() for s in args.service}
    for i in convert.pages(args.incidents, TOOL, "incidents"):
        if keep and str((i.get("service") or {}).get("summary", "")).lower() not in keep:
            continue
        began, restored = convert.when(i.get("created_at")), convert.when(i.get("resolved_at"))
        if not began or not restored:
            skipped["are not resolved"] += 1
            continue
        severity = i.get("urgency") if args.severity_from == "urgency" else (i.get("priority") or {}).get("summary")
        rows.append(
            {
                "id": str(i.get("incident_number") or i.get("id")),
                "started_at": began.isoformat(),
                "restored_at": restored.isoformat(),
                "severity": str(severity or ""),
            }
        )
    convert.report_skipped(TOOL, skipped, "incident(s)")
    if not rows:
        raise convert.fail(TOOL, "found no resolved incidents. The incidents source stays Unknown; no file was written.")
    what = f"PagerDuty incidents, created_at to resolved_at{', services ' + ', '.join(args.service) if args.service else ''}"
    out = convert.write(
        "incidents",
        rows,
        f"PagerDuty ({args.account})",
        what,
        collect.retrieved_date(args.retrieved_at, args.incidents[0]),
        Path(args.incidents[0]).name,
        args.run,
    )
    print(f"{TOOL}: {len(rows)} resolved incidents, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
