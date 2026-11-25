# The Product & Technology Leader Report

A Claude skill that builds a product and engineering update from your own data: one deck for leadership, the board and all staff, as a single HTML file with an evidence ledger.

Most coding agents now write, review and approve the code, then stop at merge. This update reports what landed. It is built not to overclaim. Every figure is computed in code and carries a row in the ledger. A slide without its data says so. A deck with an unsupported claim does not render.

See the worked example and the template at https://www.dacard.ai/update. How it was built, and every eval result: [field note 24](https://www.dacard.ai/paper-trail/how-i-built-the-product-engineering-update-skill-in-claude-code).

## Get started: three steps

1. **Use the tools Claude already has.** GitHub through the `gh` command line, and Linear, Jira, Vercel, Sentry, Stripe, PostHog, HubSpot, Notion or Google Drive through Claude's connectors. Any other system: a CSV export.
2. **Paste one prompt into Claude Code.** Replace `OWNER/REPO`. It installs the pinned release, checks it, reads what's connected and asks only what it can't find: the company, the period and its dates, the data date, and who owns the gaps and by when.
3. **Read slide 1.** It shows what your data disagrees on, what happened, the decision you need and every gap with an owner. The board version renders once a named person signs it off.

```text
Install the Product & Technology Leader Report skill from the v0.9.3 release at https://github.com/darrencard/product-engineering-update/releases/tag/v0.9.3, and check the download against its SHA256SUMS before installing. Then build my product & engineering update for last quarter from the tools already connected to this session: GitHub for OWNER/REPO through gh, and any connected Linear, Jira, Vercel, Sentry, Stripe, PostHog, HubSpot, Notion or Google Drive. Ask me only for what you cannot find, show every gap with an owner and a date, and render the full deck.
```

The prompt names a fixed release, so a later change to the repository can't reach you until you choose a newer one. Tested on live accounts so far: GitHub, Vercel and Google Drive; the other readers are tested on fixtures. Something wrong or missing? [Open an issue](https://github.com/darrencard/product-engineering-update/issues).

## Features, functions and benefits

| Feature | What it does | What it does for you |
|---|---|---|
| Figures computed in code | Python computes every number from your exports; the model never does the arithmetic | No wrong numbers in front of the board: 0 arithmetic errors in every eval run so far, against 2 to 5 a run for Claude alone ([ablation](docs/ablation.md)) |
| Evidence ledger | Each figure has a row with its source, window and confidence, also written as a CSV | Any number traces back to its source in seconds when someone asks |
| Figure check | Blocks any printed number the pipeline didn't compute (`figure-not-computed`) | Claude can rewrite the words but can't invent or change a number |
| 22 blocking rules | Stops the render on, for example, speed without quality, an unsourced or stale figure, or a bet with no stop rule | The deck can't claim more than the data shows, so there's less to fix in review |
| Open questions on the data | Slide 1 opens with sources that disagree, revenue that doesn't match ARR and decisions past their date, each with an owner | Problems with the data show up before anyone relies on the numbers |
| Gaps and data notes | Lists every missing input and data caveat with an owner and a due date | Missing data becomes owned work, not a vague slide |
| Shipped against impact | Lists last period's work against the outcome each piece named, and says which moved | You can say whether what shipped worked, without claiming it caused the change |
| Your voice | Claude writes the prose in your style, from a few lines or a past update | It reads like you wrote it, with the checks still in place |
| One-page board version | One page, then the detail as an appendix; renders only after a named person signs off | Ready to send, with a clear owner of what went out |
| Three versions | Leadership, board and all-staff versions from one run | One run covers three meetings, with the same numbers in each |
| Readers for your tools | 19 readers for GitHub, Linear, Jira, Vercel, Stripe, PostHog, HubSpot, Google Drive and more, plus CSV | Works from the tools already connected to Claude, with no new tooling |
| Local and open | Runs on your machine; MIT licensed; signed releases with checksums; Python standard library only | Board data never leaves the company, and the code can be audited |
| Published evals | Every blind eval against Claude alone is public, losses included | Claims can be checked rather than taken on trust |

Results so far come from synthetic test companies and one real repository, not a real team's full data.

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

## Documentation

- [Validator rules](docs/validator-rules.md): every check that blocks a render, and how to fix it.
- [Connectors](docs/connectors.md): each reader, what it needs, and which have run on a live account.
- [Security and data handling](docs/security.md): where data goes, the supply chain, prompt injection and the Action's permissions.
- [Intake and CLI reference](docs/intake-and-cli.md): every `intake.json` field and script flag.
- [Troubleshooting](docs/troubleshooting.md): the errors the scripts give, and the fix for each.
- [Ablation](docs/ablation.md): the skill against Claude alone on the same data, judged blind. Claude alone won every comparison on the synthetic fixtures.

## Privacy

Your data stays in your own session. The scripts read files in a run folder and write files back to it. They hold no network code, which a test checks. They use the Python standard library only and declare no dependencies, so they install nothing. Nothing reaches dacard.ai. The full detail, including what is not covered, is in [Security and data handling](docs/security.md).

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

Version 0.9.3. The scripts pass 174 tests. Fresh model sessions ran version 0.1.0 on the bundled fixtures 6 times, across two model sizes, under pressure to overclaim, invent figures and pick the better-looking of two conflicting numbers; each held the line. Versions 0.2.0 and 0.3.0 have run on one real repository's GitHub and Vercel history. The Linear converter is tested on Linear's real response shape but not on a workspace with completed issues, and the PostHog converter only on fixtures of PostHog's documented responses. The Linear projects, project updates, initiatives and customer requests readers (0.4.0) are tested only on fixtures built from Linear's documented fields. It has not yet been run on a real company's full data. See CHANGELOG.md.

Not built: an export to Slides or PowerPoint. The deck is one HTML file: present it in a browser or print it to PDF.

## Credit

Built by Darren Card at Dacard, an applied AI studio: https://www.dacard.ai. Harborline and Kestrel Labs are fictional, and every figure for them is illustrative. The fonts embedded in the template are Geist, Geist Mono and Instrument Sans, each under the SIL Open Font License.

## Licence

Two licences, by kind of file:

- **Code** (the scripts, tests, tools, schema and slide contracts): MIT. See `LICENSE`.
- **Template and deck content** (the skill's instructions and references, the page template, the blank deck and the examples): CC BY 4.0. See `LICENSE-CONTENT.md`. Use and adapt it freely, with credit.
