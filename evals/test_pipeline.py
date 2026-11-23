#!/usr/bin/env python3
"""Run the skill's scripts end to end and hold them to their promises.

Usage:
  python3 -m unittest discover -s evals -v

Three groups:
  Fixtures      5 synthetic companies run through collect, compute, draft,
                validate and render, each with its expected outcome.
  Adversarial   requests that push for an overclaim. Each must be blocked.
  Safety        the security properties: escaping, link schemes, CSV
                formulas, no network code, parity with the site's renderer.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import copy
import csv
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


def run_fixture(name: str, work: Path) -> tuple[Json, Json]:
    """Collect, compute and draft one fixture. Returns (deck, metrics)."""
    fixture = FIXTURES / name
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


def rules(report: Json) -> set[str]:
    return {e["rule"] for e in report["errors"]}


def slide(deck: Json, slide_id: str) -> Json:
    return next(s for s in deck["slides"] if s["id"] == slide_id)


def block_types(s: Json) -> set[str]:
    return {b["type"] for b in validate.walk_blocks(s["blocks"]) if b.get("type")}


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
        gaps = [s for s in deck["slides"] if s["kind"] == "slide" and "data_needed" in block_types(s)]
        self.assertGreaterEqual(len(gaps), self.expect("sparse")["min_gaps"])
        for s in gaps:
            self.assertEqual(block_types(s), {"cards", "data_needed"}, f"slide {s['id']} mixes a gap with other content")
            self.assertIn("The data is missing", s["title"])
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
        self.assertIn("2 figures held because two sources disagree", json.dumps(slide(deck, "01")))

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
        self.assertIn("16 of 19 slides show data", cover)
        rows = {r["metric"]: r for r in slide(deck, "11")["blocks"][0]["rows"] if "metric" in r}
        self.assertEqual((rows["Activation"]["prior"], rows["Activation"]["actual"]), ("39%", "41%"))
        self.assertIn("data_needed", block_types(slide(deck, "12")), "slide 12 must show the AI margin gap")

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
        self.assertEqual(len(re.findall(r'<section class="slide" id="s\d', html)), 8)
        self.assertTrue((self.work / "board.ledger.csv").exists())

    def test_review_lists_changes_gaps_and_the_checklist(self) -> None:
        done = script("review.py", "--run", str(self.work / "complete"))
        self.assertEqual(done.returncode, 0, done.stderr)
        for expected in ("Computed changes", "Gaps shown as data needed", "Board cut (8 slides)", "Checklist", "explicit yes"):
            self.assertIn(expected, done.stdout)


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
