#!/usr/bin/env python3
"""Turn Salesforce's closed opportunities into the crm source: deal, outcome, reason.

Usage:
  python3 scripts/from_salesforce.py --records opps-*.json --reason-field Loss_Reason__c \\
      --period-start 2026-08-08 --period-end 2026-11-23 --org acme --run run

Input: a REST query result (GET /services/data/vXX.X/query?q=SOQL, or the Salesforce connector), saved
as it stands, one file per page: {"records": [...], "done": ..., "nextRecordsUrl": ...}. Query
Opportunity for Id, IsClosed, IsWon, CloseDate and the field your team keeps the reason in.

Salesforce has no standard win or loss reason field that we could confirm; teams add their own, such
as Loss_Reason__c. --reason-field names it, and a closed opportunity with it empty is left out and
counted. An opportunity counts when IsClosed is true and CloseDate falls in the window; IsWon gives
the outcome.

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

TOOL = "from_salesforce"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn Salesforce's closed opportunities into the crm source.")
    ap.add_argument("--records", nargs="+", required=True, help="Opportunity query results as Salesforce returns them, one file per page")
    ap.add_argument("--reason-field", required=True, help="the field that holds the win or loss reason, for example Loss_Reason__c")
    ap.add_argument("--org", required=True, help="the Salesforce org, for the ledger")
    convert.window_args(ap)
    args = ap.parse_args()
    start, end = convert.window(args, TOOL)
    rows, skipped = [], {"have no reason": 0}
    records = convert.pages(args.records, TOOL, "records")
    if records and args.reason_field not in records[0]:
        raise convert.fail(TOOL, f"the records have no {args.reason_field} field. Add it to the SOQL query, or name the field your team uses.")
    for opp in records:
        if opp.get("IsClosed") is not True or not convert.inside(convert.day(opp.get("CloseDate")), start, end):
            continue
        reason = str(opp.get(args.reason_field) or "").strip()
        if not reason:
            skipped["have no reason"] += 1
            continue
        rows.append({"deal": str(opp.get("Id")), "outcome": "won" if opp.get("IsWon") is True else "lost", "reason": reason})
    convert.report_skipped(TOOL, skipped, "closed opportunit(ies)")
    if not rows:
        raise convert.fail(TOOL, "found no closed opportunities with a reason in the window. The CRM source stays Unknown; no file was written.")
    what = f"Salesforce Opportunity query, closed {start} to {end}, reason from {args.reason_field}"
    out = convert.write(
        "crm", rows, f"Salesforce ({args.org})", what, collect.retrieved_date(args.retrieved_at, args.records[0]), Path(args.records[0]).name, args.run
    )
    print(f"{TOOL}: {len(rows)} closed opportunities with a reason, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
