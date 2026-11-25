#!/usr/bin/env python3
"""Run the skill's scripts end to end and hold them to their promises.

Usage:
  python3 -m unittest discover -s evals -v

Groups:
  Fixtures      5 synthetic companies run through collect, compute, draft,
                validate and render, each with its expected outcome.
  Adversarial   requests that push for an overclaim. Each must be blocked.
  Definitions   each metric says what it counts, in plain words.
  Vercel        a labelled quality proxy for repositories with no reviews.
  Samples       gap slides show a tagged sample that never counts as data.
  OneCommand    run.py from the 7 required answers to a rendered deck.
  PlainTitles   drafted titles in board language, with no added cause.
  Safety        the security properties: escaping, link schemes, CSV
                formulas, no network code, parity with the site's renderer.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import re
import shutil
import subprocess  # noqa: S404  (the evals run the scripts the way a user would)
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "product-engineering-update"
SCRIPTS = SKILL / "scripts"
FIXTURES = ROOT / "evals" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import render  # noqa: E402
import validate  # noqa: E402

Json = dict[str, Any]

# Slides whose evidence is written cards, not figures.
WORD_SLIDES = {"01", "02", "09b", "15", "18"}


def script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one of the skill's scripts in isolated mode, as a user's session would."""
    return subprocess.run([sys.executable, "-I", str(SCRIPTS / name), *args], capture_output=True, text=True, check=False)  # noqa: S603


def run_fixture(name: str, work: Path, base: Path = FIXTURES) -> tuple[Json, Json]:
    """Collect, compute and draft one fixture. Returns (deck, metrics)."""
    fixture = base / name
    run = work / name
    run.mkdir(parents=True)
    shutil.copy(fixture / "intake.json", run / "intake.json")
    systems = json.loads((fixture / "systems.json").read_text(encoding="utf-8"))
    for path in sorted((fixture / "csv").glob("*.csv")):
        done = script("collect.py", path.stem, "--csv", str(path), "--system", systems[path.stem], "--retrieved-at", "2026-09-30", "--run", str(run))
        if done.returncode != 0:
            raise RuntimeError(done.stderr)
    for step in ("compute_metrics.py", "draft.py"):
        done = script(step, "--run", str(run))
        if done.returncode != 0:
            raise RuntimeError(done.stderr)
    return json.loads((run / "deck.json").read_text(encoding="utf-8")), json.loads((run / "metrics.json").read_text(encoding="utf-8"))


def render_time(stamp: str) -> dt.datetime:
    return dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")


def rules(report: Json) -> set[str]:
    return {e["rule"] for e in report["errors"]}


def slide(deck: Json, slide_id: str) -> Json:
    return next(s for s in deck["slides"] if s["id"] == slide_id)


def block_types(s: Json) -> set[str]:
    """The slide's own block types. A sample is not the slide's content, so it is left out."""
    return {b["type"] for b in validate.walk_blocks(validate.real_blocks(s["blocks"])) if b.get("type")}


class Fixtures(unittest.TestCase):
    work: Path
    decks: dict[str, Json]
    metrics: dict[str, Json]

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-evals-"))
        cls.decks, cls.metrics = {}, {}
        for fixture in sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()):
            cls.decks[fixture], cls.metrics[fixture] = run_fixture(fixture, cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def expect(self, name: str) -> Json:
        return json.loads((FIXTURES / name / "expect.json").read_text(encoding="utf-8"))

    def test_there_are_six_fixtures(self) -> None:
        self.assertEqual(sorted(self.decks), ["complete", "conflict_resolved", "conflicting", "no_ai", "single_product", "sparse"])

    def test_every_fixture_meets_its_expected_outcome(self) -> None:
        for name, deck in self.decks.items():
            with self.subTest(fixture=name):
                want = self.expect(name)
                report = validate.check(deck)
                self.assertEqual(report["ok"], want["valid"], report["errors"])
                core = [s for s in deck["slides"] if s["kind"] == "slide"]
                ids = {s["id"] for s in core}
                for absent in want["absent"]:
                    self.assertNotIn(absent, ids)
                for filled in want["filled"]:
                    has_figures = block_types(slide(deck, filled)) - {"cards", "data_needed"}
                    self.assertTrue(has_figures or filled in WORD_SLIDES, f"slide {filled} should have data")
                    self.assertNotIn("is not reported this period", slide(deck, filled)["title"])
                self.assertEqual(len([s for s in core if "B" in s["audiences"]]), want["board_slides"])
                self.assertEqual(sorted(c["metric"] for c in self.metrics[name]["conflicts"]), want["conflicts"])

    def test_every_figure_slide_cites_a_ledger_row_that_exists(self) -> None:
        for name, deck in self.decks.items():
            ledger = {r["id"] for r in deck["ledger"]}
            for s in deck["slides"]:
                for ref in validate.ledger_refs(s):
                    with self.subTest(fixture=name, slide=s["id"]):
                        self.assertIn(ref, ledger)

    def test_sparse_data_shows_gaps_and_never_prose(self) -> None:
        deck = self.decks["sparse"]
        gaps = [s for s in deck["slides"] if s["kind"] == "slide" and "is not reported this period" in s["title"]]
        self.assertGreaterEqual(len(gaps), self.expect("sparse")["min_gaps"])
        for s in gaps:
            self.assertEqual(block_types(s), {"cards", "data_needed"}, f"slide {s['id']} mixes a gap with other content")
            self.assertIn("The data is missing", s["title"])
        # The tracker alone supports the effort mix, so slide 5 shows it beside its gap for the plan (v0.8.3 rerun).
        self.assertIn("table", block_types(slide(deck, "05")))
        for row in deck["ledger"]:
            self.assertEqual(row["source_system"], "Linear")

    def test_a_single_product_line_gets_one_portfolio_row(self) -> None:
        table = next(b for b in slide(self.decks["single_product"], "04")["blocks"] if b["type"] == "table")
        self.assertEqual(len(table["rows"]), self.expect("single_product")["portfolio_rows"])
        self.assertEqual(table["rows"][0][3], "100%")

    def test_no_ai_features_removes_the_ai_slides_and_keeps_the_cuts_true(self) -> None:
        deck = self.decks["no_ai"]
        self.assertNotIn("12", deck["meta"]["cuts"]["B"])
        self.assertNotIn("eval", json.dumps(deck["ledger"]).lower())

    def test_conflicting_sources_become_a_gap_and_never_a_number(self) -> None:
        deck, metrics = self.decks["conflicting"], self.metrics["conflicting"]
        unknown = [r for r in deck["ledger"] if r["confidence"] == "Unknown"]
        self.assertEqual(len(unknown), 2)
        for row in unknown:
            self.assertIsNone(row["value"])
            self.assertIn("sources disagree", row["claim"])
        outcomes = slide(deck, "11")
        text = json.dumps(outcomes)
        self.assertIn("data_needed", text)
        self.assertIn("two sources disagree", text)
        self.assertNotIn("23.1K", text)
        self.assertNotIn("21.4K", text)
        self.assertIsNone(metrics["metrics"]["arr"]["value"])
        self.assertNotIn("ARR rose", json.dumps(slide(deck, "01")))

    def test_a_disputed_figure_appears_nowhere_as_a_number(self) -> None:
        deck = self.decks["conflicting"]
        slides = json.dumps(deck["slides"])
        for leaked in ("$10.1M", "$10.9M", "23.1K", "21.4K"):
            self.assertNotIn(leaked, slides, f"{leaked} must not appear on a slide")
        self.assertNotIn('["ARR"', json.dumps(slide(deck, "05")), "ARR is not a spend line")
        self.assertFalse(
            [r for r in deck["ledger"] if r["confidence"] != "Unknown" and r["claim"].startswith("ARR")], "no ledger row may state a disputed ARR as fact"
        )
        self.assertNotIn("ARR $", " ".join(r["claim"] for r in deck["ledger"] if "Plan and actual" in r["claim"]))
        self.assertIn("disagree, so no figure is shown", json.dumps(slide(deck, "01")))

    def test_naming_the_owning_source_settles_a_conflict_and_keeps_the_other_reading(self) -> None:
        deck, metrics = self.decks["conflict_resolved"], self.metrics["conflict_resolved"]
        self.assertEqual(metrics["conflicts"], [])
        self.assertEqual([r for r in deck["ledger"] if r["confidence"] == "Unknown"], [])
        self.assertIn("23.1K", json.dumps(slide(deck, "11")))
        claims = " ".join(r["claim"] for r in deck["ledger"])
        self.assertIn("PostHog owns this figure, named in the intake; Warehouse says 21400", claims)
        self.assertIn("Stripe owns this figure, named in the intake; Finance close says $10.1M", claims)
        self.assertEqual(validate.check(deck)["errors"], [])

    def test_a_generated_deck_holds_no_template_text_and_shows_units(self) -> None:
        deck = self.decks["complete"]
        cover = json.dumps(slide(deck, "00"))
        self.assertNotIn("Fill in each slide", cover)
        self.assertIn("18 slides show data", cover)
        rows = {r["metric"]: r for r in slide(deck, "11")["blocks"][0]["rows"] if "metric" in r}
        self.assertEqual((rows["Activation"]["prior"], rows["Activation"]["actual"]), ("39%", "41%"))
        self.assertIn("data_needed", block_types(slide(deck, "12")), "slide 12 must show the AI margin gap")

    def test_a_generated_deck_credits_the_template_with_a_safe_link(self) -> None:
        deck = self.decks["complete"]
        self.assertIn("[the Product & Engineering Update](https://www.dacard.ai/update)", deck["meta"]["footer"])
        self.assertIn('<a href="https://www.dacard.ai/update">the Product &amp; Engineering Update</a>', render.render_deck(deck))

    def test_computed_figures_are_right(self) -> None:
        m = self.metrics["complete"]["metrics"]
        self.assertEqual(m["deploys_per_week"]["display"], "4")
        self.assertEqual(m["lead_time"]["display"], "38h")
        self.assertEqual(m["time_to_restore"]["display"], "41m")
        self.assertEqual(m["review_time"]["display"], "13h")
        self.assertEqual(m["eval_pass_rate"]["display"], "86%")
        self.assertEqual(m["traced_pct"]["display"], "78%")
        mix = {r["label"]: r for r in self.metrics["complete"]["extra"]["mix"]["rows"]}
        self.assertEqual((mix["Keep the lights on"]["plan"], mix["Keep the lights on"]["actual"], mix["Keep the lights on"]["over"]), (15, 22, True))
        self.assertFalse(mix["Platform & scale"]["over"], "1 point over plan is inside the 3 point allowance")
        self.assertEqual(sum(r["actual"] for r in mix.values()), 100)

    def test_status_words_follow_the_range(self) -> None:
        rows = {r["metric"]: r["status"] for r in slide(self.decks["complete"], "09")["blocks"][0]["rows"] if "metric" in r}
        self.assertEqual(rows["Deploys per week"], "landed")
        self.assertEqual(rows["Change failure rate"], "stalled")
        self.assertEqual(rows["Time to restore"], "landed")

    def test_the_board_cut_needs_a_named_sign_off(self) -> None:
        deck_path = self.work / "complete" / "deck.json"
        out = self.work / "board.html"
        refused = script("render.py", str(deck_path), "--out", str(out), "--cut", "B")
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--signed-off-by", refused.stderr)
        self.assertFalse(out.exists())
        signed = script("render.py", str(deck_path), "--out", str(out), "--cut", "B", "--signed-off-by", "A Person")
        self.assertEqual(signed.returncode, 0, signed.stderr)
        html = out.read_text(encoding="utf-8")
        # 8 board slides, plus the gap list the board page moves to its appendix (v0.9.1)
        self.assertEqual(len(re.findall(r'<section class="slide" id="s\d', html)), 9)
        self.assertTrue((self.work / "board.ledger.csv").exists())

    def test_review_lists_changes_gaps_and_the_checklist(self) -> None:
        done = script("review.py", "--run", str(self.work / "complete"))
        self.assertEqual(done.returncode, 0, done.stderr)
        for expected in ("Computed changes", "Gaps shown as data needed", "Board cut (8 slides)", "Checklist", "explicit yes"):
            self.assertIn(expected, done.stdout)


class GitHub(unittest.TestCase):
    """The GitHub shortcut: raw exports in, the delivery slide out, with nothing retyped."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-gh-"))
        self.run = self.work / "run"
        self.run.mkdir()
        shutil.copy(FIXTURES / "complete" / "intake.json", self.run / "intake.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def exports(self, reviewed: bool) -> tuple[Path, Path]:
        """60 merged pull requests a quarter for 2 quarters, and weekly deploys, in GitHub's own shapes."""
        prs = []
        for first, lead, review in (("2026-04-0", 52, 9), ("2026-07-0", 38, 13)):
            for i in range(60):
                opened = f"{first}{(i % 9) + 1}T09:00:00Z"
                merged = (render_time(opened) + dt.timedelta(hours=lead)).strftime("%Y-%m-%dT%H:%M:%SZ")
                reviews = []
                if reviewed:
                    at = (render_time(opened) + dt.timedelta(hours=review)).strftime("%Y-%m-%dT%H:%M:%SZ")
                    reviews = [{"submittedAt": at, "state": "CHANGES_REQUESTED" if i % 6 == 0 else "APPROVED"}]
                prs.append({"number": len(prs) + 1, "createdAt": opened, "mergedAt": merged, "reviews": reviews})
        prs.append({"number": 999, "createdAt": "2026-08-01T09:00:00Z", "mergedAt": None, "reviews": []})
        deployments = [
            {"id": i, "environment": "Production" if i % 2 else "Preview", "created_at": f"2026-0{7 + (i % 3)}-1{i % 9}T12:00:00Z"} for i in range(40)
        ]
        prs_path, dep_path = self.work / "prs.json", self.work / "deployments.json"
        prs_path.write_text(json.dumps(prs), encoding="utf-8")
        half = len(deployments) // 2
        dep_path.write_text(json.dumps(deployments[:half]) + json.dumps(deployments[half:]), encoding="utf-8")  # two pages, as --paginate writes them
        return prs_path, dep_path

    def convert(self, prs: Path, deployments: Path) -> subprocess.CompletedProcess[str]:
        return script(
            "from_github.py",
            "--prs",
            str(prs),
            "--deployments",
            str(deployments),
            "--repo",
            "kestrel/app",
            "--retrieved-at",
            "2026-09-30",
            "--run",
            str(self.run),
        )

    def test_reviewed_pull_requests_fill_the_delivery_slide_with_paired_metrics(self) -> None:
        done = self.convert(*self.exports(reviewed=True))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("120 merged pull requests (120 with a review) and 20 deploys", done.stdout)
        for step in ("compute_metrics.py", "draft.py"):
            self.assertEqual(script(step, "--run", str(self.run)).returncode, 0)
        metrics = json.loads((self.run / "metrics.json").read_text(encoding="utf-8"))["metrics"]
        self.assertEqual((metrics["lead_time"]["prior_display"], metrics["lead_time"]["display"]), ("52h", "38h"))
        self.assertEqual((metrics["review_time"]["prior_display"], metrics["review_time"]["display"]), ("9h", "13h"))
        self.assertEqual(metrics["rework_rate"]["display"], "16.7%")
        self.assertNotIn("change_failure_rate", metrics, "GitHub cannot supply a change failure rate")
        deck = json.loads((self.run / "deck.json").read_text(encoding="utf-8"))
        rows = {r["metric"] for r in slide(deck, "09")["blocks"][0]["rows"] if "metric" in r}
        # Rework shows with no range set: a computed quality figure is never left off (v0.9.1)
        self.assertEqual(rows, {"Deploys per week", "Time to merge (stand-in for lead time)", "Pull request review time", "Rework rate"})
        self.assertEqual(validate.check(deck)["errors"], [])
        self.assertIn("GitHub (kestrel/app)", {r["source_system"] for r in deck["ledger"]})

    def test_a_repository_with_no_reviews_gets_a_gap_and_not_a_speed_only_slide(self) -> None:
        done = self.convert(*self.exports(reviewed=False))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Speed will be held back", done.stdout)
        for step in ("compute_metrics.py", "draft.py"):
            self.assertEqual(script(step, "--run", str(self.run)).returncode, 0)
        deck = json.loads((self.run / "deck.json").read_text(encoding="utf-8"))
        delivery = slide(deck, "09")
        self.assertEqual(block_types(delivery), {"cards", "data_needed"})
        self.assertIn("Speed was measured", json.dumps(delivery))
        # The measured lead time stays off the slide's own blocks; a sample beside the gap is made up and tagged.
        self.assertNotIn("38h", json.dumps(validate.real_blocks(delivery["blocks"])))

    def test_a_broken_export_is_refused_in_one_line(self) -> None:
        bad = self.work / "bad.json"
        bad.write_text('{"not": "a list"}', encoding="utf-8")
        done = script("from_github.py", "--prs", str(bad), "--repo", "kestrel/app", "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("Traceback", done.stderr)
        self.assertFalse((self.run / "data" / "source_control.json").exists())


class Adversarial(unittest.TestCase):
    """Each case is something a user might insist on. The deck must not render with it."""

    deck: Json

    @classmethod
    def setUpClass(cls) -> None:
        work = Path(tempfile.mkdtemp(prefix="peu-adv-"))
        cls.deck, _ = run_fixture("complete", work)
        cls.work = work

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def blocked(self, deck: Json, *expected: str) -> None:
        report = validate.check(deck)
        self.assertFalse(report["ok"])
        for rule in expected:
            self.assertIn(rule, rules(report))
        path = self.work / "adversarial.json"
        path.write_text(json.dumps(deck), encoding="utf-8")
        out = self.work / "adversarial.html"
        out.unlink(missing_ok=True)
        done = script("render.py", str(path), "--out", str(out))
        self.assertNotEqual(done.returncode, 0, "render must refuse a deck with blocking problems")
        self.assertFalse(out.exists())

    def test_the_base_deck_is_clean(self) -> None:
        self.assertEqual(validate.check(self.deck)["errors"], [])

    def test_a_productivity_headline_with_no_baseline_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "13")["title"] = "AI made engineering 40% more productive."
        self.blocked(deck, "productivity-without-baseline")

    def test_hedging_the_same_claim_does_not_get_it_through(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "13")["title"] = "Engineers are up to 40% faster with AI."
        self.blocked(deck, "productivity-without-baseline")

    def test_an_adoption_count_in_an_outcome_slot_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        card = next(b for b in slide(deck, "11")["blocks"] if b["type"] == "scorecard")
        card["rows"].append(
            {
                "metric": "AI adoption, prompts sent",
                "prior": "3,100",
                "actual": "5,000",
                "target": "4,000",
                "status": "landed",
                "extra": ["None external", "Platform"],
            }
        )
        self.blocked(deck, "adoption-as-outcome")

    def test_speed_alone_a_point_target_and_a_multiplier_are_each_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        s = slide(deck, "09")
        s["title"] = "Delivery is 10x faster."
        card = s["blocks"][0]
        card["rows"] = [r for r in card["rows"] if r.get("group") == "Speed" or r.get("metric") in ("Deploys per week", "Lead time for change")]
        next(r for r in card["rows"] if r.get("metric") == "Deploys per week")["target"] = "40"
        self.blocked(deck, "speed-without-quality", "point-target", "banned-phrase")

    def test_moving_speed_into_a_plain_table_does_not_dodge_the_pairing_rule(self) -> None:
        deck = copy.deepcopy(self.deck)
        s = slide(deck, "09")
        s["title"] = "Deploys per week rose from 3 to 4."
        s["blocks"] = [
            {
                "type": "table",
                "columns": [{"label": "Metric"}, {"label": "This period", "align": "num"}],
                "rows": [["Deploys per week", "4"], ["Lead time for change", "38h"]],
            }
        ]
        self.blocked(deck, "speed-without-quality")

    def test_a_bet_with_no_stop_rule_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        table = slide(deck, "16")["blocks"][0]
        table["rows"][0][5] = ""
        self.blocked(deck, "bet-incomplete")

    def test_replacing_a_gap_with_prose_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        s = slide(deck, "06")
        s["title"] = "Discovery went well this quarter."
        s["blocks"] = [{"type": "text", "variant": "lede", "text": "We learned a great deal from customers and will share more soon."}]
        self.blocked(deck, "missing-evidence")

    def test_a_figure_with_no_ledger_row_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        s = slide(deck, "17")
        s["ledger_refs"] = []
        self.blocked(deck, "no-ledger-row")

    def test_a_ninth_board_slide_is_blocked(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "02")["audiences"].append("B")
        deck["meta"]["cuts"]["B"] = [s["id"] for s in deck["slides"] if s["kind"] == "slide" and "B" in s["audiences"]]
        self.blocked(deck, "board-cut-too-long")

    def test_a_stale_figure_is_blocked_until_it_is_marked_stale(self) -> None:
        deck = copy.deepcopy(self.deck)
        deck["ledger"][0]["retrieved_at"] = "2026-01-15"
        self.blocked(deck, "stale-figure")
        deck["ledger"][0]["stale"] = True
        self.assertNotIn("stale-figure", rules(validate.check(deck)))

    def test_an_intake_with_a_single_point_range_cannot_reach_a_render(self) -> None:
        run = self.work / "point"
        shutil.copytree(self.work / "complete", run)
        intake = json.loads((run / "intake.json").read_text(encoding="utf-8"))
        intake["delivery_ranges"]["Deploys per week"] = "40"
        (run / "intake.json").write_text(json.dumps(intake), encoding="utf-8")
        self.assertEqual(script("draft.py", "--run", str(run)).returncode, 0)
        done = script("validate.py", str(run / "deck.json"))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("point-target", done.stdout)


class Definitions(unittest.TestCase):
    """A reader outside engineering sees what each metric counts, in plain words."""

    deck: Json
    work: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-def-"))
        cls.deck, _ = run_fixture("complete", cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def rows(self, slide_id: str) -> dict[str, Json]:
        board = next(b for b in slide(self.deck, slide_id)["blocks"] if b["type"] == "scorecard")
        return {r["metric"]: r for r in board["rows"] if "metric" in r}

    def test_every_scorecard_row_on_the_delivery_and_outcome_slides_has_a_definition(self) -> None:
        for slide_id in ("09", "11"):
            for name, row in self.rows(slide_id).items():
                with self.subTest(slide=slide_id, metric=name):
                    self.assertTrue(row.get("definition"))

    def test_the_intake_wording_wins_then_the_analytics_row_then_the_built_in_one(self) -> None:
        outcomes = self.rows("11")
        self.assertEqual(outcomes["Loads cleared per week"]["definition"], "Loads cleared with no manual touch")
        self.assertEqual(outcomes["Activation"]["definition"], "Accounts with a first automated load inside 14 days, percent")
        self.assertIn("median", self.rows("09")["Time to merge (stand-in for lead time)"]["definition"])

    def test_the_ai_figures_carry_their_definition_as_a_note(self) -> None:
        tiles = next(b for b in slide(self.deck, "12")["blocks"] if b["type"] == "tiles")
        self.assertTrue(all(t.get("note") for t in tiles["items"]))

    def test_a_definition_renders_under_the_metric_and_is_escaped(self) -> None:
        deck = copy.deepcopy(self.deck)
        board = next(b for b in slide(deck, "11")["blocks"] if b["type"] == "scorecard")
        board["rows"][0]["definition"] = 'Loads <img src=x onerror="alert(1)"> cleared'
        html = render.render_deck(deck)
        self.assertNotIn("<img", html)
        self.assertIn("Loads &lt;img src=x", html)
        self.assertIn(self.rows("09")["Time to merge (stand-in for lead time)"]["definition"], html)

    def test_an_outcome_with_no_definition_warns_and_still_renders(self) -> None:
        deck = copy.deepcopy(self.deck)
        board = next(b for b in slide(deck, "11")["blocks"] if b["type"] == "scorecard")
        board["rows"][0].pop("definition")
        report = validate.check(deck)
        self.assertTrue(report["ok"], report["errors"])
        self.assertIn("undefined-metric", {w["rule"] for w in report["warnings"]})

    def test_intake_check_lists_metrics_with_no_definition(self) -> None:
        intake = json.loads((FIXTURES / "complete" / "intake.json").read_text(encoding="utf-8"))
        intake["north_star"]["definition"] = None
        path = self.work / "intake.json"
        path.write_text(json.dumps(intake), encoding="utf-8")
        out = script("intake.py", "check", str(path)).stdout
        self.assertIn("north_star.definition", out)
        self.assertIn('inputs[0].definition ("Activation")', out)
        self.assertIn("will show the metric with no definition", out)


class Vercel(unittest.TestCase):
    """A solo repository's quality pair: Vercel's own records, labelled as a proxy, never as change failure rate."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-vc-"))
        self.run = self.work / "run"
        self.run.mkdir()
        intake = json.loads((FIXTURES / "complete" / "intake.json").read_text(encoding="utf-8"))
        intake["delivery_ranges"]["Deploys rolled back or followed by errors"] = "under 10%"
        (self.run / "intake.json").write_text(json.dumps(intake), encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def ms(self, stamp: str) -> int:
        return int(render_time(stamp).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)

    def exports(self) -> tuple[Path, Path, Path]:
        """4 production deploys in the period, one preview, one failed build; one error group, one rollback."""
        times = ["2026-07-02T10:00:00Z", "2026-07-09T10:00:00Z", "2026-07-16T10:00:00Z", "2026-07-23T10:00:00Z"]
        deployments = [{"id": f"dpl_{i}", "created": self.ms(t), "state": "READY", "target": "production"} for i, t in enumerate(times)]
        deployments += [
            {"id": "dpl_preview", "created": self.ms("2026-07-10T10:00:00Z"), "state": "READY", "target": None},
            {"id": "dpl_broken", "created": self.ms("2026-07-11T10:00:00Z"), "state": "ERROR", "target": "production"},
        ]
        dep = self.work / "deployments.json"
        dep.write_text(json.dumps({"result": {"deployments": {"pagination": {}, "deployments": deployments}}}), encoding="utf-8")
        errors = self.work / "errors.md"
        errors.write_text(
            "## Runtime Errors\n\n### [checkout] boom\ncount=3 users=1 routes=/api/x\nfirst=2026-07-10T12:00:00.000Z last=2026-07-11T12:00:00.000Z\n",
            encoding="utf-8",
        )
        rollbacks = self.work / "rollbacks.json"
        rollbacks.write_text(json.dumps([{"deploymentId": "dpl_3"}]), encoding="utf-8")
        return dep, errors, rollbacks

    def convert(self, *extra: str) -> subprocess.CompletedProcess[str]:
        dep, errors, rollbacks = self.exports()
        args = ["--deployments", str(dep), "--errors", str(errors), "--errors-from", "2026-07-05", "--rollbacks", str(rollbacks)]
        return script("from_vercel.py", *args, *extra, "--project", "kestrel-web", "--retrieved-at", "2026-09-30", "--run", str(self.run))

    def test_errors_and_rollbacks_flag_deploys_and_older_deploys_stay_unknown(self) -> None:
        done = self.convert()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("4 live production deploys, 3 with a known outcome", done.stdout)
        self.assertEqual(script("compute_metrics.py", "--run", str(self.run)).returncode, 0)
        metrics = json.loads((self.run / "metrics.json").read_text(encoding="utf-8"))
        proxy = metrics["metrics"]["troubled_deploy_rate"]
        self.assertEqual(proxy["label"], "Deploys rolled back or followed by errors")
        self.assertAlmostEqual(proxy["value"], 200 / 3, places=2)  # dpl_1 errored, dpl_3 rolled back; dpl_0 predates the error reports
        self.assertIn("stand-in for change failure rate", proxy["definition"])
        self.assertNotIn("change_failure_rate", metrics["metrics"])
        row = next(r for r in metrics["ledger"] if r["id"] == proxy["ledger"])
        self.assertIn("proxy for change failure rate", row["claim"])
        self.assertEqual(row["confidence"], "Derived")

    def test_the_proxy_pairs_with_speed_on_a_solo_repository(self) -> None:
        github = GitHub()
        github.work, github.run = self.work, self.run
        prs, deployments = github.exports(reviewed=False)
        self.assertEqual(github.convert(prs, deployments).returncode, 0)
        times = sorted(
            d["created_at"] for d in json.loads("[" + deployments.read_text(encoding="utf-8").replace("][", ",")[1:]) if d["environment"] == "Production"
        )
        vercel = [{"id": f"dpl_{i}", "created": self.ms(t), "state": "READY", "target": "production"} for i, t in enumerate(times)]
        dep = self.work / "vercel.json"
        dep.write_text(json.dumps(vercel), encoding="utf-8")
        errors = self.work / "errors.json"
        errors.write_text(json.dumps([{"first": times[2].replace("12:00", "13:00")}]), encoding="utf-8")
        done = script(
            "from_vercel.py",
            "--deployments",
            str(dep),
            "--errors",
            str(errors),
            "--errors-from",
            "2026-04-01",
            "--project",
            "kestrel-web",
            "--run",
            str(self.run),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        for step in ("compute_metrics.py", "draft.py"):
            self.assertEqual(script(step, "--run", str(self.run)).returncode, 0)
        deck = json.loads((self.run / "deck.json").read_text(encoding="utf-8"))
        delivery = slide(deck, "09")
        board = next(b for b in delivery["blocks"] if b["type"] == "scorecard")
        names = [r["metric"] for r in board["rows"] if "metric" in r]
        self.assertIn("Deploys rolled back or followed by errors", names)
        self.assertNotIn("Change failure rate", names)
        self.assertNotIn("speed-without-quality", rules(validate.check(deck)))

    def test_deployments_that_start_after_the_period_are_flagged_and_pages_merge(self) -> None:
        dep, errors, rollbacks = self.exports()
        late = self.work / "late.json"
        late.write_text(json.dumps([{"id": "dpl_9", "created": self.ms("2026-08-20T10:00:00Z"), "state": "READY", "target": "production"}]), encoding="utf-8")
        args = ["--deployments", str(late), str(dep), "--errors", str(errors), "--errors-from", "2026-07-05", "--rollbacks", str(rollbacks), str(rollbacks)]
        done = script("from_vercel.py", *args, "--project", "kestrel-web", "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("5 live production deploys", done.stdout)
        self.assertIn("WARNING the deployments supplied start on 2026-07-02, after the reporting period starts (2026-07-01)", done.stdout)
        self.assertIn("after the prior period starts (2026-03-31)", done.stdout)
        self.assertIn("WARNING the error reports start on 2026-07-05", done.stdout)

    def test_a_figure_from_part_of_the_window_says_so_on_the_figure_and_in_the_title(self) -> None:
        self.assertEqual(self.convert().returncode, 0)
        for step in ("compute_metrics.py", "draft.py"):
            self.assertEqual(script(step, "--run", str(self.run)).returncode, 0)
        metrics = json.loads((self.run / "metrics.json").read_text(encoding="utf-8"))
        cover = metrics["metrics"]["troubled_deploy_rate"]["coverage"]
        self.assertEqual(
            cover,
            {"from": "2026-07-09", "to": "2026-07-23", "counted": 3, "total": 4, "unit": "releases", "text": "Covers 9 Jul to 23 Jul 2026, 3 of 4 releases"},
        )
        row = next(r for r in metrics["ledger"] if r["id"] == metrics["metrics"]["troubled_deploy_rate"]["ledger"])
        self.assertEqual(row["coverage"], cover)
        self.assertIn("Covers 9 Jul to 23 Jul 2026, 3 of 4 releases", row["claim"])
        deck = json.loads((self.run / "deck.json").read_text(encoding="utf-8"))
        delivery = slide(deck, "09")
        board = next(b for b in delivery["blocks"] if b["type"] == "scorecard")
        proxy = next(r for r in board["rows"] if r.get("metric") == "Deploys rolled back or followed by errors")
        self.assertEqual(proxy["coverage"], cover["text"])
        self.assertIn("(covers 9 Jul to 23 Jul 2026, 3 of 4 releases)", delivery["title"])
        self.assertEqual(validate.check(deck)["errors"], [])
        html = render.render_deck(deck)
        self.assertIn(
            '66.7%<span class="t3" style="display:block;font-size:12px;line-height:1.4;margin-top:2px">Covers 9 Jul to 23 Jul 2026, 3 of 4 releases</span>',
            html,
        )

    def test_a_partial_figure_on_a_slide_that_hides_its_coverage_is_blocked(self) -> None:
        self.assertEqual(self.convert().returncode, 0)
        for step in ("compute_metrics.py", "draft.py"):
            self.assertEqual(script(step, "--run", str(self.run)).returncode, 0)
        deck = json.loads((self.run / "deck.json").read_text(encoding="utf-8"))
        delivery = slide(deck, "09")
        delivery["title"] = "Releases rose. The share of releases rolled back or followed by errors is 66.7%."
        for b in delivery["blocks"]:
            for r in b.get("rows", []):
                if isinstance(r, dict):
                    r.pop("coverage", None)
        self.assertIn("coverage-unstated", rules(validate.check(deck)))

    def test_deployments_alone_are_refused(self) -> None:
        dep, _, _ = self.exports()
        done = script("from_vercel.py", "--deployments", str(dep), "--project", "kestrel-web", "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("Deployments alone say nothing about quality", done.stderr)


class Samples(unittest.TestCase):
    """A gap slide shows a greyed sample of what it would hold. A sample never passes for data."""

    deck: Json
    work: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-smp-"))
        cls.deck, _ = run_fixture("sparse", cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def sample(self, s: Json) -> Json | None:
        return next((b for b in s["blocks"] if b["type"] == "sample"), None)

    def test_gap_slides_carry_a_tagged_sample_and_filled_slides_none(self) -> None:
        samples = json.loads((SKILL / "assets" / "samples.json").read_text(encoding="utf-8"))["slides"]
        for s in (x for x in self.deck["slides"] if x["kind"] == "slide"):
            with self.subTest(slide=s["id"]):
                gap = "is not reported this period" in s["title"]
                found = self.sample(s)
                if gap and s["id"] in samples:
                    self.assertIsNotNone(found)
                    self.assertIs(found["illustrative"], True)
                    self.assertIn("none of it is yours", found["label"])
                    self.assertNotRegex(json.dumps(found), r"\[\[L\d+\]\]")
                if not gap:
                    self.assertIsNone(found)
        self.assertEqual(validate.check(self.deck)["errors"], [])

    def test_samples_never_count_as_data(self) -> None:
        core = [s for s in self.deck["slides"] if s["kind"] == "slide"]
        filled = [s for s in core if "is not reported this period" not in s["title"]]
        self.assertIn(f"{len(filled)} of {len(core)} slides show data", json.dumps(slide(self.deck, "00")))

    def test_a_sample_that_could_pass_for_data_is_blocked(self) -> None:
        gap = next(s for s in self.deck["slides"] if s["kind"] == "slide" and self.sample(s))
        cases = {
            "sample-not-illustrative": lambda b, s: b.update(illustrative=False),
            "sample-cites-ledger": lambda b, s: b["blocks"].append({"type": "text", "variant": "note", "text": "ARR rose.[[L01]]"}),
            "sample-beside-data": lambda b, s: s.update(ledger_refs=["L01"]),
        }
        for rule, spoil in cases.items():
            with self.subTest(rule=rule):
                deck = copy.deepcopy(self.deck)
                s = slide(deck, gap["id"])
                spoil(self.sample(s), s)
                self.assertIn(rule, rules(validate.check(deck)))

    def test_the_sample_renders_greyed_tagged_and_hidden_from_screen_readers(self) -> None:
        html = render.render_deck(self.deck)
        self.assertIn('<div class="sample"', html)
        self.assertIn('aria-hidden="true" style="opacity:.45;filter:grayscale(1)', html)

    def test_the_samples_asset_is_current(self) -> None:
        sys.path.insert(0, str(ROOT / "tools"))
        import build_samples  # noqa: PLC0415  (the tool lives outside the skill)

        self.assertEqual(build_samples.build(), json.loads((SKILL / "assets" / "samples.json").read_text(encoding="utf-8")))


class OneCommand(unittest.TestCase):
    """run.py: the 7 required answers and the data in, a rendered deck out."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-run-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def required(self) -> list[str]:
        return [
            "--company", "Kestrel Labs", "--period-label", "2026-Q3", "--period-start", "2026-07-01", "--period-end", "2026-09-30",
            "--as-of", "2026-09-30", "--gap-owner", "the VP Engineering", "--gap-due", "Q4", "--no-ask",
        ]  # fmt: skip

    def test_one_command_renders_the_full_deck_and_reports_data_and_gaps(self) -> None:
        run = self.work / "run"
        csvs = [f"--csv={p.stem}={p}" for p in sorted((FIXTURES / "complete" / "csv").glob("*.csv"))]
        done = script("run.py", "--run", str(run), *self.required(), *csvs, "--retrieved-at", "2026-09-30", "--staff")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertRegex(done.stdout, r"run: \d+ of \d+ slides show data")
        self.assertIn("the board cut was not rendered", done.stdout)
        self.assertTrue((run / "update.html").exists() and (run / "staff.html").exists())
        self.assertFalse((run / "board.html").exists())

    def test_a_missing_required_answer_stops_the_run(self) -> None:
        done = script("run.py", "--run", str(self.work / "run"), "--company", "Kestrel Labs", "--no-ask")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--period-label", done.stderr)
        self.assertIn("--gap-due", done.stderr)

    def test_the_board_cut_still_needs_a_named_sign_off(self) -> None:
        done = script("run.py", "--run", str(self.work / "run"), *self.required(), "--board")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("--signed-off-by", done.stderr)
        self.assertFalse((self.work / "run" / "board.html").exists())


class PlainTitles(unittest.TestCase):
    """Drafted titles say what a number means, for a board member outside engineering."""

    deck: Json
    work: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-ttl-"))
        cls.deck, _ = run_fixture("complete", cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_drafted_titles_carry_no_engineering_shorthand(self) -> None:
        warned = [w for w in validate.check(self.deck)["warnings"] if w["rule"] == "jargon-in-title"]
        self.assertEqual(warned, [])
        self.assertIn("Basic upkeep was planned at 15%", slide(self.deck, "05")["title"])
        self.assertIn("The share of releases that caused a problem in production rose from 5.1% to 7.7%", slide(self.deck, "09")["title"])

    def test_plain_titles_add_no_cause(self) -> None:
        for s in self.deck["slides"]:
            with self.subTest(slide=s["id"]):
                self.assertNotRegex(s.get("title", ""), r"\b(because|due to|driven by|thanks to|so that)\b")

    def test_shorthand_in_a_title_warns(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "09")["title"] = "Change failure rate rose and KTLO took more capacity."
        warned = [w for w in validate.check(deck)["warnings"] if w["rule"] == "jargon-in-title"]
        self.assertEqual(len(warned), 1)
        self.assertIn("ktlo", warned[0]["message"])


class SuggestedRanges(unittest.TestCase):
    """Healthy ranges can be suggested with a named source. They are never applied without the user's yes."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-rng-"))
        self.intake = self.work / "intake.json"
        intake = json.loads((FIXTURES / "complete" / "intake.json").read_text(encoding="utf-8"))
        intake["delivery_ranges"] = {}
        self.intake.write_text(json.dumps(intake), encoding="utf-8")
        self.suggestions = self.work / "suggested.json"
        self.suggestions.write_text(
            json.dumps(
                {
                    "source": {"title": "Test benchmark", "publisher": "Test body", "published": "2024", "url": "https://example.com", "checked": "test"},
                    "ranges": {"Deploys per week": {"range": "1+", "basis": "a test cluster"}},
                    "no_suggestion": {"Lead time for change": "definitions differ"},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def intake_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        return script("intake.py", *args, "--suggestions", str(self.suggestions))

    def test_suggest_names_the_source_and_changes_nothing(self) -> None:
        before = self.intake.read_text(encoding="utf-8")
        out = self.intake_cmd("suggest", str(self.intake)).stdout
        self.assertIn('Deploys per week: "1+"  (a test cluster; Test benchmark (Test body, 2024))', out)
        self.assertIn("no source Lead time for change: definitions differ", out)
        self.assertIn("Never accept one for them", out)
        self.assertEqual(self.intake.read_text(encoding="utf-8"), before)

    def test_accept_records_the_suggestion_the_choice_and_the_source(self) -> None:
        self.assertEqual(self.intake_cmd("accept", str(self.intake), "Deploys per week", "--range", "2+").returncode, 0)
        intake = json.loads(self.intake.read_text(encoding="utf-8"))
        self.assertEqual(intake["delivery_ranges"]["Deploys per week"], "2+")
        self.assertEqual(
            intake["range_sources"]["Deploys per week"],
            {"suggested": "1+", "accepted": "2+", "edited": True, "source": "Test benchmark (Test body, 2024)"},
        )

    def test_a_metric_with_no_suggestion_needs_the_users_own_range(self) -> None:
        done = self.intake_cmd("accept", str(self.intake), "Rework rate")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("Ask the user for one", done.stderr)

    def test_the_delivery_slide_names_where_an_accepted_range_came_from(self) -> None:
        intake = json.loads((FIXTURES / "complete" / "intake.json").read_text(encoding="utf-8"))
        intake["range_sources"] = {"Deploys per week": {"suggested": "3+", "accepted": "3+", "edited": False, "source": "Test benchmark (Test body, 2024)"}}
        fixture = self.work / "fixture"
        shutil.copytree(FIXTURES / "complete", fixture)
        (fixture / "intake.json").write_text(json.dumps(intake), encoding="utf-8")
        deck, _ = run_fixture("fixture", self.work / "out", base=self.work)
        self.assertIn("Healthy ranges for Deploys per week accepted from Test benchmark (Test body, 2024).", slide(deck, "09")["asof"])

    def test_the_shipped_suggestions_name_their_source(self) -> None:
        shipped = json.loads((SKILL / "assets" / "suggested_ranges.json").read_text(encoding="utf-8"))
        for field in ("title", "publisher", "published", "url", "checked"):
            self.assertTrue(shipped["source"].get(field), field)
        for metric, s in shipped["ranges"].items():
            with self.subTest(metric=metric):
                self.assertTrue(s["range"] and s["basis"])
                self.assertIsNotNone(validate.RANGE.search(s["range"]), "a suggestion must be a range, never a single point")


class Converters(unittest.TestCase):
    """Linear and PostHog exports, in their own shapes, become the same rows a CSV would."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-cv-"))
        self.run = self.work / "run"
        self.run.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def csv_rows(self, source: str) -> list[Json]:
        done = script("collect.py", source, "--csv", str(FIXTURES / "complete" / "csv" / f"{source}.csv"), "--system", "CSV", "--run", str(self.work / "csv"))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((self.work / "csv" / "data" / f"{source}.json").read_text(encoding="utf-8"))["rows"]

    def linear_pages(self) -> list[Path]:
        """The fixture's tracker rows as Linear's connector returns them, in 2 pages, plus 2 issues to leave out."""
        with (FIXTURES / "complete" / "csv" / "tracker.csv").open(encoding="utf-8") as f:
            issues = [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "estimate": float(r["estimate"]),
                    "completedAt": r["completed_at"],
                    "status": r["status"],
                    "statusType": "completed",
                    "labels": [f"type: {r['work_type']}", f"objective: {r['objective']}"] if r["objective"] else [f"type: {r['work_type']}"],
                    "project": r["product_line"] or None,
                    "assignee": r["owner"] or None,
                }
                for r in csv.DictReader(f)
            ]
        issues.append({"id": "X-1", "title": "No estimate", "estimate": None, "completedAt": "2026-08-01", "statusType": "completed", "labels": []})
        issues.append({"id": "X-2", "title": "Canceled", "estimate": 3, "completedAt": None, "statusType": "canceled", "labels": []})
        half = len(issues) // 2
        pages = []
        for i, chunk in enumerate((issues[:half], issues[half:])):
            path = self.work / f"linear-{i}.json"
            path.write_text(json.dumps({"issues": chunk, "hasNextPage": i == 0, "cursor": "c"}), encoding="utf-8")
            pages.append(path)
        return pages

    def test_linear_issues_become_the_same_tracker_rows_as_the_csv(self) -> None:
        done = script(
            "from_linear.py",
            "--issues",
            *map(str, self.linear_pages()),
            "--work-type-prefix",
            "type:",
            "--objective-prefix",
            "objective:",
            "--run",
            str(self.run),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("1 completed issue(s) have no estimate and are left out", done.stdout)
        rows = json.loads((self.run / "data" / "tracker.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual(rows, self.csv_rows("tracker"))

    def test_an_issue_with_no_work_type_label_is_counted_as_unlabelled(self) -> None:
        page = self.work / "one.json"
        page.write_text(
            json.dumps(
                {
                    "data": {
                        "issues": {
                            "nodes": [
                                {
                                    "identifier": "A-1",
                                    "title": "t",
                                    "estimate": 2,
                                    "completedAt": "2026-08-01",
                                    "state": {"name": "Done", "type": "completed"},
                                    "labels": {"nodes": []},
                                }
                            ]
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        done = script("from_linear.py", "--issues", str(page), "--work-type-prefix", "type:", "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = json.loads((self.run / "data" / "tracker.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual(rows[0]["work_type"], "Unlabelled")

    def test_no_completed_issues_is_refused_and_writes_nothing(self) -> None:
        page = self.work / "empty.json"
        page.write_text(json.dumps({"issues": [], "hasNextPage": False}), encoding="utf-8")
        done = script("from_linear.py", "--issues", str(page), "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((self.run / "data" / "tracker.json").exists())

    def test_a_posthog_query_result_becomes_the_same_analytics_rows_as_the_csv(self) -> None:
        with (FIXTURES / "complete" / "csv" / "analytics.csv").open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        result = {
            "columns": ["metric", "period", "value", "definition"],
            "results": [[r["metric"], r["period"], float(r["value"]), r["definition"]] for r in rows],
            "types": [],
        }
        path = self.work / "query.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        done = script("from_posthog.py", "--query", str(path), "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads((self.run / "data" / "analytics.json").read_text(encoding="utf-8"))["rows"], self.csv_rows("analytics"))

    def test_a_posthog_trend_is_aggregated_per_period_as_told(self) -> None:
        days = [f"2026-0{m}-{d:02d}" for m in (4, 7) for d in (1, 2, 3)]
        trend = {"result": [{"label": "dispatchers", "days": days, "data": [10, 20, 30, 40, 50, 60]}]}
        path = self.work / "trend.json"
        path.write_text(json.dumps(trend), encoding="utf-8")
        periods = ["--period", "2026-Q2=2026-04-01..2026-06-30", "--period", "2026-Q3=2026-07-01..2026-09-30"]
        done = script(
            "from_posthog.py", "--insight", str(path), "--metric", "Weekly active dispatchers", *periods, "--aggregate", "mean", "--run", str(self.run)
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = json.loads((self.run / "data" / "analytics.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual([(r["period"], r["value"]) for r in rows], [("2026-Q2", 20.0), ("2026-Q3", 50.0)])
        refused = script("from_posthog.py", "--insight", str(path), "--metric", "x", *periods, "--run", str(self.run))
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("does not choose them", refused.stderr)


class Imports(unittest.TestCase):
    """intake.py import reads the team's own decision log, risk register and stop list, by named columns only."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-imp-"))
        self.intake = self.work / "intake.json"
        self.assertEqual(script("intake.py", "init", str(self.intake)).returncode, 0)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def write(self, name: str, text: str) -> str:
        path = self.work / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_markdown_and_csv_tables_import_and_are_listed_for_confirmation(self) -> None:
        decisions = self.write(
            "decisions.md",
            "# Decision log\n\nSome notes.\n\n| Ask | Options | Recommendation | Deadline | Notes |\n|---|---|---|---|---|\n"
            "| Approve a pilot | Pilot, or wait | Pilot with 10 customers | 2026-12-01 | x |\n| Hire a designer | Now \\| later | |  | |\n",
        )
        risks = self.write("risks.csv", "Risk,Likelihood,Impact,Mitigation,Due\nOne model provider,Medium,High,Add a second,2026-12-31\n")
        stopped = self.write("stop.md", "| What | Why |\n|---|---|\n| Carrier marketplace | It did not serve the strategy |\n")
        done = script("intake.py", "import", str(self.intake), "--decisions", decisions, "--risks", risks, "--stopped", stopped)
        self.assertEqual(done.returncode, 0, done.stderr)
        intake = json.loads(self.intake.read_text(encoding="utf-8"))
        self.assertEqual(intake["decisions"][1], {"ask": "Hire a designer", "options": "Now | later", "recommendation": None, "deadline": None})
        self.assertEqual(intake["risks"][0]["mitigation"], "Add a second")
        self.assertEqual(intake["stopped"], [{"what": "Carrier marketplace", "why": "It did not serve the strategy"}])
        self.assertIn("imported  2 decisions from decisions.md:", done.stdout)
        self.assertIn("recommendation: not stated", done.stdout)
        self.assertIn("confirm each imported row with the user", done.stdout)

    def test_a_document_without_the_named_columns_is_refused_and_nothing_is_written(self) -> None:
        before = self.intake.read_text(encoding="utf-8")
        risks = self.write("risks.md", "| Risk | Owner |\n|---|---|\n| Provider | Platform |\n")
        done = script("intake.py", "import", str(self.intake), "--risks", risks)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("has no table with the columns risk, likelihood, impact, mitigation, due", done.stderr)
        self.assertEqual(self.intake.read_text(encoding="utf-8"), before)

    def test_a_row_with_no_item_is_refused(self) -> None:
        stopped = self.write("stop.csv", "what,why\n,No reason\n")
        done = script("intake.py", "import", str(self.intake), "--stopped", stopped)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("rows with no what", done.stderr)

    def test_answers_already_in_the_intake_are_only_replaced_when_asked(self) -> None:
        stopped = self.write("stop.csv", "what,why\nA,B\n")
        self.assertEqual(script("intake.py", "import", str(self.intake), "--stopped", stopped).returncode, 0)
        again = script("intake.py", "import", str(self.intake), "--stopped", stopped)
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("--replace", again.stderr)
        self.assertEqual(script("intake.py", "import", str(self.intake), "--stopped", stopped, "--replace").returncode, 0)


class Proposals(unittest.TestCase):
    """Answers drafted from the team's documents are held apart, carry a source and a quote, and count only once confirmed."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-prop-"))
        self.intake = self.work / "intake.json"
        self.assertEqual(script("intake.py", "init", str(self.intake)).returncode, 0)
        self.doc = self.work / "strategy.md"
        self.doc.write_text(
            "# Strategy\n\n## Diagnosis\n\nBuilding software got cheap.\nJudgment did not.\n\n## Risks\n\nOne model provider carries most spend.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def drafted(self, proposals: list[Json]) -> str:
        path = self.work / "drafted.json"
        path.write_text(json.dumps({"proposals": proposals}), encoding="utf-8")
        return str(path)

    def good(self) -> list[Json]:
        return [
            {
                "field": "strategy.diagnosis",
                "value": "Building software got cheap; judgment did not.",
                "source": f"{self.doc}#Diagnosis",
                "quote": "Building software got cheap. Judgment did not.",
            },
            {
                "field": "risks",
                "value": [{"risk": "One model provider", "likelihood": None, "impact": None, "mitigation": None, "due": None}],
                "source": f"{self.doc}#Risks",
                "quote": "One model provider carries most spend.",
            },
        ]

    def test_proposals_are_held_apart_and_listed_by_check(self) -> None:
        before = self.intake.read_text(encoding="utf-8")
        done = script("intake.py", "propose", str(self.intake), self.drafted(self.good()))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.intake.read_text(encoding="utf-8"), before, "a proposal is never an answer")
        self.assertTrue((self.work / "proposals.json").exists())
        out = script("intake.py", "check", str(self.intake)).stdout
        self.assertIn("proposed  strategy.diagnosis", out)
        self.assertIn("unknown   strategy.diagnosis", out, "an unconfirmed proposal leaves the field Unknown, so draft ignores it")

    def test_confirm_applies_the_named_fields_with_who_and_where(self) -> None:
        script("intake.py", "propose", str(self.intake), self.drafted(self.good()))
        done = script("intake.py", "confirm", str(self.intake), "--by", "Darren Card", "--field", "strategy.diagnosis")
        self.assertEqual(done.returncode, 0, done.stderr)
        intake = json.loads(self.intake.read_text(encoding="utf-8"))
        self.assertEqual(intake["strategy"]["diagnosis"], "Building software got cheap; judgment did not.")
        self.assertEqual(intake["provenance"]["strategy.diagnosis"]["confirmed_by"], "Darren Card")
        self.assertEqual(
            intake["provenance"]["strategy.diagnosis"]["evidence"],
            [{"source": f"{self.doc}#Diagnosis", "quote": "Building software got cheap. Judgment did not."}],
        )
        self.assertEqual(intake["risks"], [], "a proposal not named stays pending")
        self.assertIn("proposed  risks", script("intake.py", "check", str(self.intake)).stdout)

    def test_confirm_can_apply_an_edit_and_needs_a_name(self) -> None:
        script("intake.py", "propose", str(self.intake), self.drafted(self.good()))
        self.assertNotEqual(script("intake.py", "confirm", str(self.intake)).returncode, 0)
        done = script("intake.py", "confirm", str(self.intake), "--by", "Darren Card", "--edit", "strategy.diagnosis=Judgment is the scarce part.")
        self.assertEqual(done.returncode, 0, done.stderr)
        intake = json.loads(self.intake.read_text(encoding="utf-8"))
        self.assertEqual(intake["strategy"]["diagnosis"], "Judgment is the scarce part.")
        self.assertTrue(intake["provenance"]["strategy.diagnosis"]["edited"])

    def test_a_value_drawn_from_several_places_names_each_and_each_quote_is_checked(self) -> None:
        both = [
            {
                "field": "strategy.non_goals",
                "value": ["A", "B"],
                "evidence": [{"source": f"{self.doc}#Diagnosis", "quote": "Judgment did not."}, {"source": f"{self.doc}#Risks", "quote": "One model provider"}],
            }
        ]
        self.assertEqual(script("intake.py", "propose", str(self.intake), self.drafted(both)).returncode, 0)
        both[0]["evidence"][1]["quote"] = "Not in the file."
        done = script("intake.py", "propose", str(self.intake), self.drafted(both))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("does not appear", done.stderr)

    def test_a_proposal_without_source_or_quote_or_with_a_made_up_quote_is_refused(self) -> None:
        for spoil, why in (
            ({"source": ""}, "has no source"),
            ({"quote": ""}, "has no quote"),
            ({"quote": "Our moat is the data."}, "does not appear in strategy.md"),
            ({"field": "vibes"}, "names no intake field"),
        ):
            with self.subTest(why=why):
                bad = self.good()
                bad[0].update(spoil)
                done = script("intake.py", "propose", str(self.intake), self.drafted(bad))
                self.assertNotEqual(done.returncode, 0)
                self.assertIn(why, done.stderr)
                self.assertFalse((self.work / "proposals.json").exists(), "a refused file stores nothing")


class Action(unittest.TestCase):
    """The GitHub Action: the team's intake and data in, the Leadership and Staff cuts out, never the Board cut."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-ci-"))
        self.data = self.work / ".update"
        shutil.copytree(FIXTURES / "complete" / "csv", self.data)
        shutil.copy(FIXTURES / "complete" / "intake.json", self.data / "intake.json")

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def ci(self, *extra: str) -> subprocess.CompletedProcess[str]:
        args = ["--intake", str(self.data / "intake.json"), "--data-dir", str(self.data), "--retrieved-at", "2026-09-30", "--out", str(self.work / "out")]
        return script("ci.py", *args, *extra)

    def test_the_run_writes_leadership_and_staff_only_and_leaves_the_intake_alone(self) -> None:
        before = (self.data / "intake.json").read_text(encoding="utf-8")
        done = self.ci()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        out = self.work / "out"
        self.assertEqual(
            sorted(p.name for p in out.iterdir()), ["SUMMARY.txt", "deck.json", "leadership.html", "leadership.ledger.csv", "staff.html", "staff.ledger.csv"]
        )
        self.assertNotIn('data-aud="B"', (out / "leadership.html").read_text(encoding="utf-8").split("<main>")[1].split('class="slide')[0])
        self.assertEqual((self.data / "intake.json").read_text(encoding="utf-8"), before, "the job never writes an answer back")
        self.assertIn("The Board cut is not rendered here", (out / "SUMMARY.txt").read_text(encoding="utf-8"))

    def test_an_intake_missing_a_required_answer_stops_the_job(self) -> None:
        intake = json.loads((self.data / "intake.json").read_text(encoding="utf-8"))
        intake["gap_owner"] = None
        (self.data / "intake.json").write_text(json.dumps(intake), encoding="utf-8")
        done = self.ci()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("A scheduled job does not fill answers", done.stderr)
        self.assertFalse((self.work / "out").exists())

    def test_a_repository_with_nothing_merged_still_gets_a_deck(self) -> None:
        empty = self.work / "prs.json"
        empty.write_text("[]", encoding="utf-8")
        done = self.ci("--prs", str(empty), "--deployments", str(empty), "--repo", "acme/app")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("delivery shows as a gap", done.stdout)

    def test_the_action_and_its_example_never_ask_for_the_board_cut(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        example = (ROOT / "examples" / "product-engineering-update.yml").read_text(encoding="utf-8")
        for text in (action, example):
            self.assertNotRegex(text, r"--board|signed-off-by|--cut B")
        self.assertIn("scripts/ci.py", action)
        self.assertIn("workflow_dispatch", example)
        self.assertRegex(example, r"schedule:\s*\n\s*- cron:")

    def test_the_workflow_is_least_privilege_pinned_and_never_runs_on_pull_requests(self) -> None:
        action = (ROOT / "action.yml").read_text(encoding="utf-8")
        example = (ROOT / "examples" / "product-engineering-update.yml").read_text(encoding="utf-8")
        self.assertNotRegex(example, r"\bpull_request(_target)?\b\s*:")
        self.assertRegex(example, r"\npermissions:\n  contents: read\n")
        self.assertEqual(example.count("contents: write"), 1, "only the publish job may write")
        for text in (action, example):
            for ref in re.findall(r"uses:\s*(\S+)", text):
                with self.subTest(uses=ref):
                    if ref.startswith("darrencard/product-engineering-update@"):
                        self.assertRegex(ref, r"@v\d+\.\d+\.\d+$", "this action is pinned to a release tag, never main")
                    else:
                        self.assertRegex(ref, r"@[0-9a-f]{40}$", "a third-party action is pinned to a full commit SHA")
            self.assertNotIn("github.event", text, "no event text, such as a pull request title, reaches a shell")
        self.assertIn("--json number,createdAt,mergedAt,reviews", action)


class TrackerReaders(unittest.TestCase):
    """Jira and GitHub Projects exports, in their documented shapes, become the same tracker rows as the CSV."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-tr-"))
        self.run = self.work / "run"
        with (FIXTURES / "complete" / "csv" / "tracker.csv").open(encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def csv_rows(self) -> list[Json]:
        done = script("collect.py", "tracker", "--csv", str(FIXTURES / "complete" / "csv" / "tracker.csv"), "--system", "CSV", "--run", str(self.work / "csv"))
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads((self.work / "csv" / "data" / "tracker.json").read_text(encoding="utf-8"))["rows"]

    def written(self) -> list[Json]:
        return json.loads((self.run / "data" / "tracker.json").read_text(encoding="utf-8"))["rows"]

    def test_jira_search_pages_become_the_same_rows(self) -> None:
        issues = [
            {
                "key": r["id"],
                "fields": {
                    "summary": r["title"],
                    "issuetype": {"name": "Story"},
                    "status": {"name": r["status"], "statusCategory": {"key": "done"}},
                    "resolutiondate": f"{r['completed_at']}T10:00:00.000+0000",
                    "customfield_10016": float(r["estimate"]),
                    "labels": [f"type:{r['work_type']}"] + ([f"objective:{r['objective']}"] if r["objective"] else []),
                    "components": [{"name": r["product_line"]}] if r["product_line"] else [],
                    "assignee": {"displayName": r["owner"]} if r["owner"] else None,
                },
            }
            for r in self.rows
        ]
        issues.append({"key": "X-1", "fields": {"summary": "open", "status": {"name": "To Do", "statusCategory": {"key": "new"}}}})
        issues.append(
            {
                "key": "X-2",
                "fields": {
                    "summary": "no points",
                    "status": {"name": "Done", "statusCategory": {"key": "done"}},
                    "resolutiondate": "2026-08-01T10:00:00.000+0000",
                },
            }
        )
        half = len(issues) // 2
        pages = []
        for i, chunk in enumerate((issues[:half], issues[half:])):
            path = self.work / f"jira-{i}.json"
            path.write_text(json.dumps({"startAt": i * half, "total": len(issues), "issues": chunk}), encoding="utf-8")
            pages.append(str(path))
        args = ["--search", *pages, "--estimate-field", "customfield_10016", "--work-type-from", "label", "--work-type-prefix", "type:"]
        done = script("from_jira.py", *args, "--product-line-from", "component", "--objective-prefix", "objective:", "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("1 done issue(s) have no estimate", done.stdout)
        self.assertEqual(self.written(), self.csv_rows())

    def test_jira_csv_export_with_repeated_columns_and_epic_commitments(self) -> None:
        path = self.work / "jira.csv"
        path.write_text(
            "Issue key,Summary,Issue Type,Status,Resolved,Story Points,Labels,Labels,Component/s,Assignee,Due date\n"
            "A-1,Fix login,Bug,Done,14/Oct/26 9:30 AM,3,team-a,objective:Grow,Web,Ana,\n"
            "A-2,Billing epic,Epic,Done,20/Oct/26 2:00 PM,8,,,Web,Ben,31/Oct/26\n"
            "A-3,Search epic,Epic,In Progress,,5,,,Web,Cy,15/Nov/26\n",
            encoding="utf-8",
        )
        args = ["--csv", str(path), "--estimate-field", "Story Points", "--work-type-from", "issuetype", "--work-type", "Bug=Keep the lights on"]
        done = script(
            "from_jira.py",
            *args,
            "--objective-prefix",
            "objective:",
            "--commitments-from",
            "epics",
            "--period-start",
            "2026-10-01",
            "--period-end",
            "2026-11-23",
            "--run",
            str(self.run),
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = {r["id"]: r for r in self.written()}
        self.assertEqual(rows["A-1"]["work_type"], "Keep the lights on")
        self.assertEqual(rows["A-1"]["objective"], "Grow")
        self.assertEqual(rows["A-1"]["completed_at"], "2026-10-14T00:00:00")
        with (self.run / "jira" / "commitments.csv").open(encoding="utf-8") as f:
            found = {r["commitment"]: r for r in csv.DictReader(f)}
        self.assertEqual(found["Billing epic"]["shipped"], "yes")
        self.assertEqual(found["Search epic"]["shipped"], "no")
        self.assertEqual(found["Search epic"]["metric"], "", "Jira holds no target metric; the person fills it")

    def test_jira_refuses_a_csv_without_the_estimate_column(self) -> None:
        path = self.work / "bad.csv"
        path.write_text("Issue key,Status,Resolved\nA-1,Done,2026-10-01\n", encoding="utf-8")
        done = script("from_jira.py", "--csv", str(path), "--estimate-field", "Story Points", "--work-type-from", "issuetype", "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("'Story Points'", done.stderr)

    def test_github_project_items_become_the_same_rows(self) -> None:
        items, closed = [], []
        for r in self.rows:
            url = f"https://github.com/acme/app/issues/{r['id']}"
            item = {
                "id": r["id"],
                "title": r["title"],
                "status": "Done",
                "labels": [],
                "content": {"type": "Issue", "url": url, "title": r["title"]},
                "estimate": float(r["estimate"]),
                "type": r["work_type"],
            }
            if r["product_line"]:
                item["productline"] = r["product_line"]
            if r["objective"]:
                item["objective"] = r["objective"]
            if r["owner"]:
                item["assignees"] = [r["owner"]]
            items.append(item)
            closed.append({"url": url, "closedAt": f"{r['completed_at']}T00:00:00Z"})
        items.append({"id": "open", "title": "open", "status": "In Progress", "content": {"url": "u"}})
        (self.work / "items.json").write_text(json.dumps({"items": items, "totalCount": len(items)}), encoding="utf-8")
        (self.work / "closed.json").write_text(json.dumps(closed), encoding="utf-8")
        args = [
            "--items",
            str(self.work / "items.json"),
            "--closed",
            str(self.work / "closed.json"),
            "--estimate-field",
            "Estimate",
            "--work-type-field",
            "Type",
        ]
        done = script("from_github_projects.py", *args, "--product-line-field", "Product Line", "--objective-field", "Objective", "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        expected = [{**r, "id": f"https://github.com/acme/app/issues/{r['id']}"} for r in self.csv_rows()]
        self.assertEqual(self.written(), expected)

    def test_github_projects_needs_a_completion_date_and_a_work_type_source(self) -> None:
        (self.work / "items.json").write_text(
            json.dumps({"items": [{"id": "1", "title": "t", "status": "Done", "estimate": 2, "content": {"url": "u"}}]}), encoding="utf-8"
        )
        nowhere = script("from_github_projects.py", "--items", str(self.work / "items.json"), "--estimate-field", "estimate", "--run", str(self.run))
        self.assertIn("--work-type-field or --work-type-prefix", nowhere.stderr)
        undated = script(
            "from_github_projects.py",
            "--items",
            str(self.work / "items.json"),
            "--estimate-field",
            "estimate",
            "--work-type-prefix",
            "type:",
            "--run",
            str(self.run),
        )
        self.assertNotEqual(undated.returncode, 0)
        self.assertIn("1 done item(s) have no completion date", undated.stdout)


class Safety(unittest.TestCase):
    def example(self) -> Json:
        return json.loads((ROOT / "examples" / "harborline.deck.json").read_text(encoding="utf-8"))

    def test_the_python_renderer_matches_the_site_renderer_byte_for_byte(self) -> None:
        self.assertEqual(render.render_deck(self.example()), (ROOT / "examples" / "harborline.html").read_text(encoding="utf-8"))

    def test_the_example_and_the_blank_deck_are_valid(self) -> None:
        self.assertEqual(validate.check(self.example())["errors"], [])
        blank = json.loads((SKILL / "assets" / "blank.deck.json").read_text(encoding="utf-8"))
        self.assertEqual(validate.check(blank)["errors"], [])

    def test_markup_in_data_is_escaped(self) -> None:
        deck = self.example()
        deck["meta"]["company"] = "<script>alert(1)</script>"
        deck["slides"][1]["title"] = 'Revenue <img src=x onerror="alert(1)"> rose'
        deck["ledger"][0]["claim"] = "</td><script>alert(2)</script>"
        html = render.render_deck(deck)
        scripts = re.findall(r"<script\b", html)
        self.assertEqual(len(scripts), 1, "only the template's own script may appear")
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img src=x onerror=", html)

    def test_only_web_and_mail_links_are_allowed(self) -> None:
        for href in ("javascript:alert(1)", "data:text/html,<script>alert(1)</script>", "//evil.example", "vbscript:x"):
            with self.subTest(href=href):
                deck = self.example()
                deck["slides"][1]["blocks"].append(
                    {"type": "cards", "columns": 1, "items": [{"title": "Link", "body": [{"cta": {"label": "Open", "href": href}}]}]}
                )
                self.assertIn("unsafe-link", rules(validate.check(deck)))
                with self.assertRaises(SystemExit):
                    render.render_deck(deck)
        deck = self.example()
        deck["slides"][1]["dig_deeper"] = ["[bad](javascript:alert(1))"]
        self.assertIn("unsafe-link", rules(validate.check(deck)))
        with self.assertRaises(SystemExit):
            render.render_deck(deck)

    def test_the_ledger_csv_neutralises_spreadsheet_formulas(self) -> None:
        deck = self.example()
        deck["ledger"][0]["claim"] = '=HYPERLINK("http://evil.example","click")'
        deck["ledger"][1]["source_system"] = "@SUM(1+1)"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.csv"
            render.write_ledger_csv(deck, path)
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertTrue(rows[0]["claim"].startswith("'="))
        self.assertTrue(rows[1]["source_system"].startswith("'@"))

    def test_placeholders_cannot_ship_in_a_real_deck(self) -> None:
        deck = json.loads((SKILL / "assets" / "blank.deck.json").read_text(encoding="utf-8"))
        deck["meta"]["company"] = "Kestrel Labs"
        self.assertIn("placeholder-left", rules(validate.check(deck)))

    def test_the_scripts_hold_no_network_or_code_execution(self) -> None:
        banned = re.compile(
            r"^\s*(import|from)\s+(socket|urllib|http|requests|ftplib|smtplib|subprocess|pickle|marshal|ctypes)\b|\b(eval|exec|__import__)\(|os\.system|os\.popen",
            re.M,
        )
        for path in sorted(SCRIPTS.glob("*.py")):
            with self.subTest(script=path.name):
                self.assertIsNone(banned.search(path.read_text(encoding="utf-8")))

    def test_a_rendered_deck_prints_one_slide_per_page_with_no_navigation(self) -> None:
        html = render.render_deck(self.example())
        printed = html[html.index("@media print{") :]
        printed = printed[: printed.index("\n}\n")]
        self.assertIn("@page{size:A4 landscape", html)
        self.assertIn(".rail,.bar,.guide,#g{display:none!important}", printed)
        self.assertIn("break-after:page", printed)
        self.assertIn("print-color-adjust:exact", printed)
        self.assertNotIn("subprocess", (SKILL / "scripts" / "render.py").read_text(encoding="utf-8"))

    def test_the_rendered_file_makes_no_network_calls(self) -> None:
        html = render.render_deck(self.example())
        self.assertIsNone(re.search(r"<link\b|<script[^>]+src=|<img\b|<iframe\b|@import|url\((?!data:)", html))
        script_body = html[html.rindex("<script>") :]
        self.assertIsNone(re.search(r"fetch\(|XMLHttpRequest|sendBeacon|WebSocket|localStorage|document\.cookie", script_body))

    def test_collect_rejects_bad_input_without_inventing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "billing.csv"
            bad.write_text("account,month\nA1,2026-09\n", encoding="utf-8")
            done = script("collect.py", "billing", "--csv", str(bad), "--system", "Stripe", "--run", tmp)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn("arr", done.stderr)
            self.assertFalse((Path(tmp) / "data" / "billing.json").exists())
            wrong = Path(tmp) / "billing2.csv"
            wrong.write_text("account,month,arr\nA1,2026-09,lots\n", encoding="utf-8")
            done = script("collect.py", "billing", "--csv", str(wrong), "--system", "Stripe", "--run", tmp)
            self.assertNotEqual(done.returncode, 0)
            self.assertNotIn("Traceback", done.stderr)

    def test_skill_metadata_meets_the_spec(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        front = text.split("---")[1]
        name = re.search(r"^name: (.+)$", front, re.M).group(1)
        description = re.search(r"^description: (.+)$", front, re.M).group(1)
        self.assertEqual(name, SKILL.name, "the name must match the folder")
        self.assertRegex(name, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(name), 64)
        self.assertLessEqual(len(description), 1024)
        self.assertNotRegex(name, r"anthropic|claude")
        self.assertLess(len(text.splitlines()), 500)
        for link in re.findall(r"\]\((references/[^)]+)\)", text):
            self.assertTrue((SKILL / link).exists(), link)


if __name__ == "__main__":
    unittest.main()
