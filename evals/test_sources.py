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


class ProductAnalytics(Base):
    PERIODS = ("--period", "2026-Q2=2026-04-01..2026-06-30", "--period", "2026-Q3=2026-07-01..2026-09-30")

    def test_amplitude_segmentation_becomes_one_value_per_period(self) -> None:
        chart = self.save(
            "amp.json",
            {
                "data": {
                    "series": [[10, 20, 40, 50], [1, 1, 1, 1]],
                    "seriesLabels": ["Dispatchers", "Admins"],
                    "xValues": ["2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"],
                    "seriesCollapsed": [[{"value": 120}]],
                }
            },
        )
        refused = self.refused(
            "from_amplitude.py", "--chart", chart, "--metric", "Weekly active dispatchers", *self.PERIODS, "--aggregate", "mean", "--project", "acme"
        )
        self.assertIn("Pick one with --series", refused)
        self.ok(
            "from_amplitude.py",
            "--chart",
            chart,
            "--series",
            "Dispatchers",
            "--metric",
            "Weekly active dispatchers",
            *self.PERIODS,
            "--aggregate",
            "mean",
            "--definition",
            "Dispatchers active in a week",
            "--project",
            "acme",
        )
        self.assertEqual([(r["period"], r["value"]) for r in self.rows("analytics")], [("2026-Q2", 15.0), ("2026-Q3", 45.0)])

    def test_mixpanel_insights_and_segmentation_both_read_and_keep_other_metrics(self) -> None:
        insights = self.save(
            "mp.json",
            {
                "computed_at": "2026-10-01T00:00:00+00:00",
                "headers": ["$event"],
                "series": {"Signed up": {"2026-06-01T00:00:00-07:00": 5, "2026-07-06T00:00:00-07:00": 7, "2026-08-03T00:00:00-07:00": 8}},
            },
        )
        self.ok("from_mixpanel.py", "--chart", insights, "--metric", "Signups", *self.PERIODS, "--aggregate", "sum", "--project", "acme")
        seg = self.save(
            "seg.json", {"data": {"series": ["2026-06-02", "2026-07-02"], "values": {"Activated": {"2026-07-02": 3, "2026-06-02": 2}}}, "legend_size": 1}
        )
        self.ok("from_mixpanel.py", "--chart", seg, "--metric", "Activations", *self.PERIODS, "--aggregate", "sum", "--project", "acme")
        got = {(r["metric"], r["period"]): r["value"] for r in self.rows("analytics")}
        self.assertEqual(got, {("Signups", "2026-Q2"): 5.0, ("Signups", "2026-Q3"): 15.0, ("Activations", "2026-Q2"): 2.0, ("Activations", "2026-Q3"): 3.0})
        self.assertIn(
            "required: --aggregate",
            script("from_mixpanel.py", "--chart", seg, "--metric", "x", *self.PERIODS, "--project", "acme", "--run", str(self.run)).stderr,
        )


class CustomerSystems(Base):
    WINDOW = ("--period-start", "2026-07-01", "--period-end", "2026-09-30")

    def fixture(self, name: str) -> list[Json]:
        with (FIXTURES / "complete" / "csv" / f"{name}.csv").open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_hubspot_deals_rebuild_the_fixture_crm(self) -> None:
        results = []
        for r in self.fixture("crm"):
            won = r["outcome"] == "won"
            props = {
                "dealname": r["deal"],
                "hs_is_closed": "true",
                "hs_is_closed_won": "true" if won else "false",
                "closedate": "2026-08-15T10:00:00.000Z",
                "closed_won_reason": r["reason"] if won else None,
                "closed_lost_reason": None if won else r["reason"],
            }
            results.append({"id": r["deal"], "properties": props, "createdAt": "2026-07-01T00:00:00.000Z", "archived": False})
        results.append({"id": "OPEN", "properties": {"hs_is_closed": "false", "closedate": "2026-08-15T00:00:00Z"}})
        results.append({"id": "NOREASON", "properties": {"hs_is_closed": "true", "hs_is_closed_won": "false", "closedate": "2026-08-15T00:00:00Z"}})
        results.append(
            {"id": "OLD", "properties": {"hs_is_closed": "true", "hs_is_closed_won": "true", "closedate": "2025-01-01T00:00:00Z", "closed_won_reason": "x"}}
        )
        out = self.ok("from_hubspot.py", "--deals", self.save("deals.json", {"total": len(results), "results": results}), "--portal", "acme", *self.WINDOW)
        self.assertIn("1 closed deal(s) have no reason", out)
        self.assertEqual(self.rows("crm"), self.fixture("crm"))

    def test_salesforce_needs_the_named_reason_field(self) -> None:
        records = {
            "totalSize": 2,
            "done": True,
            "records": [
                {"attributes": {"type": "Opportunity"}, "Id": "006A", "IsClosed": True, "IsWon": False, "CloseDate": "2026-08-01", "Loss_Reason__c": "Price"},
                {"attributes": {"type": "Opportunity"}, "Id": "006B", "IsClosed": False, "IsWon": False, "CloseDate": "2026-08-01", "Loss_Reason__c": None},
            ],
        }
        path = self.save("opps.json", records)
        self.ok("from_salesforce.py", "--records", path, "--reason-field", "Loss_Reason__c", "--org", "acme", *self.WINDOW)
        self.assertEqual(self.rows("crm"), [{"deal": "006A", "outcome": "lost", "reason": "Price"}])
        self.assertIn(
            "have no Reason__c field", self.refused("from_salesforce.py", "--records", path, "--reason-field", "Reason__c", "--org", "acme", *self.WINDOW)
        )

    def test_zendesk_tickets_rebuild_the_fixture_support(self) -> None:
        tickets = [
            {"id": r["ticket"], "created_at": "2026-08-01T10:00:00Z", "tags": ["vip", f"theme_{r['theme']}"], "organization_id": r["account"] or None}
            for r in self.fixture("support")
        ]
        tickets.append({"id": "untagged", "created_at": "2026-08-01T10:00:00Z", "tags": ["vip"]})
        out = self.ok(
            "from_zendesk.py",
            "--tickets",
            self.save("tickets.json", {"tickets": tickets, "meta": {"has_more": False}}),
            "--theme-prefix",
            "theme_",
            "--subdomain",
            "acme",
            *self.WINDOW,
        )
        self.assertIn("1 ticket(s) have no theme", out)
        self.assertEqual(self.rows("support"), self.fixture("support"))

    def test_intercom_reads_named_theme_tags_and_never_picks_one(self) -> None:
        conv = {
            "type": "conversation.list",
            "conversations": [
                {
                    "id": "515",
                    "created_at": 1785600000,
                    "tags": {"type": "tag.list", "tags": [{"type": "tag", "name": "Billing"}, {"name": "vip"}]},
                    "custom_attributes": {"Account": "A001"},
                },
                {"id": "516", "created_at": 1785600000, "tags": {"tags": [{"name": "vip"}]}},
            ],
        }
        path = self.save("conv.json", conv)
        self.assertIn("does not choose a tag", self.refused("from_intercom.py", "--conversations", path, "--workspace", "acme", *self.WINDOW))
        self.ok("from_intercom.py", "--conversations", path, "--theme", "Billing", "--account-attribute", "Account", "--workspace", "acme", *self.WINDOW)
        self.assertEqual(self.rows("support"), [{"ticket": "515", "theme": "Billing", "account": "A001"}])


class Incidents(Base):
    def fixture(self) -> list[Json]:
        with (FIXTURES / "complete" / "csv" / "incidents.csv").open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def collected(self) -> list[Json]:
        done = script(
            "collect.py", "incidents", "--csv", str(FIXTURES / "complete" / "csv" / "incidents.csv"), "--system", "CSV", "--run", str(self.work / "csv")
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((self.work / "csv" / "data" / "incidents.json").read_text(encoding="utf-8"))["rows"]

    def test_pagerduty_rebuilds_the_fixture_incidents_and_time_to_restore(self) -> None:
        incidents = [
            {
                "id": f"P{r['id']}",
                "incident_number": r["id"],
                "status": "resolved",
                "urgency": "high",
                "created_at": r["started_at"] + "Z",
                "resolved_at": r["restored_at"] + "Z",
                "priority": {"type": "priority_reference", "summary": r["severity"]},
                "service": {"summary": "Dispatch API"},
            }
            for r in self.fixture()
        ]
        incidents.append(
            {
                "id": "OPEN",
                "incident_number": 9,
                "status": "triggered",
                "created_at": "2026-08-01T00:00:00Z",
                "resolved_at": None,
                "service": {"summary": "Dispatch API"},
            }
        )
        incidents.append(
            {
                "id": "NOISE",
                "incident_number": 10,
                "status": "resolved",
                "created_at": "2026-08-01T00:00:00Z",
                "resolved_at": "2026-08-01T05:00:00Z",
                "service": {"summary": "Office wifi"},
            }
        )
        out = self.ok(
            "from_pagerduty.py",
            "--incidents",
            self.save("pd.json", {"incidents": incidents, "limit": 100, "offset": 0, "more": False}),
            "--severity-from",
            "priority",
            "--service",
            "Dispatch API",
            "--account",
            "acme",
        )
        self.assertIn("1 incident(s) are not resolved", out)
        expected = [{**r, "started_at": r["started_at"] + "+00:00", "restored_at": r["restored_at"] + "+00:00"} for r in self.collected()]
        self.assertEqual(self.rows("incidents"), expected)

    def test_incidentio_uses_the_named_timestamps(self) -> None:
        def value(name: str, at: str) -> Json:
            return {"incident_timestamp": {"id": name, "name": name, "rank": 1}, "value": {"value": at}}

        data = {
            "incidents": [
                {
                    "id": "01F",
                    "reference": "INC-1",
                    "created_at": "2026-08-01T09:00:00.000000Z",
                    "severity": {"name": "Major", "rank": 2},
                    "incident_timestamp_values": [value("Impact started", "2026-08-01T08:30:00.000000Z"), value("Resolved", "2026-08-01T10:00:00.000000Z")],
                },
                {
                    "id": "01G",
                    "reference": "INC-2",
                    "created_at": "2026-08-02T09:00:00Z",
                    "incident_timestamp_values": [value("Impact started", "2026-08-02T08:00:00Z")],
                },
            ],
            "pagination_meta": {"page_size": 25},
        }
        path = self.save("inc.json", data)
        out = self.ok("from_incidentio.py", "--incidents", path, "--started", "Impact started", "--restored", "Resolved", "--organization", "acme")
        self.assertIn("1 incident(s) have no start or restore time", out)
        self.assertEqual(
            self.rows("incidents"),
            [{"id": "INC-1", "started_at": "2026-08-01T08:30:00+00:00", "restored_at": "2026-08-01T10:00:00+00:00", "severity": "Major"}],
        )
        self.assertIn(
            "Check the timestamp names",
            self.refused("from_incidentio.py", "--incidents", path, "--started", "Detected", "--restored", "Closed", "--organization", "acme"),
        )


class Documents(Base):
    def test_notion_pages_and_drive_files_list_documents_side_by_side(self) -> None:
        pages = {
            "object": "list",
            "results": [
                {
                    "object": "page",
                    "id": "b55c",
                    "url": "https://www.notion.so/Strategy-b55c",
                    "last_edited_time": "2026-11-01T09:15:00.000Z",
                    "in_trash": False,
                    "properties": {"Name": {"id": "title", "type": "title", "title": [{"type": "text", "plain_text": "Strategy 2026"}]}},
                },
                {"object": "page", "id": "x", "properties": {}, "in_trash": False},
            ],
        }
        out = self.ok("from_notion.py", "--pages", self.save("notion.json", pages), "--kind", "strategy", "--workspace", "acme")
        self.assertIn("1 page(s) have no title", out)
        files = {
            "kind": "drive#fileList",
            "files": [
                {
                    "id": "1",
                    "name": "Risk register",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "modifiedTime": "2026-10-20T12:00:00.000Z",
                    "webViewLink": "https://docs.google.com/x",
                },
                {"id": "2", "name": "Folder", "mimeType": "application/vnd.google-apps.folder"},
            ],
        }
        self.ok("from_gdrive.py", "--files", self.save("drive.json", files), "--kind", "risk register", "--drive", "acme")
        self.assertEqual(
            self.rows("docs"),
            [
                {"document": "Strategy 2026", "kind": "strategy", "updated_at": "2026-11-01T09:15:00+00:00", "location": "https://www.notion.so/Strategy-b55c"},
                {"document": "Risk register", "kind": "risk register", "updated_at": "2026-10-20T12:00:00+00:00", "location": "https://docs.google.com/x"},
            ],
        )

    def test_the_claude_drive_connector_shape_reads_the_same_as_the_api(self) -> None:
        """The live run on 24 Nov found the connector says title and viewUrl where the API says name and webViewLink."""
        files = {
            "files": [
                {
                    "id": "1",
                    "title": "Risk register",
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                    "modifiedTime": "2026-10-20T12:00:00.000Z",
                    "viewUrl": "https://docs.google.com/x",
                    "trashed": False,
                },
                {"id": "2", "title": "Old plan", "mimeType": "application/vnd.google-apps.document", "trashed": True},
                {"id": "3", "title": "A folder", "mimeType": "application/vnd.google-apps.folder"},
            ],
            "nextPageToken": "next",
        }
        self.ok("from_gdrive.py", "--files", self.save("connector.json", files), "--kind", "risk register", "--drive", "acme")
        self.assertEqual(
            self.rows("docs"),
            [{"document": "Risk register", "kind": "risk register", "updated_at": "2026-10-20T12:00:00+00:00", "location": "https://docs.google.com/x"}],
        )

    def test_a_notion_markdown_export_lists_pages_and_backs_a_quoted_proposal(self) -> None:
        folder = self.work / "export"
        folder.mkdir()
        (folder / "Strategy 1a2b.md").write_text("# Strategy\n\n## Diagnosis\n\nBuyers trust the record, not the pitch.\n", encoding="utf-8")
        self.ok("from_notion.py", "--markdown", str(folder), "--kind", "strategy", "--workspace", "acme")
        self.assertEqual(self.rows("docs"), [{"document": "Strategy", "kind": "strategy", "updated_at": None, "location": "Strategy 1a2b.md"}])
        intake = self.work / "intake.json"
        self.assertEqual(script("intake.py", "init", str(intake)).returncode, 0)
        source = f"{folder / 'Strategy 1a2b.md'}#Diagnosis"
        good = self.save(
            "good.json",
            {
                "proposals": [
                    {"field": "strategy.diagnosis", "value": "Buyers trust the record.", "source": source, "quote": "Buyers trust the record, not the pitch."}
                ]
            },
        )
        self.assertEqual(script("intake.py", "propose", str(intake), good).returncode, 0)
        bad = self.save("bad.json", {"proposals": [{"field": "strategy.diagnosis", "value": "x", "source": source, "quote": "Buyers love us."}]})
        self.assertIn("does not appear", script("intake.py", "propose", str(intake), bad).stderr)


if __name__ == "__main__":
    unittest.main()
