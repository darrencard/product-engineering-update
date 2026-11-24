#!/usr/bin/env python3
"""Turn Intercom conversations into the support source: ticket, theme, account.

Usage:
  python3 scripts/from_intercom.py --conversations conv-*.json --theme-prefix "theme:" \\
      --period-start 2026-08-08 --period-end 2026-11-23 --workspace acme --run run

Input: conversation search results (POST /conversations/search, or the Intercom connector), saved as
they stand, one file per page: {"conversations": [...], "pages": {...}}. created_at is epoch seconds;
tags are {"tags": [{"name": ...}]}.

A conversation counts when it was created in the window. Its theme is the tag after --theme-prefix, or a
tag named with --theme; a conversation with neither is left out and counted, never given the first tag.
Its account is the custom attribute named by --account-attribute, if given.

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

TOOL = "from_intercom"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn Intercom conversations into the support source.")
    ap.add_argument("--conversations", nargs="+", required=True, help="conversation search results as Intercom returns them, one file per page")
    convert.theme_args(ap)
    ap.add_argument("--account-attribute", help="the conversation custom attribute that names the customer account")
    ap.add_argument("--workspace", required=True, help="the Intercom workspace, for the ledger")
    convert.window_args(ap)
    args = ap.parse_args()
    if not (args.theme_prefix or args.theme):
        raise convert.fail(TOOL, "name the themes: --theme-prefix or --theme. The script does not choose a tag.")
    start, end = convert.window(args, TOOL)
    rows, skipped = [], {"have no theme tag": 0}
    for c in convert.pages(args.conversations, TOOL, "conversations"):
        if not convert.inside(convert.day(c.get("created_at")), start, end):
            continue
        tags = [t.get("name", "") for t in ((c.get("tags") or {}).get("tags") or []) if isinstance(t, dict)]
        theme = convert.theme_of(tags, args.theme_prefix, args.theme)
        if not theme:
            skipped["have no theme tag"] += 1
            continue
        account = (c.get("custom_attributes") or {}).get(args.account_attribute) if args.account_attribute else ""
        rows.append({"ticket": str(c.get("id")), "theme": theme, "account": str(account or "")})
    convert.report_skipped(TOOL, skipped, "conversation(s)")
    if not rows:
        raise convert.fail(TOOL, "found no conversations with a theme in the window. Support stays Unknown; no file was written.")
    what = f"Intercom conversations created {start} to {end}, themed by tag"
    out = convert.write(
        "support",
        rows,
        f"Intercom ({args.workspace})",
        what,
        collect.retrieved_date(args.retrieved_at, args.conversations[0]),
        Path(args.conversations[0]).name,
        args.run,
    )
    print(f"{TOOL}: {len(rows)} conversations with a theme, written to {out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
