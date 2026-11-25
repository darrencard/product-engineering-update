"""Evals for 0.7: what changed since the last update, a reason for every moved status, the capitalisable
estimate, the projected pace to a target, and the share of changes written by an agent.

Run: python3 -m unittest discover -s evals
"""

from __future__ import annotations

import copy
import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

import draft  # noqa: E402  (on the path through test_pipeline)
import from_github  # noqa: E402
import validate  # noqa: E402
from test_pipeline import FIXTURES, rules, run_fixture, script, slide

Json = dict[str, Any]

PERIOD = {"label": "2026-Q3", "start": "2026-07-01", "end": "2026-09-30"}


def variant(work: Path, change_intake: Json | None = None, agent_marks: dict[int, str] | None = None) -> Path:
    """A copy of the complete fixture with intake fields set, and optionally an agent_authored column."""
    base = work / "fixtures"
    target = base / "complete"
    shutil.copytree(FIXTURES / "complete", target)
    if change_intake:
        path = target / "intake.json"
        intake = json.loads(path.read_text(encoding="utf-8"))
        intake.update(change_intake)
        path.write_text(json.dumps(intake), encoding="utf-8")
    if agent_marks is not None:
        path = target / "csv" / "source_control.csv"
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        prs = [r for r in rows if r["kind"] == "pull_request"]
        for i, r in enumerate(prs):
            r["agent_authored"] = agent_marks.get(i % 4, "")
        for r in rows:
            r.setdefault("agent_authored", "")
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return base


def text_of(s: Json) -> str:
    return " ".join(validate.strings([s.get("title", ""), s["blocks"]]))


def since_card(deck: Json) -> list[str] | None:
    for b in slide(deck, "01")["blocks"]:
        for item in b.get("items", []):
            if item.get("title") == "Since the last update":
                body = item["body"][0]
                return body["list"] if isinstance(body, dict) else [body]
    return None


class SinceLast(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp())
        self.deck, _ = run_fixture("complete", self.work)
        self.run = self.work / "complete"

    def tearDown(self) -> None:
        shutil.rmtree(self.work)

    def redraft(self, previous: Json, reasons: Json | None = None) -> Json:
        prev = self.work / "previous.json"
        prev.write_text(json.dumps(previous), encoding="utf-8")
        if reasons is not None:
            path = self.run / "intake.json"
            intake = json.loads(path.read_text(encoding="utf-8"))
            intake["status_reasons"] = reasons
            path.write_text(json.dumps(intake), encoding="utf-8")
        done = script("draft.py", "--run", str(self.run), "--previous", str(prev))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((self.run / "deck.json").read_text(encoding="utf-8"))

    def outcome_rows(self, deck: Json) -> list[Json]:
        card = next(b for b in slide(deck, "11")["blocks"] if b["type"] == "scorecard")
        return [r for r in card["rows"] if "metric" in r]

    def moved(self) -> tuple[Json, str]:
        """A previous deck in which the first outcome had another status and another target, and one more metric."""
        prev = copy.deepcopy(self.deck)
        row = self.outcome_rows(prev)[0]
        row["status"] = "stalled" if row["status"] != "stalled" else "landed"
        row["target"] = "1"
        card = next(b for b in slide(prev, "11")["blocks"] if b["type"] == "scorecard")
        card["rows"].append({"metric": "Retired metric", "prior": "1", "actual": "2", "target": "3", "status": "watch"})
        return prev, row["metric"]

    def test_no_previous_deck_means_no_since_card(self) -> None:
        self.assertIsNone(since_card(self.deck))

    def test_the_same_deck_twice_says_nothing_moved(self) -> None:
        deck = self.redraft(self.deck)
        self.assertEqual(since_card(deck), [draft.NO_CHANGE])
        self.assertNotIn("status-change-unexplained", rules(validate.check(deck)))

    def test_a_moved_status_with_no_reason_is_blocked(self) -> None:
        prev, name = self.moved()
        deck = self.redraft(prev)
        lines = since_card(deck)
        self.assertTrue(any(line.startswith(f"{name}: ") and draft.REASON_NEEDED in line for line in lines), lines)
        self.assertTrue(any("target moved" in line and line.startswith(name) for line in lines), lines)
        self.assertIn("Retired metric: no longer reported (was watch).", lines)
        self.assertIn("status-change-unexplained", rules(validate.check(deck)))

    def test_a_reason_clears_the_block_and_prints(self) -> None:
        prev, name = self.moved()
        deck = self.redraft(prev, {name: "The new onboarding shipped in week 2."})
        lines = since_card(deck)
        self.assertTrue(any(line.endswith("Reason: The new onboarding shipped in week 2.") for line in lines), lines)
        self.assertNotIn("status-change-unexplained", rules(validate.check(deck)))

    def test_a_metric_new_this_period_is_listed(self) -> None:
        prev = copy.deepcopy(self.deck)
        card = next(b for b in slide(prev, "11")["blocks"] if b["type"] == "scorecard")
        dropped = card["rows"].pop()
        deck = self.redraft(prev)
        self.assertTrue(any(line.startswith(f"{dropped['metric']}: newly reported") for line in since_card(deck)))

    def test_a_missing_previous_deck_is_refused_in_one_line(self) -> None:
        done = script("draft.py", "--run", str(self.run), "--previous", str(self.work / "nope.json"))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("is missing", done.stderr)


class Pace(unittest.TestCase):
    def test_met_has_no_projection(self) -> None:
        self.assertEqual(draft.pace(55, 40, 50, True, None, PERIOD), "Met")

    def test_flat_or_worse_is_not_on_pace(self) -> None:
        self.assertEqual(draft.pace(40, 40, 50, True, None, PERIOD), "Projected: not on pace")
        self.assertEqual(draft.pace(30, 20, 10, False, None, PERIOD), "Projected: not on pace")

    def test_a_projection_counts_periods_and_rounds_up(self) -> None:
        self.assertEqual(draft.pace(40, 35, 50, True, None, PERIOD), "Projected: 2 more periods")
        self.assertEqual(draft.pace(12, 16, 10, False, None, PERIOD), "Projected: 1 more period")

    def test_a_target_date_says_before_or_after(self) -> None:
        self.assertEqual(draft.pace(40, 35, 50, True, "2027-03-31", PERIOD), "Projected: 2 more periods, before 2027-03-31")
        self.assertEqual(draft.pace(40, 35, 50, True, "2026-12-31", PERIOD), "Projected: 2 more periods, after 2026-12-31")

    def test_no_prior_or_no_target_projects_nothing(self) -> None:
        self.assertEqual(draft.pace(40, None, 50, True, None, PERIOD), "No prior period to project from")
        self.assertEqual(draft.pace(40, 35, None, True, None, PERIOD), "No target")

    def test_the_pace_sits_under_the_scorecard_and_not_in_it(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            deck, _ = run_fixture("complete", work)
        finally:
            shutil.rmtree(work)
        s11 = slide(deck, "11")
        card = next(b for b in s11["blocks"] if b["type"] == "scorecard")
        self.assertEqual(card["labels"]["extra"], ["Benchmark", "Owner"])
        self.assertNotIn("Projected", json.dumps(card))
        note = next(i for b in s11["blocks"] for i in b.get("items", []) if i.get("title") == "At this pace (Projected)")
        missed = [r["metric"] for r in card["rows"] if "metric" in r and r["status"] != "landed"]
        self.assertEqual([line.split(":")[0] for line in note["body"][0]["list"]], missed)
        self.assertIn("never a result", note["body"][1])


class Capitalisable(unittest.TestCase):
    def test_the_estimate_is_computed_labelled_and_cited(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            base = variant(
                work, {"capitalisation": {"work_types": ["New capabilities", "Improve the core"], "cost_lines": ["R&D payroll"], "confirmed_by": None}}
            )
            deck, metrics = run_fixture("complete", work / "out", base)
        finally:
            shutil.rmtree(work)
        capex = metrics["extra"]["capex"]
        share = metrics["extra"]["mix_share"]
        expected = 3_700_000 * (share["New capabilities"] + share["Improve the core"]) / 100
        row = next(r for r in metrics["ledger"] if r["id"] == capex["ledger"])
        self.assertAlmostEqual(row["value"], round(expected, 4), places=2)
        s05 = slide(deck, "05")
        self.assertIn("an estimate for finance to confirm", text_of(s05))
        self.assertIn("Not yet confirmed by finance.", text_of(s05))
        self.assertIn(capex["ledger"], s05["ledger_refs"])
        self.assertNotIn("capex-not-estimate", rules(validate.check(deck)))

    def test_without_the_intake_answer_there_is_no_estimate(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            deck, metrics = run_fixture("complete", work)
        finally:
            shutil.rmtree(work)
        self.assertNotIn("capex", metrics["extra"])
        self.assertNotIn("Capitalisable", text_of(slide(deck, "05")))

    def test_a_capitalised_figure_not_called_an_estimate_is_blocked(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            deck, _ = run_fixture("complete", work)
        finally:
            shutil.rmtree(work)
        slide(deck, "05")["title"] = "We capitalised $1.2M of R&D this quarter."
        self.assertIn("capex-not-estimate", rules(validate.check(deck)))


class AgentAuthored(unittest.TestCase):
    def test_github_marks_only_what_the_person_named(self) -> None:
        pr = {"labels": [{"name": "AI-Generated"}], "author": {"login": "dana"}}
        bot = {"labels": [], "author": {"login": "claude[bot]"}}
        self.assertEqual(from_github.agent_mark(pr, set(), set()), "")
        self.assertEqual(from_github.agent_mark(pr, {"ai-generated"}, set()), "yes")
        self.assertEqual(from_github.agent_mark(bot, {"ai-generated"}, {"claude[bot]"}), "yes")
        self.assertEqual(from_github.agent_mark({"labels": [], "author": {"login": None}}, {"x"}, set()), "no")

    def test_the_share_counts_only_marked_changes_and_says_so(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            base = variant(work, agent_marks={0: "yes", 1: "no", 2: "no"})
            deck, metrics = run_fixture("complete", work / "out", base)
        finally:
            shutil.rmtree(work)
        share = metrics["metrics"]["agent_authored_share"]
        self.assertAlmostEqual(share["value"], 100 / 3, places=1)
        self.assertIn("coverage", share)
        s13 = slide(deck, "13")
        self.assertIn("written by an agent", text_of(s13))
        self.assertIn(share["ledger"], s13["ledger_refs"])
        self.assertIn("We make no claim that the team got faster.", s13["title"])
        self.assertEqual(validate.check(deck)["errors"], [])

    def test_unmarked_changes_leave_the_share_unknown(self) -> None:
        work = Path(tempfile.mkdtemp())
        try:
            deck, metrics = run_fixture("complete", work)
        finally:
            shutil.rmtree(work)
        self.assertNotIn("agent_authored_share", metrics["metrics"])
        self.assertNotIn("written by an agent", text_of(slide(deck, "13")))


if __name__ == "__main__":
    unittest.main()
