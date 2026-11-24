#!/usr/bin/env python3
"""Turn AI vendors' own admin exports into the ai_tools source, and model API spend into finance lines.

Usage, run once per period (the reporting period and the one before):
  python3 scripts/from_ai_spend.py --period "2026-Q4=2026-10-01..2026-12-31" \\
      --copilot-billing billing.json --copilot-report report.json --copilot-seat-price 19 \\
      --cursor-members members.json --cursor-daily daily-*.json --cursor-spend spend.json \\
      --anthropic-cost cost-*.json --openai-costs costs-*.json --run run

Inputs are what each vendor already gives you, saved as they stand:
  GitHub Copilot  GET /orgs/{org}/copilot/billing (seat_breakdown.total) and an organization usage
                  report record set (the metrics report files, with day and weekly_active_users).
                  The API states no price, so --copilot-seat-price (per seat per month, from your
                  invoice) is required for a cost; without it no Copilot row is written.
  Cursor          Admin API /teams/members (seats: members not removed), /teams/daily-usage-data
                  (weekly active: people active in the period's last 7 days) and /teams/spend
                  (cost: overallSpendCents, for the billing cycle the export covers).
  Anthropic       Admin API cost report (amount is a decimal string in cents, USD).
  OpenAI          /v1/organization/costs (amount.value in dollars).

Team tools (Copilot, Cursor) become ai_tools rows: tool, period, seats, weekly_active, cost.
Model API spend has no seats, so it is not an ai_tools row. It goes to run/ai_spend/finance.csv as
finance lines with the actual filled and the plan empty, for the person to add the plan and collect.

What is never written: lines of code, acceptance rates, requests or any other usage count presented
as productivity. The deck reports no productivity figure without a baseline and a window, and these
exports carry neither.

This script reads files and writes files. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402

TOOL = "from_ai_spend"
Json = dict[str, Any]
FINANCE_COLUMNS = ("line", "period", "plan", "actual")


def months_in(start: datetime.date, end: datetime.date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def copilot(args: argparse.Namespace, start: datetime.date, end: datetime.date) -> tuple[Json | None, str]:
    billing = convert.load_json(Path(args.copilot_billing), TOOL)
    seats = (billing.get("seat_breakdown") or {}).get("total") if isinstance(billing, dict) else None
    if seats is None:
        return None, "Copilot: the billing export has no seat_breakdown.total. No row written."
    if not args.copilot_seat_price:
        return None, "Copilot: the API states no price. Pass --copilot-seat-price from your invoice to write a cost. No row written."
    weekly = None
    if args.copilot_report:
        records = []
        for p in args.copilot_report:
            text = Path(p).read_text(encoding="utf-8")
            try:
                data = json.loads(text)
                records += data if isinstance(data, list) else [data]
            except json.JSONDecodeError:
                records += [json.loads(line) for line in text.splitlines() if line.strip()]
        dated = sorted((convert.day(r.get("day")), r) for r in records if convert.day(r.get("day")) and r.get("weekly_active_users") is not None)
        last = [r for d, r in dated if d <= end and d >= end - datetime.timedelta(days=6)]
        if last:
            weekly = last[-1]["weekly_active_users"]
    if weekly is None:
        return None, "Copilot: no usage report record with weekly_active_users in the period's last week. No row written."
    cost = float(args.copilot_seat_price) * seats * months_in(start, end)
    return {"tool": "GitHub Copilot", "seats": seats, "weekly_active": weekly, "cost": round(cost, 2)}, (
        f"Copilot: cost is {seats} seats x {args.copilot_seat_price} a month x {months_in(start, end)} months, from the price you stated."
    )


def cursor(args: argparse.Namespace, start: datetime.date, end: datetime.date) -> tuple[Json | None, str]:
    members = convert.items(convert.load_json(Path(args.cursor_members), TOOL), "teamMembers") or []
    seats = sum(1 for m in members if not m.get("isRemoved"))
    if not seats:
        return None, "Cursor: the members export lists no active members. No row written."
    week = end - datetime.timedelta(days=6)
    days = convert.pages(args.cursor_daily, TOOL, "data") if args.cursor_daily else []
    active = {d.get("userId") or d.get("email") for d in days if d.get("isActive") and convert.inside(convert.day(d.get("day") or d.get("date")), week, end)}
    if not days:
        return None, "Cursor: no daily usage export, so weekly active is unknown. No row written."
    spend = convert.load_json(Path(args.cursor_spend), TOOL) if args.cursor_spend else None
    people = convert.items(spend, "teamMemberSpend") if spend is not None else None
    if not people:
        return None, "Cursor: no spend export, so cost is unknown. No row written."
    cost = sum(float(p.get("overallSpendCents") or 0) for p in people) / 100
    return {"tool": "Cursor", "seats": seats, "weekly_active": len(active - {None}), "cost": round(cost, 2)}, (
        "Cursor: cost is overallSpendCents for the billing cycle the spend export covers; check it matches the period."
    )


def api_spend(paths: list[str], vendor: str, start: datetime.date, end: datetime.date) -> float:
    total = 0.0
    for bucket in convert.pages(paths, TOOL, "data"):
        began = convert.day(bucket.get("starting_at") or bucket.get("start_time"))
        if not convert.inside(began, start, end):
            continue
        for r in bucket.get("results") or bucket.get("result") or []:
            if vendor == "anthropic":
                if str(r.get("currency", "USD")).upper() != "USD":
                    raise convert.fail(TOOL, f"an Anthropic cost line is in {r.get('currency')}, not USD.")
                total += float(r.get("amount") or 0) / 100
            else:
                amount = r.get("amount") or {}
                if str(amount.get("currency", "usd")).lower() != "usd":
                    raise convert.fail(TOOL, f"an OpenAI cost line is in {amount.get('currency')}, not usd.")
                total += float(amount.get("value") or 0)
    return round(total, 2)


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn AI vendors' admin exports into ai_tools rows and finance lines.")
    ap.add_argument("--period", required=True, help="LABEL=YYYY-MM-DD..YYYY-MM-DD, as the intake names the period")
    ap.add_argument("--copilot-billing", help="GET /orgs/{org}/copilot/billing")
    ap.add_argument("--copilot-report", nargs="*", default=[], help="Copilot organization usage report records (JSON or NDJSON)")
    ap.add_argument("--copilot-seat-price", type=float, help="Copilot's price per seat per month, from your invoice")
    ap.add_argument("--cursor-members", help="Cursor Admin API /teams/members")
    ap.add_argument("--cursor-daily", nargs="*", default=[], help="Cursor Admin API /teams/daily-usage-data, one file per page")
    ap.add_argument("--cursor-spend", help="Cursor Admin API /teams/spend")
    ap.add_argument("--anthropic-cost", nargs="*", default=[], help="Anthropic Admin API cost report, one file per page")
    ap.add_argument("--openai-costs", nargs="*", default=[], help="OpenAI /v1/organization/costs, one file per page")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    label, start, end = convert.period(args.period, TOOL)
    rows, notes = [], []
    if args.copilot_billing:
        row, note = copilot(args, start, end)
        notes.append(note)
        if row:
            rows.append(row)
    if args.cursor_members:
        row, note = cursor(args, start, end)
        notes.append(note)
        if row:
            rows.append(row)
    finance = []
    for vendor, paths, line in (("anthropic", args.anthropic_cost, "Model API: Anthropic"), ("openai", args.openai_costs, "Model API: OpenAI")):
        if paths:
            finance.append({"line": line, "period": label, "plan": "", "actual": api_spend(paths, vendor, start, end)})
    if not rows and not finance:
        raise convert.fail(TOOL, "nothing to write: " + " ".join(notes or ["pass at least one vendor's export."]))
    first = next(x for x in (args.copilot_billing, args.cursor_members, *args.anthropic_cost, *args.openai_costs) if x)
    if rows:
        rows = [{**r, "period": label} for r in rows]
        out = Path(args.run) / "data" / "ai_tools.json"
        if out.exists():
            existing = json.loads(out.read_text(encoding="utf-8"))["rows"]
            done = {(r["tool"], r["period"]) for r in rows}
            rows = [r for r in existing if (r["tool"], r["period"]) not in done] + rows
        what = "AI tool admin exports (seats, weekly active, cost); no productivity figure"
        convert.write("ai_tools", rows, "AI tool admin exports", what, collect.retrieved_date(args.retrieved_at, first), Path(first).name, args.run)
        print(f"{TOOL}: {len(rows)} ai_tools row(s) written to {out}.")
    if finance:
        path = Path(args.run) / "ai_spend" / "finance.csv"
        convert.write_csv(path, FINANCE_COLUMNS, finance)
        print(f"{TOOL}: {len(finance)} model API spend line(s) for {label} written to {path}. Add each plan with the person, then collect it as finance.")
    for note in notes:
        print(f"{TOOL}: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
