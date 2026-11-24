#!/usr/bin/env python3
"""Turn raw Jira exports into the tracker source, and commitments where they map cleanly.

Usage:
  python3 scripts/from_jira.py --search page1.json [page2.json ...] --estimate-field customfield_10016 \\
      --work-type-from issuetype --run run
  python3 scripts/from_jira.py --csv jira.csv --estimate-field "Story Points" --work-type-from issuetype --run run

Inputs are what Jira already gives you, saved as they stand:
  --search   REST search results ({"issues": [{"key", "fields": {...}}], "startAt", "total"}), one file per
             page, from /rest/api/3/search or the Jira connector.
  --csv      Jira's CSV export, with its own column names (Issue key, Summary, Issue Type, Status,
             Resolved, Labels, Component/s, Assignee, Fix Version/s and the estimate column you name).

How a done issue maps to a tracker row, only from fields that exist:
  estimate      the field named by --estimate-field. An issue without it is left out and counted.
  work_type     --work-type-from issuetype, label or component, mapped with --work-type "Bug=Keep the
                lights on" where the team's names differ from the plan's. An issue without the field is
                "Unlabelled".
  product_line  --product-line-from component or project, if given.
  objective     the label after --objective-prefix, if given.
  completed_at  the resolution date. An issue resolved with no date is left out and counted.

Commitments (slide 8), with --commitments-from versions or epics and --period-start/--period-end:
  versions  a fix version released inside the period (shipped), or due inside it and not released.
  epics     an epic resolved inside the period (shipped), or due inside it and not resolved.
They go to run/jira/commitments.csv for intake.py import. Jira holds no target metric, so the metric
column is left empty for the person to fill before importing.

This script reads files and writes files. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]
UNLABELLED = "Unlabelled"
COMMITMENT_COLUMNS = ("commitment", "shipped", "metric", "owner", "source", "url", "status", "target date", "completed", "note")
# Jira's CSV column for each field the script reads. --estimate-field names the estimate column.
CSV_NAMES = {
    "key": "Issue key",
    "summary": "Summary",
    "issuetype": "Issue Type",
    "status": "Status",
    "resolved": "Resolved",
    "labels": "Labels",
    "components": "Component/s",
    "assignee": "Assignee",
    "project": "Project name",
    "duedate": "Due date",
}


def fail(message: str) -> SystemExit:
    return SystemExit(f"from_jira: {message}")


def day(value: Any) -> datetime.date | None:
    """Jira's dates: ISO (2026-10-14T09:30:00.000+0000) in JSON, or its CSV export's 14/Oct/26 9:30 AM."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%d/%b/%y %I:%M %p", "%d/%b/%Y %I:%M %p", "%d/%b/%y %H:%M", "%d/%b/%y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("displayName") or value.get("value") or "")
    return str(value) if value not in (None, "") else ""


def from_search(paths: list[Path], estimate_field: str) -> list[Json]:
    """One flat record per issue, keyed the same way as a CSV row, from REST search pages."""
    found: dict[str, Json] = {}
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise fail(f"cannot read {path} ({e}). Save Jira's response as it stands.") from None
        issues = data.get("issues") if isinstance(data, dict) else None
        if not isinstance(issues, list):
            raise fail(f"{path} holds no issues list, as Jira's search returns it.")
        for issue in issues:
            f = issue.get("fields") or {}
            status = f.get("status") or {}
            category = (status.get("statusCategory") or {}).get("key") if isinstance(status, dict) else None
            found[issue.get("key", "")] = {
                "key": issue.get("key", ""),
                "summary": f.get("summary") or "",
                "issuetype": name(f.get("issuetype")),
                "status": name(status),
                "done": category == "done",
                "resolved": f.get("resolutiondate"),
                "estimate": f.get(estimate_field),
                "labels": [str(x) for x in f.get("labels") or []],
                "components": [name(x) for x in f.get("components") or []],
                "assignee": name(f.get("assignee")),
                "project": name(f.get("project")),
                "duedate": f.get("duedate"),
                "versions": [
                    {"name": name(v), "released": bool(v.get("released")), "date": v.get("releaseDate")}
                    for v in f.get("fixVersions") or []
                    if isinstance(v, dict)
                ],
            }
    return list(found.values())


def from_csv(path: Path, estimate_field: str) -> list[Json]:
    """Jira's CSV export repeats a column for each label, component and version; every copy is read."""
    try:
        rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
    except (OSError, UnicodeDecodeError) as e:
        raise fail(f"cannot read {path} ({e}).") from None
    if not rows:
        raise fail(f"{path} is empty.")
    header = rows[0]
    missing = [c for c in (CSV_NAMES["key"], CSV_NAMES["status"], CSV_NAMES["resolved"], estimate_field) if c not in header]
    if missing:
        raise fail(f"{path} has no column {', '.join(repr(c) for c in missing)}. Export with those columns, or name the estimate column with --estimate-field.")

    def all_of(row: list[str], column: str) -> list[str]:
        return [row[i].strip() for i, h in enumerate(header) if h == column and i < len(row) and row[i].strip()]

    def one(row: list[str], column: str) -> str:
        values = all_of(row, column)
        return values[0] if values else ""

    out = []
    for row in rows[1:]:
        if not any(x.strip() for x in row):
            continue
        out.append(
            {
                "key": one(row, CSV_NAMES["key"]),
                "summary": one(row, CSV_NAMES["summary"]),
                "issuetype": one(row, CSV_NAMES["issuetype"]),
                "status": one(row, CSV_NAMES["status"]),
                "done": bool(one(row, CSV_NAMES["resolved"])),
                "resolved": one(row, CSV_NAMES["resolved"]),
                "estimate": one(row, estimate_field) or None,
                "labels": all_of(row, CSV_NAMES["labels"]),
                "components": all_of(row, CSV_NAMES["components"]),
                "assignee": one(row, CSV_NAMES["assignee"]),
                "project": one(row, CSV_NAMES["project"]),
                "duedate": one(row, CSV_NAMES["duedate"]),
                "versions": [{"name": v, "released": None, "date": None} for v in all_of(row, "Fix Version/s")],
            }
        )
    return out


def first_with(values: list[str], prefix: str) -> str:
    return next((v[len(prefix) :].strip() for v in values if v.lower().startswith(prefix.lower()) and v[len(prefix) :].strip()), "")


def to_rows(issues: list[Json], args: argparse.Namespace, type_map: dict[str, str]) -> tuple[list[Json], dict[str, int]]:
    rows, skipped = [], {"no estimate": 0, "no resolution date": 0}
    for i in issues:
        if not i["done"]:
            continue
        if day(i["resolved"]) is None:
            skipped["no resolution date"] += 1
            continue
        if i["estimate"] in (None, ""):
            skipped["no estimate"] += 1
            continue
        source = {"issuetype": [i["issuetype"]] if i["issuetype"] else [], "label": i["labels"], "component": i["components"]}[args.work_type_from]
        raw = next((type_map[v] for v in source if v in type_map), None) or (source[0] if source else "")
        if args.work_type_from == "label" and args.work_type_prefix:
            raw = first_with(i["labels"], args.work_type_prefix) or raw
        line = {"component": i["components"][0] if i["components"] else "", "project": i["project"], None: ""}[args.product_line_from]
        rows.append(
            {
                "id": i["key"],
                "title": i["summary"],
                "work_type": raw or UNLABELLED,
                "status": i["status"] or "Done",
                "estimate": i["estimate"],
                "completed_at": day(i["resolved"]).isoformat(),
                "product_line": line,
                "objective": first_with(i["labels"], args.objective_prefix) if args.objective_prefix else "",
                "owner": i["assignee"],
            }
        )
    return rows, skipped


def commitments(issues: list[Json], kind: str, start: datetime.date, end: datetime.date) -> list[Json]:
    out: dict[str, Json] = {}
    if kind == "versions":
        for i in issues:
            for v in i["versions"]:
                due = day(v["date"])
                if v["released"] is None or due is None or not (start <= due <= end):
                    continue
                out[v["name"]] = {
                    "commitment": v["name"],
                    "shipped": "yes" if v["released"] else "no",
                    "target date": due.isoformat(),
                    "status": "released" if v["released"] else "unreleased",
                }
    else:
        for i in issues:
            if i["issuetype"].lower() != "epic":
                continue
            done, due = day(i["resolved"]) if i["done"] else None, day(i["duedate"])
            shipped = done is not None and start <= done <= end
            if not shipped and not (due and start <= due <= end and not i["done"]):
                continue
            out[i["key"]] = {
                "commitment": i["summary"] or i["key"],
                "shipped": "yes" if shipped else "no",
                "target date": due.isoformat() if due else "",
                "completed": done.isoformat() if done else "",
                "status": i["status"],
                "owner": i["assignee"],
            }
    rows = []
    for c in out.values():
        rows.append(
            {k: c.get(k, "") for k in COMMITMENT_COLUMNS} | {"source": f"Jira {kind}", "note": "Jira holds no target metric: fill metric before importing."}
        )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn raw Jira exports into the tracker source.")
    given = ap.add_mutually_exclusive_group(required=True)
    given.add_argument("--search", nargs="+", help="REST search results as Jira returns them, one file per page")
    given.add_argument("--csv", help="Jira's CSV export")
    ap.add_argument("--estimate-field", required=True, help='the estimate field, for example customfield_10016 or "Story Points"')
    ap.add_argument("--work-type-from", required=True, choices=["issuetype", "label", "component"], help="the field that names a work type")
    ap.add_argument("--work-type-prefix", help='with --work-type-from label: the prefix, for example "type:"')
    ap.add_argument("--work-type", action="append", default=[], metavar="VALUE=TYPE", help="a field value that stands for a work type; repeat it")
    ap.add_argument("--product-line-from", choices=["component", "project"], help="the field that names a product line, if any")
    ap.add_argument("--objective-prefix", help='the label prefix that names an objective, for example "objective:"')
    ap.add_argument("--commitments-from", choices=["versions", "epics"], help="also write commitments for slide 8")
    ap.add_argument("--period-start", help="with --commitments-from: YYYY-MM-DD")
    ap.add_argument("--period-end", help="with --commitments-from: YYYY-MM-DD")
    ap.add_argument("--site", default="Jira", help="the Jira site or project, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    type_map = {}
    for pair in args.work_type:
        if "=" not in pair:
            raise fail(f'--work-type takes VALUE=TYPE, for example --work-type "Bug=Keep the lights on". Got {pair!r}.')
        value, kind = pair.split("=", 1)
        type_map[value.strip()] = kind.strip()
    first = args.search[0] if args.search else args.csv
    issues = from_search([Path(p) for p in args.search], args.estimate_field) if args.search else from_csv(Path(args.csv), args.estimate_field)
    rows, skipped = to_rows(issues, args, type_map)
    run = Path(args.run)
    if rows:
        what = "Jira REST search (done issues)" if args.search else "Jira CSV export"
        data = collect.collect("tracker", rows, f"Jira ({args.site})", what, collect.retrieved_date(args.retrieved_at, first), Path(first).name)
        out = run / "data" / "tracker.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"from_jira: {len(rows)} done issues with an estimate, written to {out}.")
    for why, n in skipped.items():
        if n:
            print(f"from_jira: {n} done issue(s) have {why} and are left out. Nothing is filled in for them.")
    untyped = sum(1 for r in rows if r["work_type"] == UNLABELLED)
    if untyped:
        print(f'from_jira: {untyped} issue(s) have no {args.work_type_from} and count as "{UNLABELLED}".')
    if args.commitments_from:
        if not (args.period_start and args.period_end):
            raise fail("--commitments-from needs --period-start and --period-end.")
        if args.commitments_from == "versions" and args.csv:
            raise fail("Jira's CSV export carries no release dates for versions. Use --search, or --commitments-from epics.")
        found = commitments(issues, args.commitments_from, datetime.date.fromisoformat(args.period_start), datetime.date.fromisoformat(args.period_end))
        path = run / "jira" / "commitments.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(COMMITMENT_COLUMNS))
            writer.writeheader()
            writer.writerows(found)
        print(f"from_jira: {len(found)} commitment(s) from {args.commitments_from}, written to {path}.")
        print("from_jira: fill each metric, show the rows to the person, then intake.py import --commitments.")
    if not rows and not args.commitments_from:
        raise fail("found no done issues with an estimate and a resolution date. The tracker stays Unknown; no file was written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
