#!/usr/bin/env python3
"""Print a rendered deck to PDF with headless Chrome: one slide per page, no navigation, the ledger at the end.

Usage:
  python3 tools/print_pdf.py run/staff.html run/staff.pdf

It finds Chrome or Chromium on this machine (or the binary named by --chrome) and asks it to print
the HTML file with the deck's own print stylesheet. It reads a local file and writes a local file.

This lives outside the skill on purpose: the skill's scripts are standard library with no process
calls. Without Chrome, open the HTML in any browser and print to PDF; the same stylesheet applies.

Standard library only. Runs on Python 3.9 or later.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess  # noqa: S404  (runs a local browser, the one thing this tool is for)
import sys
from pathlib import Path

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]


def find_chrome(given: str | None) -> str:
    for name in [given] if given else CANDIDATES:
        path = shutil.which(name) or (name if name and Path(name).exists() else None)
        if path:
            return path
    playwright = sorted(Path.home().glob("Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*"))
    playwright += sorted(Path.home().glob(".cache/ms-playwright/chromium-*/chrome-linux*/chrome"))
    if playwright:
        return str(playwright[-1])
    raise SystemExit("print_pdf: no Chrome or Chromium found. Pass --chrome, or open the HTML in a browser and print to PDF.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a rendered deck to PDF with headless Chrome.")
    ap.add_argument("html", help="a deck rendered by render.py")
    ap.add_argument("pdf", help="where to write the PDF")
    ap.add_argument("--chrome", help="the Chrome or Chromium binary to use")
    args = ap.parse_args()
    source, out = Path(args.html).resolve(), Path(args.pdf).resolve()
    if not source.exists():
        raise SystemExit(f"print_pdf: {source} does not exist. Render the deck first.")
    chrome = find_chrome(args.chrome)
    done = subprocess.run(  # noqa: S603  (the arguments are a local binary and local paths)
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={out}", source.as_uri()],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if done.returncode != 0 or not out.exists():
        raise SystemExit(f"print_pdf: Chrome could not print {source.name}.\n{done.stderr.strip()[-600:]}")
    print(f"print_pdf: wrote {out} ({out.stat().st_size // 1024} KB) with {Path(chrome).name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
