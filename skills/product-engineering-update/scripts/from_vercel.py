#!/usr/bin/env python3
"""Turn raw Vercel exports into a quality signal for the source_control source.

Usage:
  python3 scripts/from_vercel.py --deployments deployments.json --errors errors-week1.md errors-week2.md \\
      --errors-from 2026-11-02 --project dacard-www --run run

Inputs are what Vercel already gives you, saved to a file as it stands:
  --deployments   production deployments, from the Vercel connector's list_deployments
                  (target production) or `vercel api /v6/deployments`. One file per page.
  --errors        optional: runtime error groups, from the connector's get_runtime_errors
                  (its markdown report) or the same data as JSON. One file per window.
  --errors-from   the first day the error files cover. Deploys before it are left Unknown.
  --rollbacks     optional: deployment IDs that were rolled back, as JSON (a list of IDs, or
                  objects with a deploymentId or id field), one file per page.

It warns when the deployments or error reports supplied start after the reporting period, or the
one before it, begins (read from run/intake.json): deploys outside them stay Unknown.

What it derives, in code, for each production deploy that was live:
  troubled   yes when the deploy was rolled back, or a runtime error group was first seen
             while it was the live deployment (between it and the next production deploy).

This is a proxy for change failure rate, and is named as one on the slide. A runtime error
is not always a failed change, and an error that predates a deploy is not counted against it.
It is never relabelled change failure rate.

If run/data/source_control.json already exists (from from_github.py), its rows are kept and each
of its deploys that matches a Vercel deploy within 10 minutes takes the flag. Deploys Vercel has
no record for stay Unknown, so the rate is over the deploys it can speak for. Otherwise the
Vercel deploys become the deploy rows.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]

# A GitHub deployment and the Vercel deployment it records are created within moments of each other.
MATCH_WINDOW = datetime.timedelta(minutes=10)
LIVE_STATES = {"READY"}
FIRST_SEEN = re.compile(r"\bfirst=(\S+)")


def fail(message: str) -> SystemExit:
    return SystemExit(f"from_vercel: {message}")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise fail(f"cannot read {path} ({e}). Save the export as a UTF-8 file and run this again.") from None


def unwrap(value: Any) -> list[Json]:
    """The deployment list, whether it is bare or wrapped the way the connector and the API return it."""
    while isinstance(value, dict):
        for key in ("result", "deployments"):
            if key in value:
                value = value[key]
                break
        else:
            break
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise fail("a deployments file must hold a list of deployments, as Vercel returns it.")
    return value


def stamp(value: Any) -> datetime.datetime:
    """Vercel gives milliseconds since the epoch; other exports give ISO text."""
    if isinstance(value, (int, float)):
        return datetime.datetime.fromtimestamp(value / 1000, tz=datetime.timezone.utc)
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def read_deployments(paths: list[Path]) -> list[Json]:
    found: dict[str, Json] = {}
    for path in paths:
        try:
            rows = unwrap(json.loads(read_text(path)))
        except json.JSONDecodeError as e:
            raise fail(f"{path} is not valid JSON ({e.msg} at character {e.pos}). Save the export again without editing it.") from None
        for d in rows:
            created = d.get("created") or d.get("createdAt")
            if d.get("id") and created is not None:
                found[d["id"]] = d  # pages can overlap; one row per deployment
    live = [d for d in found.values() if str(d.get("target", "")).lower() == "production" and (d.get("state") or d.get("readyState")) in LIVE_STATES]
    return sorted(live, key=lambda d: stamp(d.get("created") or d.get("createdAt")))


def read_error_times(paths: list[Path]) -> list[datetime.datetime]:
    """When each runtime error group was first seen, from the connector's report or from JSON."""
    times: list[datetime.datetime] = []
    for path in paths:
        text = read_text(path)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            times += [stamp(m) for m in FIRST_SEEN.findall(text)]
            continue
        groups = data if isinstance(data, list) else data.get("errors") or data.get("groups") or []
        for g in groups:
            first = g.get("first") or g.get("firstSeen") or g.get("first_seen") if isinstance(g, dict) else None
            if first:
                times.append(stamp(first))
    return times


def read_rollbacks(paths: list[Path]) -> set[str]:
    """Rolled-back deployment IDs from every page given: a list of IDs, or objects with deploymentId or id."""
    found: set[str] = set()
    for path in paths:
        try:
            data = json.loads(read_text(path))
        except json.JSONDecodeError as e:
            raise fail(f"{path} is not valid JSON ({e.msg}).") from None
        items = data if isinstance(data, list) else (data.get("events") or data.get("rollbacks") or []) if isinstance(data, dict) else []
        found |= {x if isinstance(x, str) else str(x.get("deploymentId") or x.get("id")) for x in items if x}
    return found


def coverage_warnings(run: Path, deploys: list[Json], since: datetime.date | None) -> list[str]:
    """What the exports leave uncovered in the reporting period and the one before, read from the intake."""
    path = run / "intake.json"
    try:
        period = json.loads(path.read_text(encoding="utf-8")).get("period") or {}
        start, end = datetime.date.fromisoformat(period["start"]), datetime.date.fromisoformat(period["end"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return []
    prior_start = start - (end - start) - datetime.timedelta(days=1)
    first = stamp(deploys[0].get("created") or deploys[0].get("createdAt")).date()
    out = []
    if first > prior_start:
        which = "the reporting period" if first > start else "the prior period"
        out.append(
            f"WARNING the deployments supplied start on {first}, after {which} starts ({start if first > start else prior_start}). "
            "Deploys before then stay Unknown. Export every page back to that date; if Vercel holds no older deployments, say so on the slide."
        )
    if since and since > prior_start:
        out.append(f"WARNING the error reports start on {since}, after the prior period starts ({prior_start}). Deploys before {since} stay Unknown.")
    return out


def flags(
    deploys: list[Json], errors: list[datetime.datetime], rollbacks: set[str], since: datetime.date | None
) -> list[tuple[datetime.datetime, bool | None]]:
    """Each live deploy's time and whether it was troubled, or None where the exports cannot say."""
    out: list[tuple[datetime.datetime, bool | None]] = []
    times = [stamp(d.get("created") or d.get("createdAt")) for d in deploys]
    for i, (d, start) in enumerate(zip(deploys, times)):
        end = times[i + 1] if i + 1 < len(times) else None
        if since is None or start.date() < since:
            out.append((start, True if d["id"] in rollbacks else None))
            continue
        errored = any(start <= t and (end is None or t < end) for t in errors)
        out.append((start, d["id"] in rollbacks or errored))
    return out


def as_rows(flagged: list[tuple[datetime.datetime, bool | None]], deploys: list[Json]) -> list[Json]:
    return [
        {
            "kind": "deploy",
            "id": f"vercel-{d['id']}",
            "opened_at": "",
            "merged_at": "",
            "review_hours": "",
            "deployed_at": t.isoformat(),
            "failed": "",
            "reworked": "",
            "troubled": "" if flag is None else ("yes" if flag else "no"),
        }
        for (t, flag), d in zip(flagged, deploys)
    ]


def merge(existing: Json, flagged: list[tuple[datetime.datetime, bool | None]]) -> tuple[list[Json], int]:
    """Give each existing deploy the flag of the Vercel deploy it matches. Returns (rows, matched)."""
    rows, matched = [], 0
    free = list(range(len(flagged)))  # each Vercel deploy matches at most one existing deploy
    for row in existing["rows"]:
        row = dict(row)
        if row["kind"] == "deploy" and row.get("deployed_at"):
            at = stamp(row["deployed_at"])
            near = min(free, key=lambda i: abs(flagged[i][0] - at), default=None)
            if near is not None and abs(flagged[near][0] - at) <= MATCH_WINDOW:
                free.remove(near)
                row["troubled"] = flagged[near][1]
                matched += flagged[near][1] is not None
        rows.append({k: ("" if v is None else ("yes" if v is True else "no" if v is False else v)) for k, v in row.items()})
    return rows, matched


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw Vercel exports into a quality signal for the source_control source.")
    ap.add_argument("--deployments", nargs="+", required=True, help="production deployments as JSON, one file per page")
    ap.add_argument("--errors", nargs="*", default=[], help="runtime error reports, one file per window")
    ap.add_argument("--errors-from", help="YYYY-MM-DD, the first day the error files cover")
    ap.add_argument("--rollbacks", nargs="*", default=[], help="rolled-back deployment IDs as JSON, one file per page (optional)")
    ap.add_argument("--project", required=True, help="the Vercel project name, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first deployments file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    if args.errors and not args.errors_from:
        raise fail("--errors needs --errors-from, the first day the error files cover, so older deploys are not counted as clean.")
    since = datetime.date.fromisoformat(args.errors_from) if args.errors_from else None
    deploys = read_deployments([Path(p) for p in args.deployments])
    if not deploys:
        raise fail("found no live production deployments. Export with target production, then run this again.")
    rollbacks = read_rollbacks([Path(p) for p in args.rollbacks])
    if not args.errors and not rollbacks:
        raise fail("supply --errors or --rollbacks. Deployments alone say nothing about quality.")
    flagged = flags(deploys, read_error_times([Path(p) for p in args.errors]), rollbacks, since)

    out = Path(args.run) / "data" / "source_control.json"
    retrieved = collect.retrieved_date(args.retrieved_at, args.deployments[0])
    what = "Vercel list_deployments (target production)" + ("; get_runtime_errors" if args.errors else "") + ("; rollbacks" if rollbacks else "")
    system = f"Vercel ({args.project})"
    known = sum(1 for _, f in flagged if f is not None)
    if out.exists():
        existing = json.loads(out.read_text(encoding="utf-8"))
        rows, matched = merge(existing, flagged)
        data = collect.collect(
            "source_control", rows, f"{existing['system']} + {system}", f"{existing.get('query_or_url') or ''}; {what}", retrieved, existing["origin"]
        )
        print(f"from_vercel: {len(deploys)} live production deploys, {known} with a known outcome; {matched} matched deploys in {out}.")
    else:
        data = collect.collect("source_control", as_rows(flagged, deploys), system, what, retrieved, Path(args.deployments[0]).name)
        print(f"from_vercel: {len(deploys)} live production deploys, {known} with a known outcome, written to {out}.")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    troubled = sum(1 for _, f in flagged if f)
    print(f"from_vercel: {troubled} rolled back or followed by errors. This is a proxy for change failure rate, labelled as one.")
    if not rollbacks:
        print("from_vercel: no rollback data supplied, so only runtime errors count.")
    for warning in coverage_warnings(Path(args.run), deploys, since):
        print(f"from_vercel: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
