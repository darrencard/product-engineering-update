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

# The systems each source has a converter for: (system, script, guide). The guide names the connector, if any.
CONVERTERS = {
    "docs": [("Notion", "from_notion.py", "connect-notion.md"), ("Google Drive", "from_gdrive.py", "connect-gdrive.md")],
    "tracker": [
        ("Linear", "from_linear.py", "connect-linear.md"),
        ("Jira", "from_jira.py", "connect-jira.md"),
        ("GitHub Projects", "from_github_projects.py", "connect-github-projects.md"),
    ],
    "finance": [("Anthropic and OpenAI API costs (plan added by you)", "from_ai_spend.py", "connect-ai-spend.md")],
    "billing": [("Stripe", "from_stripe.py", "connect-stripe.md")],
    "analytics": [
        ("PostHog", "from_posthog.py", "connect-posthog.md"),
        ("Amplitude", "from_amplitude.py", "connect-amplitude.md"),
        ("Mixpanel", "from_mixpanel.py", "connect-mixpanel.md"),
    ],
    "crm": [("HubSpot", "from_hubspot.py", "connect-hubspot.md"), ("Salesforce", "from_salesforce.py", "connect-salesforce.md")],
    "support": [("Intercom", "from_intercom.py", "connect-intercom.md"), ("Zendesk", "from_zendesk.py", "connect-zendesk.md")],
    "source_control": [
        ("GitHub", "from_github.py", "connect-github.md"),
        ("Vercel (labelled quality proxy)", "from_vercel.py", "connect-vercel.md"),
        ("Sentry (labelled quality proxy)", "from_sentry.py", "connect-sentry.md"),
    ],
    "incidents": [("incident.io", "from_incidentio.py", "connect-incidentio.md"), ("PagerDuty", "from_pagerduty.py", "connect-pagerduty.md")],
    "ai_tools": [("GitHub Copilot and Cursor", "from_ai_spend.py", "connect-ai-spend.md")],
    "customer_requests": [("Linear customer requests", "from_linear.py", "connect-linear.md")],
}


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
        "Systems with a converter read the system's own export and write the source for you, mapping only fields that exist."
        " Every other system works through a CSV with the columns below.",
        "",
        "| Source | Converters |",
        "|---|---|",
        *[f"| {key} | " + ", ".join(f"[{name}]({guide}) (`{script}`)" for name, script, guide in found) + " |" for key, found in CONVERTERS.items()],
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
            f"Examples: {', '.join(t['examples'])}. Feeds slides: {', '.join(feeds) or 'none yet'}."
            + (f" Converters: {', '.join(name for name, _, _ in CONVERTERS[key])}." if key in CONVERTERS else ""),
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
