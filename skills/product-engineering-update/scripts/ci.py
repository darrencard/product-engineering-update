#!/usr/bin/env python3
"""The GitHub Action's run step: a team's own data in, the Leadership and Staff cuts out.

Usage (the Action calls it; it also runs on a laptop):
  python3 scripts/ci.py --intake .update/intake.json --data-dir .update \\
      --prs prs.json --deployments deployments.json --repo owner/name --out deck-out

What it does, in order:
  1. Copies the team's intake into a fresh run folder. The copy is never written back: an answer
     the intake does not hold stays a gap. Nothing is inferred and nothing is filled in.
  2. Passes every CSV in the data folder named after a source (tracker.csv, incidents.csv, ...)
     to collect, and the GitHub exports to the GitHub converter.
  3. Runs run.py, which computes, drafts and validates, and stops on any validator error.
  4. Renders the Leadership and Staff cuts. It never renders the Board cut, which needs a named
     person's explicit yes that a scheduled job cannot give.
  5. Writes the two cuts, their ledgers, deck.json and a one-line summary to --out.

The exports are made by the Action with the workflow's own token, inside the team's CI. This
script reads files and writes files. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import intake as intake_mod  # noqa: E402
import render  # noqa: E402
import run as run_mod  # noqa: E402

CUTS = {"L": "leadership.html", "S": "staff.html"}


def call(entry, *args: str) -> str:
    """Run a script's entry point with its own arguments. Stop with its message if it fails."""
    out, err = io.StringIO(), io.StringIO()
    saved, sys.argv = sys.argv, ["ci", *args]
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = entry()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        err.write("" if isinstance(e.code, int) or e.code is None else str(e.code))
    finally:
        sys.argv = saved
    if code:
        raise SystemExit(f"ci: the run stopped.\n{(out.getvalue() + err.getvalue()).strip()}")
    return out.getvalue().strip()


def has_rows(path: Path) -> bool:
    """Whether a GitHub export holds anything. `gh api --paginate` writes pages back to back, so any non-empty array counts."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(ch not in "[] \n\r\t" for ch in text)


def csv_sources(data_dir: Path, github: bool) -> list[str]:
    """--csv SOURCE=FILE for each CSV in the folder named after a source. Other files are left alone. A
    source_control.csv is skipped when the GitHub exports supply that source, so it is never counted twice."""
    if not data_dir.is_dir():
        return []
    found = sorted(p for p in data_dir.glob("*.csv") if p.stem in collect.SOURCES and not (github and p.stem == "source_control"))
    return [f"--csv={p.stem}={p}" for p in found]


def main() -> int:
    ap = argparse.ArgumentParser(description="The GitHub Action's run step.")
    ap.add_argument("--intake", default=".update/intake.json", help="the team's intake (default: .update/intake.json)")
    ap.add_argument("--data-dir", default=".update", help="a folder of CSV exports named after their source (default: .update)")
    ap.add_argument("--prs", help="merged pull requests, as `gh pr list --json` wrote them")
    ap.add_argument("--deployments", help="deployments, as `gh api .../deployments --paginate` wrote them")
    ap.add_argument("--repo", help="owner/name, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD, the day the exports were made")
    ap.add_argument("--out", default="deck-out", help="where the two cuts are written")
    args = ap.parse_args()

    source = Path(args.intake)
    if not source.exists():
        raise SystemExit(f"ci: {source} does not exist. Add the team's intake there first: references/github-action.md says how.")
    blocking, unknown = intake_mod.check(intake_mod.read_intake(source))
    if blocking:
        raise SystemExit("ci: the intake cannot start a run yet. A scheduled job does not fill answers:\n  " + "\n  ".join(blocking))

    work = Path(tempfile.mkdtemp(prefix="peu-ci-"))
    try:
        shutil.copy(source, work / "intake.json")
        exported = [Path(x) for x in (args.prs, args.deployments) if x]
        github = bool(args.prs) and any(has_rows(x) for x in exported)
        flags = ["--run", str(work), "--no-ask", *csv_sources(Path(args.data_dir), github)]
        if args.retrieved_at:
            flags += ["--retrieved-at", args.retrieved_at]
        if args.prs and not github:
            print("ci: the repository has no merged pull requests or deployments to read, so delivery shows as a gap.")
        elif args.prs:
            if not args.repo:
                raise SystemExit("ci: --prs needs --repo OWNER/NAME, for the ledger.")
            flags += ["--github-prs", args.prs, "--repo", args.repo]
            if args.deployments:
                flags += ["--github-deployments", args.deployments]
        log = call(run_mod.main, *flags)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for cut, name in CUTS.items():
            call(render.main, str(work / "deck.json"), "--out", str(out / name), "--cut", cut)
        shutil.copy(work / "deck.json", out / "deck.json")
        summary = next((line for line in log.splitlines() if " slides show data" in line), "run: done.")
        (out / "SUMMARY.txt").write_text(
            f"{summary}\n{len(unknown)} intake answer(s) still open. The Board cut is not rendered here: it needs a named person's yes.\n",
            encoding="utf-8",
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(log)
    print(f"ci: wrote {', '.join(CUTS.values())}, their ledgers and deck.json to {out}. The Board cut was not rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
