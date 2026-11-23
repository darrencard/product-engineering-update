#!/usr/bin/env python3
"""Regenerate the reference files that are derived from data.

Usage:
  python3 tools/build_references.py

Writes references/sources.md (from collect.SOURCES and assets/contracts.json)
and references/frameworks.md (from the reading lists in the example deck), so
neither drifts from the code or the deck.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "product-engineering-update"
sys.path.insert(0, str(SKILL / "scripts"))

import collect  # noqa: E402  (needs the path above)


def slide_no(slide_id: str) -> str:
    return slide_id.lstrip("0") or "0"


def sources_md() -> str:
    contracts = json.loads((SKILL / "assets" / "contracts.json").read_text(encoding="utf-8"))
    deck = json.loads((SKILL / "assets" / "blank.deck.json").read_text(encoding="utf-8"))
    types = {t["key"]: t for t in deck["meta"]["source_types"]}
    lines = [
        "# Sources",
        "",
        "Each source, the columns `scripts/collect.py` needs, and the slides it feeds. A column marked optional may be left empty.",
        "",
        "Get the rows from whatever connector the session has, or from a CSV export. `collect.py` does not call any system itself.",
        "",
        "## Contents",
        "",
    ]
    keys = [k for k in types if k in collect.SOURCES]
    lines += [f"- [{types[k]['label']}](#{k})" for k in keys] + ["- [Sources with no table](#sources-with-no-table)", ""]
    for key in keys:
        t = types[key]
        feeds = sorted({slide_no(c["id"]) for c in contracts for r in c["requires"] if r["source"] == key}, key=lambda x: (len(x), x))
        needs = sorted({r["data"] for c in contracts for r in c["requires"] if r["source"] == key})
        lines += [
            f'<a id="{key}"></a>',
            f"## {t['label']} (`{key}`)",
            "",
            f"Examples: {', '.join(t['examples'])}. Feeds slides: {', '.join(feeds) or 'none yet'}.",
            "",
            "| Column | Type | Required |",
            "|---|---|---|",
        ]
        for column, kind in collect.SOURCES[key]["columns"].items():
            lines.append(f"| `{column}` | {kind.rstrip('?')} | {'No' if kind.endswith('?') else 'Yes'} |")
        lines += ["", "What the slides read from it:", ""] + [f"- {n}" for n in needs] + [""]
    lines += [
        '<a id="sources-with-no-table"></a>',
        "## Sources with no table",
        "",
        "The intake interview is recorded in `run/intake.json` by `scripts/intake.py`. It needs no export.",
        "",
    ]
    return "\n".join(lines)


def frameworks_md() -> str:
    deck = json.loads((ROOT / "examples" / "harborline.deck.json").read_text(encoding="utf-8"))
    slides = [s for s in deck["slides"] if s.get("dig_deeper")]
    lines = [
        "# Frameworks and reading",
        "",
        "The reading behind each slide, with its source and date. Cite these as they are. Do not add a statistic that is not on this page.",
        "",
        "## Contents",
        "",
    ]
    lines += [f"- [{'Slide ' + slide_no(s['id']) if s['kind'] == 'slide' else 'Appendix ' + s['id']}: {s['nav']}](#s{s['id'].lower()})" for s in slides] + [""]
    for s in slides:
        name = f"Slide {slide_no(s['id'])}" if s["kind"] == "slide" else f"Appendix {s['id']}"
        lines += [f'<a id="s{s["id"].lower()}"></a>', f"## {name}: {s['nav']}", ""] + [f"- {d}" for d in s["dig_deeper"]] + [""]
    return "\n".join(lines)


def main() -> None:
    refs = SKILL / "references"
    (refs / "sources.md").write_text(sources_md(), encoding="utf-8")
    (refs / "frameworks.md").write_text(frameworks_md(), encoding="utf-8")
    print("build_references: wrote sources.md and frameworks.md")


if __name__ == "__main__":
    main()
