#!/usr/bin/env python3
"""Regenerate assets/samples.json: what each slide looks like with data.

Usage:
  python3 tools/build_samples.py

Runs the complete test fixture (Kestrel Labs, a made-up company) through
collect, compute and draft, then keeps each filled slide's title and blocks
as a sample. draft.py shows a sample, greyed and tagged Illustrative, beside
the data_needed block of a slide that has no data. Ledger references and any
gaps inside the sample are removed: a sample is made up and cites nothing.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # noqa: S404  (runs the skill's own scripts, as a user would)
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "product-engineering-update"
FIXTURE = ROOT / "evals" / "fixtures" / "complete"
OUT = SKILL / "assets" / "samples.json"
SOURCE = "Kestrel Labs, a made-up company"
LEDGER_MARK = re.compile(r"\[\[L\d+\]\]")

Json = dict[str, Any]


def script(name: str, *args: str) -> None:
    done = subprocess.run([sys.executable, "-I", str(SKILL / "scripts" / name), *args], capture_output=True, text=True, check=False)  # noqa: S603
    if done.returncode != 0:
        raise SystemExit(f"build_samples: {name} failed.\n{done.stderr}")


def scrub(node: Any) -> Any:
    """The node with every ledger reference removed."""
    if isinstance(node, str):
        return re.sub(r"\s+([.,;:])", r"\1", LEDGER_MARK.sub("", node)).strip()
    if isinstance(node, list):
        return [scrub(x) for x in node]
    if isinstance(node, dict):
        return {k: scrub(v) for k, v in node.items()}
    return node


def without_gaps(blocks: list[Json]) -> list[Json]:
    """The blocks with data_needed items taken out, and any card set left empty dropped."""
    out = []
    for b in blocks:
        if b["type"] == "cards":
            items = [i for i in b["items"] if i.get("type") != "data_needed"]
            if not items:
                continue
            b = {**b, "items": items}
        out.append(b)
    return out


def build() -> Json:
    work = Path(tempfile.mkdtemp(prefix="peu-samples-"))
    try:
        shutil.copy(FIXTURE / "intake.json", work / "intake.json")
        systems = json.loads((FIXTURE / "systems.json").read_text(encoding="utf-8"))
        for path in sorted((FIXTURE / "csv").glob("*.csv")):
            script("collect.py", path.stem, "--csv", str(path), "--system", systems[path.stem], "--retrieved-at", "2026-09-30", "--run", str(work))
        script("compute_metrics.py", "--run", str(work))
        script("draft.py", "--run", str(work))
        deck = json.loads((work / "deck.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    slides: Json = {}
    for s in deck["slides"]:
        if s["kind"] != "slide" or "is not reported this period" in s["title"]:
            continue
        blocks = without_gaps([b for b in s["blocks"] if b["type"] != "sample"])
        if blocks:
            slides[s["id"]] = scrub([{"type": "strip", "label": "Title", "text": s["title"]}, *blocks])
    return {"source": SOURCE, "slides": slides}


def main() -> int:
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"build_samples: wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
