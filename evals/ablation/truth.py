"""Recompute the headline figures of one fixture straight from its CSVs, without the skill's code.

This is the answer key for the arithmetic check. It is written apart from compute_metrics.py on
purpose, so a shared bug cannot make the skill look right. Where a metric has more than one fair
definition (a median or a mean, 13 weeks or the exact days), every variant is kept and a printed
figure counts as correct if it matches any of them.

Standard library only.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import statistics
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def rows(fixture: Path, name: str) -> list[dict[str, str]]:
    path = fixture / "csv" / f"{name}.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(x: str | None) -> float | None:
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def day(x: str) -> dt.date:
    return dt.date.fromisoformat(x[:10])


def stamp(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x)


def windows(intake: Json) -> tuple[dt.date, dt.date, dt.date, dt.date]:
    start = dt.date.fromisoformat(intake["period"]["start"])
    end = dt.date.fromisoformat(intake["period"]["end"])
    span = end - start
    p_end = start - dt.timedelta(days=1)
    return start, end, p_end - span, p_end


def prior_label(label: str) -> str:
    year, q = label.split("-Q")
    q_i = int(q) - 1
    return f"{int(year) - 1}-Q4" if q_i == 0 else f"{year}-Q{q_i}"


def add(out: dict[str, Json], key: str, label: str, values: list[float | None], prior: list[float | None] | None = None, unit: str = "") -> None:
    vals = [v for v in values if v is not None]
    if not vals:
        return
    out[key] = {"label": label, "values": sorted(set(round(v, 6) for v in vals)), "unit": unit}
    if prior:
        pv = [v for v in prior if v is not None]
        if pv:
            out[key]["prior"] = sorted(set(round(v, 6) for v in pv))


def pct(a: float, b: float) -> float | None:
    return 100.0 * a / b if b else None


def recompute(fixture: Path) -> dict[str, Json]:
    """Every headline figure this fixture's data supports, keyed by a short name."""
    intake = json.loads((fixture / "intake.json").read_text(encoding="utf-8"))
    start, end, p_start, p_end = windows(intake)
    label = intake["period"]["label"]
    plabel = prior_label(label)
    out: dict[str, Json] = {}

    def in_window(d: dt.date, a: dt.date, b: dt.date) -> bool:
        return a <= d <= b

    # Source control: deploys, change failure, lead time, review time, rework.
    sc = rows(fixture, "source_control")
    if sc:
        stats = {}
        for name, a, b in (("now", start, end), ("prior", p_start, p_end)):
            deploys = [r for r in sc if r["kind"] == "deploy" and r["deployed_at"] and in_window(day(r["deployed_at"]), a, b)]
            prs = [r for r in sc if r["kind"] == "pull_request" and r["merged_at"] and in_window(day(r["merged_at"]), a, b)]
            lead = [(stamp(r["merged_at"]) - stamp(r["opened_at"])).total_seconds() / 3600 for r in prs if r["opened_at"]]
            review = [num(r["review_hours"]) for r in prs if num(r["review_hours"]) is not None]
            days = (b - a).days + 1
            stats[name] = {
                "deploys": len(deploys),
                "per_week": [len(deploys) / (days / 7), len(deploys) / 13] if deploys else [],
                "cfr": [pct(sum(r["failed"] == "yes" for r in deploys), len(deploys))] if deploys else [],
                "lead": [statistics.median(lead), statistics.mean(lead)] if lead else [],
                "review": [statistics.median(review), statistics.mean(review)] if review else [],  # type: ignore[type-var]
                "rework": [pct(sum(r["reworked"] == "yes" for r in prs), len(prs))] if prs else [],
                "prs": len(prs),
            }
        n, p = stats["now"], stats["prior"]
        add(out, "deploys_count", "Deploys in the period", [n["deploys"]], [p["deploys"]], "count")
        add(out, "deploys_per_week", "Deploys per week", n["per_week"], p["per_week"], "per week")
        add(out, "change_failure_rate", "Change failure rate", n["cfr"], p["cfr"], "%")
        add(out, "lead_time", "Lead time for change", n["lead"], p["lead"], "h")
        add(out, "review_time", "Pull request review time", n["review"], p["review"], "h")
        add(out, "rework_rate", "Rework rate", n["rework"], p["rework"], "%")
        add(out, "prs_merged", "Pull requests merged", [n["prs"]], [p["prs"]], "count")

    inc = rows(fixture, "incidents")
    if inc:

        def restore(a: dt.date, b: dt.date) -> list[float]:
            mins = [(stamp(r["restored_at"]) - stamp(r["started_at"])).total_seconds() / 60 for r in inc if in_window(day(r["started_at"]), a, b)]
            return [statistics.median(mins), statistics.mean(mins)] if mins else []

        add(out, "time_to_restore", "Time to restore", restore(start, end), restore(p_start, p_end), "m")
        add(out, "incidents", "Incidents", [sum(in_window(day(r["started_at"]), start, end) for r in inc)], None, "count")

    # Billing: ARR at the last month of each window, retention on accounts that paid before.
    bill = rows(fixture, "billing")
    if bill:
        now_m, prior_m = end.strftime("%Y-%m"), p_end.strftime("%Y-%m")
        cur = {r["account"]: num(r["arr"]) or 0.0 for r in bill if r["month"] == now_m}
        old = {r["account"]: num(r["arr"]) or 0.0 for r in bill if r["month"] == prior_m}
        arr, arr_p = sum(cur.values()), sum(old.values())
        add(out, "arr", "ARR", [arr], [arr_p], "$")
        add(out, "arr_growth", "ARR growth over the period", [pct(arr - arr_p, arr_p)], None, "%")
        add(out, "arr_change", "ARR added over the period", [arr - arr_p], None, "$")
        base = sum(old.values())
        kept = sum(cur.get(a, 0.0) for a in old)
        add(out, "nrr", "Net revenue retention", [pct(kept, base)], None, "%")
        add(out, "grr", "Gross revenue retention", [pct(sum(min(cur.get(a, 0.0), v) for a, v in old.items()), base)], None, "%")
        add(out, "expansion_arr", "Expansion ARR", [sum(max(cur.get(a, 0.0) - v, 0.0) for a, v in old.items())], None, "$")
        add(out, "churned_arr", "Churned or contracted ARR", [sum(max(v - cur.get(a, 0.0), 0.0) for a, v in old.items())], None, "$")
        add(out, "new_arr", "New-logo ARR", [sum(v for a, v in cur.items() if a not in old)], None, "$")
        add(out, "accounts", "Paying accounts", [sum(v > 0 for v in cur.values())], [sum(v > 0 for v in old.values())], "count")

    # Product analytics and a warehouse that may disagree with it.
    for source in ("analytics", "warehouse"):
        for metric in sorted({r["metric"] for r in rows(fixture, source)}):
            now = [num(r["value"]) for r in rows(fixture, source) if r["metric"] == metric and r["period"] == label]
            before = [num(r["value"]) for r in rows(fixture, source) if r["metric"] == metric and r["period"] == plabel]
            add(out, f"{source}:{metric}", f"{metric} ({source})", now, before)

    fin = rows(fixture, "finance")
    # Where finance also reports ARR, the two sources disagree; either one, named, is a true figure.
    fin_arr = [num(r["actual"]) for r in fin if r["line"] == "ARR"]
    if fin_arr and "arr" in out:
        out["arr"]["values"] = sorted(set(out["arr"]["values"] + [round(v, 6) for v in fin_arr if v is not None]))
    for r in fin:
        add(out, f"finance:{r['line']}", f"{r['line']} actual (finance)", [num(r["actual"])], None, "$")
        add(out, f"finance_plan:{r['line']}", f"{r['line']} plan (finance)", [num(r["plan"])], None, "$")
    revenue = next((num(r["actual"]) for r in fin if r["line"] == "Revenue"), None)
    rd_lines = set(intake.get("rd_lines") or [])
    rd = sum(num(r["actual"]) or 0.0 for r in fin if r["line"] in rd_lines)
    if revenue and rd:
        add(out, "rd_share", "R&D as a share of revenue", [pct(rd, revenue)], None, "%")
        add(out, "rd_spend", "R&D spend", [rd], None, "$")

    ev = rows(fixture, "evals")
    for r in ev:
        add(out, f"eval_pass:{r['version']}", f"Eval pass rate, {r['version']}", [pct(num(r["passed"]) or 0, num(r["cases"]) or 0)], None, "%")
        add(out, f"cost_per_task:{r['version']}", f"Cost per task, {r['version']}", [num(r["cost_per_task"])], None, "$")

    ai = [r for r in rows(fixture, "ai_tools") if r["period"] == label]
    if ai:
        add(out, "ai_tool_cost", "AI tool spend", [sum(num(r["cost"]) or 0 for r in ai)], None, "$")
        seats = sum(num(r["seats"]) or 0 for r in ai)
        per_tool = [pct(num(r["weekly_active"]) or 0, num(r["seats"]) or 0) for r in ai]
        add(out, "ai_weekly_use", "AI seats used weekly, in all or per tool", [pct(sum(num(r["weekly_active"]) or 0 for r in ai), seats), *per_tool], None, "%")

    hr = rows(fixture, "hr")
    if hr:
        add(out, "headcount", "Headcount, in all or per function", [sum(num(r["now"]) or 0 for r in hr), *(num(r["now"]) for r in hr)], None, "count")
        add(
            out,
            "headcount_plan",
            "Headcount plan, in all or per function",
            [sum(num(r["plan"]) or 0 for r in hr), *(num(r["plan"]) for r in hr)],
            None,
            "count",
        )

    sv = rows(fixture, "survey")
    for q in sorted({r["question"] for r in sv}):
        add(
            out,
            f"survey:{q}",
            q,
            [num(r["score"]) for r in sv if r["question"] == q and r["period"] == label],
            [num(r["score"]) for r in sv if r["question"] == q and r["period"] == plabel],
            "score",
        )

    crm = rows(fixture, "crm")
    if crm:
        won = sum(r["outcome"] == "won" for r in crm)
        add(out, "deals_won", "Deals won", [won], None, "count")
        add(out, "win_rate", "Win rate", [pct(won, len(crm))], None, "%")

    # Tracker: completed work in the period, by estimate and by count.
    tr = [r for r in rows(fixture, "tracker") if r["status"].lower() == "done" and r["completed_at"] and in_window(day(r["completed_at"]), start, end)]
    if tr:
        total_est = sum(num(r["estimate"]) or 0 for r in tr)
        add(out, "items_done", "Tracker items completed", [len(tr)], None, "count")
        for wt in sorted({r["work_type"] for r in tr}):
            sel = [r for r in tr if r["work_type"] == wt]
            add(out, f"mix:{wt}", f"Share of work: {wt}", [pct(sum(num(r["estimate"]) or 0 for r in sel), total_est), pct(len(sel), len(tr))], None, "%")
        traced = [r for r in tr if (r.get("objective") or "").strip()]
        add(
            out, "traced_pct", "Work tied to an objective", [pct(sum(num(r["estimate"]) or 0 for r in traced), total_est), pct(len(traced), len(tr))], None, "%"
        )

    req = [r for r in rows(fixture, "customer_requests") if r["created_at"] and in_window(day(r["created_at"]), start, end)]
    if req:
        add(out, "customer_requests", "Customer requests in the period", [len(req)], None, "count")
    return out


if __name__ == "__main__":
    import sys

    print(json.dumps(recompute(Path(sys.argv[1])), indent=1))
