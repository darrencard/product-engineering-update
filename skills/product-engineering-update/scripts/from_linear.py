#!/usr/bin/env python3
"""Turn raw Linear exports into the tracker source, with no retyping.

Usage:
  python3 scripts/from_linear.py --issues page1.json [page2.json ...] --work-type-prefix "type:" --run run

Inputs are what Linear already gives you, saved to a file as it stands, one file per page:
  - the Linear connector's list_issues result ({"issues": [...], "hasNextPage": ..., "cursor": ...}),
    asked for completed issues with the fields id, title, estimate, completedAt, statusType, labels,
    project and assignee; or
  - the Linear GraphQL API's response ({"data": {"issues": {"nodes": [...]}}}).

How each completed issue maps to a tracker row, in code:
  work_type     the label that starts with --work-type-prefix, without the prefix, or a label named
                in --work-type (repeat it: --work-type "Bug=Keep the lights on"). An issue with
                neither is "Unlabelled", so the untyped share shows instead of being guessed.
  estimate      Linear's estimate. An issue with no estimate is left out and counted, never given one.
  product_line  the issue's project.
  objective     the label that starts with --objective-prefix, without the prefix, if one is given.
  owner         the assignee.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]

UNLABELLED = "Unlabelled"


def fail(message: str) -> SystemExit:
    return SystemExit(f"from_linear: {message}")


def name_of(value: Any) -> str | None:
    """Linear's connector gives names as strings; its API gives objects with a name."""
    if isinstance(value, dict):
        return value.get("name") or value.get("displayName")
    return value if isinstance(value, str) and value else None


def labels_of(issue: Json) -> list[str]:
    raw = issue.get("labels") or []
    if isinstance(raw, dict):
        raw = raw.get("nodes") or []
    return [n for n in (name_of(x) for x in raw) if n]


def read_issues(paths: list[Path]) -> list[Json]:
    found: dict[str, Json] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise fail(f"cannot read {path} ({e}). Save the export as it stands, as UTF-8 JSON.") from None
        if isinstance(data, dict) and "data" in data:
            data = (data["data"] or {}).get("issues") or {}
        items = data.get("issues", data.get("nodes")) if isinstance(data, dict) else data
        if isinstance(items, dict):
            items = items.get("nodes")
        if not isinstance(items, list) or not all(isinstance(x, dict) for x in items):
            raise fail(f"{path} holds no list of issues, as Linear returns it.")
        for issue in items:
            key = issue.get("identifier") or issue.get("id")
            if key:
                found[str(key)] = issue  # pages can overlap; one row per issue
    return list(found.values())


def completed(issue: Json) -> bool:
    state = issue.get("state")
    kind = issue.get("statusType") or (state.get("type") if isinstance(state, dict) else None)
    return bool(issue.get("completedAt")) and kind in (None, "completed")


def with_prefix(labels: list[str], prefix: str | None) -> str | None:
    if not prefix:
        return None
    return next((x[len(prefix) :].strip() for x in labels if x.lower().startswith(prefix.lower()) and x[len(prefix) :].strip()), None)


def to_rows(issues: list[Json], type_prefix: str | None, type_map: dict[str, str], objective_prefix: str | None) -> tuple[list[Json], int]:
    rows, unestimated = [], 0
    for issue in issues:
        if not completed(issue):
            continue
        if issue.get("estimate") is None:
            unestimated += 1
            continue
        labels = labels_of(issue)
        mapped = next((type_map[x] for x in labels if x in type_map), None)
        rows.append(
            {
                "id": str(issue.get("identifier") or issue.get("id")),
                "title": issue.get("title") or "",
                "work_type": with_prefix(labels, type_prefix) or mapped or UNLABELLED,
                "status": name_of(issue.get("status")) or name_of(issue.get("state")) or "Done",
                "estimate": issue["estimate"],
                "completed_at": issue["completedAt"],
                "product_line": name_of(issue.get("project")) or "",
                "objective": with_prefix(labels, objective_prefix) or "",
                "owner": name_of(issue.get("assignee")) or "",
            }
        )
    return rows, unestimated


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw Linear exports into the tracker source.")
    ap.add_argument("--issues", nargs="+", required=True, help="completed issues as Linear returns them, one file per page")
    ap.add_argument("--work-type-prefix", help='the label prefix that names a work type, for example "type:"')
    ap.add_argument("--work-type", action="append", default=[], metavar="LABEL=TYPE", help="a label that stands for a work type; repeat it")
    ap.add_argument("--objective-prefix", help='the label prefix that names an objective, for example "objective:"')
    ap.add_argument("--workspace", default="Linear", help="the workspace or team name, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    type_map = {}
    for pair in args.work_type:
        if "=" not in pair:
            raise fail(f'--work-type takes LABEL=TYPE, for example --work-type "Bug=Keep the lights on". Got {pair!r}.')
        label, kind = pair.split("=", 1)
        type_map[label.strip()] = kind.strip()
    issues = read_issues([Path(p) for p in args.issues])
    rows, unestimated = to_rows(issues, args.work_type_prefix, type_map, args.objective_prefix)
    if not rows:
        extra = f" {unestimated} completed issue(s) had no estimate." if unestimated else ""
        raise fail(f"found no completed issues with an estimate.{extra} The tracker stays Unknown; do not create a file for it.")
    retrieved = collect.retrieved_date(args.retrieved_at, args.issues[0])
    query = "Linear list_issues (completed, with estimate, labels, project, assignee)"
    data = collect.collect("tracker", rows, f"Linear ({args.workspace})", query, retrieved, Path(args.issues[0]).name)
    out = Path(args.run) / "data" / "tracker.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    untyped = sum(1 for r in rows if r["work_type"] == UNLABELLED)
    print(f"from_linear: {len(rows)} completed issues with an estimate, written to {out}.")
    if unestimated:
        print(f"from_linear: {unestimated} completed issue(s) have no estimate and are left out. They are not given one.")
    if untyped:
        print(f'from_linear: {untyped} issue(s) carry no work-type label and count as "{UNLABELLED}".')
    return 0


if __name__ == "__main__":
    sys.exit(main())
