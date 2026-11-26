#!/usr/bin/env python3
"""Write the synthetic company fixtures the evals run against.

Usage:
  python3 evals/make_fixtures.py

Five fixtures, each a directory with intake.json and a csv/ folder:
  complete         every source and a full intake
  sparse           one source and a thin intake
  single_product   one product line
  no_ai            no AI features in production
  conflicting      two pairs of sources that disagree

Kestrel Labs is fictional. Every figure here is made up for testing and is
generated from fixed inputs, so the files are the same on every run.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import copy
import csv
import datetime
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
Rows = list[dict[str, Any]]

START, END = datetime.date(2026, 7, 1), datetime.date(2026, 9, 30)
PRIOR_START = datetime.date(2026, 4, 1)
LABEL, PRIOR_LABEL = "2026-Q3", "2026-Q2"

# Work completed in the quarter: (work type, product line, share of 100 points, share tagged to an objective).
WORK = [
    ("New capabilities", "Dispatch Agent", 31, 31),
    ("Improve the core", "Core Dispatch", 18, 18),
    ("Growth", "Core Dispatch", 8, 8),
    ("Platform & scale", "Platform", 21, 21),
    ("Keep the lights on", "Platform", 22, 0),
]
PLAN = {"New capabilities": 35, "Improve the core": 20, "Growth": 10, "Platform & scale": 20, "Keep the lights on": 15}

INTAKE: dict[str, Any] = {
    "company": "Kestrel Labs",
    "author": "the CPTO",
    "period": {"label": LABEL, "start": START.isoformat(), "end": END.isoformat()},
    "as_of": END.isoformat(),
    "gap_owner": "the VP Engineering",
    "gap_due": "Q4",
    "objectives": [{"name": "Grow ARR to $50M", "target": "$50M", "owner": "CEO"}],
    "strategy": {
        "diagnosis": "Dispatchers lose most of their day to exceptions that rules engines can't handle.",
        "policy": "We win mid-market brokers by automating the exception, priced per load.",
        "actions": ["Raise agent task success to 90%", "First automated load inside 14 days"],
        "non_goals": ["Build a carrier marketplace", "Ship on-premise"],
    },
    "product_lines": [
        {"name": "Dispatch Agent", "stage": "Expand", "objective": "Grow ARR to $50M"},
        {"name": "Core Dispatch", "stage": "Sustain", "objective": "Grow ARR to $50M"},
        {"name": "Platform", "stage": "Sustain", "objective": "Grow ARR to $50M"},
    ],
    "investment_plan": PLAN,
    "rd_lines": ["R&D payroll", "AI tools for the team", "Cloud"],
    "north_star": {
        "metric": "Loads cleared per week",
        "definition": "Loads cleared with no manual touch",
        "target": 22000,
        "target_display": "22K",
        "owner": "Agent team",
    },
    "inputs": [
        {"metric": "Activation", "unit": "%", "target": 50, "target_display": "50%", "higher_is_better": True, "owner": "Activation team"},
        {"metric": "Weekly active dispatchers", "target": 6000, "target_display": "6,000", "higher_is_better": True, "owner": "Core dispatch"},
    ],
    "delivery_ranges": {
        "Deploys per week": "3+",
        "Lead time for change": "under 40h",
        "Change failure rate": "under 5%",
        "Time to restore": "under 60m",
        "Pull request review time": "under 10h",
    },
    "ai_features": [{"name": "Dispatch Agent", "eval_set": "v14"}],
    "bets": [
        {
            "bet": "Multi-stop reroutes",
            "commitment": "Promise",
            "appetite": "6 weeks, 5 engineers",
            "expected": "Task success 86% to 90%",
            "confidence": "High",
            "stop_rule": "Evals gain under 2 points by week 3",
            "objective": "Grow ARR to $50M",
            "cause": "Higher task success lets accounts move more loads to the agent",
            "owner": "Agent team",
        },
        {
            "bet": "Guided activation",
            "commitment": "Experiment",
            "appetite": "4 weeks, 3 engineers",
            "expected": "Activation 41% to 50%",
            "confidence": "Medium",
            "stop_rule": "No lift in a 2 week live test",
            "objective": "Grow ARR to $50M",
            "cause": "A faster first automated load lifts trial conversion",
            "owner": "Activation team",
        },
    ],
    "risks": [
        {
            "risk": "One model provider carries most inference spend",
            "likelihood": "Medium",
            "impact": "High",
            "mitigation": "Routing layer across 2 providers. Platform lead",
            "due": "Dec 2026",
        }
    ],
    "stopped": [{"what": "Carrier marketplace", "why": "It did not serve the strategy"}],
    "decisions": [
        {
            "ask": "Approve a per-load pricing pilot",
            "options": "Pilot with 10 customers, or wait a quarter",
            "recommendation": "Run the pilot with 10 customers.",
            "deadline": "4 Nov 2026",
        }
    ],
    # Last period's commitments, each with the outcome metric named before launch (slide 8).
    "commitments": [
        {"commitment": "Guided activation", "shipped": "yes", "metric": "Activation", "owner": "Activation team", "source": "Linear (Kestrel)"},
        {"commitment": "Multi-stop reroutes", "shipped": "yes", "metric": "Loads cleared per week", "owner": "Agent team", "source": "Linear (Kestrel)"},
        {"commitment": "Dispatcher inbox", "shipped": "yes", "metric": "Weekly active dispatchers", "owner": "Core dispatch", "source": "Linear (Kestrel)"},
        {"commitment": "Cheaper agent retries", "shipped": "yes", "metric": "Cost per successful task", "owner": "Agent team", "source": "Linear (Kestrel)"},
        {"commitment": "Release checklist", "shipped": "yes", "metric": "Change failure rate", "owner": "Platform", "source": "Linear (Kestrel)"},
        {"commitment": "Self-serve carrier onboarding", "shipped": "no", "metric": "Activation", "owner": "Activation team", "source": "Linear (Kestrel)"},
        {"commitment": "Audit log export", "shipped": "yes", "metric": None, "owner": "Platform", "source": "Linear (Kestrel)"},
    ],
    "connected": [],
}


def stamp(day: datetime.date, hour: int = 12) -> str:
    return f"{day.isoformat()}T{hour:02d}:00:00"


def tracker() -> Rows:
    rows: Rows = []
    for work_type, line, points, traced in WORK:
        for i in range(points):
            rows.append(
                {
                    "id": f"{work_type[:3].upper()}-{i + 1}",
                    "title": f"{work_type} item {i + 1}",
                    "work_type": work_type,
                    "status": "Done",
                    "estimate": 1,
                    "completed_at": (START + datetime.timedelta(days=(i * 3) % 90)).isoformat(),
                    "product_line": line,
                    "objective": "Grow ARR to $50M" if i < traced else "",
                    "owner": f"{line} team",
                }
            )
    return rows


def finance() -> Rows:
    lines = [
        ("Revenue", 10_000_000, 10_300_000),
        ("R&D payroll", 3_750_000, 3_700_000),
        ("Inference (cost of revenue)", 480_000, 612_000),
        ("AI tools for the team", 95_000, 90_000),
        ("Cloud", 400_000, 410_000),
    ]
    return [{"line": line, "period": LABEL, "plan": plan, "actual": actual} for line, plan, actual in lines]


def billing() -> Rows:
    rows: Rows = []
    for i in range(40):
        before = 240_000 + i * 1_000
        change = 1.20 if i < 15 else 1.0 if i < 36 else 0.0
        rows.append({"account": f"A{i + 1:03d}", "month": "2026-06", "arr": before})
        if change:
            rows.append({"account": f"A{i + 1:03d}", "month": "2026-09", "arr": round(before * change)})
    rows += [{"account": f"N{i + 1:02d}", "month": "2026-09", "arr": 150_000} for i in range(6)]
    return rows


def analytics() -> Rows:
    metrics = [
        ("Loads cleared per week", 18_400, 23_100, "Loads cleared with no manual touch, weekly average"),
        ("Activation", 39, 41, "Accounts with a first automated load inside 14 days, percent"),
        ("Weekly active dispatchers", 5_890, 6_120, "Dispatchers active in a week"),
    ]
    return [
        {"metric": m, "period": period, "value": value, "definition": d} for m, old, new, d in metrics for period, value in ((PRIOR_LABEL, old), (LABEL, new))
    ]


def source_control() -> Rows:
    rows: Rows = []
    for quarter, first, deploys, failed_every, review in (("p", PRIOR_START, 39, 20, 9.0), ("c", START, 52, 13, 13.0)):
        for i in range(deploys):
            day = first + datetime.timedelta(days=(i * 90) // deploys)
            rows.append(
                {
                    "kind": "deploy",
                    "id": f"D{quarter}{i}",
                    "opened_at": "",
                    "merged_at": "",
                    "review_hours": "",
                    "deployed_at": stamp(day),
                    "failed": "yes" if i % failed_every == 0 else "no",
                    "reworked": "",
                }
            )
        for i in range(60):
            opened = first + datetime.timedelta(days=(i * 85) // 60)
            lead_hours = 52 if quarter == "p" else 38
            merged = datetime.datetime.fromisoformat(stamp(opened, 9)) + datetime.timedelta(hours=lead_hours)
            rows.append(
                {
                    "kind": "pull_request",
                    "id": f"P{quarter}{i}",
                    "opened_at": stamp(opened, 9),
                    "merged_at": merged.isoformat(timespec="seconds"),
                    "review_hours": review,
                    "deployed_at": "",
                    "failed": "",
                    "reworked": "yes" if i % (9 if quarter == "p" else 7) == 0 else "no",
                }
            )
    return rows


def incidents() -> Rows:
    rows: Rows = []
    for quarter, first, minutes in (("p", PRIOR_START, 46), ("c", START, 41)):
        for i in range(5):
            started = datetime.datetime.fromisoformat(stamp(first + datetime.timedelta(days=10 + i * 15), 3))
            rows.append(
                {
                    "id": f"I{quarter}{i}",
                    "started_at": started.isoformat(timespec="seconds"),
                    "restored_at": (started + datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds"),
                    "severity": "Sev-2",
                }
            )
    return rows


def evals() -> Rows:
    return [
        {"version": "v13", "run_at": "2026-06-20", "cases": 500, "passed": 410, "cost_per_task": 0.41, "tasks": 12000, "tasks_unassisted": 7560},
        {"version": "v14", "run_at": "2026-09-22", "cases": 500, "passed": 430, "cost_per_task": 0.33, "tasks": 18400, "tasks_unassisted": 12880},
    ]


def ai_tools() -> Rows:
    return [
        {"tool": "Code assistant", "period": LABEL, "seats": 44, "weekly_active": 39, "cost": 66_000},
        {"tool": "Review agent", "period": LABEL, "seats": 44, "weekly_active": 27, "cost": 24_000},
    ]


def hr() -> Rows:
    return [
        {"function": "Engineering", "now": 44, "plan": 46, "open_roles": "1 platform, 1 product engineer"},
        {"function": "Product management", "now": 5, "plan": 5, "open_roles": ""},
        {"function": "Design", "now": 4, "plan": 5, "open_roles": "1 designer"},
    ]


def crm() -> Rows:
    reasons = [("won", "Agent clears exceptions")] * 22 + [("lost", "No TMS integration")] * 11 + [("lost", "Price")] * 6
    return [{"deal": f"DEAL-{i + 1}", "outcome": outcome, "reason": reason} for i, (outcome, reason) in enumerate(reasons)]


def support() -> Rows:
    themes = ["Integration errors"] * 30 + ["Onboarding"] * 18 + ["Billing"] * 7
    return [{"ticket": f"T{i + 1}", "theme": theme, "account": f"A{(i % 40) + 1:03d}"} for i, theme in enumerate(themes)]


def customer_requests() -> Rows:
    """Customer requests from Linear, each linked to an issue or project. One falls before the period and is not counted."""
    asks = [
        ("Multi-stop reroutes", "https://linear.app/kestrel/project/multi-stop-reroutes", ["Northwind", "Haulwell", "Bluepeak", "Northwind"]),
        ("KES-412 Bulk load import", "https://linear.app/kestrel/issue/KES-412", ["Haulwell", "Tidewater"]),
        ("KES-388 Carrier rating export", None, ["Bluepeak"]),
    ]
    rows: Rows = []
    for linked, link, customers in asks:
        for i, customer in enumerate(customers):
            rows.append(
                {"request": f"R-{len(rows) + 1:03d}", "customer": customer, "linked_to": linked, "link": link or "", "created_at": f"2026-08-{i + 3:02d}"}
            )
    rows.append({"request": "R-999", "customer": "Tidewater", "linked_to": "KES-388 Carrier rating export", "link": "", "created_at": "2026-05-02"})
    return rows


def survey() -> Rows:
    return [
        {"question": "Developer experience index", "period": PRIOR_LABEL, "score": 68},
        {"question": "Developer experience index", "period": LABEL, "score": 71},
    ]


ALL = {
    "tracker": tracker,
    "finance": finance,
    "billing": billing,
    "analytics": analytics,
    "source_control": source_control,
    "incidents": incidents,
    "evals": evals,
    "ai_tools": ai_tools,
    "hr": hr,
    "crm": crm,
    "support": support,
    "survey": survey,
    "customer_requests": customer_requests,
}
SYSTEMS = {
    "tracker": "Linear",
    "finance": "Finance close",
    "billing": "Stripe",
    "analytics": "PostHog",
    "warehouse": "Warehouse",
    "source_control": "GitHub",
    "incidents": "Incident tool",
    "evals": "Eval harness",
    "ai_tools": "Tool admin exports",
    "hr": "HR system",
    "crm": "CRM",
    "support": "Support desk",
    "survey": "Developer survey",
    "customer_requests": "Linear",
}


def write(name: str, intake: dict[str, Any], sources: dict[str, Rows], expect: dict[str, Any]) -> None:
    folder = FIXTURES / name
    (folder / "csv").mkdir(parents=True, exist_ok=True)
    for old in (folder / "csv").glob("*.csv"):
        old.unlink()
    intake = dict(intake, connected=sorted(sources))
    (folder / "intake.json").write_text(json.dumps(intake, indent=2) + "\n", encoding="utf-8")
    (folder / "expect.json").write_text(json.dumps(expect, indent=2) + "\n", encoding="utf-8")
    (folder / "systems.json").write_text(json.dumps({k: SYSTEMS[k] for k in sorted(sources)}, indent=2) + "\n", encoding="utf-8")
    for source, rows in sources.items():
        with (folder / "csv" / f"{source}.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def main() -> None:
    everything = {key: make() for key, make in ALL.items()}
    full = ["02", "03", "04", "05", "06", "07", "08", "09", "11", "12", "14", "16", "17", "18"]
    write("complete", INTAKE, everything, {"valid": True, "filled": full, "absent": [], "conflicts": [], "board_slides": 8})

    thin = copy.deepcopy(INTAKE)
    for key in (
        "strategy",
        "objectives",
        "product_lines",
        "investment_plan",
        "rd_lines",
        "inputs",
        "delivery_ranges",
        "bets",
        "risks",
        "stopped",
        "decisions",
        "commitments",
    ):
        thin[key] = {"diagnosis": None, "policy": None, "actions": [], "non_goals": []} if key == "strategy" else ({} if isinstance(thin[key], dict) else [])
    thin["north_star"] = {"metric": None, "definition": None, "target": None, "owner": None}
    write("sparse", thin, {"tracker": everything["tracker"]}, {"valid": True, "filled": [], "absent": [], "conflicts": [], "board_slides": 8, "min_gaps": 15})

    one = copy.deepcopy(INTAKE)
    one["product_lines"] = [{"name": "Dispatch Agent", "stage": "Expand", "objective": "Grow ARR to $50M"}]
    single = copy.deepcopy(everything)
    for row in single["tracker"]:
        row["product_line"] = "Dispatch Agent"
    write("single_product", one, single, {"valid": True, "filled": full, "absent": [], "conflicts": [], "board_slides": 8, "portfolio_rows": 1})

    no_ai = copy.deepcopy(INTAKE)
    no_ai["ai_features"] = []
    without = {k: v for k, v in everything.items() if k not in ("evals", "ai_tools")}
    write("no_ai", no_ai, without, {"valid": True, "filled": [s for s in full if s != "12"], "absent": ["12", "13"], "conflicts": [], "board_slides": 7})

    clash = copy.deepcopy(everything)
    clash["warehouse"] = [{"metric": "Loads cleared per week", "period": LABEL, "value": 21_400, "query": "select avg(loads) from ns_weekly"}]
    clash["finance"] = clash["finance"] + [{"line": "ARR", "period": LABEL, "plan": 11_000_000, "actual": 10_100_000}]
    write("conflicting", INTAKE, clash, {"valid": True, "filled": full, "absent": [], "conflicts": ["ARR", "Loads cleared per week"], "board_slides": 8})
    # The same clash, after the user has said which source owns each figure.
    settled = copy.deepcopy(INTAKE)
    settled["source_of_truth"] = {"ARR": "billing", "Loads cleared per week": "PostHog"}
    write("conflict_resolved", settled, clash, {"valid": True, "filled": full, "absent": [], "conflicts": [], "board_slides": 8})
    print(f"make_fixtures: wrote 6 fixtures to {FIXTURES}")


if __name__ == "__main__":
    main()
