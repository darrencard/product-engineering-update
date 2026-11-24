#!/usr/bin/env python3
"""Draft the deck from the intake and the computed metrics.

Usage:
  python3 scripts/draft.py --run run [--previous last/deck.json]

Reads run/intake.json and run/metrics.json, starts from assets/blank.deck.json
and writes run/deck.json. With --previous, slide 1 lists what changed since that
deck: each status that moved, each target that moved, and each metric added or
dropped. A status that moved needs a reason in the intake's status_reasons, or
the validator blocks the deck.

What it does, and what it leaves to you:
  - A slide with computed data gets its blocks, its ledger references and a
    plain title stating the computed change. Rewrite the title in better
    words if you can, without changing what it claims.
  - A slide without its data keeps a data_needed block with the gap owner and
    due date from the intake. Never replace that block with prose.
  - Slides that do not apply (no AI features in production) are removed.

Every figure placed on a slide comes from metrics.json with its ledger row.
This script does no arithmetic of its own beyond comparing a value to its
target to choose a status word, and projecting this period's change forward to
the target, which prints as Projected and never as a result.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parent.parent / "assets"
Json = dict[str, Any]

# The one line a generated deck carries about where it came from. The licence asks for credit; this is it.
CREDIT = "Made with [the Product & Engineering Update](https://www.dacard.ai/update) by Dacard."

# The most items a list slide shows; a longer list stops being a summary.
TOP_ITEMS = 5
# A link drafted from data: a web address with no characters that could end the link markup early.
DATA_LINK = re.compile(r"https://[^\s()\[\]<>\"']+")

# Slides that only make sense when AI features are in production.
AI_SLIDES = ("12", "13")
# The slides whose scorecards carry a status word, compared with the previous deck.
SCORED_SLIDES = ("09", "11")
# Printed where a moved status has no reason. validate.py blocks a deck that still holds it.
REASON_NEEDED = "[reason needed]"
NO_CHANGE = "No status or target changed, and no metric was added or dropped."


def load(path: Path) -> Json:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def in_range(value: float, text: str) -> bool | None:
    """Whether a value sits inside a healthy range such as "under 40h", "3+" or "80 to 90%". None when the range cannot be read."""
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", ""))]
    lowered = text.lower()
    if len(numbers) == 2 and re.search(r"\bto\b|between|-", lowered):
        return numbers[0] <= value <= numbers[1]
    if len(numbers) != 1:
        return None
    if re.search(r"under|below|at most|up to|<", lowered):
        return value <= numbers[0] if re.search(r"at most|up to", lowered) else value < numbers[0]
    if re.search(r"over|above|at least|>|\+", lowered):
        return value >= numbers[0] if re.search(r"at least|\+", lowered) else value > numbers[0]
    return None


def range_status(value: float, prior: float | None, text: str, higher_is_better: bool) -> str:
    """landed: inside the healthy range. watch: outside it and improving, or unreadable. stalled: outside it and not improving."""
    inside = in_range(value, text)
    if inside:
        return "landed"
    if inside is None or prior is None:
        return "watch"
    improving = value > prior if higher_is_better else value < prior
    return "watch" if improving else "stalled"


def status_for(value: float, prior: float | None, target: float | None, higher_is_better: bool) -> str:
    """landed: the target is met. watch: moving the right way, not there yet. stalled: flat or moving the wrong way."""
    if target is None:
        return "watch"
    met = value >= target if higher_is_better else value <= target
    if met:
        return "landed"
    if prior is None:
        return "watch"
    improving = value > prior if higher_is_better else value < prior
    return "watch" if improving else "stalled"


def pace(value: float, prior: float | None, target: float | None, higher_is_better: bool, by: str | None, period: Json) -> str:
    """Where this period's change, repeated, takes a metric: Projected, in periods, and against the target date when
    one was stated. A straight line from one period is a rough guide, so the column says Projected and never Met."""
    if target is None:
        return "No target"
    if (value >= target) if higher_is_better else (value <= target):
        return "Met"
    if prior is None:
        return "No prior period"
    step = value - prior if higher_is_better else prior - value
    if step <= 0:
        return "Projected: not on pace"
    n = math.ceil(abs(target - value) / step)
    text = f"Projected: {n} more {'period' if n == 1 else 'periods'}"
    try:
        start, end, due = (datetime.date.fromisoformat(x) for x in (period["start"], period["end"], by or ""))
    except (KeyError, TypeError, ValueError):
        return text
    # Whole periods left before the date. Rounded, because calendar quarters differ by a day or two.
    left = round((due - end).days / ((end - start).days + 1))
    return f"{text}, {'before' if n <= left else 'after'} {due.isoformat()}"


def described(row: Json, definition: str | None, coverage: Json | None = None) -> Json:
    """A scorecard row, with the metric's plain-English definition when one is known, and what the figure covers
    when that is less than the window. Rows without either stay as they were."""
    if definition:
        row["definition"] = definition
    if coverage:
        row["coverage"] = coverage["text"]
    return row


def described_tile(metric: Json) -> Json:
    """A figure tile, with the metric's definition as its note when one is known."""
    tile: Json = {"value": metric["display"], "label": metric["label"]}
    covers = f"{metric['coverage']['text']}." if metric.get("coverage") else None
    note = " ".join(x for x in (metric.get("definition"), covers) if x)
    if note:
        tile["note"] = note
    return tile


# How a title names a computed metric, for a reader outside engineering. A title says what the number
# means, never the engineering term for it (writing-rules.md). The metric's own label stays in the tables.
PLAIN_SUBJECTS = {
    "traced_pct": "The share of the team's time tied to a company objective",
    "deploys_per_week": "Releases to customers per week",
    "lead_time": "The time from a code change being proposed to it being accepted",
    "change_failure_rate": "The share of releases that caused a problem in production",
    "troubled_deploy_rate": "The share of releases rolled back or followed by errors",
    "review_time": "The time a code change spent in review",
    "rework_rate": "The share of code changes that had to be redone",
    "time_to_restore": "The time to restore the service after an incident",
    "arr": "Yearly recurring revenue",
    "nrr": "Revenue from existing customers, against what they paid before,",
    "grr": "Revenue kept from existing customers",
    "expansion_arr": "New yearly revenue from existing customers",
    "rd_share": "Research and development spend as a share of revenue",
    "eval_pass_rate": "The share of quality tests the AI feature passes",
    "cost_per_task": "The cost of each task the AI feature completes",
    "ai_tool_cost": "Spend on AI tools for the team",
    "ai_weekly_use": "The share of AI tool licences used each week",
    "dev_experience": "The developer survey score",
}
# Work types as a board member would say them. A team's own work type names pass through unchanged.
PLAIN_WORK_TYPES = {
    "keep the lights on": "Basic upkeep",
    "ktlo": "Basic upkeep",
    "new capabilities": "New features",
    "improve the core": "Improving what we already sell",
    "platform & scale": "Platform work",
    "platform and scale": "Platform work",
    "growth": "Growth work",
}


def lower_first(text: str) -> str:
    """ "Approve a pilot" reads as "approve a pilot" mid-sentence; "AI pricing" keeps its capitals."""
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def plain_work_type(label: str) -> str:
    return PLAIN_WORK_TYPES.get(label.strip().lower(), label)


class Draft:
    def __init__(self, run: Path, previous: Path | None = None) -> None:
        self.intake = load(run / "intake.json")
        self.previous: Json | None = load(previous) if previous else None
        self.m = load(run / "metrics.json")
        self.metrics: Json = self.m["metrics"]
        self.extra: Json = self.m["extra"]
        self.deck = copy.deepcopy(load(ASSETS / "blank.deck.json"))
        samples = ASSETS / "samples.json"
        self.samples: Json = load(samples) if samples.exists() else {"source": "", "slides": {}}
        self.slides = {s["id"]: s for s in self.deck["slides"]}
        self.filled: list[str] = []

    # ---- helpers ---------------------------------------------------------

    def gap(self, text: str) -> Json:
        return {
            "type": "data_needed",
            "label": "Data needed",
            "text": text,
            "owner": self.intake.get("gap_owner") or "[owner]",
            "due": self.intake.get("gap_due") or "[date]",
        }

    def fill(self, sid: str, title: str, blocks: list[Json], refs: list[str], asof: str) -> None:
        s = self.slides[sid]
        s["title"], s["blocks"], s["asof"] = title, blocks, asof
        s["ledger_refs"] = sorted(set(refs))
        self.filled.append(sid)

    def systems(self, *sources: str) -> str:
        names = sorted(
            {
                row["source_system"]
                for row in self.m["ledger"]
                for key, metric in self.metrics.items()
                if metric["source"] in sources and metric["ledger"] == row["id"]
            }
        )
        period = self.m["period"]
        return f"Sources: {', '.join(names) or 'see the ledger'}. {period['label']}, {period['start']} to {period['end']}."

    def change(self, key: str) -> str | None:
        """One plain sentence stating a computed change. This is the claim a title may make."""
        metric = self.metrics.get(key)
        if not metric or metric.get("conflict") or metric["display"] is None:
            return None
        subject = PLAIN_SUBJECTS.get(key, metric["label"])
        # A figure built from less than the window says so wherever it is cited, title included.
        covers = f" ({metric['coverage']['text'][0].lower()}{metric['coverage']['text'][1:]})" if metric.get("coverage") else ""
        if metric["prior_display"] is None:
            return f"{subject} is {metric['display']}{covers}."
        if metric["value"] == metric["prior"]:
            return f"{subject} held at {metric['display']}{covers}."
        verb = "rose" if metric["value"] > metric["prior"] else "fell"
        return f"{subject} {verb} from {metric['prior_display']} to {metric['display']}{covers}."

    # ---- slides ----------------------------------------------------------

    def strategy(self) -> None:
        st = self.intake.get("strategy") or {}
        if not (st.get("diagnosis") and st.get("policy") and st.get("actions") and st.get("non_goals")):
            return
        cards = {
            "type": "cards",
            "columns": 4,
            "items": [
                {"title": "Diagnosis", "body": [st["diagnosis"]]},
                {"title": "Guiding policy", "body": [st["policy"]]},
                {"title": "Coherent actions", "body": [{"list": st["actions"]}]},
                {"title": "We will not", "body": [{"list": st["non_goals"]}]},
            ],
        }
        self.fill("02", st["policy"], [cards], [], "Strategy as stated in the intake interview.")

    def line_of_sight(self) -> None:
        bets = [b for b in self.intake.get("bets", []) if b.get("objective") and b.get("cause")]
        if not bets:
            return
        trees: list[Json] = []
        for objective in dict.fromkeys(b["objective"] for b in bets):
            trees.append(
                {
                    "type": "tree",
                    "objective": objective,
                    "bets": [
                        {
                            "bet": b["bet"],
                            "owner": b.get("owner") or "Owner not stated",
                            "outcome": b.get("expected") or "Outcome not stated",
                            "cause": b["cause"],
                            "confidence": b["confidence"],
                        }
                        for b in bets
                        if b["objective"] == objective
                    ],
                }
            )
        traced = self.metrics.get("traced_pct")
        refs = [traced["ledger"]] if traced else []
        title = (
            f"{traced['display']} of the team's time goes to work tied to a company objective, each with a stated reason it should pay off."
            if traced
            else f"{len(bets)} bets trace to {len(trees)} objectives, each through a stated cause."
        )
        self.fill("03", title, trees, refs, self.systems("tracker") if traced else "Bets and objectives as stated in the intake interview.")

    def portfolio(self) -> None:
        lines = self.intake.get("product_lines") or []
        capacity: Json = self.extra.get("capacity_by_line") or {}
        mix = self.extra.get("mix")
        if not lines or not capacity or not mix:
            return
        rows = [[line["name"], line.get("stage") or "Not stated", line.get("objective") or "Not stated", f"{capacity.get(line['name'], 0)}%"] for line in lines]
        table: Json = {
            "type": "table",
            "columns": [{"label": "Product line"}, {"label": "Stage"}, {"label": "Objective served"}, {"label": "Capacity", "align": "num"}],
            "rows": rows,
        }
        top = max(lines, key=lambda line: capacity.get(line["name"], 0))
        title = (
            f"{top['name']} takes {capacity.get(top['name'], 0)}% of the team's time."
            if len(lines) == 1
            else f"{top['name']} takes the largest share of the team's time, at {capacity.get(top['name'], 0)}%."
        )
        self.fill("04", title, [table], [mix["ledger"]], self.systems("tracker"))

    def investment_mix(self) -> None:
        mix = self.extra.get("mix")
        if not mix or not mix["has_plan"]:
            return
        rows = [{"label": r["label"], "plan": r["plan"] or 0, "actual": r["actual"], **({"over": True} if r["over"] else {})} for r in mix["rows"]]
        left: Json = {
            "title": "Capacity by type of work",
            "body": [{"type": "plan_vs_actual", "legend": {"plan": "Plan", "actual": "Actual", "over": "Over plan"}, "rows": rows}],
        }
        items: list[Json] = [left]
        refs = [mix["ledger"]]
        finance = self.extra.get("finance")
        if finance:
            table: Json = {
                "type": "table",
                "columns": [{"label": "Line"}, {"label": "Plan", "align": "num"}, {"label": "Actual", "align": "num"}],
                "rows": [[r["line"], r["plan"], r["actual"]] for r in finance["rows"]],
            }
            share = self.metrics.get("rd_share")
            if share:
                table["rows"].append(["R&D as a share of revenue", "", share["display"]])
                refs.append(share["ledger"])
            items.append({"title": "Spend in the period", "body": [table]})
            refs.append(finance["ledger"])
        over = [r for r in mix["rows"] if r["over"]]
        title = (
            f"{plain_work_type(over[0]['label'])} was planned at {over[0]['plan']}% of the team's time and took {over[0]['actual']}%."
            if over
            else "The team's time went where the plan said it would, within 3 points on every type of work."
        )
        blocks: list[Json] = [{"type": "cards", "columns": "2:1" if len(items) == 2 else 1, "items": items}]
        capex = self.extra.get("capex")
        if capex:
            confirmed = f"Confirmed by {capex['confirmed_by']}." if capex.get("confirmed_by") else "Not yet confirmed by finance."
            blocks.append(
                {
                    "type": "cards",
                    "columns": 1,
                    "items": [
                        {
                            "title": "Capitalisable cost, an estimate for finance to confirm",
                            "body": [
                                {
                                    "type": "table",
                                    "columns": [{"label": "Estimate"}, {"label": "This period", "align": "num"}],
                                    "rows": [
                                        ["Capitalisable, estimated", capex["capitalisable"]],
                                        ["Expensed, estimated", capex["expensed"]],
                                        [f"Cost the estimate covers ({', '.join(capex['cost_lines'])})", capex["cost"]],
                                    ],
                                },
                                f"Basis: {capex['share']} of the team's time went to {', '.join(capex['work_types'])}, applied to that cost. "
                                f"What may be capitalised is the company's accounting policy. {confirmed}",
                            ],
                        }
                    ],
                }
            )
            refs.append(capex["ledger"])
        if "arr" not in self.metrics or not finance:
            blocks.append({"type": "cards", "columns": 1, "items": [self.gap("Cash, net burn and runway in months. A board cut needs all three.")]})
        self.fill("05", title, blocks, refs, self.systems("tracker", "finance"))

    def delivery(self) -> None:
        ranges: Json = self.intake.get("delivery_ranges") or {}
        groups = [
            ("Speed", ["deploys_per_week", "lead_time"]),
            ("Quality, the pair for every speed metric", ["change_failure_rate", "troubled_deploy_rate", "time_to_restore", "review_time", "rework_rate"]),
            ("Effectiveness", ["dev_experience"]),
        ]
        rows: list[Json] = []
        refs: list[str] = []
        shown: dict[str, list[str]] = {}
        for group, keys in groups:
            picked = [k for k in keys if k in self.metrics and self.metrics[k]["label"] in ranges]
            if not picked:
                continue
            rows.append({"group": group})
            shown[group] = picked
            for k in picked:
                metric = self.metrics[k]
                rows.append(
                    described(
                        {
                            "metric": metric["label"],
                            "prior": metric["prior_display"] or "No prior",
                            "actual": metric["display"],
                            "target": ranges[metric["label"]],
                            "status": range_status(metric["value"], metric["prior"], ranges[metric["label"]], metric.get("higher_is_better", True)),
                        },
                        metric.get("definition"),
                        metric.get("coverage"),
                    )
                )
                refs.append(metric["ledger"])
        if "Speed" not in shown or "Quality, the pair for every speed metric" not in shown:
            return
        blocks: list[Json] = [
            {
                "type": "scorecard",
                "target_kind": "range",
                "labels": {"metric": "Metric", "prior": "Prior period", "actual": "This period", "target": "Healthy range", "status": "Status"},
                "rows": rows,
            }
        ]
        speed, quality = self.change(shown["Speed"][0]), self.change(shown["Quality, the pair for every speed metric"][0])
        asof = self.systems("source_control", "incidents", "survey")
        # A range the user accepted from a suggestion names where the suggestion came from.
        sourced = self.intake.get("range_sources") or {}
        shown_labels = [r["metric"] for r in rows if "metric" in r]
        by_source: dict[str, list[str]] = {}
        for label in shown_labels:
            if label in sourced:
                by_source.setdefault(sourced[label]["source"], []).append(label)
        for source, labels in by_source.items():
            asof += f" Healthy ranges for {', '.join(labels)} accepted from {source}."
        self.fill("09", f"{speed} {quality}", blocks, refs, asof)

    def held_speed(self) -> str:
        """Why the delivery slide is a gap when speed was measured: speed never shows without a quality pair and a range."""
        speed = [k for k in ("deploys_per_week", "lead_time") if k in self.metrics]
        quality = [k for k in ("change_failure_rate", "troubled_deploy_rate", "time_to_restore", "review_time", "rework_rate") if k in self.metrics]
        if not speed:
            return ""
        missing = []
        if not quality:
            missing.append(
                "a quality metric to pair with speed (change failure rate, time to restore, review time, rework, or deploys rolled back or followed by errors)"
            )
        if not self.intake.get("delivery_ranges"):
            missing.append("a healthy range for each delivery metric")
        if not missing:
            return ""
        rows = ", ".join(self.metrics[k]["ledger"] for k in speed)
        return f"Speed was measured (ledger {rows}) and is held back. This slide needs {' and '.join(missing)}."

    def find_metric(self, name: str) -> Json | None:
        """A collected metric by the name an intake uses: an analytics metric, or any computed metric's label."""
        return self.metrics.get(f"analytics:{name}") or next((m for m in self.metrics.values() if m["label"] == name), None)

    def better_for(self, name: str, metric: Json) -> bool:
        """Which way is better for a metric: the intake's own north star or input wins, then the metric's."""
        wanted = [self.intake.get("north_star") or {}] + list(self.intake.get("inputs") or [])
        want = next((w for w in wanted if isinstance(w, dict) and w.get("metric") == name), {})
        return bool(want.get("higher_is_better", metric.get("higher_is_better", True)))

    def shipped_vs_impact(self) -> None:
        """Slide 8: last period's commitments, grouped by the outcome each named before launch.

        "Moved" means the metric went the right way this period. It never says the commitment caused it.
        A commitment with no metric, or whose metric was not collected or is disputed, goes under "No movement"
        with the reason. A commitment that was not shipped says so."""
        commitments = [c for c in self.intake.get("commitments") or [] if isinstance(c, dict) and c.get("commitment")]
        if not commitments:
            return
        groups: dict[str, list[list[str]]] = {}
        still: list[list[str]] = []
        refs: list[str] = []
        covers: dict[str, str] = {}
        moved = 0
        for c in commitments:
            shipped = str(c.get("shipped") or "").strip().lower() == "yes"
            name = (c.get("metric") or "").strip()
            row = [c["commitment"], c.get("owner") or "Owner not stated", "Yes" if shipped else "No"]
            metric = self.find_metric(name) if name else None
            if not name:
                still.append([*row, "No target metric named", "Not shipped" if not shipped else "No movement: no metric was named before launch"])
                continue
            if not metric:
                still.append([*row, f"{name}: not collected", "Not shipped" if not shipped else "No movement: the metric was not collected"])
                continue
            refs.append(metric["ledger"])
            if metric.get("conflict") or metric["value"] is None:
                still.append([*row, f"{name}: two sources disagree", "Not shipped" if not shipped else f"No movement: see ledger row {metric['ledger']}"])
                continue
            # A figure built from less than the window says so on the figure and in the title.
            coverage = metric.get("coverage")
            covered = f"{coverage['text'][0].lower()}{coverage['text'][1:]}" if coverage else ""
            note = f" ({covered})" if covered else ""
            if covered:
                covers[name] = f"{name} {covered}."
            figure = f"{metric['prior_display'] or 'No prior'} to {metric['display']}{note}"
            if not shipped:
                result = "Not shipped"
            elif metric["prior"] is None:
                result = "Too early to call: no prior period"
            elif metric["value"] == metric["prior"]:
                result = "Flat"
            elif (metric["value"] > metric["prior"]) == self.better_for(name, metric):
                result = "Moved"
                moved += 1
            else:
                result = "Moved the wrong way"
            groups.setdefault(name, []).append([*row, figure, result])
        rows: list[Json | list[str]] = []
        for outcome, items in groups.items():
            rows.append({"group": outcome})
            rows.extend(items)
        if still:
            rows.append({"group": "No movement"})
            rows.extend(still)
        table: Json = {
            "type": "table",
            "columns": [{"label": c} for c in ("Commitment", "Owner", "Shipped", "Metric, before to after", "Result")],
            "rows": rows,
        }
        note = {
            "title": "What moved means",
            "body": ["Moved means the target metric went the right way this period. It is not proof that the commitment caused it."],
        }
        shipped_count = sum(1 for c in commitments if str(c.get("shipped") or "").strip().lower() == "yes")
        has = "has" if moved == 1 else "have"
        title = f"We shipped {shipped_count} of {plural(len(commitments), 'commitment')}. {moved} {has} moved their target metric so far."
        if covers:
            title += " " + " ".join(covers.values())
        sources = list(dict.fromkeys(str(c["source"]).strip() for c in commitments if c.get("source")))
        said = f"Commitments from {', '.join(sources)}." if sources else "Commitments as stated in the intake interview."
        period = self.m["period"]
        used = {m["source"] for m in self.metrics.values() if m["ledger"] in refs}
        asof = f"{said} {self.systems(*used)}" if used else f"{said} {period['label']}, {period['start']} to {period['end']}."
        self.fill("08", title, [table, {"type": "cards", "columns": 1, "items": [note]}], refs, asof)

    def outcomes(self) -> None:
        north = self.intake.get("north_star") or {}
        wanted = [north] + list(self.intake.get("inputs") or [])
        rows: list[Json] = []
        refs: list[str] = []
        gaps: list[str] = []
        for want in wanted:
            name = want.get("metric")
            if not name:
                continue
            metric = self.find_metric(name)
            target = want.get("target")
            if not metric:
                gaps.append(f"{name}: not collected.")
                continue
            refs.append(metric["ledger"])
            if metric.get("conflict") or metric["value"] is None:
                gaps.append(f"{name}: two sources disagree. See ledger row {metric['ledger']}.")
                continue
            better = want.get("higher_is_better", metric.get("higher_is_better", True))
            unit = want.get("unit", "")
            # The user's own wording of a definition wins over the one the analytics system carries.
            rows.append(
                described(
                    {
                        "metric": name,
                        "prior": metric["prior_display"] or "No prior",
                        "actual": metric["display"],
                        "target": want.get("target_display") or (f"{target:g}{unit}" if isinstance(target, (int, float)) else (target or "Not set")),
                        "status": status_for(metric["value"], metric["prior"], target if isinstance(target, (int, float)) else None, better),
                        "extra": [
                            pace(
                                metric["value"],
                                metric["prior"],
                                target if isinstance(target, (int, float)) else None,
                                better,
                                want.get("by"),
                                self.intake["period"],
                            ),
                            "None external",
                            want.get("owner") or "Owner not stated",
                        ],
                    },
                    want.get("definition") or metric.get("definition"),
                    metric.get("coverage"),
                )
            )
        if not rows and not gaps:
            return
        blocks: list[Json] = []
        if rows:
            blocks.append(
                {
                    "type": "scorecard",
                    "target_kind": "target",
                    "labels": {
                        "metric": "Outcome",
                        "prior": "Prior period",
                        "actual": "This period",
                        "target": "Target",
                        "status": "Status",
                        "extra": ["At this pace", "Benchmark", "Owner"],
                    },
                    "rows": rows,
                }
            )
        if gaps:
            blocks.append({"type": "cards", "columns": 1, "items": [self.gap(" ".join(gaps))]})
        landed = [r for r in rows if r["status"] == "landed"]
        missed = [r for r in rows if r["status"] != "landed"]
        if not rows:
            title = "Outcomes are not reported this period. The sources disagree or are missing."
        elif landed and missed:
            hit, short = landed[0], missed[0]
            title = (
                f"{hit['metric']} reached {hit['actual']}, against a target of {hit['target']}. "
                f"{short['metric']}, at {short['actual']} against {short['target']}, did not."
            )
        elif landed:
            title = f"All {len(landed)} reported outcomes met their targets."
        else:
            title = f"None of the {len(missed)} reported outcomes met its target."
        self.fill("11", title, blocks, refs, self.systems("analytics", "billing", "warehouse"))

    def ai_in_product(self) -> None:
        tiles = [described_tile(self.metrics[k]) for k in ("eval_pass_rate", "cost_per_task") if k in self.metrics]
        if not tiles:
            return
        refs = [self.metrics[k]["ledger"] for k in ("eval_pass_rate", "cost_per_task") if k in self.metrics]
        title = " ".join(c for c in (self.change("eval_pass_rate"), self.change("cost_per_task")) if c)
        blocks: list[Json] = [{"type": "tiles", "columns": 3, "items": tiles}]
        # The slide's contract also needs AI revenue against its cost. Nothing computes that yet, so the gap is shown.
        blocks.append({"type": "cards", "columns": 1, "items": [self.gap("AI revenue and cost of revenue, for AI gross margin.")]})
        self.fill("12", title, blocks, refs, self.systems("evals"))

    def learned(self) -> None:
        """Slide 6, from customer requests: what customers asked for, counted in code, each linked to its issue or
        project. Requests are what customers asked for; the slide never calls them a tested result."""
        asks = self.extra.get("customer_requests")
        if not asks:
            return
        items = asks["items"][:TOP_ITEMS]

        def named(i: Json) -> str:
            label = re.sub(r"[\[\]]", "", i["linked_to"])
            return f"[{label}]({i['link']})" if i.get("link") and DATA_LINK.fullmatch(i["link"]) else i["linked_to"]

        table: Json = {
            "type": "table",
            "columns": [{"label": "Issue or project"}, {"label": "Requests", "align": "num"}, {"label": "Customers", "align": "num"}],
            "rows": [[named(i), str(i["requests"]), str(i["customers"])] for i in items],
        }
        note = {
            "title": "What this does not show",
            "body": ["Requests are what customers asked for. They are not a tested result: no interview, prototype or experiment is counted here."],
        }
        top = asks["items"][0]
        linked = len(asks["items"])
        title = (
            f"{plural(asks['customers'], 'customer')} made {plural(asks['total'], 'request')} this period, linked to "
            f"{linked} {'issue or project' if linked == 1 else 'issues and projects'}. The most requested is {top['linked_to']}, "
            f"with {plural(top['requests'], 'request')} from {plural(top['customers'], 'customer')}."
        )
        self.fill("06", title, [table, {"type": "cards", "columns": 1, "items": [note]}], [asks["ledger"]], self.systems_of(asks["ledger"]))

    def systems_of(self, *ledger_ids: str) -> str:
        """The sources line for figures that are ledger rows but not metrics."""
        names = sorted({row["source_system"] for row in self.m["ledger"] if row["id"] in ledger_ids})
        period = self.m["period"]
        return f"Sources: {', '.join(names) or 'see the ledger'}. {period['label']}, {period['start']} to {period['end']}."

    def signal(self) -> None:
        crm, support, asks = self.extra.get("crm"), self.extra.get("support"), self.extra.get("customer_requests")
        if not crm and not support and not asks:
            return
        tiles: list[Json] = []
        refs: list[str] = []
        claims: list[str] = []
        for found, noun in ((crm, "closed deals"), (support, "support tickets")):
            if not found:
                continue
            reason, count = found["top"][0]
            tiles.append({"value": f"{count} of {found['total']}", "label": f"{noun.capitalize()} citing: {reason}"})
            claims.append(f"The most cited reason in {found['total']} {noun}: {reason}.")
            refs.append(found["ledger"])
        if asks:
            top = asks["items"][0]
            tiles.append({"value": f"{top['requests']} of {asks['total']}", "label": f"Customer requests linked to: {top['linked_to']}"})
            claims.append(f"The most requested item in {asks['total']} customer requests: {top['linked_to']}.")
            refs.append(asks["ledger"])
        sources = self.systems_of(*refs)
        self.fill("07", " ".join(claims), [{"type": "tiles", "columns": 3 if len(tiles) > 2 else 2, "items": tiles}], refs, sources)

    def ai_in_build(self) -> None:
        use, cost = self.metrics.get("ai_weekly_use"), self.metrics.get("ai_tool_cost")
        agent = self.metrics.get("agent_authored_share")
        if not (use and cost) and not agent:
            return
        rows: list[list[str]] = []
        refs: list[str] = []
        if use and cost:
            rows += [["AI tool seats used weekly", use["display"]], ["AI tool spend in the period", cost["display"]]]
            refs += [use["ledger"], cost["ledger"]]
        if agent:
            covers = f" ({lower_first(agent['coverage']['text'])})" if agent.get("coverage") else ""
            rows.append([f"Accepted changes written by an agent{covers}", agent["display"]])
            refs.append(agent["ledger"])
        table: Json = {
            "type": "table",
            "columns": [{"label": "Measure"}, {"label": "This period", "align": "num"}],
            "rows": rows,
        }
        note = {
            "title": "What we do not claim",
            "body": ["Use and spend are inputs. This slide reports no productivity figure, because none has a baseline and a window yet."],
        }
        said = []
        if use and cost:
            said.append(f"{use['display']} of AI tool licences are used each week, at {cost['display']} this period.")
        if agent:
            said.append(f"Agents wrote {agent['display']} of accepted changes.")
        self.fill(
            "13",
            " ".join(said) + " We make no claim that the team got faster.",
            [table, {"type": "cards", "columns": 1, "items": [note]}],
            refs,
            self.systems("ai_tools", "source_control"),
        )

    def stopped(self) -> None:
        items = self.intake.get("stopped") or []
        if not items:
            return
        cards = [{"title": x["what"], "body": [x.get("why") or "No reason recorded."]} for x in items]
        self.fill(
            "15",
            f"We stopped one thing this period: {lower_first(items[0]['what'])}."
            if len(items) == 1
            else f"We stopped {plural(len(items), 'thing')} this period.",
            [{"type": "cards", "columns": min(max(len(cards), 2), 3), "items": cards}],
            [],
            "Decision log as stated in the intake interview.",
        )

    def delivery_on_a_page(self) -> None:
        """The board's one delivery slide: the computed changes from the slides it condenses."""
        keys = ("deploys_per_week", "change_failure_rate", "review_time", "ai_weekly_use")
        points = [(self.change(k), self.metrics[k]["ledger"]) for k in keys if k in self.metrics and self.change(k)]
        if len(points) < 2 or "09" not in self.filled:
            return
        cards = [{"title": "Delivery and its cost", "body": [{"list": [f"{text}[[{ref}]]" for text, ref in points]}]}]
        self.fill(
            "09b",
            f"{points[0][0]} {points[1][0]}",
            [{"type": "cards", "columns": 1, "items": cards}],
            [ref for _, ref in points],
            "Condensed from the leadership cut's delivery slides.",
        )

    def answer(self) -> None:
        """Slide 1, written last: the changes that matter and the asks. It adds nothing new."""
        north = (self.intake.get("north_star") or {}).get("metric")
        keys = [f"analytics:{north}" if north else "", "arr", "nrr", "eval_pass_rate", "change_failure_rate"]
        points = [(self.change(k), self.metrics[k]["ledger"]) for k in keys if k in self.metrics and self.change(k)]
        asks = [d["ask"] for d in self.intake.get("decisions") or []]
        if len(points) < 2:
            return
        items: list[Json] = [{"title": "What happened", "body": [{"list": [f"{text}[[{ref}]]" for text, ref in points[:4]]}]}]
        items.append({"title": "Now what", "body": [{"list": asks}] if asks else ["No decisions were supplied for this period."]})
        gaps = [s["nav"] for s in self.deck["slides"] if s["kind"] == "slide" and s["id"] not in self.filled and s["id"] != "01"]
        held = [c["metric"] for c in self.m["conflicts"]]
        notes = []
        if gaps:
            notes.append(f"{plural(len(gaps), 'slide')} lack data this period: {', '.join(gaps)}.")
        if held:
            notes.append(f"{plural(len(held), 'figure')} held because two sources disagree: {', '.join(held)}.")
        if notes:
            items.append({"title": "Not reported", "body": notes})
        title = self.slides["11"]["title"] if "11" in self.filled else points[0][0]
        blocks: list[Json] = [{"type": "cards", "columns": 3 if len(items) == 3 else 2, "items": items}]
        since = self.since_last()
        if since is not None:
            blocks.append({"type": "cards", "columns": 1, "items": [{"title": "Since the last update", "body": [{"list": since}] if since else [NO_CHANGE]}]})
        self.fill(
            "01",
            title,
            blocks,
            [ref for _, ref in points[:4]],
            f"Data as of {self.intake['as_of']}. Status words: landed, watch, stalled.",
        )

    def scorecard_rows(self, slides: list[Json]) -> dict[str, Json]:
        """Each metric row on the delivery and outcome scorecards, by metric name."""
        rows: dict[str, Json] = {}
        for s in slides:
            if s.get("id") not in SCORED_SLIDES:
                continue
            for b in s.get("blocks", []):
                if b.get("type") == "scorecard":
                    rows.update({r["metric"]: r for r in b["rows"] if "metric" in r})
        return rows

    def since_last(self) -> list[str] | None:
        """What moved since the previous deck: statuses, targets, and metrics added or dropped. None without a
        previous deck. A status that moved carries the reason from the intake, or a marker the validator blocks."""
        if self.previous is None:
            return None
        before = self.scorecard_rows(self.previous.get("slides", []))
        now = self.scorecard_rows(self.deck["slides"])
        reasons: Json = self.intake.get("status_reasons") or {}
        lines: list[str] = []
        for name, row in now.items():
            old = before.get(name)
            if old is None:
                lines.append(f"{name}: newly reported, {row['status']}.")
                continue
            if old["status"] != row["status"]:
                reason = (reasons.get(name) or "").strip() or REASON_NEEDED
                lines.append(f"{name}: {old['status']} to {row['status']}. Reason: {reason}")
            if old["target"] != row["target"]:
                lines.append(f"{name}: the target moved from {old['target']} to {row['target']}.")
        lines += [f"{name}: no longer reported (was {old['status']})." for name, old in before.items() if name not in now]
        return lines

    def bets(self) -> None:
        bets = self.intake.get("bets") or []
        if not bets:
            return
        table: Json = {
            "type": "table",
            "columns": [{"label": c} for c in ("Bet", "Commitment", "Appetite", "Expected result", "Confidence", "We stop if")],
            "rows": [
                [b["bet"], b.get("commitment") or "Not stated", b["appetite"], b.get("expected") or "Not stated", b["confidence"], b["stop_rule"]] for b in bets
            ],
        }
        title = f"We are making {plural(len(bets), 'bet')}, each with a set budget of time and people and a stated point at which we stop."
        self.fill("16", title, [table], [], "Bets as stated in the intake interview.")

    def risks(self) -> None:
        risks = self.intake.get("risks") or []
        if not risks:
            return
        table: Json = {
            "type": "table",
            "columns": [{"label": c} for c in ("Risk", "Likelihood", "Impact", "Mitigation and owner", "Due")],
            "rows": [
                [r["risk"], r.get("likelihood") or "Not rated", r.get("impact") or "Not rated", r.get("mitigation") or "None yet", r.get("due") or "No date"]
                for r in risks
            ],
        }
        title = f"One risk: {lower_first(risks[0]['risk'])}." if len(risks) == 1 else f"{plural(len(risks), 'risk')}, each with an owner and a date."
        self.fill("14", title, [table], [], "Risk register as stated in the intake interview.")

    def people(self) -> None:
        hr = self.extra.get("hr")
        if not hr:
            return
        rows = [[r["function"], f"{r['now']:g}", f"{r['plan']:g}", r.get("open_roles") or ""] for r in hr["rows"]]
        rows.append(["Total", f"{hr['now']:g}", f"{hr['plan']:g}", ""])
        table: Json = {
            "type": "table",
            "columns": [{"label": "Function"}, {"label": "Now", "align": "num"}, {"label": "Plan", "align": "num"}, {"label": "Open"}],
            "rows": rows,
        }
        self.fill("17", f"{hr['now']:g} of {hr['plan']:g} planned roles are filled.", [table], [hr["ledger"]], self.systems("hr"))

    def decisions(self) -> None:
        asks = self.intake.get("decisions") or []
        if not asks:
            return
        items = [
            {
                "title": d["ask"],
                "body": [
                    d.get("recommendation") or "No recommendation yet.",
                    {"p": f"Options: {d.get('options') or 'not stated'}. Deadline: {d.get('deadline') or 'not set'}.", "emphasis": True},
                ],
            }
            for d in asks
        ]
        self.fill(
            "18",
            f"One decision for you today: {lower_first(asks[0]['ask'])}." if len(asks) == 1 else f"{plural(len(asks), 'decision')} for you today.",
            [{"type": "cards", "columns": min(max(len(items), 2), 3), "items": items}],
            [],
            "Decisions as stated in the intake interview.",
        )

    # ---- assembly --------------------------------------------------------

    def build(self) -> Json:
        intake, deck = self.intake, self.deck
        deck["meta"].update(
            company=intake["company"],
            period=intake["period"]["label"],
            as_of=intake["as_of"],
            notice={
                "illustrative": False,
                "text": f"{intake['company']}, {intake['period']['label']}. Every figure has a row in the evidence ledger. A slide without its data says so.",
            },
            footer=f"{intake['company']} product & engineering update, {intake['period']['label']}. {CREDIT}",
        )
        cover = self.slides["00"]
        cover["title"] = f"{intake['company']} product & engineering update"
        cover["meta"] = [intake["period"]["label"], f"By {intake.get('author') or 'the product and engineering leads'}"]
        for step in (
            self.strategy,
            self.line_of_sight,
            self.portfolio,
            self.investment_mix,
            self.delivery,
            self.shipped_vs_impact,
            self.outcomes,
            self.learned,
            self.signal,
            self.ai_in_product,
            self.ai_in_build,
            self.risks,
            self.stopped,
            self.bets,
            self.people,
            self.decisions,
            self.delivery_on_a_page,
            self.answer,
        ):
            step()
        # An empty list means "none in production", so the AI slides go. null means "not asked yet", so they stay as gaps.
        if intake.get("ai_features") == []:
            deck["slides"] = [s for s in deck["slides"] if s["id"] not in AI_SLIDES]
            self.slides = {s["id"]: s for s in deck["slides"]}
            for s in deck["slides"]:
                # A rollup slide may only name slides that are still in the deck.
                if "rolls_up" in s:
                    s["rolls_up"] = [sid for sid in s["rolls_up"] if sid in self.slides]
        for s in deck["slides"]:
            if s["kind"] != "slide":
                continue
            s["kicker"] = s["act"]
            if s["id"] in self.filled:
                continue
            s["title"] = f"{s['nav']} is not reported this period. The data is missing."
            for b in s["blocks"]:
                for item in b.get("items", []):
                    if item.get("type") == "data_needed":
                        if s["id"] == "09" and self.held_speed():
                            item["text"] = self.held_speed()
                        item["owner"] = intake.get("gap_owner") or item["owner"]
                        item["due"] = intake.get("gap_due") or item["due"]
            s["asof"] = f"No data collected for {intake['period']['label']}."
            sample = self.samples["slides"].get(s["id"])
            if sample:
                # Shows what the slide would hold, greyed and tagged. It is never evidence and cites no ledger row.
                s["blocks"].append(
                    {
                        "type": "sample",
                        "illustrative": True,
                        "label": f"What this slide looks like with data. A sample from {self.samples['source']}; none of it is yours.",
                        "blocks": copy.deepcopy(sample),
                    }
                )
        core = [s for s in deck["slides"] if s["kind"] == "slide"]
        cover["blocks"] = [
            {
                "type": "text",
                "variant": "lede",
                "text": f"{len(self.filled)} of {len(core)} slides show data for {intake['period']['label']}. "
                "The rest show what is missing, who owns it and when it is due. Every figure has a row in the evidence ledger.",
            },
            *[b for b in cover["blocks"] if b["type"] == "facts"],
        ]
        deck["ledger"] = self.m["ledger"]
        deck["meta"]["cuts"] = {
            a["key"]: [s["id"] for s in deck["slides"] if s["kind"] == "slide" and a["key"] in s["audiences"]] for a in deck["meta"]["audiences"]
        }
        return deck


def main() -> int:
    ap = argparse.ArgumentParser(description="Draft the deck from the intake and the computed metrics.")
    ap.add_argument("--run", default="run")
    ap.add_argument("--previous", help="the last update's deck.json, to list what changed since it")
    args = ap.parse_args()
    run = Path(args.run)
    previous = Path(args.previous) if args.previous else None
    if previous and not previous.exists():
        raise SystemExit(f"draft: {previous} is missing. Pass the deck.json from the last update, or leave --previous out.")
    for name in ("intake.json", "metrics.json"):
        if not (run / name).exists():
            raise SystemExit(f"draft: {run / name} is missing. Run intake.py, collect.py and compute_metrics.py first.")
    draft = Draft(run, previous)
    deck = draft.build()
    out = run / "deck.json"
    out.write_text(json.dumps(deck, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    core = [s for s in deck["slides"] if s["kind"] == "slide"]
    with_data = ", ".join(x.lstrip("0") for x in draft.filled) or "none"
    print(f"draft: wrote {out}. {len(draft.filled)} of {len(core)} core slides across the 3 cuts have data ({with_data}). The rest show data needed.")
    print("draft: next, improve the titles without changing what they claim, then run validate.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
