#!/usr/bin/env python3
"""Hold version 0.4's additions to their promises: did merged work land?

Usage:
  python3 -m unittest discover -s evals -v

Groups:
  ShippedVsImpact  slide 8 drafted from commitments, grouped by outcome, with no claim of cause.
  Commitments      intake.py import --commitments and --targets, refused whole when malformed.
  LinearProjects   from_linear.py on projects, updates, initiatives and customer requests.
  CustomerSignal   slides 6 and 7 from customer requests, counted in code and linked.
  LandingBrief     the landing-brief skill: parsing, refusals and the status rule.
  WriteBack        summary.py: a postable summary, and no board cut without a named sign-off.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import copy
import csv
import itertools
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "skills" / "product-engineering-update" / "scripts"
BRIEF_SKILL = ROOT / "skills" / "landing-brief"
for folder in (HERE, SCRIPTS, BRIEF_SKILL / "scripts"):
    sys.path.insert(0, str(folder))

import draft  # noqa: E402
import landing_brief  # noqa: E402
import validate  # noqa: E402
from test_pipeline import SKILL, rules, run_fixture, script, slide  # noqa: E402  (the shared helpers, beside this file)

Json = dict[str, Any]

TEMPLATE = (BRIEF_SKILL / "assets" / "project-template.md").read_text(encoding="utf-8")


def table_of(s: Json) -> Json:
    return next(b for b in s["blocks"] if b["type"] == "table")


def grouped(table: Json) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    group = ""
    for r in table["rows"]:
        if isinstance(r, dict):
            group = r["group"]
            out[group] = []
        else:
            out[group].append(r)
    return out


class ShippedVsImpact(unittest.TestCase):
    work: Path
    decks: dict[str, Json]

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-s8-"))
        cls.decks = {name: run_fixture(name, cls.work)[0] for name in ("complete", "conflicting", "no_ai", "sparse")}

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_the_title_counts_shipped_and_moved_as_the_spec_asks(self) -> None:
        s = slide(self.decks["complete"], "08")
        self.assertEqual(s["title"], "We shipped 6 of 7 commitments. 4 have moved their target metric so far.")
        self.assertEqual(validate.check(self.decks["complete"])["errors"], [])

    def test_rows_are_grouped_by_outcome_with_no_movement_last(self) -> None:
        groups = grouped(table_of(slide(self.decks["complete"], "08")))
        self.assertEqual(list(groups)[-1], "No movement")
        self.assertEqual(groups["Activation"][0], ["Guided activation", "Activation team", "Yes", "39% to 41%", "Moved"])
        self.assertEqual(groups["Activation"][1][-1], "Not shipped")
        # Lower is better for cost, so a fall is the right way; a rise in failures is the wrong way.
        self.assertEqual(groups["Cost per successful task"][0][-2:], ["$0.41 to $0.33", "Moved"])
        self.assertEqual(groups["Change failure rate"][0][-1], "Moved the wrong way")
        self.assertEqual(groups["No movement"][0][3:], ["No target metric named", "No movement: no metric was named before launch"])

    def test_the_slide_says_moved_is_not_proof_of_cause_and_cites_the_metrics_used(self) -> None:
        s = slide(self.decks["complete"], "08")
        self.assertIn("It is not proof that the commitment caused it.", json.dumps(s))
        self.assertNotRegex(s["title"], r"\b(because|caused|thanks to|drove)\b")
        ledger = {r["id"]: r for r in self.decks["complete"]["ledger"]}
        claims = " ".join(ledger[ref]["claim"] for ref in s["ledger_refs"])
        for metric in ("Activation", "Loads cleared per week", "Weekly active dispatchers", "Change failure rate"):
            self.assertIn(metric, claims)

    def test_a_disputed_or_missing_metric_goes_under_no_movement_with_the_reason(self) -> None:
        clash = grouped(table_of(slide(self.decks["conflicting"], "08")))["No movement"]
        self.assertIn(["Multi-stop reroutes", "Agent team", "Yes", "Loads cleared per week: two sources disagree"], [r[:4] for r in clash])
        none = grouped(table_of(slide(self.decks["no_ai"], "08")))["No movement"]
        self.assertIn("Cost per successful task: not collected", [r[3] for r in none])
        self.assertEqual(slide(self.decks["no_ai"], "08")["title"], "We shipped 6 of 7 commitments. 3 have moved their target metric so far.")
        for name in ("conflicting", "no_ai"):
            self.assertEqual(validate.check(self.decks[name])["errors"], [], name)

    def test_with_no_commitments_the_slide_is_a_gap_with_its_sample(self) -> None:
        s = slide(self.decks["sparse"], "08")
        self.assertIn("is not reported this period", s["title"])
        sample = next(b for b in s["blocks"] if b["type"] == "sample")
        self.assertIs(sample["illustrative"], True)
        self.assertNotRegex(json.dumps(sample), r"\[\[L\d+\]\]")
        self.assertEqual(validate.check(self.decks["sparse"])["errors"], [])

    def test_a_metric_built_from_part_of_the_window_says_so_in_the_title_and_cell(self) -> None:
        run = self.work / "complete"
        metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
        coverage = {"from": "2026-08-02", "to": "2026-09-30", "counted": 60, "total": 92, "unit": "days", "text": "Covers 2 Aug to 30 Sep 2026, 60 of 92 days"}
        metrics["metrics"]["analytics:Activation"]["coverage"] = coverage
        lid = metrics["metrics"]["analytics:Activation"]["ledger"]
        next(r for r in metrics["ledger"] if r["id"] == lid)["coverage"] = coverage
        (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
        deck = draft.Draft(run).build()
        s = slide(deck, "08")
        self.assertIn("Activation covers 2 Aug to 30 Sep 2026, 60 of 92 days.", s["title"])
        self.assertIn("39% to 41% (covers 2 Aug", json.dumps(s))
        self.assertEqual(validate.check(deck)["errors"], [])
        hidden = copy.deepcopy(deck)
        slide(hidden, "08")["title"] = "We shipped 6 of 7 commitments."
        table_of(slide(hidden, "08"))["rows"] = [
            r if isinstance(r, dict) else [*r[:3], r[3].split(" (")[0], r[4]] for r in table_of(slide(hidden, "08"))["rows"]
        ]
        self.assertIn("coverage-unstated", rules(validate.check(hidden)))

    def test_the_sample_for_slide_8_is_current_and_tagged(self) -> None:
        samples = json.loads((SKILL / "assets" / "samples.json").read_text(encoding="utf-8"))["slides"]
        self.assertIn("08", samples)
        self.assertEqual(samples["08"][0]["text"], "We shipped 6 of 7 commitments. 4 have moved their target metric so far.")


class Commitments(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-cm-"))
        self.intake = self.work / "intake.json"
        self.assertEqual(script("intake.py", "init", str(self.intake)).returncode, 0)

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def write(self, name: str, text: str) -> str:
        path = self.work / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_commitments_import_from_csv_or_markdown_and_shipped_is_normalised(self) -> None:
        md = self.write(
            "c.md",
            "| Commitment | Shipped | Metric | Owner | Source |\n|---|---|---|---|---|\n"
            "| Guided activation | YES | Activation | Ana | Linear |\n| Audit log | no | | Ben | Linear |\n",
        )
        done = script("intake.py", "import", str(self.intake), "--commitments", md)
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = json.loads(self.intake.read_text(encoding="utf-8"))["commitments"]
        self.assertEqual(rows[0], {"commitment": "Guided activation", "shipped": "yes", "metric": "Activation", "owner": "Ana", "source": "Linear"})
        self.assertEqual((rows[1]["shipped"], rows[1]["metric"]), ("no", None))
        self.assertIn("imported  2 commitments", done.stdout)

    def test_a_malformed_commitments_file_is_refused_whole(self) -> None:
        before = self.intake.read_text(encoding="utf-8")
        bad = self.write("c.csv", "commitment,shipped,metric,owner,source\nA,yes,Activation,x,y\nB,mostly,Activation,x,y\n")
        done = script("intake.py", "import", str(self.intake), "--commitments", bad, "--stopped", self.write("s.csv", "what,why\nX,Y\n"))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("shipped 'mostly'; write yes or no", done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertEqual(self.intake.read_text(encoding="utf-8"), before)
        missing = self.write("m.csv", "commitment,shipped\nA,yes\n")
        done = script("intake.py", "import", str(self.intake), "--commitments", missing)
        self.assertIn("has no table with the columns commitment, shipped, metric, owner, source", done.stderr)

    def test_check_lists_slide_8_and_blocks_a_bad_hand_written_commitment(self) -> None:
        done = script("intake.py", "check", str(self.intake))
        self.assertIn("unknown   commitments  (slide 8 will show data needed)", done.stdout)
        intake = json.loads(self.intake.read_text(encoding="utf-8"))
        intake["commitments"] = [{"commitment": "A", "shipped": True, "metric": None}]
        self.intake.write_text(json.dumps(intake), encoding="utf-8")
        self.assertIn('BLOCKING  commitment 1 ("A") has shipped True; write yes or no', script("intake.py", "check", str(self.intake)).stdout)

    def test_targets_import_into_the_inputs_and_bad_ones_are_refused(self) -> None:
        good = self.write("t.csv", "metric,target,better,by,owner,source\nActivation,50%,higher,2026-12-31,Ana,Linear project Guided activation\n")
        done = script("intake.py", "import", str(self.intake), "--targets", good)
        self.assertEqual(done.returncode, 0, done.stderr)
        inputs = json.loads(self.intake.read_text(encoding="utf-8"))["inputs"]
        self.assertEqual(
            {k: inputs[0][k] for k in ("metric", "target", "unit", "target_display", "higher_is_better")},
            {"metric": "Activation", "target": 50.0, "unit": "%", "target_display": "50%", "higher_is_better": True},
        )
        again = script("intake.py", "import", str(self.intake), "--targets", good)
        self.assertIn("already holds Activation. Pass --replace", again.stderr)
        before = self.intake.read_text(encoding="utf-8")
        for text, why in (
            ("metric,target,better,by,owner,source\nX,about half,higher,,a,b\n", "is not one number"),
            ("metric,target,better,by,owner,source\nX,50%,up,,a,b\n", "write higher or lower"),
            ("metric,target,better,by,owner,source\nX,50%,higher,,a,b\nX,60%,higher,,a,c\n", "has two targets"),
        ):
            with self.subTest(why=why):
                done = script("intake.py", "import", str(self.intake), "--targets", self.write("bad.csv", text))
                self.assertNotEqual(done.returncode, 0)
                self.assertIn(why, done.stderr)
                self.assertEqual(self.intake.read_text(encoding="utf-8"), before)


def project(name: str, **fields: Any) -> Json:
    return {"id": name.lower().replace(" ", "-"), "name": name, "url": f"https://linear.app/acme/project/{name.lower().replace(' ', '-')}", **fields}


class LinearProjects(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="peu-lp-"))
        self.run = self.work / "run"

    def tearDown(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)

    def save(self, name: str, data: Any) -> str:
        path = self.work / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def read_csv(self, name: str) -> list[Json]:
        with (self.run / "linear" / name).open(encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def projects(self) -> str:
        """The connector's list_projects shape, with one project of each kind."""
        broken = TEMPLATE.replace("- **Bar:** 50%\n", "")
        return self.save(
            "projects.json",
            {
                "projects": [
                    project(
                        "Guided activation",
                        status={"name": "Completed", "type": "completed"},
                        completedAt="2026-11-02T10:00:00Z",
                        targetDate="2026-11-15",
                        lead={"name": "Ana"},
                        description="Intro.\n\n" + TEMPLATE,
                    ),
                    project("Audit log", status="Completed", completedAt="2026-10-20", lead="Ben", description="No brief here."),
                    project("Carrier rating", status={"type": "started"}, targetDate="2026-12-01", lead={"name": "Cy"}, description=broken),
                    project("Old work", status={"type": "completed"}, completedAt="2026-06-01"),
                    project("Next year", status={"type": "planned"}, targetDate="2027-03-01"),
                    project('=HYPERLINK("http://evil.example")', status={"type": "completed"}, completedAt="2026-10-05"),
                ],
                "hasNextPage": False,
            },
        )

    def convert(self, *extra: str) -> Any:
        return script(
            "from_linear.py", "--projects", self.projects(), "--period-start", "2026-10-01", "--period-end", "2026-12-31", "--run", str(self.run), *extra
        )

    def test_projects_become_commitments_and_only_a_brief_gives_a_metric(self) -> None:
        updates = self.save(
            "updates.json",
            {
                "statusUpdates": [
                    {"project": {"name": "Guided activation"}, "createdAt": "2026-11-10T00:00:00Z", "health": "onTrack", "body": "We think it worked."},
                    {"project": {"name": "Guided activation"}, "createdAt": "2026-10-10T00:00:00Z", "health": "atRisk", "body": "Early."},
                ]
            },
        )
        done = self.convert("--project-updates", updates)
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = {r["commitment"]: r for r in self.read_csv("commitments.csv")}
        self.assertEqual(sorted(rows), ['\'=HYPERLINK("http://evil.example")', "Audit log", "Carrier rating", "Guided activation"])
        self.assertEqual((rows["Guided activation"]["shipped"], rows["Guided activation"]["metric"]), ("yes", "Activation"))
        self.assertEqual(rows["Guided activation"]["latest update"], "2026-11-10, onTrack")
        self.assertEqual((rows["Audit log"]["shipped"], rows["Audit log"]["metric"]), ("yes", ""))
        self.assertEqual((rows["Carrier rating"]["shipped"], rows["Carrier rating"]["metric"]), ("no", ""))
        self.assertIn("landing brief is incomplete (bar is missing or empty.)", done.stdout)
        self.assertEqual(
            self.read_csv("targets.csv"),
            [{"metric": "Activation", "target": "50%", "better": "higher", "by": "2026-12-31", "owner": "Ana", "source": "Linear project Guided activation"}],
        )
        self.assertFalse((self.run / "intake.json").exists(), "the converter never writes the intake")

    def test_the_converted_files_import_and_draft_slide_8_and_slide_11(self) -> None:
        self.assertEqual(self.convert().returncode, 0)
        deck, _ = run_fixture("complete", self.work)
        run = self.work / "complete"
        intake = run / "intake.json"
        data = json.loads(intake.read_text(encoding="utf-8"))
        data["commitments"], data["inputs"] = [], [i for i in data["inputs"] if i["metric"] != "Activation"]
        intake.write_text(json.dumps(data), encoding="utf-8")
        done = script(
            "intake.py",
            "import",
            str(intake),
            "--commitments",
            str(self.run / "linear" / "commitments.csv"),
            "--targets",
            str(self.run / "linear" / "targets.csv"),
            "--replace",
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(script("draft.py", "--run", str(run)).returncode, 0)
        deck = json.loads((run / "deck.json").read_text(encoding="utf-8"))
        self.assertEqual(slide(deck, "08")["title"], "We shipped 3 of 4 commitments. 1 has moved their target metric so far.")
        outcomes = json.dumps(slide(deck, "11"))
        self.assertIn('"metric": "Activation"', outcomes)
        self.assertIn('"target": "50%"', outcomes)
        self.assertEqual(validate.check(deck)["errors"], [])

    def test_no_project_in_the_period_is_refused_and_writes_nothing(self) -> None:
        path = self.save("none.json", {"projects": [project("Next year", status={"type": "planned"}, targetDate="2027-03-01")]})
        done = script("from_linear.py", "--projects", path, "--period-start", "2026-10-01", "--period-end", "2026-12-31", "--run", str(self.run))
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse((self.run / "linear" / "commitments.csv").exists())
        self.assertIn("--period-start needs a date", script("from_linear.py", "--projects", path, "--run", str(self.run)).stderr)
        self.assertIn(
            "holds no list of projects",
            script(
                "from_linear.py",
                "--projects",
                self.save("bad.json", {"projects": "x"}),
                "--period-start",
                "2026-10-01",
                "--period-end",
                "2026-12-31",
                "--run",
                str(self.run),
            ).stderr,
        )

    def test_a_projects_csv_reads_by_column_name_and_a_wrong_one_is_refused(self) -> None:
        path = self.work / "projects.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Name", "Status", "Target date", "Completed", "Lead", "Description"])
            w.writerow(["Guided activation", "Completed", "2026-11-15", "2026-11-02", "Ana", TEMPLATE])
            w.writerow(["Carrier rating", "In Progress", "2026-12-01", "", "Cy", ""])
        args = ("--period-start", "2026-10-01", "--period-end", "2026-12-31", "--run", str(self.run))
        done = script("from_linear.py", "--projects", str(path), *args)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            [(r["commitment"], r["shipped"], r["metric"]) for r in self.read_csv("commitments.csv")],
            [("Guided activation", "yes", "Activation"), ("Carrier rating", "no", "")],
        )
        bad = self.work / "bad.csv"
        bad.write_text("Project,State\nA,Done\n", encoding="utf-8")
        done = script("from_linear.py", "--projects", str(bad), *args)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("has no name and status columns", done.stderr)

    def test_initiatives_give_issues_an_objective_only_when_there_is_one(self) -> None:
        initiatives = self.save(
            "initiatives.json",
            {
                "data": {
                    "initiatives": {
                        "nodes": [
                            {"name": "Grow ARR", "owner": {"name": "CEO"}, "projects": {"nodes": [{"name": "Dispatch"}, {"name": "Shared"}]}},
                            {"name": "Cut cost", "owner": {"name": "CFO"}, "projects": {"nodes": [{"name": "Shared"}]}},
                        ]
                    }
                }
            },
        )
        issues = self.save(
            "issues.json",
            {
                "issues": [
                    {"id": "A-1", "title": "a", "estimate": 2, "completedAt": "2026-11-01", "statusType": "completed", "labels": [], "project": "Dispatch"},
                    {"id": "A-2", "title": "b", "estimate": 3, "completedAt": "2026-11-01", "statusType": "completed", "labels": [], "project": "Shared"},
                    {
                        "id": "A-3",
                        "title": "c",
                        "estimate": 1,
                        "completedAt": "2026-11-01",
                        "statusType": "completed",
                        "labels": ["objective: Win"],
                        "project": "Shared",
                    },
                ]
            },
        )
        done = script("from_linear.py", "--issues", issues, "--initiatives", initiatives, "--objective-prefix", "objective:", "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = {r["id"]: r["objective"] for r in json.loads((self.run / "data" / "tracker.json").read_text(encoding="utf-8"))["rows"]}
        self.assertEqual(rows, {"A-1": "Grow ARR", "A-2": None, "A-3": "Win"})
        listed = self.read_csv("initiatives.csv")
        self.assertEqual(listed[0], {"initiative": "Grow ARR", "owner": "CEO", "projects": "Dispatch; Shared", "cause": "", "confidence": ""})
        self.assertIn("Linear holds no cause or confidence", done.stdout)

    def test_customer_requests_keep_their_link_and_unlinked_ones_are_counted(self) -> None:
        needs = self.save(
            "needs.json",
            {
                "customerNeeds": [
                    {
                        "id": "N1",
                        "customer": {"name": "Northwind"},
                        "createdAt": "2026-11-01T00:00:00Z",
                        "issue": {"identifier": "ACM-1", "title": "Bulk import", "url": "https://linear.app/acme/issue/ACM-1"},
                    },
                    {"id": "N2", "customer": {"name": "Haulwell"}, "createdAt": "2026-11-02", "project": {"name": "Reroutes", "url": "javascript:alert(1)"}},
                    {"id": "N3", "customer": {"name": "Haulwell"}, "createdAt": "2026-11-03"},
                ]
            },
        )
        done = script("from_linear.py", "--customer-needs", needs, "--run", str(self.run))
        self.assertEqual(done.returncode, 0, done.stderr)
        rows = json.loads((self.run / "data" / "customer_requests.json").read_text(encoding="utf-8"))["rows"]
        self.assertEqual([(r["linked_to"], r["link"]) for r in rows], [("ACM-1 Bulk import", "https://linear.app/acme/issue/ACM-1"), ("Reroutes", None)])
        self.assertIn("1 request(s) are linked to no issue or project and are left out", done.stdout)
        empty = self.save("empty.json", {"customerNeeds": [{"id": "N3", "customer": "x", "createdAt": "2026-11-03"}]})
        shutil.rmtree(self.run)
        self.assertNotEqual(script("from_linear.py", "--customer-needs", empty, "--run", str(self.run)).returncode, 0)
        self.assertFalse((self.run / "data" / "customer_requests.json").exists())


class CustomerSignal(unittest.TestCase):
    deck: Json
    work: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-cs-"))
        cls.deck, _ = run_fixture("complete", cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_slide_6_counts_requests_in_the_period_and_links_each_item(self) -> None:
        s = slide(self.deck, "06")
        self.assertEqual(
            s["title"],
            "4 customers made 7 requests this period, linked to 3 issues and projects. "
            "The most requested is Multi-stop reroutes, with 4 requests from 3 customers.",
        )
        rows = table_of(s)["rows"]
        self.assertEqual(rows[0], ["[Multi-stop reroutes](https://linear.app/kestrel/project/multi-stop-reroutes)", "4", "3"])
        self.assertEqual(rows[2], ["KES-388 Carrier rating export", "1", "1"], "the request from before the period is not counted")
        self.assertIn("They are not a tested result", json.dumps(s))

    def test_slide_7_adds_requests_beside_deals_and_tickets(self) -> None:
        s = slide(self.deck, "07")
        self.assertIn({"value": "4 of 7", "label": "Customer requests linked to: Multi-stop reroutes"}, s["blocks"][0]["items"])
        self.assertIn("Linear", s["asof"])
        self.assertEqual(validate.check(self.deck)["errors"], [])


def brief(**changes: str | None) -> str:
    """The template with parts changed (a value) or removed (None)."""
    text = TEMPLATE
    for key, value in changes.items():
        label = key.replace("_", " ").capitalize() if key != "line" else "The line"
        pattern = re.compile(rf"^- \*\*{re.escape(label)}:\*\* .*\n", re.M | re.I)
        self_line = f"- **{label}:** {value}\n" if value is not None else ""
        text = pattern.sub(lambda _m, s=self_line: s, text)
    return text


class LandingBrief(unittest.TestCase):
    def test_the_template_parses_into_its_five_parts(self) -> None:
        b = landing_brief.parse(TEMPLATE)
        self.assertEqual((b.metric, b.bar, b.unit, b.higher_is_better, b.by), ("Activation", 50.0, "%", True, "2026-12-31"))
        self.assertEqual((b.tokens_per_task, b.price_per_token), (12000.0, 0.000003))
        self.assertEqual(b.line, "model call")
        self.assertTrue(b.problem and b.non_goals and b.decides)

    def test_a_malformed_brief_is_refused_with_every_problem_named(self) -> None:
        cases = {
            "bar is missing or empty": brief(bar=None),
            'bar "about half" is not one number': brief(bar="about half"),
            'better is "up"': brief(better="up"),
            'by is "end of Q4"': brief(by="end of Q4"),
            'Start it with "fixed code" or "model call"': brief(line="a bit of both"),
            "is none, but the line is a model call": brief(tokens_per_task="none"),
            "is not one of the brief's parts": TEMPLATE + "- **Mood:** good\n",
            "is given twice": TEMPLATE + "- **Metric:** Revenue\n",
            'there is no "Landing brief" heading': "Just a description.",
            'there are 2 "Landing brief" headings': TEMPLATE + "\n" + TEMPLATE,
        }
        for why, text in cases.items():
            with self.subTest(why=why), self.assertRaises(landing_brief.BriefError) as caught:
                landing_brief.parse(text)
            self.assertIn(why, str(caught.exception))
        both = str(self.catch(brief(bar=None, metric=None)))
        self.assertIn("metric is missing", both)
        self.assertIn("bar is missing", both)

    def catch(self, text: str) -> Exception:
        try:
            landing_brief.parse(text)
        except landing_brief.BriefError as e:
            return e
        raise AssertionError("not refused")

    def test_fixed_code_may_have_no_token_budget_and_the_section_ends_at_the_next_heading(self) -> None:
        text = brief(line="fixed code. Rules only.", tokens_per_task="none", price_per_token="none")  # noqa: S106  (a budget, not a secret) + "\n## Notes\n\nAnything goes here.\n"
        b = landing_brief.parse("# Project\n\n" + text)
        self.assertEqual((b.line, b.line_note, b.tokens_per_task), ("fixed code", "Rules only.", None))

    def test_the_status_rule_is_the_update_skills_rule(self) -> None:
        values = (None, 0.0, 40.0, 50.0, 60.0)
        for value, prior, target, better in itertools.product(values[1:], values, values, (True, False)):
            self.assertEqual(landing_brief.status_for(value, prior, target, better), draft.status_for(value, prior, target, better))

    def test_the_drafted_update_prints_the_word_the_number_the_bar_the_date_and_who_decides(self) -> None:
        b = landing_brief.parse(TEMPLATE)
        cases = [
            ((52, 41, None), "landed", "The bar is met."),
            ((46, 41, None), "watch", "Moving the right way, not there yet."),
            ((46, None, None), "watch", "too early to call"),
            ((41, 41, None), "stalled", "flat since the last reading"),
            ((38, 41, "2027-01-04"), "stalled", "The date, 2026-12-31, has passed."),
        ]
        for (current, prior, as_of), word, phrase in cases:
            with self.subTest(word=word, phrase=phrase):
                u = landing_brief.draft_update(b, current, prior, as_of)
                self.assertEqual(u["status"], word)
                self.assertTrue(u["body"].startswith(f"**{word}**. Activation is {current}%, against a bar of 50% by 2026-12-31."))
                self.assertIn(phrase, u["body"])
                self.assertIn("Who decides the next step: Priya Shah, Head of Product.", u["body"])
                self.assertIn("not proof that this project moved it", u["body"])
                self.assertEqual(u["health"], {"landed": "onTrack", "watch": "atRisk", "stalled": "offTrack"}[word])
        cheaper = landing_brief.parse(brief(metric="Cost per task", bar="$0.30", better="lower"))
        self.assertEqual(landing_brief.draft_update(cheaper, 0.33, 0.41)["status"], "watch")
        self.assertIn("Cost per task is $0.33, against a bar of $0.30", landing_brief.draft_update(cheaper, 0.33, 0.41)["body"])

    def test_the_cli_reads_linear_json_and_refuses_cleanly(self) -> None:
        tool = BRIEF_SKILL / "scripts" / "landing_brief.py"
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "project.json"
            good.write_text(json.dumps({"project": {"name": "Guided activation", "description": TEMPLATE}}), encoding="utf-8")
            done = script(str(tool), "update", str(good), "--current", "46", "--prior", "41", "--json")
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(done.stdout)["status"], "watch")
            self.assertIn("post it only after they confirm", done.stderr)
            bad = Path(tmp) / "bad.md"
            bad.write_text(brief(by="soon"), encoding="utf-8")
            done = script(str(tool), "check", str(bad))
            self.assertNotEqual(done.returncode, 0)
            self.assertIn('by is "soon"', done.stderr)
            self.assertNotIn("Traceback", done.stderr)
            self.assertIn("needs --current", script(str(tool), "update", str(good)).stderr)

    def test_the_two_copies_of_the_parser_are_identical(self) -> None:
        self.assertEqual((BRIEF_SKILL / "scripts" / "landing_brief.py").read_bytes(), (SCRIPTS / "landing_brief.py").read_bytes())

    def test_the_kit_holds_no_network_code_and_its_skill_metadata_meets_the_spec(self) -> None:
        banned = re.compile(r"^\s*(import|from)\s+(socket|urllib|http|requests|subprocess|pickle|ctypes)\b|\b(eval|exec|__import__)\(|os\.system", re.M)
        for path in (BRIEF_SKILL / "scripts").glob("*.py"):
            self.assertIsNone(banned.search(path.read_text(encoding="utf-8")), path.name)
        text = (BRIEF_SKILL / "SKILL.md").read_text(encoding="utf-8")
        front = text.split("---")[1]
        self.assertEqual(re.search(r"^name: (.+)$", front, re.M).group(1), "landing-brief")
        self.assertLessEqual(len(re.search(r"^description: (.+)$", front, re.M).group(1)), 1024)
        self.assertIn("only after the person confirms", text)
        for link in re.findall(r"\]\(((?:assets|scripts)/[^)]+)\)", text):
            self.assertTrue((BRIEF_SKILL / link).exists(), link)


class WriteBack(unittest.TestCase):
    deck: Json
    work: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="peu-wb-"))
        cls.deck, _ = run_fixture("complete", cls.work)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def summarise(self, deck: Json, *args: str) -> tuple[Any, Path]:
        path, out = self.work / "deck.json", self.work / "summary.md"
        out.unlink(missing_ok=True)
        path.write_text(json.dumps(deck), encoding="utf-8")
        return script("summary.py", str(path), "--out", str(out), *args), out

    def test_the_summary_lists_each_title_with_its_ledger_rows(self) -> None:
        done, out = self.summarise(self.deck, "--cut", "L", "--link", "https://example.com/update.html")
        self.assertEqual(done.returncode, 0, done.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn("- **Shipped vs impact.** We shipped 6 of 7 commitments. 4 have moved their target metric so far. Moved means", text)
        self.assertRegex(text, r"Ledger: L\d\d")
        self.assertIn("| ID | Claim | Source | Window | Confidence |", text)
        self.assertIn("[open it](https://example.com/update.html)", text)
        self.assertIn("post it to Linear only after they confirm", done.stdout)

    def test_the_board_cut_needs_a_named_sign_off_and_writes_nothing_without_one(self) -> None:
        done, out = self.summarise(self.deck, "--cut", "B")
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(out.exists())
        done, out = self.summarise(self.deck, "--cut", "B", "--signed-off-by", "  ")
        self.assertNotEqual(done.returncode, 0)
        done, out = self.summarise(self.deck, "--cut", "B", "--signed-off-by", "Dana Reyes")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Signed off by Dana Reyes.", out.read_text(encoding="utf-8"))
        self.assertIn("Never post it automatically", done.stdout)

    def test_a_deck_that_fails_validation_gets_no_summary(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "09")["ledger_refs"] = []
        done, out = self.summarise(deck)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("validator error", done.stderr)
        self.assertFalse(out.exists())

    def test_markup_from_data_cannot_become_html_an_image_or_a_mention(self) -> None:
        deck = copy.deepcopy(self.deck)
        slide(deck, "15")["title"] = "We stopped <b>x</b> ![p](https://evil.example/p.png) for @dana."
        done, out = self.summarise(deck)
        self.assertEqual(done.returncode, 0, done.stderr)
        text = out.read_text(encoding="utf-8")
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", text)
        self.assertNotIn("![", text)
        self.assertNotIn(" @dana", text)


class OutcomesTitle(unittest.TestCase):
    """Slide 11's title reads as a sentence for one outcome as well as many."""

    @staticmethod
    def row(metric: str, status: str) -> dict[str, str]:
        return {"metric": metric, "actual": "15", "target": "25", "status": status}

    def test_one_outcome_is_named_with_its_number_and_target(self) -> None:
        self.assertEqual(draft.outcomes_title([self.row("Unique cloners", "watch")]), "Unique cloners is at 15, short of its target of 25.")
        self.assertEqual(draft.outcomes_title([self.row("Unique cloners", "landed")]), "Unique cloners reached 15, against a target of 25.")

    def test_several_outcomes_are_counted_in_the_plural(self) -> None:
        missed = [self.row("A", "watch"), self.row("B", "stalled")]
        landed = [self.row("A", "landed"), self.row("B", "landed")]
        self.assertEqual(draft.outcomes_title(missed), "None of the 2 reported outcomes met their targets.")
        self.assertEqual(draft.outcomes_title(landed), "All 2 reported outcomes met their targets.")

    def test_no_title_counts_a_single_outcome(self) -> None:
        for status in ("landed", "watch", "stalled"):
            title = draft.outcomes_title([self.row("A", status)])
            self.assertNotRegex(title, r"\b(of the|All) 1\b")


class Release073(unittest.TestCase):
    """The three gaps the reference docs found: the rules list, a blank board sign-off, and an item with nothing to print."""

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.work)

    def test_every_rule_the_validator_raises_is_listed_and_documented(self) -> None:
        code = (SKILL / "scripts" / "validate.py").read_text(encoding="utf-8")
        raised = set(re.findall(r'\.(?:err|warn)\(\s*"([a-z]+(?:-[a-z]+)*)"', code))
        raised |= set(re.findall(r'^\s+"([a-z]+(?:-[a-z]+)+)",\s*$', code, re.M))
        listed = set(validate.RULES) | set(validate.WARNINGS)
        self.assertEqual(raised - listed, set(), "a rule is raised but not listed in RULES or WARNINGS")
        docs = (Path(__file__).resolve().parent.parent / "docs" / "validator-rules.md").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"^### `([a-z-]+)`", docs, re.M)), listed, "docs/validator-rules.md and the code list different rules")

    def test_the_board_cut_refuses_a_blank_name_and_prints_the_name_on_its_cover(self) -> None:
        run_fixture("complete", self.work)
        deck = self.work / "complete" / "deck.json"
        out = self.work / "board.html"
        blank = script("render.py", str(deck), "--out", str(out), "--cut", "B", "--signed-off-by", "   ")
        self.assertNotEqual(blank.returncode, 0)
        self.assertIn("needs --signed-off-by", blank.stderr)
        self.assertFalse(out.exists(), "a refused render writes nothing")
        done = script("render.py", str(deck), "--out", str(out), "--cut", "B", "--signed-off-by", "  Ana Ruiz ")
        self.assertEqual(done.returncode, 0, done.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertIn("Signed off by Ana Ruiz", html)
        self.assertIn("Signed off by Ana Ruiz.", done.stdout)
        leadership = self.work / "leadership.html"
        self.assertEqual(script("render.py", str(deck), "--out", str(leadership), "--cut", "L").returncode, 0)
        self.assertNotIn("Signed off by", leadership.read_text(encoding="utf-8"), "only the board cut carries a sign-off")

    def test_an_item_with_nothing_to_print_blocks_the_check_and_the_draft_says_why(self) -> None:
        run_fixture("complete", self.work)
        run = self.work / "complete"
        path = run / "intake.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        dropped = []
        for field, key in (("bets", "bet"), ("risks", "risk"), ("stopped", "what"), ("decisions", "ask")):
            if data.get(field):
                data[field][0].pop(key, None)
                dropped.append(f'{field}[0] has no "{key}"')
        self.assertTrue(dropped, "the fixture holds the lists this test needs")
        path.write_text(json.dumps(data), encoding="utf-8")
        checked = script("intake.py", "check", str(path))
        self.assertEqual(checked.returncode, 1)
        for problem in dropped:
            self.assertIn(problem, checked.stdout + checked.stderr)
        drafted = script("draft.py", "--run", str(run))
        self.assertNotEqual(drafted.returncode, 0)
        self.assertIn("nothing to print", drafted.stderr)
        self.assertNotIn("Traceback", drafted.stderr)


class SkillHygiene(unittest.TestCase):
    """What a skill linter checks: a body short enough to load, a recovery table, and a working path for friction reports."""

    def test_the_skill_body_stays_short_and_has_its_recovery_table_and_friction_form(self) -> None:
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertLess(len(body.splitlines()), 500, "SKILL.md is loaded whole when the skill runs; keep it under 500 lines")
        self.assertIn("## Error recovery", body)
        self.assertIn("## Friction reports", body)
        self.assertIn("template=friction.yml", body)
        form = Path(__file__).resolve().parent.parent / ".github" / "ISSUE_TEMPLATE" / "friction.yml"
        self.assertTrue(form.is_file(), "SKILL.md links an issue form that does not exist")
        for field in ("Tried", "Expected", "Happened", "Would fix it"):
            self.assertIn(field, body)
            self.assertIn(f"label: {field}", form.read_text(encoding="utf-8"))
        self.assertIn("Never file it on your own", body, "a friction report is filed only after the user says yes")


if __name__ == "__main__":
    unittest.main()
