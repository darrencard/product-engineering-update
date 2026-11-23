#!/usr/bin/env python3
"""Draft the deck from the intake and the computed metrics.

Usage:
  python3 scripts/draft.py --run run

Reads run/intake.json and run/metrics.json, starts from assets/blank.deck.json
and writes run/deck.json.

What it does, and what it leaves to you:
  - A slide with computed data gets its blocks, its ledger references and a
    plain title stating the computed change. Rewrite the title in better
    words if you can, without changing what it claims.
  - A slide without its data keeps a data_needed block with the gap owner and
    due date from the intake. Never replace that block with prose.
  - Slides that do not apply (no AI features in production) are removed.

Every figure placed on a slide comes from metrics.json with its ledger row.
This script does no arithmetic of its own beyond comparing a value to its
target to choose a status word.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ASSETS = Path(__file__).resolve().parent.parent / "assets"
Json = dict[str, Any]

# Slides that only make sense when AI features are in production.
AI_SLIDES = ("12", "13")


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


class Draft:
    def __init__(self, run: Path) -> None:
        self.intake = load(run / "intake.json")
        self.m = load(run / "metrics.json")
        self.metrics: Json = self.m["metrics"]
        self.extra: Json = self.m["extra"]
        self.deck = copy.deepcopy(load(ASSETS / "blank.deck.json"))
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
        if metric["prior_display"] is None:
            return f"{metric['label']} is {metric['display']}."
        if metric["value"] == metric["prior"]:
            return f"{metric['label']} held at {metric['display']}."
        verb = "rose" if metric["value"] > metric["prior"] else "fell"
        return f"{metric['label']} {verb} from {metric['prior_display']} to {metric['display']}."

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
            f"{traced['display']} of capacity traces to a company objective through a stated cause."
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
            f"{top['name']} takes {capacity.get(top['name'], 0)}% of capacity."
            if len(lines) == 1
            else f"{top['name']} takes the largest share of capacity at {capacity.get(top['name'], 0)}%."
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
            f"{over[0]['label']} was planned at {over[0]['plan']}% of capacity and took {over[0]['actual']}%."
            if over
            else "Capacity went where the plan said it would, within 3 points on every line."
        )
        blocks: list[Json] = [{"type": "cards", "columns": "2:1" if len(items) == 2 else 1, "items": items}]
        if "arr" not in self.metrics or not finance:
            blocks.append({"type": "cards", "columns": 1, "items": [self.gap("Cash, net burn and runway in months. A board cut needs all three.")]})
        self.fill("05", title, blocks, refs, self.systems("tracker", "finance"))

    def delivery(self) -> None:
        ranges: Json = self.intake.get("delivery_ranges") or {}
        groups = [
            ("Speed", ["deploys_per_week", "lead_time"]),
            ("Quality, the pair for every speed metric", ["change_failure_rate", "time_to_restore", "review_time", "rework_rate"]),
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
                    {
                        "metric": metric["label"],
                        "prior": metric["prior_display"] or "No prior",
                        "actual": metric["display"],
                        "target": ranges[metric["label"]],
                        "status": range_status(metric["value"], metric["prior"], ranges[metric["label"]], metric.get("higher_is_better", True)),
                    }
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
        self.fill("09", f"{speed} {quality}", blocks, refs, self.systems("source_control", "incidents", "survey"))

    def held_speed(self) -> str:
        """Why the delivery slide is a gap when speed was measured: speed never shows without a quality pair and a range."""
        speed = [k for k in ("deploys_per_week", "lead_time") if k in self.metrics]
        quality = [k for k in ("change_failure_rate", "time_to_restore", "review_time", "rework_rate") if k in self.metrics]
        if not speed:
            return ""
        missing = []
        if not quality:
            missing.append("a quality metric to pair with speed (change failure rate, time to restore, review time or rework)")
        if not self.intake.get("delivery_ranges"):
            missing.append("a healthy range for each delivery metric")
        if not missing:
            return ""
        rows = ", ".join(self.metrics[k]["ledger"] for k in speed)
        return f"Speed was measured (ledger {rows}) and is held back. This slide needs {' and '.join(missing)}."

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
            metric = self.metrics.get(f"analytics:{name}") or next((m for m in self.metrics.values() if m["label"] == name), None)
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
            rows.append(
                {
                    "metric": name,
                    "prior": metric["prior_display"] or "No prior",
                    "actual": metric["display"],
                    "target": want.get("target_display") or (f"{target:g}{unit}" if isinstance(target, (int, float)) else (target or "Not set")),
                    "status": status_for(metric["value"], metric["prior"], target if isinstance(target, (int, float)) else None, better),
                    "extra": ["None external", want.get("owner") or "Owner not stated"],
                }
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
                        "extra": ["Benchmark", "Owner"],
                    },
                    "rows": rows,
                }
            )
        if gaps:
            blocks.append({"type": "cards", "columns": 1, "items": [self.gap(" ".join(gaps))]})
        landed = [r["metric"] for r in rows if r["status"] == "landed"]
        missed = [r["metric"] for r in rows if r["status"] != "landed"]
        if not rows:
            title = "Outcomes are not reported this period. The sources disagree or are missing."
        elif landed and missed:
            title = f"{landed[0]} met its target. {missed[0]} did not."
        elif landed:
            title = f"All {len(landed)} reported outcomes met their targets."
        else:
            title = f"None of the {len(missed)} reported outcomes met its target."
        self.fill("11", title, blocks, refs, self.systems("analytics", "billing", "warehouse"))

    def ai_in_product(self) -> None:
        tiles = [{"value": self.metrics[k]["display"], "label": self.metrics[k]["label"]} for k in ("eval_pass_rate", "cost_per_task") if k in self.metrics]
        if not tiles:
            return
        refs = [self.metrics[k]["ledger"] for k in ("eval_pass_rate", "cost_per_task") if k in self.metrics]
        title = " ".join(c for c in (self.change("eval_pass_rate"), self.change("cost_per_task")) if c)
        self.fill("12", title, [{"type": "tiles", "columns": 3, "items": tiles}], refs, self.systems("evals"))

    def signal(self) -> None:
        crm, support = self.extra.get("crm"), self.extra.get("support")
        if not crm and not support:
            return
        tiles: list[Json] = []
        refs: list[str] = []
        claims: list[str] = []
        for found, noun in ((crm, "closed deals"), (support, "support tickets")):
            if not found:
                continue
            reason, count = found["top"][0]
            tiles.append({"value": f"{count} of {found['total']}", "label": f"{noun.capitalize()} citing: {reason}"})
            claims.append(f"{reason} is the most cited reason in {found['total']} {noun}.")
            refs.append(found["ledger"])
        self.fill("07", " ".join(claims), [{"type": "tiles", "columns": 3 if len(tiles) > 2 else 2, "items": tiles}], refs, self.systems("crm", "support"))

    def ai_in_build(self) -> None:
        use, cost = self.metrics.get("ai_weekly_use"), self.metrics.get("ai_tool_cost")
        if not use or not cost:
            return
        table: Json = {
            "type": "table",
            "columns": [{"label": "Measure"}, {"label": "This period", "align": "num"}],
            "rows": [["AI tool seats used weekly", use["display"]], ["AI tool spend in the period", cost["display"]]],
        }
        note = {
            "title": "What we do not claim",
            "body": ["Use and spend are inputs. This slide reports no productivity figure, because none has a baseline and a window yet."],
        }
        self.fill(
            "13",
            f"{use['display']} of AI tool seats are used weekly, at {cost['display']} for the period. We report no productivity figure.",
            [table, {"type": "cards", "columns": 1, "items": [note]}],
            [use["ledger"], cost["ledger"]],
            self.systems("ai_tools"),
        )

    def stopped(self) -> None:
        items = self.intake.get("stopped") or []
        if not items:
            return
        cards = [{"title": x["what"], "body": [x.get("why") or "No reason recorded."]} for x in items]
        self.fill(
            "15",
            f"We stopped {plural(len(items), 'thing')} this period.",
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
        if gaps:
            items.append({"title": "Not reported", "body": [f"{plural(len(gaps), 'slide')} lack data this period: {', '.join(gaps)}."]})
        title = self.slides["11"]["title"] if "11" in self.filled else points[0][0]
        self.fill(
            "01",
            title,
            [{"type": "cards", "columns": 3 if len(items) == 3 else 2, "items": items}],
            [ref for _, ref in points[:4]],
            f"Data as of {self.intake['as_of']}. Status words: landed, watch, stalled.",
        )

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
        self.fill("16", f"{plural(len(bets), 'bet')}, each with an appetite and a stop rule.", [table], [], "Bets as stated in the intake interview.")

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
        self.fill("14", f"{plural(len(risks), 'risk')}, each with an owner and a date.", [table], [], "Risk register as stated in the intake interview.")

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
            f"{plural(len(asks), 'decision')} to make at this meeting.",
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
            footer=f"{intake['company']} product & engineering update, {intake['period']['label']}. Built on the Dacard template.",
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
            self.outcomes,
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
        deck["ledger"] = self.m["ledger"]
        deck["meta"]["cuts"] = {
            a["key"]: [s["id"] for s in deck["slides"] if s["kind"] == "slide" and a["key"] in s["audiences"]] for a in deck["meta"]["audiences"]
        }
        return deck


def main() -> int:
    ap = argparse.ArgumentParser(description="Draft the deck from the intake and the computed metrics.")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()
    run = Path(args.run)
    for name in ("intake.json", "metrics.json"):
        if not (run / name).exists():
            raise SystemExit(f"draft: {run / name} is missing. Run intake.py, collect.py and compute_metrics.py first.")
    draft = Draft(run)
    deck = draft.build()
    out = run / "deck.json"
    out.write_text(json.dumps(deck, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    core = [s for s in deck["slides"] if s["kind"] == "slide"]
    with_data = ", ".join(x.lstrip("0") for x in draft.filled) or "none"
    print(f"draft: wrote {out}. {len(draft.filled)} of {len(core)} slides have data ({with_data}). The rest show data needed.")
    print("draft: next, improve the titles without changing what they claim, then run validate.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
