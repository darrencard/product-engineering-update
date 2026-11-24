#!/usr/bin/env python3
"""Hold the version 0.6 converters to their promises: each system's own export, in its documented shape,
becomes an existing source, maps only fields that exist, and never guesses.

Usage:
  python3 -m unittest discover -s evals -v

Every fixture here is shaped like the vendor's documented response. None of these converters has run
on a live account yet.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import csv
import datetime
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_pipeline import FIXTURES, run_fixture, script  # noqa: E402  (the shared helpers, beside this file)

Json = dict[str, Any]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-src-"))
        self.run = self.work / "run"

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def save(self, name: str, data: Any) -> str:
        path = self.work / name
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return str(path)

    def rows(self, source: str) -> list[Json]:
        return json.loads((self.run / "data" / f"{source}.json").read_text(encoding="utf-8"))["rows"]

    def ok(self, name: str, *args: str) -> str:
        done = script(name, *args, "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout

    def refused(self, name: str, *args: str) -> str:
        done = script(name, *args, "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        return done.stderr


class Sentry(Base):
    def releases(self) -> str:
        def release(version: str, finished: str, env: str = "production") -> Json:
            return {
                "version": version,
                "dateCreated": finished,
                "lastDeploy": {"id": version, "environment": env, "dateStarted": None, "dateFinished": finished},
            }

        return self.save(
            "releases.json",
            [
                release("app@1", "2026-07-02T10:00:00Z"),
                release("app@2", "2026-07-09T10:00:00Z"),
                release("app@3", "2026-07-16T10:00:00Z"),
                release("app@4", "2026-07-23T10:00:00Z"),
                release("app@3-staging", "2026-07-17T10:00:00Z", "staging"),
            ],
        )

    def test_a_new_error_after_a_release_or_named_by_it_flags_that_release(self) -> None:
        issues = self.save(
            "issues.json",
            [
                {"id": "1", "level": "error", "status": "unresolved", "count": "4", "firstSeen": "2026-07-10T12:00:00Z", "lastSeen": "2026-07-11T00:00:00Z"},
                {"id": "2", "level": "warning", "count": "9", "firstSeen": "2026-07-24T12:00:00Z"},
                {"id": "3", "level": "fatal", "count": "1", "firstSeen": "2026-06-01T00:00:00Z", "firstRelease": {"version": "app@4"}},
            ],
        )
        out = self.ok("from_sentry.py", "--releases", self.releases(), "--issues", issues, "--errors-from", "2026-07-05", "--organization", "acme")
        self.assertIn("4 releases deployed to production, 3 with a known outcome", out)
        flags = {r["id"]: r["troubled"] for r in self.rows("source_control")}
        self.assertEqual(flags, {"sentry-app@1": None, "sentry-app@2": True, "sentry-app@3": False, "sentry-app@4": True})
        self.assertIn("proxy for change failure rate", out)

    def test_no_production_release_is_refused(self) -> None:
        issues = self.save("issues.json", [])
        empty = self.save("none.json", [{"version": "x", "lastDeploy": {"environment": "staging", "dateFinished": "2026-07-02T10:00:00Z"}}])
        self.assertIn(
            "found no release deployed to production",
            self.refused("from_sentry.py", "--releases", empty, "--issues", issues, "--errors-from", "2026-07-01", "--organization", "acme"),
        )


def epoch(d: datetime.date) -> int:
    return int(datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc).timestamp())


class Stripe(Base):
    def billing_rows(self) -> list[Json]:
        with (FIXTURES / "complete" / "csv" / "billing.csv").open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def invoices(self) -> str:
        """The fixture's ARR as Stripe would bill it: one paid monthly invoice per account and month, plus noise to skip."""
        data = []
        for i, r in enumerate(self.billing_rows()):
            start = datetime.date.fromisoformat(r["month"] + "-01")
            end = (start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            line = {
                "id": f"il_{i}",
                "amount": round(float(r["arr"]) * 100 / 12),
                "currency": "usd",
                "period": {"start": epoch(start), "end": epoch(end)},
                "parent": {"type": "subscription_item_details", "subscription_item_details": {"subscription": "sub_x", "proration": False}},
            }
            data.append(
                {
                    "id": f"in_{i}",
                    "object": "invoice",
                    "customer": r["account"],
                    "status": "paid",
                    "currency": "usd",
                    "lines": {"object": "list", "data": [line], "has_more": False},
                }
            )
        data.append({"id": "in_void", "customer": "A001", "status": "void", "currency": "usd", "lines": {"data": []}})
        proration = {
            "amount": 999,
            "period": {"start": epoch(datetime.date(2026, 9, 10)), "end": epoch(datetime.date(2026, 10, 1))},
            "parent": {"type": "subscription_item_details", "subscription_item_details": {"proration": True}},
        }
        data.append({"id": "in_pro", "customer": "A001", "status": "paid", "currency": "usd", "lines": {"data": [proration]}})
        return self.save("invoices.json", {"object": "list", "data": data, "has_more": False, "url": "/v1/invoices"})

    def test_invoices_reproduce_the_fixture_billing_and_its_revenue_figures(self) -> None:
        months = sorted({r["month"] for r in self.billing_rows()})
        out = self.ok("from_stripe.py", "--invoices", self.invoices(), "--months", f"{months[0]}..{months[-1]}")
        self.assertIn("1 line(s) or item(s) are a proration", out)
        rebuilt = {(r["account"], r["month"]): r["arr"] for r in self.rows("billing")}
        expected = {(r["account"], r["month"]): float(r["arr"]) for r in self.billing_rows()}
        self.assertEqual(rebuilt.keys(), expected.keys())
        for key, value in expected.items():
            self.assertAlmostEqual(rebuilt[key], value, delta=0.12, msg=str(key))
        _, from_csv = run_fixture("complete", self.work / "csv")
        run = self.work / "csv" / "complete"
        shutil.copy(self.run / "data" / "billing.json", run / "data" / "billing.json")
        self.assertEqual(script("compute_metrics.py", "--run", str(run)).returncode, 0)
        from_stripe = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        for key in ("arr", "nrr", "grr", "expansion_arr"):
            with self.subTest(metric=key):
                self.assertEqual(from_stripe["metrics"][key]["display"], from_csv["metrics"][key]["display"])

    def test_subscriptions_count_active_items_at_each_month_end_and_skip_metered(self) -> None:
        subs = [
            {
                "id": "sub_1",
                "customer": "cus_a",
                "status": "active",
                "start_date": epoch(datetime.date(2026, 7, 15)),
                "ended_at": None,
                "items": {
                    "data": [
                        {
                            "quantity": 3,
                            "price": {
                                "currency": "usd",
                                "unit_amount": 2000,
                                "recurring": {"interval": "month", "interval_count": 1, "usage_type": "licensed"},
                            },
                        },
                        {"quantity": 1, "price": {"currency": "usd", "unit_amount": None, "recurring": {"interval": "month", "usage_type": "metered"}}},
                    ]
                },
            },
            {"id": "sub_2", "customer": "cus_b", "status": "trialing", "start_date": epoch(datetime.date(2026, 7, 1)), "items": {"data": []}},
            {
                "id": "sub_3",
                "customer": "cus_c",
                "status": "active",
                "start_date": epoch(datetime.date(2026, 1, 1)),
                "items": {
                    "data": [{"quantity": 1, "price": {"currency": "usd", "unit_amount": 120000, "recurring": {"interval": "year", "interval_count": 1}}}]
                },
            },
        ]
        out = self.ok("from_stripe.py", "--subscriptions", self.save("subs.json", {"object": "list", "data": subs}), "--months", "2026-06..2026-07")
        self.assertIn("1 line(s) or item(s) are a usage-based price", out)
        self.assertEqual(
            self.rows("billing"),
            [
                {"account": "cus_a", "month": "2026-07", "arr": 720.0},
                {"account": "cus_c", "month": "2026-06", "arr": 1200.0},
                {"account": "cus_c", "month": "2026-07", "arr": 1200.0},
            ],
        )

    def test_another_currency_is_refused_not_converted(self) -> None:
        bad = {"data": [{"id": "in_1", "customer": "x", "status": "paid", "currency": "eur", "lines": {"data": []}}]}
        self.assertIn("is in eur, not usd", self.refused("from_stripe.py", "--invoices", self.save("eur.json", bad), "--months", "2026-07..2026-07"))


class AISpend(Base):
    PERIOD = "2026-Q3=2026-07-01..2026-09-30"

    def team_exports(self) -> list[str]:
        billing = self.save("billing.json", {"seat_breakdown": {"total": 40, "active_this_cycle": 38}, "plan_type": "business"})
        report = self.save(
            "report.ndjson",
            "\n".join(
                json.dumps({"day": d, "weekly_active_users": w, "loc_added_sum": 9999}) for d, w in (("2026-09-29", 31), ("2026-09-30", 33), ("2026-10-02", 50))
            ),
        )
        members = self.save(
            "members.json", {"teamMembers": [{"id": "u1", "isRemoved": False}, {"id": "u2", "isRemoved": False}, {"id": "u3", "isRemoved": True}]}
        )
        daily = self.save(
            "daily.json",
            {
                "data": [{"day": "2026-09-28", "userId": 1, "isActive": True, "totalLinesAdded": 500}, {"day": "2026-09-01", "userId": 2, "isActive": True}],
                "pagination": {"hasNextPage": False},
            },
        )
        spend = self.save(
            "spend.json", {"teamMemberSpend": [{"userId": 1, "overallSpendCents": 4000.5}, {"userId": 2, "overallSpendCents": 3999.5}], "totalMembers": 2}
        )
        return ["--copilot-billing", billing, "--copilot-report", report, "--cursor-members", members, "--cursor-daily", daily, "--cursor-spend", spend]

    def test_team_tools_become_seats_weekly_active_and_cost_and_nothing_else(self) -> None:
        out = self.ok("from_ai_spend.py", "--period", self.PERIOD, *self.team_exports(), "--copilot-seat-price", "19")
        rows = {r["tool"]: r for r in self.rows("ai_tools")}
        self.assertEqual(rows["GitHub Copilot"], {"tool": "GitHub Copilot", "period": "2026-Q3", "seats": 40.0, "weekly_active": 33.0, "cost": 2280.0})
        self.assertEqual(rows["Cursor"], {"tool": "Cursor", "period": "2026-Q3", "seats": 2.0, "weekly_active": 1.0, "cost": 80.0})
        self.assertIn("from the price you stated", out)
        written = json.dumps(self.rows("ai_tools"))
        for word in ("loc", "lines", "accept", "productiv"):
            self.assertNotIn(word, written.lower())

    def test_copilot_without_a_stated_price_writes_no_row(self) -> None:
        out = self.ok("from_ai_spend.py", "--period", self.PERIOD, *self.team_exports())
        self.assertIn("the API states no price", out)
        self.assertEqual([r["tool"] for r in self.rows("ai_tools")], ["Cursor"])

    def test_model_api_spend_goes_to_finance_lines_with_the_plan_left_to_the_person(self) -> None:
        anthropic = self.save(
            "anthropic.json",
            {
                "data": [
                    {"starting_at": "2026-07-01T00:00:00Z", "ending_at": "2026-07-02T00:00:00Z", "results": [{"amount": "123456.78", "currency": "USD"}]},
                    {"starting_at": "2026-10-01T00:00:00Z", "results": [{"amount": "99999", "currency": "USD"}]},
                ],
                "has_more": False,
            },
        )
        openai = self.save(
            "openai.json",
            {
                "object": "page",
                "data": [{"object": "bucket", "start_time": 1782864000, "end_time": 1782950400, "results": [{"amount": {"value": 12.5, "currency": "usd"}}]}],
                "has_more": False,
            },
        )
        out = self.ok("from_ai_spend.py", "--period", self.PERIOD, "--anthropic-cost", anthropic, "--openai-costs", openai)
        self.assertIn("Add each plan with the person", out)
        with (self.run / "ai_spend" / "finance.csv").open(encoding="utf-8") as f:
            lines = list(csv.DictReader(f))
        self.assertEqual(
            lines,
            [
                {"line": "Model API: Anthropic", "period": "2026-Q3", "plan": "", "actual": "1234.57"},
                {"line": "Model API: OpenAI", "period": "2026-Q3", "plan": "", "actual": "12.5"},
            ],
        )
        self.assertFalse((self.run / "data" / "ai_tools.json").exists(), "API spend has no seats, so it is never an ai_tools row")


if __name__ == "__main__":
    unittest.main()
