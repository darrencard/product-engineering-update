#!/usr/bin/env python3
"""Turn Zendesk tickets into the support source: ticket, theme, account.

Usage:
  python3 scripts/from_zendesk.py --tickets tickets-*.json --theme-prefix "theme_" \\
      --period-start 2026-08-08 --period-end 2026-11-23 --subdomain acme --run run

Input, saved as it stands, one file per page: the ticket list (GET /api/v2/tickets, {"tickets": [...]}),
a search (GET /api/v2/search?query=type:ticket, {"results": [...]} with result_type ticket), or a
search export (GET /api/v2/search/export). created_at is ISO; tags are a list of strings.

A ticket counts when it was created in the window. Its theme is the tag after --theme-prefix, a tag named
with --theme, or the value of the custom field named by --theme-field; a ticket with none is left out
and counted. Its account is its organization_id.

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

TOOL = "from_zendesk"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn Zendesk tickets into the support source.")
    ap.add_argument("--tickets", nargs="+", required=True, help="tickets, search or search export results as Zendesk returns them, one file per page")
    convert.theme_args(ap)
    ap.add_argument("--theme-field", type=int, help="the id of a custom field that holds the theme")
    ap.add_argument("--subdomain", required=True, help="the Zendesk subdomain, for the ledger")
    convert.window_args(ap)
    args = ap.parse_args()
    if not (args.theme_prefix or args.theme or args.theme_field):
        raise convert.fail(TOOL, "name the themes: --theme-prefix, --theme or --theme-field. The script does not choose a tag.")
    start, end = convert.window(args, TOOL)
    rows, skipped = [], {"have no theme": 0}
    for t in convert.pages(args.tickets, TOOL, "tickets", "results"):
        if t.get("result_type", "ticket") != "ticket" or not convert.inside(convert.day(t.get("created_at")), start, end):
            continue
        theme = convert.theme_of([str(x) for x in t.get("tags") or []], args.theme_prefix, args.theme)
        if not theme and args.theme_field:
            theme = str(next((f.get("value") for f in t.get("custom_fields") or [] if f.get("id") == args.theme_field and f.get("value")), "") or "")
        if not theme:
            skipped["have no theme"] += 1
            continue
        org = t.get("organization_id")
        rows.append({"ticket": str(t.get("id")), "theme": theme, "account": "" if org is None else str(org)})
    convert.report_skipped(TOOL, skipped, "ticket(s)")
    if not rows:
        raise convert.fail(TOOL, "found no tickets with a theme in the window. Support stays Unknown; no file was written.")
    what = f"Zendesk tickets created {start} to {end}, themed by tag or field"
    out = convert.write(
        "support", rows, f"Zendesk ({args.subdomain})", what, collect.retrieved_date(args.retrieved_at, args.tickets[0]), Path(args.tickets[0]).name, args.run
    )
    print(f"{TOOL}: {len(rows)} tickets with a theme, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
