# Changelog

## 0.4.0 (2026-11-23)

Coding agents stop at merge. This release reports whether merged work landed.

- **Shipped vs impact (slide 8) is drafted.** A new intake field, `commitments` (commitment, shipped yes or no, metric, owner, source), imported with `intake.py import --commitments` from CSV or a Markdown table and refused whole if any row is malformed. The slide groups commitments by the outcome each named before launch, shows the metric before and after, and says Moved, Flat, Moved the wrong way or Not shipped. Moved means the metric went the right way this period, using each metric's own direction; the slide says it is not proof of cause. A commitment with no metric, or one that was not collected or is disputed, goes under "No movement" with the reason. The title follows the spec, for example "We shipped 6 of 7 commitments. 4 have moved their target metric so far.", and states coverage when a metric carries one.
- **Linear projects, updates, initiatives and customer requests.** `from_linear.py --projects` turns projects into commitments (completed in the period is shipped; due in the period and not completed is not) and writes them to a file for `intake.py import`, never to the intake. A project's metric comes only from a "Landing brief" block in its description; with none, the metric stays empty and the slide says so. A brief's metric and bar go to `targets.csv`, imported with `intake.py import --targets` into the outcome scorecard (slide 11). `--project-updates` lists each project's latest update for the person to check; its text is never read as a result. `--initiatives` gives an issue its project's initiative as its objective (slide 3) when there is exactly one, and lists initiatives for the interview, since Linear holds no cause or confidence. `--customer-needs` writes a new `customer_requests` source: slide 6 lists the most requested issues and projects with counts computed in code and a link to each, and slide 7 adds the top one beside deals and tickets.
- **Write back.** `scripts/summary.py` writes a Markdown summary of the deck (titles, ledger IDs, gaps and the cited ledger rows) to post to Linear after the person says yes. It refuses a deck with validator errors and the board cut without `--signed-off-by`, and neutralises markup that could become HTML, an image or a mention.
- **A weekly rhythm.** `references/weekly-rhythm.md` sets the update up as a scheduled job. The schedule lives outside the scripts, and never renders, summarises or posts the board cut.
- **The landing brief kit.** A second skill, `skills/landing-brief/`: a Linear project template with the five parts of a landing brief (the problem, the definition of good, the non-goals, the cost budget as tokens per task and price per token, the line), and `landing_brief.py`, which refuses an incomplete brief with every problem listed and drafts a project update that prints landed, watch or stalled with the same rule as `draft.status_for`, the number against the bar and date, and who decides the next step. The agent posts it through the Linear connector only after the person confirms.
- Slide 7's sources line now names the CRM and support systems; before, it fell back to "see the ledger".
- Not tested on live data: the projects, updates, initiatives and customer requests readers, which are tested on fixtures built from Linear's documented fields.
- 113 tests, up from 82.

## 0.3.0 (2026-11-23)

- **Coverage on the figure.** A figure built from less than the reporting window carries a coverage record (first and last day, how many of how many) in its metric and ledger row. The slide prints it under the figure, and any title or rollup that cites the figure says it, for example "covers 2 Nov to 23 Nov 2026, 113 of 514 releases". New validator error `coverage-unstated` blocks a slide that cites a partial figure without it. The Vercel proxy is the first figure to carry one; any metric can.
- **Drafted answers, held to their sources.** `intake.py propose` stores intake answers the agent drafted from the team's own documents in `run/proposals.json`, apart from the intake. Each names a field and its evidence (a file with a heading or line, or a URL, and a word-for-word quote, checked against a local file). A file with any proposal lacking evidence is refused whole. `intake.py confirm --by <name>` applies the ones the user accepts, all, by field or edited, and records who confirmed each and where it came from. Pending proposals leave their fields Unknown, and `draft.py` never reads them. Step 1 of the skill now starts from the team's documents and keeps the interview for the rest.
- 82 tests, up from 75.

## 0.2.0 (2026-11-23)

### What a reader sees
- **Metric definitions.** Each scorecard row prints a one-sentence, plain-English definition under the metric's name, and the AI slide's figures carry theirs. Computed metrics take a built-in definition; outcome metrics take the intake's wording first, then the analytics source's. An outcome with no definition warns (`undefined-metric`).
- **Samples on empty slides.** A slide without its data keeps its `data_needed` block and shows a greyed sample of what it would hold, from the made-up Kestrel Labs fixture, tagged Illustrative and hidden from screen readers. A sample never counts as data: the validator blocks one that is untagged, sits on a slide with real data, or cites a ledger row.
- **Plain titles.** Drafted titles say what a number means for a reader outside engineering ("basic upkeep", "the share of releases that caused a problem in production"), with no added cause. Shorthand in a title warns (`jargon-in-title`).
- **Full-width titles.** Slide titles run the full column width with a little padding.

### Getting data in
- **One command.** `scripts/run.py` asks only for the 7 answers a run needs, then collects, computes, drafts, validates and renders the full deck, and prints which slides show data and which show gaps. The board cut still needs `--signed-off-by`.
- **Vercel quality proxy.** `scripts/from_vercel.py` turns Vercel's deployments, runtime error reports and rollbacks (every page) into "Deploys rolled back or followed by errors", a proxy for change failure rate that pairs with speed for a repository with no reviews. It is never relabelled change failure rate, deploys outside the exports stay Unknown, and it warns when the exports start after the period begins.
- **Linear and PostHog converters.** `scripts/from_linear.py` (completed issues into the tracker source) and `scripts/from_posthog.py` (a HogQL query result or a trends insight into the analytics source). The PostHog converter is untested on live data.
- **Suggested healthy ranges.** `intake.py suggest` offers a range for each delivery metric that has a published benchmark, with its source and date; `intake.py accept` records the user's yes, as suggested or edited. Nothing is applied without it, and the delivery slide names the source. The shipped suggestions come from the performance-levels table on page 13 of DORA's Accelerate State of DevOps Report 2024, for deploys per week, change failure rate and the Vercel proxy. Lead time and time to restore get none, because the skill measures them differently from DORA.
- **Imports.** `intake.py import` reads a decision log, risk register and stop list from CSV or Markdown tables with named columns, refuses anything else, and lists what it imported for the user to confirm.

### Also
- New guides: `references/connect-vercel.md`, `connect-linear.md`, `connect-posthog.md`.
- 75 tests, up from 40.

## 0.1.0 (2026-11-23)

- First public version: interview, collect, compute, draft, validate, review and render, with 13 rules that block a render, an evidence ledger, and the GitHub shortcut.
