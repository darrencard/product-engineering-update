#!/usr/bin/env python3
"""Turn raw Sentry exports into a quality signal for the source_control source, for any host.

Usage:
  python3 scripts/from_sentry.py --releases releases-*.json --issues issues-*.json \\
      --errors-from 2026-10-01 --organization acme --run run

Inputs are what Sentry already gives you, saved as they stand, one file per page:
  --releases   GET /api/0/organizations/{org}/releases/ (each release carries its lastDeploy, with
               environment and dateFinished), from the Sentry connector or the API.
  --issues     GET /api/0/organizations/{org}/issues/?project=... (or an issue's details, which add
               firstRelease). Only issues at level error or fatal count, unless --levels says otherwise.
  --errors-from  the first day the issue export covers. Releases deployed before it stay Unknown.

What it derives, in code, for each release deployed to --environment (production by default):
  troubled   yes when an issue was first seen while that release was the live one (between its deploy
             and the next), or when Sentry names it as the issue's firstRelease.

This is a proxy for change failure rate, labelled as one ("Deploys rolled back or followed by errors"),
like the Vercel signal. A new error is not always a failed change. It is never relabelled change failure
rate. compute_metrics.py states its coverage on the slide.

Incidents: Sentry's public API documents no incident list (its alert incidents endpoint is not in the
API reference), so nothing goes to the incidents source. Use incident.io or PagerDuty for that.

If run/data/source_control.json exists (from from_github.py), its deploys take the flag of the Sentry
deploy within 10 minutes; others stay Unknown. Otherwise the Sentry deploys become the deploy rows.

This script reads files and writes files. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (sibling scripts, found through the path above)
import convert  # noqa: E402
import from_vercel  # noqa: E402

TOOL = "from_sentry"


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw Sentry exports into a quality signal for source control.")
    ap.add_argument("--releases", nargs="+", required=True, help="organization releases as Sentry returns them, one file per page")
    ap.add_argument("--issues", nargs="+", required=True, help="issues as Sentry returns them, one file per page")
    ap.add_argument("--errors-from", required=True, help="YYYY-MM-DD, the first day the issue export covers")
    ap.add_argument("--environment", default="production", help="the deploy environment that counts as a release (default production)")
    ap.add_argument("--levels", default="error,fatal", help="the issue levels that count (default error,fatal)")
    ap.add_argument("--organization", required=True, help="the Sentry organization, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first releases file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    since = datetime.date.fromisoformat(args.errors_from)
    wanted = args.environment.lower()
    deploys, seen = [], set()
    for r in convert.pages(args.releases, TOOL, "data", "releases"):
        last = r.get("lastDeploy") or {}
        at = convert.when(last.get("dateFinished"))
        if not at or str(last.get("environment", "")).lower() != wanted or r.get("version") in seen:
            continue
        seen.add(r["version"])
        deploys.append({"id": r["version"], "created": at.isoformat()})
    if not deploys:
        raise convert.fail(TOOL, f"found no release deployed to {args.environment}. Export releases with their lastDeploy, then run this again.")
    deploys.sort(key=lambda d: d["created"])

    levels = {x.strip().lower() for x in args.levels.split(",") if x.strip()}
    issues = [i for i in convert.pages(args.issues, TOOL, "data", "issues") if str(i.get("level", "")).lower() in levels]
    first_seen = [t for t in (convert.when(i.get("firstSeen")) for i in issues) if t]
    named = {(i.get("firstRelease") or {}).get("version") for i in issues if isinstance(i.get("firstRelease"), dict)} - {None}
    flagged = from_vercel.flags(deploys, first_seen, named & seen, since)

    out = Path(args.run) / "data" / "source_control.json"
    retrieved = collect.retrieved_date(args.retrieved_at, args.releases[0])
    what = f"Sentry releases (lastDeploy to {args.environment}) and issues (levels {','.join(sorted(levels))}) first seen after each"
    system = f"Sentry ({args.organization})"
    known = sum(1 for _, f in flagged if f is not None)
    if out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        rows, matched = from_vercel.merge(existing, flagged)
        data = collect.collect(
            "source_control", rows, f"{existing['system']} + {system}", f"{existing.get('query_or_url') or ''}; {what}", retrieved, existing["origin"]
        )
        print(f"{TOOL}: {len(deploys)} releases deployed to {args.environment}, {known} with a known outcome; {matched} matched deploys in {out}.")
    else:
        rows = [{**row, "id": f"sentry-{d['id']}"} for row, d in zip(from_vercel.as_rows(flagged, deploys), deploys)]
        data = collect.collect("source_control", rows, system, what, retrieved, Path(args.releases[0]).name)
        print(f"{TOOL}: {len(deploys)} releases deployed to {args.environment}, {known} with a known outcome, written to {out}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{TOOL}: {sum(1 for _, f in flagged if f)} followed by a new error. This is a proxy for change failure rate, labelled as one.")
    for warning in from_vercel.coverage_warnings(Path(args.run), deploys, since):
        print(f"{TOOL}: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
