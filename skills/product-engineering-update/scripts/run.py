#!/usr/bin/env python3
"""One command from data to a rendered deck.

Usage:
  python3 scripts/run.py --run run [the 7 required answers] [data files] [--staff] [--board --signed-off-by "Name"]

It asks only for the 7 answers a run cannot start without (company, period label, start and end,
as-of date, who owns the gaps and by when), or takes them as arguments. Everything else in the
intake is optional and shows as a gap until it is answered. Then it runs, in order:

  collect      every --csv SOURCE=FILE, and the GitHub and Vercel exports if given
  compute      compute_metrics.py
  draft        draft.py
  validate     validate.py, stopping on any error
  render       the full deck, plus the Staff and Board cuts if asked for

The board cut still needs --signed-off-by with a named person's explicit yes. The 7 separate
scripts stay available as the long way; this calls the same scripts' entry points, in this process.

Standard library only. Runs on Python 3.9 or later. It makes no network calls.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intake as intake_mod  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]

# The 7 answers a run cannot start without, as (intake path, flag, question).
REQUIRED = [
    ("company", "--company", "Company name"),
    ("period.label", "--period-label", "Period label, for example 2026-Q4"),
    ("period.start", "--period-start", "Period start (YYYY-MM-DD)"),
    ("period.end", "--period-end", "Period end (YYYY-MM-DD)"),
    ("as_of", "--as-of", "Data as of (YYYY-MM-DD)"),
    ("gap_owner", "--gap-owner", "Who owns the gaps"),
    ("gap_due", "--gap-due", "When the gaps are due"),
]


def step(name: str, *args: str) -> str:
    """Run one of the skill's scripts in this process, with its own arguments. Stop the run with its own message if it fails."""
    module = importlib.import_module(name.removesuffix(".py"))
    entry = module.run if name == "collect.py" else module.main
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    sys.argv = [name, *args]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = entry()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        err.write(str(e.code) if e.code and not isinstance(e.code, int) else "")
    finally:
        sys.argv = saved
    if code:
        raise SystemExit(f"run: {name} stopped the run.\n{(out.getvalue() + err.getvalue()).strip()}")
    return out.getvalue().strip()


def put(d: Json, path: str, value: str) -> None:
    keys = path.split(".")
    for k in keys[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def answer_required(intake: Json, args: argparse.Namespace, ask: bool) -> list[str]:
    """Fill the 7 required answers from the arguments, then by asking. Returns what is still missing."""
    missing = []
    for path, flag, question in REQUIRED:
        given = getattr(args, flag.lstrip("-").replace("-", "_"))
        if given:
            put(intake, path, given)
        if not intake_mod.is_unknown(intake_mod.get(intake, path)):
            continue
        if ask:
            reply = input(f"{question}: ").strip()
            if reply:
                put(intake, path, reply)
                continue
        missing.append(flag)
    return missing


def pairs(values: list[str], flag: str) -> list[tuple[str, str]]:
    out = []
    for v in values:
        if "=" not in v:
            raise SystemExit(f"run: {flag} takes SOURCE=FILE, for example {flag} tracker=linear.csv. Got {v!r}.")
        out.append(tuple(v.split("=", 1)))  # type: ignore[arg-type]
    return out  # type: ignore[return-value]


def collect_all(args: argparse.Namespace, run: Path) -> list[str]:
    done = []
    dated = ["--retrieved-at", args.retrieved_at] if args.retrieved_at else []
    for source, path in pairs(args.csv, "--csv"):
        system = dict(pairs(args.system, "--system")).get(source, "CSV export")
        done.append(step("collect.py", source, "--csv", path, "--system", system, "--query", "CSV export supplied by the user", *dated, "--run", str(run)))
    if args.github_prs:
        if not args.repo:
            raise SystemExit("run: --github-prs needs --repo OWNER/NAME, for the ledger.")
        deploys = ["--deployments", args.github_deployments] if args.github_deployments else []
        done.append(step("from_github.py", "--prs", args.github_prs, *deploys, "--repo", args.repo, *dated, "--run", str(run)))
    if args.vercel_deployments:
        if not args.vercel_project:
            raise SystemExit("run: --vercel-deployments needs --vercel-project NAME, for the ledger.")
        if args.vercel_errors and not args.vercel_errors_from:
            raise SystemExit("run: --vercel-errors needs --vercel-errors-from, the first day the error reports cover.")
        errors = ["--errors", *args.vercel_errors, "--errors-from", args.vercel_errors_from] if args.vercel_errors else []
        done.append(step("from_vercel.py", "--deployments", *args.vercel_deployments, *errors, "--project", args.vercel_project, *dated, "--run", str(run)))
    return done


def summary(deck: Json) -> tuple[list[str], list[str]]:
    core = [s for s in deck["slides"] if s["kind"] == "slide"]
    gaps = [s["id"] for s in core if "is not reported this period" in s["title"]]
    return [s["id"] for s in core if s["id"] not in gaps], gaps


def main() -> int:
    ap = argparse.ArgumentParser(description="One command from data to a rendered deck.")
    ap.add_argument("--run", default="run", help="the run folder (default: run)")
    for _, flag, question in REQUIRED:
        ap.add_argument(flag, help=question)
    ap.add_argument("--no-ask", action="store_true", help="never prompt; stop if a required answer is missing")
    ap.add_argument("--csv", action="append", default=[], metavar="SOURCE=FILE", help="a CSV export for one source; repeat for each")
    ap.add_argument("--system", action="append", default=[], metavar="SOURCE=NAME", help="the system a CSV came from, for the ledger")
    ap.add_argument("--github-prs", help="merged pull requests, as GitHub returns them")
    ap.add_argument("--github-deployments", help="deployments, as GitHub returns them")
    ap.add_argument("--repo", help="owner/name of the GitHub repository")
    ap.add_argument("--vercel-deployments", nargs="+", help="production deployments, as Vercel returns them")
    ap.add_argument("--vercel-errors", nargs="*", default=[], help="runtime error reports, as Vercel returns them")
    ap.add_argument("--vercel-errors-from", help="YYYY-MM-DD, the first day the error reports cover")
    ap.add_argument("--vercel-project", help="the Vercel project name")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD, the day the data was pulled")
    ap.add_argument("--staff", action="store_true", help="also render the Staff cut")
    ap.add_argument("--board", action="store_true", help="also render the Board cut (needs --signed-off-by)")
    ap.add_argument("--signed-off-by", help="the named person who gave an explicit yes to the board cut")
    args = ap.parse_args()
    started = time.monotonic()

    if args.board and not (args.signed_off_by or "").strip():
        raise SystemExit("run: the board cut needs --signed-off-by with the name of the person who said yes to it, asked now.")
    run = Path(args.run)
    run.mkdir(parents=True, exist_ok=True)
    path = run / "intake.json"
    intake: Json = intake_mod.read_intake(path) if path.exists() else json.loads(json.dumps(intake_mod.EMPTY))
    missing = answer_required(intake, args, ask=not args.no_ask and sys.stdin.isatty())
    path.write_text(json.dumps(intake, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if missing:
        raise SystemExit(f"run: still needed before the run can start: {', '.join(missing)}. Pass them, or run in a terminal to be asked.")
    blocking, unknown = intake_mod.check(intake)
    if blocking:
        raise SystemExit("run: the intake has blocking problems:\n  " + "\n  ".join(blocking))

    for line in collect_all(args, run):
        print(line)
    print(step("compute_metrics.py", "--run", str(run)))
    step("draft.py", "--run", str(run))
    print(step("validate.py", str(run / "deck.json")))
    outputs = [step("render.py", str(run / "deck.json"), "--out", str(run / "update.html"))]
    if args.staff:
        outputs.append(step("render.py", str(run / "deck.json"), "--out", str(run / "staff.html"), "--cut", "S"))
    if args.board:
        outputs.append(step("render.py", str(run / "deck.json"), "--out", str(run / "board.html"), "--cut", "B", "--signed-off-by", args.signed_off_by))
    for line in outputs:
        print(line)

    deck = json.loads((run / "deck.json").read_text(encoding="utf-8"))
    data, gaps = summary(deck)
    print(f"run: {len(data)} of {len(data) + len(gaps)} slides show data ({', '.join(x.lstrip('0') for x in data) or 'none'}).")
    print(f"run: {len(gaps)} show a gap with an owner and a date ({', '.join(x.lstrip('0') for x in gaps) or 'none'}).")
    if unknown:
        print(f"run: {len(unknown)} intake answers are still open; `intake.py check {path}` lists them and the slide each would fill.")
    if not args.board:
        print("run: the board cut was not rendered. It needs a named person's explicit yes: add --board --signed-off-by NAME.")
    print(f"run: done in {time.monotonic() - started:.1f}s. Titles are plain drafts; improve them in deck.json, then validate and render again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
