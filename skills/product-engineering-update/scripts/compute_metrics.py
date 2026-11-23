#!/usr/bin/env python3
"""Do all the arithmetic and write the ledger. The model never does arithmetic.

Usage:
  python3 scripts/compute_metrics.py --run run

Reads run/intake.json and every run/data/<source>.json that collect.py wrote.
Writes run/metrics.json: each computed metric with its prior value, its
display text and the ID of its ledger row, plus the ledger itself.

Rules it holds to:
  - A source that was not collected produces no metric. It stays Unknown.
  - When two sources disagree on the same figure, the figure is recorded as a
    conflict with confidence Unknown. Neither value is chosen.
  - Values read straight from the owning system are Verified. Values
    computed here are Derived.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import statistics
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Json = dict[str, Any]

# The investment mix slide says to explain any variance over 3 points, so a
# work type more than 3 points over plan is marked over.
VARIANCE_POINTS = 3
# Two sources agree when they are within half a percent: enough to absorb rounding, not a real gap.
CONFLICT_TOLERANCE = 0.005
# The win and loss slide and the support slide each show the five most common reasons; a longer list stops being a summary.
TOP_REASONS = 5


def read_json(path: Path, fix: str) -> Any:
    """Load a JSON file, or exit with one line that says what to do about it."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        raise SystemExit(f"compute: {path} is not UTF-8 text. {fix}") from None
    except json.JSONDecodeError as e:
        raise SystemExit(f"compute: {path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}). {fix}") from None
    except OSError as e:
        raise SystemExit(f"compute: cannot read {path} ({e.strerror}). {fix}") from None


def day(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s[:10])


def money(v: float) -> str:
    a = abs(v)
    if a >= 1e6:
        return f"${trim(v / 1e6, 1 if a >= 1e7 else 2)}M"
    if a >= 1e3:
        return f"${trim(v / 1e3, 0)}K"
    return f"${trim(v, 2)}"


def trim(v: float, places: int) -> str:
    s = f"{v:.{places}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def show(v: float | None, unit: str) -> str | None:
    if v is None:
        return None
    if unit == "$":
        return money(v)
    if unit == "%":
        return f"{trim(v, 1)}%"
    if unit == "h":
        # Under an hour reads as minutes; "0h" would hide a real figure.
        return f"{trim(v * 60, 0)}m" if abs(v) < 1 else f"{trim(v, 0)}h"
    if unit == "m":
        return f"{trim(v, 0)}m"
    if unit == "count" and abs(v) >= 10000:
        return f"{trim(v / 1000, 1)}K"
    if unit in ("count", "per week", "score"):
        return trim(v, 1)
    return f"{trim(v, 2)} {unit}"


def rounded(v: float | None) -> float | None:
    """A value as the ledger stores it: four decimal places, or None when there is no value."""
    return None if v is None else round(v, 4)


class Run:
    """One run directory: the intake, the collected data, and the metrics and ledger built from them."""

    def __init__(self, run_dir: str | Path) -> None:
        self.dir = Path(run_dir)
        intake_path = self.dir / "intake.json"
        if not intake_path.exists():
            raise SystemExit(f"compute: {run_dir}/intake.json is missing. Run intake.py first.")
        self.intake: Json = read_json(intake_path, "Fix it, then check it with `intake.py check`.")
        period = self.intake.get("period") if isinstance(self.intake, dict) else None
        if not (isinstance(period, dict) and period.get("start") and period.get("end") and period.get("label")):
            raise SystemExit("compute: the intake has no period. Set period.label, period.start and period.end.")
        try:
            self.start, self.end = day(period["start"]), day(period["end"])
        except (TypeError, ValueError):
            raise SystemExit("compute: period.start and period.end must be dates (YYYY-MM-DD). Fix them, then check with `intake.py check`.") from None
        length = self.end - self.start
        self.prior_end = self.start - datetime.timedelta(days=1)
        self.prior_start = self.prior_end - length
        self.label: str = period["label"]
        self.metrics: dict[str, Json] = {}
        self.ledger: list[Json] = []
        self.conflicts: list[Json] = []
        self.extra: Json = {}
        self._data: dict[str, Json | None] = {}

    @property
    def data_dir(self) -> Path:
        return self.dir / "data"

    def collected(self) -> list[str]:
        """The sources that have a data file, by key."""
        return sorted(p.stem for p in self.data_dir.glob("*.json")) if self.data_dir.is_dir() else []

    def data(self, source: str) -> Json | None:
        """What collect.py wrote for a source, or None when the source was not collected."""
        if source not in self._data:
            self._data[source] = self._read_data(source)
        return self._data[source]

    def _read_data(self, source: str) -> Json | None:
        path = self.data_dir / f"{source}.json"
        if not path.exists():
            return None
        fix = f"Run collect.py for {source} again to rewrite it."
        src = read_json(path, fix)
        rows = src.get("rows") if isinstance(src, dict) else None
        if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows) or not isinstance(src.get("system"), str):
            raise SystemExit(f"compute: {path} is not a file collect.py wrote (it needs a system and a list of rows). {fix}")
        return src

    def in_period(self, stamp: str | None, prior: bool = False) -> bool:
        if not stamp:
            return False
        d = day(stamp)
        return (self.prior_start <= d <= self.prior_end) if prior else (self.start <= d <= self.end)

    def window(self, prior: bool = False) -> str:
        a, b = (self.prior_start, self.prior_end) if prior else (self.start, self.end)
        return f"{a.isoformat()} to {b.isoformat()}"

    def row(self, claim: str, value: float | None, unit: str | None, src: Json, confidence: str, window: str | None = None) -> str:
        """Add a ledger row and return its ID."""
        lid = f"L{len(self.ledger) + 1:02d}"
        self.ledger.append(
            {
                "id": lid,
                "claim": claim,
                "value": value,
                "unit": unit,
                "source_system": src["system"],
                "query_or_url": src.get("query_or_url"),
                "window": window or self.window(),
                "retrieved_at": src.get("retrieved_at"),
                "confidence": confidence,
                "owner": None,
            }
        )
        return lid

    def metric(
        self, key: str, label: str, value: float | None, prior: float | None, unit: str, src: Json, confidence: str = "Derived", higher_is_better: bool = True
    ) -> None:
        if value is None:
            return
        text = show(value, unit)
        lid = self.row(f"{label} {text}", round(value, 4), unit, src, confidence)
        self.metrics[key] = {
            "label": label,
            "value": round(value, 4),
            "prior": rounded(prior),
            "unit": unit,
            "display": text,
            "prior_display": show(prior, unit),
            "ledger": lid,
            "source": src["source"],
            "higher_is_better": higher_is_better,
        }


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def pct(part: float, whole: float) -> float | None:
    return None if not whole else 100.0 * part / whole


def hours_between(a: str, b: str) -> float:
    return (datetime.datetime.fromisoformat(b) - datetime.datetime.fromisoformat(a)).total_seconds() / 3600.0


def total_by(rows: Iterable[Json], key: str, amount: str) -> dict[str, float]:
    """Sum one column, grouped by another. Rows with nothing in the grouping column are left out."""
    totals: dict[str, float] = {}
    for x in rows:
        if x.get(key):
            totals[x[key]] = totals.get(x[key], 0) + x[amount]
    return totals


def share_flagged(rows: list[Json], flag: str) -> float | None:
    """The percent of rows with a flag set, or None when no row records the flag at all."""
    if not rows or all(x[flag] is None for x in rows):
        return None
    return pct(sum(1 for x in rows if x[flag]), len(rows))


def said(values: Iterable[tuple[str, str]], between: str = ", ") -> str:
    """Who says what, for a disagreement: "Stripe says $10.9M, NetSuite says $10.1M"."""
    return between.join(f"{system} says {value}" for system, value in values)


def tracker(r: Run) -> None:
    src = r.data("tracker")
    if not src:
        return
    plan = r.intake.get("investment_plan") or {}
    done = [x for x in src["rows"] if r.in_period(x["completed_at"])]
    total = sum(x["estimate"] for x in done)
    if not total:
        return
    by_type = total_by(done, "work_type", "estimate")
    labels = list(plan) + [t for t in sorted(by_type) if t not in plan]
    mix = []
    for label in labels:
        actual = round(pct(by_type.get(label, 0), total))
        planned = plan.get(label)
        mix.append({"label": label, "plan": planned, "actual": actual, "over": planned is not None and actual - planned > VARIANCE_POINTS})
    lid = r.row("Capacity split by work type: " + ", ".join(f"{m['label']} {m['actual']}%" for m in mix), None, "%", src, "Derived")
    r.extra["mix"] = {"rows": mix, "ledger": lid, "has_plan": bool(plan)}
    traced = sum(x["estimate"] for x in done if x.get("objective"))
    r.metric("traced_pct", "Capacity traced to an objective", pct(traced, total), None, "%", src)
    lines = total_by(done, "product_line", "estimate")
    if lines:
        r.extra["capacity_by_line"] = {k: round(pct(v, total)) for k, v in sorted(lines.items())}


def source_control(r: Run) -> None:
    src = r.data("source_control")
    if not src:
        return
    weeks = max(((r.end - r.start).days + 1) / 7.0, 1.0)

    def stats(prior: bool) -> dict[str, float | None]:
        deploys = [x for x in src["rows"] if x["kind"] == "deploy" and r.in_period(x["deployed_at"], prior)]
        prs = [x for x in src["rows"] if x["kind"] == "pull_request" and r.in_period(x["merged_at"], prior)]
        return {
            "deploys": len(deploys) / weeks if deploys else None,
            "cfr": share_flagged(deploys, "failed"),
            "lead": median([hours_between(x["opened_at"], x["merged_at"]) for x in prs if x["opened_at"]]),
            "review": median([x["review_hours"] for x in prs if x["review_hours"] is not None]),
            "rework": share_flagged(prs, "reworked"),
        }

    now, before = stats(False), stats(True)
    r.metric("deploys_per_week", "Deploys per week", now["deploys"], before["deploys"], "per week", src)
    r.metric("lead_time", "Lead time for change", now["lead"], before["lead"], "h", src, higher_is_better=False)
    r.metric("change_failure_rate", "Change failure rate", now["cfr"], before["cfr"], "%", src, higher_is_better=False)
    r.metric("review_time", "Pull request review time", now["review"], before["review"], "h", src, higher_is_better=False)
    r.metric("rework_rate", "Rework rate", now["rework"], before["rework"], "%", src, higher_is_better=False)


def incidents(r: Run) -> None:
    src = r.data("incidents")
    if not src:
        return

    def restore(prior: bool) -> float | None:
        rows = [x for x in src["rows"] if r.in_period(x["started_at"], prior)]
        return median([hours_between(x["started_at"], x["restored_at"]) * 60 for x in rows])

    r.metric("time_to_restore", "Time to restore", restore(False), restore(True), "m", src, higher_is_better=False)


def billing(r: Run) -> None:
    src = r.data("billing")
    if not src:
        return
    end_month, prior_month = r.end.strftime("%Y-%m"), r.prior_end.strftime("%Y-%m")
    cur = {x["account"]: x["arr"] for x in src["rows"] if x["month"] == end_month}
    old = {x["account"]: x["arr"] for x in src["rows"] if x["month"] == prior_month}
    if not cur:
        return
    arr, arr_old = sum(cur.values()), (sum(old.values()) if old else None)
    r.metric("arr", "ARR", arr, arr_old, "$", src)
    if old and arr_old:
        kept = sum(cur.get(a, 0) for a in old)
        r.metric("nrr", "Net revenue retention", pct(kept, arr_old), None, "%", src)
        r.metric("grr", "Gross revenue retention", pct(sum(min(cur.get(a, 0), v) for a, v in old.items()), arr_old), None, "%", src)
        r.metric("expansion_arr", "Expansion ARR in period", sum(max(cur.get(a, 0) - v, 0) for a, v in old.items()), None, "$", src)


def owner_of(r: Run, metric: str) -> str | None:
    """The source the user named as owning a figure, from source_of_truth in the intake. Only the user can name it."""
    return (r.intake.get("source_of_truth") or {}).get(metric)


def owned_by(src: Json, owner: str) -> bool:
    return owner.lower() in (src["source"].lower(), src["system"].lower())


def unit_for(r: Run, metric: str) -> str:
    """The unit the intake gives a metric, such as "%". Analytics rows carry bare numbers."""
    wanted = [r.intake.get("north_star") or {}, *(r.intake.get("inputs") or [])]
    return next((w["unit"] for w in wanted if w.get("metric") == metric and w.get("unit")), "count")


def analytics(r: Run) -> None:
    """Analytics and warehouse rows are the same shape; a disagreement between them is a conflict."""
    found: dict[str, dict[str, list[tuple[float, Json]]]] = {}
    for source in ("analytics", "warehouse"):
        src = r.data(source)
        for x in src["rows"] if src else []:
            found.setdefault(x["metric"], {}).setdefault(x["period"], []).append((x["value"], src))
    r.extra["analytics_metrics"] = []
    for name in sorted(found):
        periods = found[name]
        if r.label not in periods:
            continue
        values = periods[r.label]
        distinct = sorted({v for v, _ in values})
        unit = unit_for(r, name)
        disagree = len(distinct) > 1 and (distinct[-1] - distinct[0]) > CONFLICT_TOLERANCE * abs(distinct[-1])
        owner = owner_of(r, name)
        owned = [(v, s) for v, s in values if owner and owned_by(s, owner)]
        if disagree and owned:
            # The user named the owning source. Use it, and keep the other reading on the ledger row.
            others = said((s["system"], trim(v, 2)) for v, s in values if not owned_by(s, owner or ""))
            earlier = sorted(p for p in periods if p < r.label)
            prior_owned = [v for v, s in periods[earlier[-1]] if owned_by(s, owner or "")] if earlier else []
            value, src = owned[0]
            r.metric("analytics:" + name, name, value, prior_owned[0] if prior_owned else None, unit, src, "Verified")
            r.ledger[-1]["claim"] += f" ({src['system']} owns this figure, named in the intake; {others})"
            r.extra["analytics_metrics"].append("analytics:" + name)
            continue
        if disagree:
            r.conflicts.append({"metric": name, "values": [{"source": s["system"], "value": v} for v, s in values]})
            lid = r.row(f"{name}: sources disagree ({said((s['system'], trim(v, 2)) for v, s in values)})", None, None, values[0][1], "Unknown")
            r.metrics["analytics:" + name] = {
                "label": name,
                "value": None,
                "prior": None,
                "unit": "count",
                "display": None,
                "prior_display": None,
                "ledger": lid,
                "source": "analytics",
                "conflict": True,
                "higher_is_better": True,
            }
            continue
        earlier = sorted(p for p in periods if p < r.label)
        prior = periods[earlier[-1]][0][0] if earlier else None
        value, src = values[0]
        r.metric("analytics:" + name, name, value, prior, unit, src, "Verified")
        r.extra["analytics_metrics"].append("analytics:" + name)


def finance(r: Run) -> None:
    src = r.data("finance")
    if not src:
        return
    rows = [x for x in src["rows"] if x["period"] == r.label]
    if not rows:
        return
    # ARR is a balance, not spend. It is read here only to check it against billing, never shown as a spend line.
    spend = [x for x in rows if x["line"].lower() != "arr"]
    if spend:
        lid = r.row("Plan and actual spend by line: " + ", ".join(f"{x['line']} {money(x['actual'])}" for x in spend), None, "$", src, "Verified")
        r.extra["finance"] = {"rows": [{"line": x["line"], "plan": money(x["plan"]), "actual": money(x["actual"])} for x in spend], "ledger": lid}
    by_line = {x["line"].lower(): x for x in rows}
    rd_lines = [line.lower() for line in (r.intake.get("rd_lines") or [])]
    revenue = by_line.get("revenue")
    if revenue and rd_lines and all(line in by_line for line in rd_lines):
        rd_spend = sum(by_line[line]["actual"] for line in rd_lines)
        r.metric("rd_share", "R&D as a share of revenue", pct(rd_spend, revenue["actual"]), None, "%", src, higher_is_better=False)
    stated = by_line.get("arr")
    billed = r.metrics.get("arr")
    if stated and billed and abs(stated["actual"] - billed["value"]) > CONFLICT_TOLERANCE * abs(billed["value"]):
        bsrc = r.data("billing")
        owner = owner_of(r, "ARR")
        row = next(x for x in r.ledger if x["id"] == billed["ledger"])
        if owner and owned_by(bsrc, owner):
            row["claim"] += f" ({bsrc['system']} owns this figure, named in the intake; {src['system']} says {money(stated['actual'])})"
            return
        if owner and owned_by(src, owner):
            row.update(
                claim=f"ARR {money(stated['actual'])} ({src['system']} owns this figure, named in the intake; {bsrc['system']} says {money(billed['value'])})",
                value=rounded(stated["actual"]),
                source_system=src["system"],
                query_or_url=src.get("query_or_url"),
                retrieved_at=src.get("retrieved_at"),
                confidence="Verified",
            )
            billed.update(value=rounded(stated["actual"]), prior=None, display=money(stated["actual"]), prior_display=None, source=src["source"])
            return
        views = [{"source": bsrc["system"], "value": billed["value"]}, {"source": src["system"], "value": stated["actual"]}]
        r.conflicts.append({"metric": "ARR", "values": views})
        claim = f"ARR: sources disagree ({said([(bsrc['system'], money(billed['value'])), (src['system'], money(stated['actual']))])})"
        for row in r.ledger:
            if row["id"] == billed["ledger"]:
                row.update(claim=claim, value=None, confidence="Unknown")
        billed.update(value=None, display=None, conflict=True)


def evals(r: Run) -> None:
    src = r.data("evals")
    if not src:
        return
    runs = sorted(src["rows"], key=lambda x: x["run_at"])
    last, before = runs[-1], (runs[-2] if len(runs) > 1 else None)
    prior_rate = pct(before["passed"], before["cases"]) if before else None
    r.metric("eval_pass_rate", f"Eval pass rate ({last['version']})", pct(last["passed"], last["cases"]), prior_rate, "%", src)
    if last["cost_per_task"] is not None:
        prior_cost = before["cost_per_task"] if before else None
        r.metric("cost_per_task", "Cost per successful task", last["cost_per_task"], prior_cost, "$", src, higher_is_better=False)


def ai_tools(r: Run) -> None:
    src = r.data("ai_tools")
    if not src:
        return
    rows = [x for x in src["rows"] if x["period"] == r.label]
    if not rows:
        return
    cost, seats, active = sum(x["cost"] for x in rows), sum(x["seats"] for x in rows), sum(x["weekly_active"] for x in rows)
    r.metric("ai_tool_cost", "AI tool spend in period", cost, None, "$", src, "Verified", higher_is_better=False)
    r.metric("ai_weekly_use", "Seats used weekly", pct(active, seats), None, "%", src)


def people(r: Run) -> None:
    src = r.data("hr")
    if not src:
        return
    as_of = r.intake.get("as_of")
    if not as_of:
        raise SystemExit("compute: the intake has no as_of date, and the headcount row needs one. Set as_of (YYYY-MM-DD), then run this again.")
    now, plan = sum(x["now"] for x in src["rows"]), sum(x["plan"] for x in src["rows"])
    # Headcount prints as whole people; int() drops the .0 that collect.py's numbers carry.
    lid = r.row(f"Headcount {int(now)} of {int(plan)}", now, "count", src, "Verified", f"As of {as_of}")
    r.extra["hr"] = {"rows": src["rows"], "now": now, "plan": plan, "ledger": lid}


def counts(r: Run, source: str, column: str, key: str, label: str) -> None:
    src = r.data(source)
    if not src:
        return
    tally = Counter(x[column] for x in src["rows"])
    top = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_REASONS]
    lid = r.row(f"{label}: {', '.join(f'{name} ({n})' for name, n in top)}", len(src["rows"]), "count", src, "Derived")
    r.extra[key] = {"top": top, "total": len(src["rows"]), "ledger": lid}


def survey(r: Run) -> None:
    src = r.data("survey")
    if not src:
        return
    rows = [x for x in src["rows"] if x["period"] == r.label]
    if rows:
        earlier = sorted({x["period"] for x in src["rows"] if x["period"] < r.label})
        prior = [x["score"] for x in src["rows"] if earlier and x["period"] == earlier[-1]]
        score = statistics.mean(x["score"] for x in rows)
        r.metric("dev_experience", "Developer experience index", score, statistics.mean(prior) if prior else None, "score", src)


STEPS = (tracker, source_control, incidents, billing, analytics, finance, evals, ai_tools, people, survey)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute every metric and write the ledger.")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()
    r = Run(args.run)
    try:
        for step in STEPS:
            step(r)
        counts(r, "crm", "reason", "crm", "Win and loss reasons")
        counts(r, "support", "theme", "support", "Support themes")
    except KeyError as e:
        # collect.py writes every column of a source, so a missing one means the file was edited by hand or is from an older run.
        raise SystemExit(f"compute: a data file in {r.data_dir} has no {e} column. Run collect.py again for that source, then run this again.") from None
    collected = r.collected()
    out = {
        "period": {"label": r.label, "start": r.start.isoformat(), "end": r.end.isoformat()},
        "prior": {"start": r.prior_start.isoformat(), "end": r.prior_end.isoformat()},
        "collected": collected,
        "metrics": r.metrics,
        "extra": r.extra,
        "conflicts": r.conflicts,
        "ledger": r.ledger,
    }
    path = r.dir / "metrics.json"
    try:
        path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"compute: cannot write {path} ({e.strerror}). Check that the run folder is writable, then run this again.") from None
    print(f"compute: {len(r.metrics)} metric(s), {len(r.ledger)} ledger row(s), {len(r.conflicts)} conflict(s), from {', '.join(collected) or 'no sources'}.")
    for c in r.conflicts:
        views = said(((v["source"], trim(v["value"], 2)) for v in c["values"]), between="; ")
        print(f"  CONFLICT {c['metric']}: {views}. Recorded as Unknown. Ask which source owns the number.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
