#!/usr/bin/env python3
"""The mini eval: a small fixed run of the ablation eval on every release, for a trend between full reruns.

Claude with the skill (C) against Claude alone (A) on 2 fixed fixtures (complete, conflicting),
1 run each, pairs only, judged in both orders: 4 judgments. It costs about $5 (2 Claude-alone
decks at about $1.05, 2 with the skill at about $0.55, 4 judgments, 4 extractions) and takes
about 15 minutes. The fixture set never changes, so the trend compares like with like.

Each run appends one row to evals/ablation/trend.csv (committed) and says whether the release
regressed against the last row: the skill made an arithmetic error, or won fewer judgments.

  python3 evals/ablation/mini.py --version 0.9.0          # run it (calls the model, costs money)
  python3 evals/ablation/mini.py --version 0.8.0 --from-summary evals/ablation/measured/2026-11-25/summary.json

--from-summary adds a row from a run already on disk and calls nothing. Run from the repository
root in a terminal where `claude -p` is signed in (see README.md in this folder).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TREND = HERE / "trend.csv"
FIXTURES = "complete,conflicting"
EXPECTED_COST_USD = 5.0
FIELDS = (
    "date",
    "version",
    "fixtures",
    "judgments",
    "skill_wins",
    "claude_wins",
    "ties",
    "skill_gaps_wins",
    "claude_gaps_wins",
    "skill_arithmetic_errors",
    "skill_figures_checked",
    "claude_arithmetic_errors",
    "claude_figures_checked",
    "cost_usd",
)

Json = dict[str, Any]


def row_from(summary: Json, version: str, fixtures: str, day: str) -> Json:
    """One trend row from an ablation summary.json: the C against A matchup and the checks."""
    ca = summary["matchups"]["CA"]["per_judgment"]
    checks = summary["checks"]
    return {
        "date": day,
        "version": version,
        "fixtures": fixtures,
        "judgments": ca["overall"]["n"],
        "skill_wins": ca["overall"]["C"],
        "claude_wins": ca["overall"]["A"],
        "ties": ca["overall"]["tie"],
        "skill_gaps_wins": ca["gaps_shown"]["C"],
        "claude_gaps_wins": ca["gaps_shown"]["A"],
        "skill_arithmetic_errors": checks["C"]["arithmetic_errors"],
        "skill_figures_checked": checks["C"]["arithmetic_checked"],
        "claude_arithmetic_errors": checks["A"]["arithmetic_errors"],
        "claude_figures_checked": checks["A"]["arithmetic_checked"],
        "cost_usd": round(sum(stage.get("cost_usd", 0) for stage in summary["cost"].values() if isinstance(stage, dict)), 2),
    }


def share(row: Json) -> float:
    n = int(row["judgments"])
    return (int(row["skill_wins"]) + 0.5 * int(row["ties"])) / n if n else 0.0


def regressions(row: Json, last: Json | None) -> list[str]:
    """Why this release looks worse than the last comparable row, or nothing."""
    found = []
    if int(row["skill_arithmetic_errors"]):
        found.append(f"the skill made {row['skill_arithmetic_errors']} arithmetic error(s)")
    if last and last["fixtures"] == row["fixtures"] and share(row) < share(last):
        found.append(f"the skill's share of judgments fell from {share(last):.0%} to {share(row):.0%} (v{last['version']} to v{row['version']})")
    return found


def read_trend() -> list[Json]:
    if not TREND.exists():
        return []
    with TREND.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append(row: Json) -> None:
    new = not TREND.exists()
    with TREND.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the mini eval for a release and add it to the trend.")
    ap.add_argument("--version", required=True, help="the skill version under test, for example 0.9.0")
    ap.add_argument("--out", help="where the run goes (default: evals/ablation/results/mini-<version>)")
    ap.add_argument("--from-summary", help="add a row from an existing summary.json instead of running")
    ap.add_argument("--fixtures", default=FIXTURES, help="only with --from-summary: the fixtures that run covered, for example all")
    args = ap.parse_args()
    if args.from_summary:
        summary_path = Path(args.from_summary)
    else:
        out = Path(args.out or HERE / "results" / f"mini-{args.version}")
        print(f"mini: about ${EXPECTED_COST_USD:.0f} and 15 minutes; each call also has its own budget cap.", flush=True)
        cmd = [sys.executable, str(HERE / "ablation.py"), "all", "--out", str(out), "--fixtures", FIXTURES]
        cmd += ["--runs", "1", "--conditions", "AC", "--matchups", "CA", "--pairs-only", "--jobs", "4"]
        done = subprocess.run(cmd, env={**os.environ, "ABLATION_DROP_API_KEY": os.environ.get("ABLATION_DROP_API_KEY", "1")})  # noqa: S603  (fixed argv, no shell)
        if done.returncode != 0:
            print("mini: the eval stopped. Run the same command again; it resumes where it left off.", file=sys.stderr)
            return done.returncode
        summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    trend = read_trend()
    last = trend[-1] if trend else None
    if not args.from_summary and args.fixtures != FIXTURES:
        raise SystemExit("mini: the fixture set is fixed so the trend compares like with like. Leave --fixtures out.")
    row = row_from(summary, args.version, args.fixtures, datetime.date.today().isoformat())
    append(row)
    print(
        f"mini: v{row['version']}: the skill won {row['skill_wins']} of {row['judgments']} judgments "
        f"(Claude alone {row['claude_wins']}, ties {row['ties']}); gaps {row['skill_gaps_wins']} to {row['claude_gaps_wins']}; "
        f"arithmetic errors {row['skill_arithmetic_errors']} in {row['skill_figures_checked']} against "
        f"{row['claude_arithmetic_errors']} in {row['claude_figures_checked']}; ${row['cost_usd']}. Added to {TREND.name}."
    )
    problems = regressions(row, last)
    for p in problems:
        print(f"mini: REGRESSION: {p}.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
