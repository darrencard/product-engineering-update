#!/usr/bin/env python3
"""Show what changed and what to check, before anyone signs off.

Usage:
  python3 scripts/review.py --run run
  python3 scripts/review.py --run run --previous last-period/deck.json

Writes run/review.md and prints it: the change in every computed metric
against the prior period, what moved since the previous deck (titles, status
words, slides added or dropped), the gaps, and a checklist.

The board cut renders only after a named person has read this and said yes.
Pass their name to render.py with --signed-off-by. A yes from earlier in the
conversation, or one implied by the request, does not count: ask again.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

Json = dict[str, Any]

CHECKLIST = (
    "Every title is a claim the slide's evidence supports.",
    "Every figure on a slide has a ledger row, and the row names its source.",
    "Each speed metric sits beside a quality metric on the same slide.",
    "No AI productivity figure appears without a baseline and a window.",
    "Every data needed block has a real owner and a real date.",
    "Anything marked Unknown or in conflict is shown as a gap, not as a number.",
    "The asks on the last slide match the answer on the first.",
    "The board cut holds 8 slides or fewer.",
)


def load(path: Path) -> Json:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def statuses(slide: Json) -> list[str]:
    return re.findall(r'"status": "(landed|watch|stalled)"', json.dumps(slide["blocks"])) + re.findall(r"\[\[status:(\w+)\]\]", json.dumps(slide["blocks"]))


def gaps(deck: Json) -> list[str]:
    out = []
    for s in deck["slides"]:
        for found in re.finditer(r'"type": "data_needed".*?"text": "(.*?)", "owner": "(.*?)", "due": "(.*?)"', json.dumps(s["blocks"])):
            out.append(f"Slide {s['id'].lstrip('0')}: {found.group(1)} Owner: {found.group(2)}. Due: {found.group(3)}.")
    return out


def build(run: Path, previous: Path | None) -> str:
    deck = load(run / "deck.json")
    lines = [f"# Review: {deck['meta']['company']}, {deck['meta']['period']}", ""]
    metrics_path = run / "metrics.json"
    if metrics_path.exists():
        m = load(metrics_path)
        lines += ["## Computed changes, this period against the prior one", "", "| Metric | Prior | Now | Ledger |", "|---|---|---|---|"]
        for metric in m["metrics"].values():
            now = "sources disagree" if metric.get("conflict") else metric["display"]
            lines.append(f"| {metric['label']} | {metric['prior_display'] or 'no prior'} | {now} | {metric['ledger']} |")
        if m["conflicts"]:
            lines += ["", "## Conflicts", ""] + [
                f"- {c['metric']}: "
                + "; ".join(f"{v['source']} says {v['value']:g}" for v in c["values"])
                + ". Shown as a gap until someone says which source owns it."
                for c in m["conflicts"]
            ]
        lines.append("")
    if previous:
        before = {s["id"]: s for s in load(previous)["slides"]}
        now = {s["id"]: s for s in deck["slides"]}
        lines += ["## Changed since the previous deck", ""]
        for sid in sorted(set(before) | set(now)):
            if sid not in now:
                lines.append(f"- Slide {sid.lstrip('0')} was dropped.")
            elif sid not in before:
                lines.append(f"- Slide {sid.lstrip('0')} is new.")
            else:
                if before[sid]["title"] != now[sid]["title"]:
                    lines.append(f'- Slide {sid.lstrip("0")} title: "{before[sid]["title"]}" became "{now[sid]["title"]}"')
                if statuses(before[sid]) != statuses(now[sid]):
                    lines.append(
                        f"- Slide {sid.lstrip('0')} status words: {', '.join(statuses(before[sid])) or 'none'} became {', '.join(statuses(now[sid])) or 'none'}"
                    )
        lines.append("")
    found = gaps(deck)
    lines += [f"## Gaps shown as data needed ({len(found)})", ""] + [f"- {g}" for g in found] + [""]
    unknown = [r for r in deck["ledger"] if r["confidence"] == "Unknown"]
    if unknown:
        lines += ["## Ledger rows marked Unknown", ""] + [f"- {r['id']}: {r['claim']}" for r in unknown] + [""]
    board = [s for s in deck["slides"] if s["kind"] == "slide" and "B" in s["audiences"]]
    lines += [f"## Board cut ({len(board)} slides)", ""] + [f"- {s['id'].lstrip('0')}. {s['title']}" for s in board] + [""]
    lines += (
        ["## Checklist", ""]
        + [f"- [ ] {c}" for c in CHECKLIST]
        + ["", "Sign-off: ask a named person for an explicit yes, then pass their name to render.py --signed-off-by.", ""]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Show the change list and the checklist.")
    ap.add_argument("--run", default="run")
    ap.add_argument("--previous", help="last period's deck.json, to compare against")
    args = ap.parse_args()
    run = Path(args.run)
    if not (run / "deck.json").exists():
        raise SystemExit(f"review: {run / 'deck.json'} is missing. Run draft.py first.")
    text = build(run, Path(args.previous) if args.previous else None)
    (run / "review.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
