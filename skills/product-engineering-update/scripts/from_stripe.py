#!/usr/bin/env python3
"""Turn raw Stripe exports into the billing source: ARR per account at each month end.

Usage:
  python3 scripts/from_stripe.py --invoices invoices-*.json --months 2026-04..2026-11 --account acme --run run
  python3 scripts/from_stripe.py --subscriptions subs-*.json --months 2026-04..2026-11 --account acme --run run

Inputs are what Stripe already gives you, saved as they stand, one file per page ({"object": "list",
"data": [...], "has_more": ...}), from the Stripe connector or the API. All Stripe money is an integer
in cents and all Stripe times are epoch seconds.

--invoices (preferred: amounts are what the customer is billed, discounts included)
  For each paid or open invoice, each subscription line (parent.type subscription_item_details, not a
  proration) bills its period (period.start to period.end). A line is annualised by the whole calendar
  months it covers: a 1-month line counts 12 times, a 12-month line once. It counts toward every month
  whose last day falls inside its period. A line whose period is not a whole number of months, or a
  proration, is left out and counted.

--subscriptions
  Each active or past_due subscription counts at a month end when it started on or before that day and
  had not ended. Each item counts unit_amount x quantity, annualised by its price's recurring interval.
  Stripe's discounts are not applied here; use --invoices for amounts net of discounts.

The rows are account (the Stripe customer), month (YYYY-MM) and arr in dollars, the billing source
compute_metrics.py already reads for ARR, net and gross revenue retention and expansion. Nothing new
is computed here. A currency other than --currency is refused, never converted.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import calendar
import datetime
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_stripe"
Json = dict[str, Any]
PER_YEAR = {"day": 365, "week": 52, "month": 12, "year": 1}
COUNTED_INVOICES = {"paid", "open"}
COUNTED_SUBSCRIPTIONS = {"active", "past_due"}


def month_ends(span: str) -> list[datetime.date]:
    try:
        first, last = (datetime.date.fromisoformat(x.strip() + "-01") for x in span.split("..", 1))
    except ValueError:
        raise convert.fail(TOOL, f"--months takes YYYY-MM..YYYY-MM, for example 2026-04..2026-11. Got {span!r}.") from None
    out, d = [], first
    while d <= last:
        out.append(d.replace(day=calendar.monthrange(d.year, d.month)[1]))
        d = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return out


def whole_months(start: datetime.date, end: datetime.date) -> int | None:
    """Calendar months from start to end, when the span is a whole number of them (Stripe bills on the anniversary day)."""
    months = (end.year - start.year) * 12 + end.month - start.month
    return months if months > 0 and end.day == start.day else None


def from_invoices(invoices: list[Json], ends: list[datetime.date], currency: str) -> tuple[dict[tuple[str, str], float], dict[str, int]]:
    arr: dict[tuple[str, str], float] = {}
    skipped = {"not a whole number of months": 0, "a proration": 0}
    for inv in invoices:
        if inv.get("status") not in COUNTED_INVOICES:
            continue
        if str(inv.get("currency", currency)).lower() != currency:
            raise convert.fail(TOOL, f"invoice {inv.get('id')} is in {inv.get('currency')}, not {currency}. Pass --currency, or export one currency at a time.")
        lines = (inv.get("lines") or {}).get("data") or []
        for line in lines:
            parent = line.get("parent") or {}
            if parent.get("type") != "subscription_item_details":
                continue
            if (parent.get("subscription_item_details") or {}).get("proration"):
                skipped["a proration"] += 1
                continue
            span = line.get("period") or {}
            start, end = convert.day(span.get("start")), convert.day(span.get("end"))
            months = whole_months(start, end) if start and end else None
            if not months:
                skipped["not a whole number of months"] += 1
                continue
            yearly = line.get("amount", 0) / 100 * 12 / months
            for m in ends:
                if start <= m < end:
                    key = (str(inv.get("customer")), m.strftime("%Y-%m"))
                    arr[key] = arr.get(key, 0.0) + yearly
    return arr, skipped


def from_subscriptions(subs: list[Json], ends: list[datetime.date], currency: str) -> tuple[dict[tuple[str, str], float], dict[str, int]]:
    arr: dict[tuple[str, str], float] = {}
    skipped = {"a price with no unit amount": 0, "a usage-based price": 0}
    for sub in subs:
        if sub.get("status") not in COUNTED_SUBSCRIPTIONS:
            continue
        began, ended = convert.day(sub.get("start_date")), convert.day(sub.get("ended_at"))
        for item in (sub.get("items") or {}).get("data") or []:
            price = item.get("price") or {}
            recurring = price.get("recurring") or {}
            if str(price.get("currency", currency)).lower() != currency:
                raise convert.fail(TOOL, f"subscription {sub.get('id')} is in {price.get('currency')}, not {currency}.")
            if recurring.get("usage_type") == "metered":
                skipped["a usage-based price"] += 1
                continue
            if price.get("unit_amount") is None or recurring.get("interval") not in PER_YEAR:
                skipped["a price with no unit amount"] += 1
                continue
            yearly = price["unit_amount"] / 100 * (item.get("quantity") or 1) * PER_YEAR[recurring["interval"]] / (recurring.get("interval_count") or 1)
            for m in ends:
                if began and began <= m and (ended is None or m < ended):
                    key = (str(sub.get("customer")), m.strftime("%Y-%m"))
                    arr[key] = arr.get(key, 0.0) + yearly
    return arr, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw Stripe exports into the billing source.")
    given = ap.add_mutually_exclusive_group(required=True)
    given.add_argument("--invoices", nargs="+", help="invoices, with their lines, as Stripe returns them, one file per page")
    given.add_argument("--subscriptions", nargs="+", help="subscriptions, with their items, as Stripe returns them, one file per page")
    ap.add_argument("--months", required=True, help="the month ends to report, YYYY-MM..YYYY-MM, covering the prior and reporting periods")
    ap.add_argument("--currency", default="usd", help="the one currency to count (default usd)")
    ap.add_argument("--account", default="Stripe", help="the Stripe account, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    ends, currency = month_ends(args.months), args.currency.lower()
    files = args.invoices or args.subscriptions
    records = convert.pages(files, TOOL, "data")
    if args.invoices:
        arr, skipped = from_invoices(records, ends, currency)
        what = "Stripe invoices (paid and open), subscription lines annualised by whole months"
    else:
        arr, skipped = from_subscriptions(records, ends, currency)
        what = "Stripe subscriptions (active and past_due), unit amount x quantity annualised, before discounts"
    if not arr:
        raise convert.fail(TOOL, "found no recurring revenue at any of those month ends. Billing stays Unknown; no file was written.")
    rows = [{"account": a, "month": m, "arr": round(v, 2)} for (a, m), v in sorted(arr.items())]
    out = convert.write("billing", rows, f"Stripe ({args.account})", what, collect.retrieved_date(args.retrieved_at, files[0]), Path(files[0]).name, args.run)
    print(f"{TOOL}: ARR for {len({r['account'] for r in rows})} accounts at {len({r['month'] for r in rows})} month ends, written to {out}.")
    for why, n in skipped.items():
        if n:
            print(f"{TOOL}: {n} line(s) or item(s) are {why} and are left out. Nothing is estimated for them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
