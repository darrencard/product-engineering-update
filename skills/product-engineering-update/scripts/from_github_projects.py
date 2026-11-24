#!/usr/bin/env python3
"""Turn a GitHub Projects export into the tracker source, with no retyping.

Usage:
  gh project item-list 3 --owner acme --format json --limit 1000 > items.json
  gh issue list --repo acme/app --state closed --json url,closedAt --limit 1000 > closed.json
  python3 scripts/from_github_projects.py --items items.json --closed closed.json \\
      --estimate-field estimate --work-type-field type --run run

`gh project item-list --format json` gives {"items": [...], "totalCount": N}. Each item has its title,
status, labels, content (the issue or pull request, with its url) and one key per custom field, named
after the field in lower case (an "Estimate" field is `estimate`).

GitHub Projects records no completion date on an item. Pass --closed with the closedAt dates from
`gh issue list` or `gh pr list` (matched by url), or name a date field with --completed-field. An item
done with no date from either is left out and counted.

How a done item (status equal to --done-status, "Done" by default) maps to a tracker row, only from
fields that exist:
  estimate      the field named by --estimate-field. An item without it is left out and counted.
  work_type     the field named by --work-type-field, or the label after --work-type-prefix, mapped with
                --work-type "Bug=Keep the lights on". An item with neither is "Unlabelled".
  product_line  the field named by --product-line-field, or the repository, if given.
  objective     the field named by --objective-field, if given.
  owner         the first assignee.

This script reads files and writes a file. It makes no network calls.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import collect  # noqa: E402  (a sibling script, found through the path above)

Json = dict[str, Any]
UNLABELLED = "Unlabelled"


def fail(message: str) -> SystemExit:
    return SystemExit(f"from_github_projects: {message}")


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        raise fail(f"cannot read {path} ({e}). Save gh's output as it stands.") from None


def key(name: str) -> str:
    """gh names a custom field's key after the field, in lower case with no spaces."""
    return name.strip().lower().replace(" ", "")


def text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("title") or value.get("name") or value.get("login") or "")
    return "" if value is None else str(value)


def day(value: Any) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def closed_dates(paths: list[Path]) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in paths:
        data = load(path)
        if not isinstance(data, list):
            raise fail(f"{path} must be the list `gh issue list --json url,closedAt` writes.")
        for x in data:
            if isinstance(x, dict) and x.get("url") and x.get("closedAt"):
                found[x["url"]] = x["closedAt"]
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Turn a GitHub Projects export into the tracker source.")
    ap.add_argument("--items", nargs="+", required=True, help="gh project item-list --format json output, one file per page")
    ap.add_argument("--closed", nargs="*", default=[], help="gh issue list / gh pr list --json url,closedAt output")
    ap.add_argument("--completed-field", help="a date field on the project that records completion")
    ap.add_argument("--done-status", default="Done", help='the status that means done (default "Done")')
    ap.add_argument("--estimate-field", required=True, help="the custom field that holds the estimate")
    ap.add_argument("--work-type-field", help="a custom field that names the work type")
    ap.add_argument("--work-type-prefix", help='a label prefix that names the work type, for example "type:"')
    ap.add_argument("--work-type", action="append", default=[], metavar="VALUE=TYPE", help="a value that stands for a work type; repeat it")
    ap.add_argument("--product-line-field", help='a custom field that names the product line, or "repository"')
    ap.add_argument("--objective-field", help="a custom field that names the objective")
    ap.add_argument("--project", default="GitHub Projects", help="the project's name, for the ledger")
    ap.add_argument("--retrieved-at", help="YYYY-MM-DD; defaults to the first file's modified date")
    ap.add_argument("--run", default="run")
    args = ap.parse_args()

    if not (args.work_type_field or args.work_type_prefix):
        raise fail("name where the work type is: --work-type-field or --work-type-prefix. The script does not choose.")
    type_map = {}
    for pair in args.work_type:
        if "=" not in pair:
            raise fail(f"--work-type takes VALUE=TYPE. Got {pair!r}.")
        value, kind = pair.split("=", 1)
        type_map[value.strip()] = kind.strip()
    items: list[Json] = []
    for path in args.items:
        data = load(Path(path))
        page = data.get("items") if isinstance(data, dict) else None
        if not isinstance(page, list):
            raise fail(f"{path} holds no items list, as `gh project item-list --format json` writes it.")
        items += page
    closed = closed_dates([Path(p) for p in args.closed])

    rows, skipped = [], {"no estimate": 0, "no completion date": 0}
    for item in items:
        if text(item.get("status")).lower() != args.done_status.lower():
            continue
        content = item.get("content") or {}
        when = day(item.get(key(args.completed_field))) if args.completed_field else None
        when = when or day(closed.get(content.get("url", "")))
        if when is None:
            skipped["no completion date"] += 1
            continue
        estimate = item.get(key(args.estimate_field))
        if estimate in (None, ""):
            skipped["no estimate"] += 1
            continue
        labels = [text(x) for x in item.get("labels") or []]
        raw = text(item.get(key(args.work_type_field))) if args.work_type_field else ""
        if not raw and args.work_type_prefix:
            raw = next((x[len(args.work_type_prefix) :].strip() for x in labels if x.lower().startswith(args.work_type_prefix.lower())), "")
        line_field = args.product_line_field
        line = text(item.get("repository")) if line_field == "repository" else text(item.get(key(line_field))) if line_field else ""
        assignees = item.get("assignees") or []
        rows.append(
            {
                "id": content.get("url") or item.get("id") or "",
                "title": item.get("title") or content.get("title") or "",
                "work_type": type_map.get(raw, raw) or UNLABELLED,
                "status": text(item.get("status")),
                "estimate": estimate,
                "completed_at": when.isoformat(),
                "product_line": line,
                "objective": text(item.get(key(args.objective_field))) if args.objective_field else "",
                "owner": text(assignees[0]) if assignees else "",
            }
        )
    for why, n in skipped.items():
        if n:
            print(f"from_github_projects: {n} done item(s) have {why} and are left out. Nothing is filled in for them.")
    if not rows:
        raise fail("found no done items with an estimate and a completion date. The tracker stays Unknown; no file was written.")
    first = args.items[0]
    data = collect.collect(
        "tracker",
        rows,
        f"GitHub Projects ({args.project})",
        "gh project item-list --format json",
        collect.retrieved_date(args.retrieved_at, first),
        Path(first).name,
    )
    out = Path(args.run) / "data" / "tracker.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"from_github_projects: {len(rows)} done items with an estimate, written to {out}.")
    untyped = sum(1 for r in rows if r["work_type"] == UNLABELLED)
    if untyped:
        print(f'from_github_projects: {untyped} item(s) name no work type and count as "{UNLABELLED}".')
    return 0


if __name__ == "__main__":
    sys.exit(main())
