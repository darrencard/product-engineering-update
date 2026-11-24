#!/usr/bin/env python3
"""Turn HubSpot's closed deals into the crm source: deal, outcome, reason.

Usage:
  python3 scripts/from_hubspot.py --deals deals-*.json --period-start 2026-08-08 --period-end 2026-11-23 --portal acme --run run

Input: CRM deals search results (POST /crm/v3/objects/deals/search, or the HubSpot connector), saved as
they stand, one file per page: {"results": [{"id", "properties": {...}}], "paging": {...}}. Ask for the
properties hs_is_closed, hs_is_closed_won, closedate, closed_won_reason and closed_lost_reason (search
returns only a few properties unless asked). HubSpot returns property values as strings.

A deal counts when hs_is_closed is "true" and its closedate falls in the window. Its outcome is won when
hs_is_closed_won is "true", otherwise lost; its reason is closed_won_reason or closed_lost_reason. A
closed deal with no reason is left out and counted: the slide counts reasons, so none is invented.

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

TOOL = "from_hubspot"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn HubSpot's closed deals into the crm source.")
    ap.add_argument("--deals", nargs="+", required=True, help="deals search results as HubSpot returns them, one file per page")
    ap.add_argument("--portal", required=True, help="the HubSpot account, for the ledger")
    convert.window_args(ap)
    args = ap.parse_args()
    start, end = convert.window(args, TOOL)
    rows, skipped = [], {"carry no hs_is_closed property": 0, "have no reason": 0}
    for deal in convert.pages(args.deals, TOOL, "results"):
        props = deal.get("properties") or {}
        if "hs_is_closed" not in props:
            skipped["carry no hs_is_closed property"] += 1
            continue
        if str(props["hs_is_closed"]).lower() != "true" or not convert.inside(convert.day(props.get("closedate")), start, end):
            continue
        won = str(props.get("hs_is_closed_won", "")).lower() == "true"
        reason = (props.get("closed_won_reason") if won else props.get("closed_lost_reason")) or ""
        if not str(reason).strip():
            skipped["have no reason"] += 1
            continue
        rows.append({"deal": str(deal.get("id")), "outcome": "won" if won else "lost", "reason": str(reason).strip()})
    convert.report_skipped(TOOL, skipped, "closed deal(s)")
    if not rows:
        raise convert.fail(TOOL, "found no closed deals with a reason in the window. The CRM source stays Unknown; no file was written.")
    what = f"HubSpot deals search, closed {start} to {end}, with closed won or lost reason"
    out = convert.write(
        "crm", rows, f"HubSpot ({args.portal})", what, collect.retrieved_date(args.retrieved_at, args.deals[0]), Path(args.deals[0]).name, args.run
    )
    print(f"{TOOL}: {len(rows)} closed deals with a reason, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
