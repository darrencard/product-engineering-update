# The Product & Engineering Update

A Claude skill that builds a product and engineering update from your own data: one deck for leadership, the board and all staff, as a single HTML file with an evidence ledger.

Most coding agents now write, review and approve the code, then stop at merge. This update reports what landed. It is built not to overclaim. Every figure is computed in code and carries a row in the ledger. A slide without its data says so. A deck with an unsupported claim does not render.

See the worked example and the template at https://www.dacard.ai/update.

## What you get

- **One deck, 3 cuts.** Leadership 18 slides, Board 8, Staff 10. The slides change between cuts. The numbers never do.
- **A ledger.** Each figure has an ID, a source, a window and a confidence label: Verified, Derived, Estimated or Unknown.
- **Checks that block a render.** A speed metric with no quality metric beside it, a productivity claim with no baseline, an adoption count in an outcome slot, a bet with no stop rule, a figure with no ledger row, and 8 more.
- **Gaps that stay visible.** Missing data shows as a "data needed" block with an owner and a date.
- **Shipped vs impact.** Slide 8 lists last period's commitments by the outcome each named before launch, and says which moved, without claiming the work caused it.
- **Linear projects, initiatives and customer requests.** `from_linear.py` turns them into commitments and stated targets (for you to confirm), line of sight, and counted customer requests.
- **Write back.** `summary.py` writes a Markdown summary with ledger IDs, to post to Linear after a yes. It refuses the board cut without a named sign-off.
- **A weekly draft.** `references/weekly-rhythm.md` sets the update up as a scheduled job that drafts the Leadership and Staff cuts each week and never renders or posts the board cut.
- **A landing brief kit for Linear.** `skills/landing-brief/` is a free project template (problem, definition of good, non-goals, cost budget, the line) and a script that drafts a landed, watch or stalled project update from it.

## Privacy

Your data stays in your own session. The scripts read files in a run folder and write files back to it. They make no network calls, use the Python standard library only, and install nothing. The test suite checks all three. Nothing reaches dacard.ai.

## Install

### Claude Code

Copy the skill folder into your skills directory:

```bash
cp -r skills/product-engineering-update ~/.claude/skills/
```

The landing brief kit installs the same way: `cp -r skills/landing-brief ~/.claude/skills/`.

Or install it as a plugin:

```bash
claude plugin marketplace add darrencard/product-engineering-update
```

```bash
claude plugin install product-engineering-update@dacard
```

### Claude.ai

1. Zip the `skills/product-engineering-update` folder.
2. Open Customize, then Skills, then "+", then "Create skill", then "Upload a skill".
3. Code execution must be on.

## One command

```bash
python3 scripts/run.py --run run --company "Acme" --period-label 2026-Q4 --period-start 2026-10-01 --period-end 2026-12-31 --as-of 2026-12-31 --gap-owner "CPO" --gap-due 2027-01-15 --csv tracker=linear.csv --no-ask
```

Run from `skills/product-engineering-update`. It asks only for the 7 answers a run needs, then collects, computes, drafts, validates and renders the full deck, and prints which slides show data and which show gaps. Slides without data show a greyed sample, tagged Illustrative, of what they would hold. The board cut needs `--board --signed-off-by "<name>"`.

## Quick start: 2 minutes, CSV only

This uses the bundled test company, Kestrel Labs, which is fictional.

```bash
cd skills/product-engineering-update
```

```bash
mkdir -p run && cp ../../evals/fixtures/complete/intake.json run/
```

```bash
for f in ../../evals/fixtures/complete/csv/*.csv; do python3 scripts/collect.py "$(basename "$f" .csv)" --csv "$f" --system "CSV export" --run run; done
```

```bash
python3 scripts/compute_metrics.py --run run && python3 scripts/draft.py --run run && python3 scripts/validate.py run/deck.json
```

```bash
python3 scripts/render.py run/deck.json --out run/update.html
```

Open `run/update.html` in a browser. With your own data, ask Claude: "Build our product and engineering update for last quarter." The skill interviews you, tells you which exports it needs, and runs the same steps.

## Fastest start: GitHub only

GitHub alone can fill the delivery slide, because pull requests carry both speed (lead time) and quality (review time, rework). Two exports and one command, no CSV to build: see `skills/product-engineering-update/references/connect-github.md`.

## What each source needs

`python3 scripts/collect.py --list` prints every source and its columns. The full list, with the slides each source feeds, is in `skills/product-engineering-update/references/sources.md`. Connectors are optional: see `CONNECTORS.md`.

| Cut | Sources it cannot render without |
|---|---|
| Leadership | 15 of 17 |
| Board | 11 of 17 |
| Staff | 8 of 17 |

## What is in this repository

| Path | What it is |
|---|---|
| `skills/product-engineering-update/SKILL.md` | The workflow Claude follows |
| `skills/product-engineering-update/scripts/` | `intake`, `collect`, `from_github`, `from_linear`, `from_posthog`, `from_vercel`, `compute_metrics`, `draft`, `validate`, `review`, `render`, `summary`, `run` |
| `skills/landing-brief/` | The landing brief kit: the Linear project template, `landing_brief.py`, and its SKILL.md |
| `skills/product-engineering-update/references/` | Writing rules, audience cuts, the metrics glossary, sources, reading, and one contract per slide |
| `skills/product-engineering-update/assets/` | The page template, the deck schema, the blank deck and the slide contracts |
| `examples/` | Harborline, the fictional worked example, as data and as a rendered deck |
| `evals/` | 6 company fixtures, the test suite, and 3 scenarios for testing the skill with a model |

## Develop

Requires Python 3.9 or later. Nothing to install.

```bash
python3 -m unittest discover -s evals -v
```

The suite runs 6 synthetic company cases through the whole pipeline, the GitHub shortcut on raw exports, 12 overclaim attempts that must be blocked, and the safety properties: escaped output, safe links, no spreadsheet formulas in the ledger CSV, no network code, and byte-for-byte parity with the site's renderer.

`assets/`, `references/slides/` and `examples/` are exported from the site repository's renderer, so the skill and https://www.dacard.ai/update share one stylesheet, one schema and one example. `references/sources.md` and `references/frameworks.md` are generated by `tools/build_references.py`. Edit the source, then regenerate.

The scenarios in `evals/scenarios/` describe how the skill should behave under pressure to overclaim. There is no built-in runner for them: give the query and files to a fresh session with the skill installed and compare what it does with `expected_behavior`.

## Status

Version 0.4.0. The scripts pass 113 tests. Fresh model sessions ran version 0.1.0 on the bundled fixtures 6 times, across two model sizes, under pressure to overclaim, invent figures and pick the better-looking of two conflicting numbers; each held the line. Versions 0.2.0 and 0.3.0 have run on one real repository's GitHub and Vercel history. The Linear converter is tested on Linear's real response shape but not on a workspace with completed issues, and the PostHog converter only on fixtures of PostHog's documented responses. The Linear projects, project updates, initiatives and customer requests readers (0.4.0) are tested only on fixtures built from Linear's documented fields. It has not yet been run on a real company's full data. See CHANGELOG.md.

Not built: an export to Slides or PowerPoint. The deck is one HTML file: present it in a browser or print it to PDF.

## Credit

Built by Darren Card at Dacard, an applied AI studio: https://www.dacard.ai. Harborline and Kestrel Labs are fictional, and every figure for them is illustrative. The fonts embedded in the template are Geist, Geist Mono and Instrument Sans, each under the SIL Open Font License.

## Licence

Two licences, by kind of file:

- **Code** (the scripts, tests, tools, schema and slide contracts): MIT. See `LICENSE`.
- **Template and deck content** (the skill's instructions and references, the page template, the blank deck and the examples): CC BY 4.0. See `LICENSE-CONTENT.md`. Use and adapt it freely, with credit.
