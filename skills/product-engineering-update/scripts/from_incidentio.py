#!/usr/bin/env python3
"""Turn incident.io incidents into the incidents source: id, started_at, restored_at, severity.

Usage:
  python3 scripts/from_incidentio.py --incidents incidents-*.json --started "Impact started" \\
      --restored "Resolved" --organization acme --run run

Input: GET /v2/incidents (or the incident.io connector), saved as it stands, one file per page
({"incidents": [...], "pagination_meta": {...}}). Each incident's times are in
incident_timestamp_values, named per account, so --started and --restored name the two to use (ask the
user; "created_at" is allowed for --started and means when the incident was declared). Severity is the
incident's severity name.

An incident with either time missing (still open, or never set) is left out and counted. Time to
restore uses every incident in the period; DORA's failed deployment recovery time counts only failures
a deployment caused, so the slide's figure is time to restore, not that.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_incidentio"


def stamp(incident: dict[str, Any], name: str) -> Any:
    if name == "created_at":
        return incident.get("created_at")
    for v in incident.get("incident_timestamp_values") or []:
        if ((v.get("incident_timestamp") or {}).get("name") or "").lower() == name.lower():
            return (v.get("value") or {}).get("value")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn incident.io incidents into the incidents source.")
    ap.add_argument("--incidents", nargs="+", required=True, help="incidents as incident.io returns them, one file per page")
    ap.add_argument("--started", required=True, help='the timestamp that marks the start, for example "Impact started", or created_at')
    ap.add_argument("--restored", required=True, help='the timestamp that marks service restored, for example "Resolved"')
    ap.add_argument("--organization", required=True, help="the incident.io organization, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()
    rows, skipped = [], {"have no start or restore time": 0}
    for i in convert.pages(args.incidents, TOOL, "incidents"):
        began, restored = convert.when(stamp(i, args.started)), convert.when(stamp(i, args.restored))
        if not began or not restored:
            skipped["have no start or restore time"] += 1
            continue
        rows.append(
            {
                "id": str(i.get("reference") or i.get("id")),
                "started_at": began.isoformat(),
                "restored_at": restored.isoformat(),
                "severity": (i.get("severity") or {}).get("name") or "",
            }
        )
    convert.report_skipped(TOOL, skipped, "incident(s)")
    if not rows:
        raise convert.fail(TOOL, f'found no incidents with both "{args.started}" and "{args.restored}". Check the timestamp names; no file was written.')
    what = f'incident.io incidents, from "{args.started}" to "{args.restored}"'
    out = convert.write(
        "incidents",
        rows,
        f"incident.io ({args.organization})",
        what,
        collect.retrieved_date(args.retrieved_at, args.incidents[0]),
        Path(args.incidents[0]).name,
        args.run,
    )
    print(f"{TOOL}: {len(rows)} incidents with a start and a restore time, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
