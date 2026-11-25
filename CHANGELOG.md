# Changelog

## 0.8.3 (2026-11-25)

- **Slide 1 leads with what not to rely on.** It opens with a "Check before you rely on this" card: every figure held because two sources disagree (named by source, never by number) and the revenue against ARR check, each cited to its ledger row. It closes with every gap in the deck, each with what is missing, its owner and its date. Before, it listed only the names of empty slides. This answers the 0.8.0 ablation rerun, where the judge preferred Claude alone on showing gaps 35 to 1.
- **Deadlines that have passed.** Slide 1's check card also names any decision or risk whose stated date ("4 Nov 2026", "Nov 2026" or an ISO date) has passed by the day the deck is drafted. Vague dates such as "Q4" are never called overdue. The 0.8.0 rerun judge credited Claude alone for flagging a passed 4 Nov deadline.
- **An owner per gap.** The intake takes an optional `gap_owners`, an owner per slide ID; unlisted slides use `gap_owner`.
- 181 tests.

## 0.8.2 (2026-11-25)

- **Ablation eval, third condition.** The eval now also runs Claude with the skill installed (condition C), loaded with `--plugin-dir`, and judges C against Claude alone, C against the pipeline, and the pipeline against Claude alone. Claude and Claude-with-skill runs read project settings only, so no user output style reaches them. On v0.8.0 and the 6 synthetic fixtures, the judge preferred Claude alone to Claude with the skill in 36 of 36 judgments, mostly because the skill holds the board cut back without a sign-off in an unattended run. Claude with the skill made 0 arithmetic errors against 2 for Claude alone. The skill's behaviour is unchanged. Results: `docs/ablation.md`.
- **Ablation eval.** `evals/ablation/` compares the skill's pipeline with Claude alone on the same fixture data, with a blind judge, noise runs and mechanical checks. It calls the model, so it stays out of the unit tests and CI. On the 6 synthetic fixtures the judge preferred Claude alone in 36 of 36 judgments. The skill made 0 arithmetic errors and Claude alone 1 in 1,049 checked figures. The skill's behaviour is unchanged. Results and limits: `docs/ablation.md`.
- **Three attempts, then the user.** SKILL.md's error recovery section now says that a step still failing after three attempts to fix it goes to the user, with what was tried and the exact message, and never by retrying unchanged, loosening a check or skipping the step. The rule comes from the Claude Code team's account of how they verify agent work (claude.dev, Nov 2026).

## 0.8.1 (2026-11-24)

- **The Google Drive reader reads the Claude Drive connector.** The first live run, on the maintainer's own drive through the Claude Google Drive connector, found it names a file's title and link `title` and `viewUrl`, where the Drive API says `name` and `webViewLink`. `from_gdrive.py` now reads either. Google Drive joins GitHub and Vercel as a reader run on a live account.
- **Signed from here.** This is the first release with a signed tag, and `main` now only accepts signed commits. `docs/security.md` says what that covers.
- 174 tests.

## 0.8.0 (2026-11-24)

Four fixes from the ablation eval in `docs/ablation.md`, where a blind judge preferred Claude alone to the skill's pipeline in 36 of 36 comparisons. The judge's reasons named these.

- **A team's deck carries no template material.** Drafted decks keep the evidence ledger (Appendix A) and drop the template's Appendices B, C and D: the explanation of the cuts, the pitch for this skill with its "Book a call" link, and the source list. The cover states the deck's own facts (core slides, each cut's length, the as-of date) in place of instructions to a template reader such as "Keys J and K move between slides". The blank template and the worked example keep every appendix.
- **The board cut carries only the ledger rows its slides cite**, in both the HTML and its ledger CSV. Other cuts keep the whole ledger.
- **Revenue is checked against ARR.** When the period's revenue, at that rate for a year, is less than half or more than twice ARR, slide 5 says the two do not reconcile, gives both figures with a ledger row, and asks for the right line before R&D as a share of revenue is read. Neither figure is changed. A disputed ARR is never quoted.
- 173 tests.

## 0.7.4 (2026-11-24)

- **Error recovery in the skill itself.** SKILL.md now holds a table of the refusals an agent meets most, each with what to do, so the fix is in the agent's context and not only in `docs/troubleshooting.md`. Facts only the user has are asked for, never filled in.
- **Friction reports.** When a script crashes, a doc is wrong or a fix does not work, the agent drafts a four-field report (tried, expected, happened, would fix it) with no company data, shows it word for word, and files it only after a yes, through a new issue form. The idea is Uber's "papercuts" (Uber Engineering, Nov 2026).

## 0.7.3 (2026-11-24)

Three fixes found while writing the reference docs in `docs/`.

- **The board cut carries its sign-off.** `render.py --cut B` now refuses a blank `--signed-off-by` (it accepted one made of spaces) and prints "Signed off by <name>" on the board cut's cover, so the sign-off travels with the file. Other cuts carry none.
- **An item with nothing to print is caught before the draft.** A product line, bet, risk, stopped item or decision without its key (`name`, `bet`, `risk`, `what`, `ask`) made `draft.py` crash with a Python `KeyError`. `intake.py check` now lists each one as blocking, and `draft.py` refuses with the same list.
- **The validator's rule list is complete.** `RULES` named 19 of the 21 blocking rules; it now names all 21, and a new `WARNINGS` list names the 4 warnings. A test keeps both in step with the rules the code raises and with `docs/validator-rules.md`.

## 0.7.2 (2026-11-24)

- **Slide 11's title reads right for one outcome.** With a single outcome the draft said "None of the 1 reported outcomes met its target." It now names the outcome with its number and target, for example "Unique cloners is at 15, short of its target of 25." Two or more outcomes keep the count, now in the plural throughout ("met their targets").

## 0.7.1 (2026-11-24)

- **The pace moves under the outcome scorecard.** In 0.7.0 it was an eighth column, which pushed slide 11 into a sideways scroll at laptop widths (about 1024px) and squeezed outcome names to 90px. It is now an "At this pace (Projected)" note under the table, listing only the outcomes not yet at their target. Checked in a browser at 1440 and 1024px: the table fits its frame with no scroll.

## 0.7.0 (2026-11-24)

Five additions, picked from how Linear, Atlassian, Swarmia, Jellyfish and LinearB report status, each computed locally from data the skill already reads.

- **What changed since the last update.** `draft.py --previous <last deck.json>` (and `run.py --previous`) adds a "Since the last update" card to slide 1: each status that moved on the delivery and outcome scorecards, each target that moved, and each metric added or dropped. Nothing moved says so in one line.
- **A reason for every moved status.** A new intake field, `status_reasons`, holds one line per metric from the person. A moved status without one prints `[reason needed]`, and the new validator rule `status-change-unexplained` blocks the deck. The weekly rhythm asks the owner and never writes the reason.
- **A capitalisable estimate on slide 5.** A new intake field, `capitalisation` (`work_types`, `cost_lines`, `confirmed_by`), from finance. The slide shows capitalisable and expensed amounts, the basis, and who confirmed it, always labelled an estimate for finance to confirm; `capex-not-estimate` blocks one that is not. Nothing is shown until finance names the work types.
- **The pace to each target on slide 11.** An "At this pace" column: periods to the target if this period's change repeats, and before or after the target's date when it has one. It prints as Projected, apart from the actual and the status.
- **Changes written by an agent on slide 13.** A new optional `source_control` column, `agent_authored`. `from_github.py --agent-labels` and `--agent-authors` set it from labels or accounts the team names; without them it stays Unknown. The share counts only marked changes and states its coverage. Slide 13 still makes no speed claim.
- 163 tests, up from 145.

## 0.6.0 (2026-11-24)

Converters for the systems teams already run. Each reads the system's own export (API JSON as the connector or REST API returns it), writes an existing source, maps only fields that exist, and leaves out and counts what it cannot place. None has run on a live account yet; each is tested on fixtures shaped like the vendor's documented response, and most rebuild the Kestrel test company's data exactly.

- **Sentry** (`from_sentry.py`): a release deployed to production is flagged when an error was first seen while it was live, or Sentry names it as the issue's first release. It feeds the existing quality proxy, labelled as one, with coverage stated. Sentry's public API documents no incident list, so nothing goes to incidents.
- **Stripe** (`from_stripe.py`): ARR per account per month from invoices (annualised by whole months, net of discounts) or subscriptions (by interval, before discounts), into the billing source. The test gets the same ARR, net and gross retention and expansion as the CSV.
- **AI spend** (`from_ai_spend.py`): GitHub Copilot and Cursor seats, weekly active people and cost into ai_tools (Copilot's cost needs your stated seat price; its API has none). Anthropic and OpenAI API costs become finance lines with the plan left for you. No usage count is ever written as productivity.
- **Amplitude and Mixpanel** (`from_amplitude.py`, `from_mixpanel.py`): one value per period from a chart's daily series, by the sum, mean or last you choose.
- **HubSpot and Salesforce** (`from_hubspot.py`, `from_salesforce.py`): closed deals with won or lost reason into crm. Salesforce's reason field is the one your team names; its docs could not be read for this release.
- **Intercom and Zendesk** (`from_intercom.py`, `from_zendesk.py`): tickets with a theme from a tag prefix, named tags or a field into support. Neither picks a tag for you.
- **incident.io and PagerDuty** (`from_incidentio.py`, `from_pagerduty.py`): incidents into the incidents source, for a real time to restore. They do not say which deploy caused an incident, so change failure rate is not derived from them; the guides say so.
- **Notion and Google Drive** (`from_notion.py`, `from_gdrive.py`): documents into the docs source, and Notion's Markdown export as quotable input for `intake.py propose`.
- `references/sources.md` and the deck's source list name every system with a converter. Each converter has a `connect-<system>.md` that names its Claude connector where one exists.
- Also in this release, from the security review: the GitHub Action runs with least privilege and pinned actions, never on pull requests; source text is data, never instructions, in both skills, with tests; `tools/release.sh` builds a reproducible release zip and SHA256SUMS.
- 145 tests.

## 0.5.0 (2026-11-23)

- **A weekly GitHub Action.** `action.yml` at the repository root is a composite action a team adds to its own repository, with `examples/product-engineering-update.yml` running it every Monday and by hand. It exports the repository's merged pull requests and deployments with the workflow's own token, collects any CSVs in `.update/` named after their source, reads `.update/intake.json`, and renders the Leadership and Staff cuts to an artifact or a branch through `scripts/ci.py`. It never renders the Board cut and never writes an intake answer; an intake missing a required answer stops the job, and a repository with nothing merged still gets a deck with delivery as a gap. `references/github-action.md` gives a 10-minute setup. Tested by running its steps locally on real exports; not yet run in GitHub's CI.
- **Jira and GitHub Projects readers.** `scripts/from_jira.py` reads Jira's REST search pages or its CSV export into the tracker source, and can write slide 8's commitments from fix versions or epics for `intake.py import` (with the metric left for the person, since Jira holds none). `scripts/from_github_projects.py` reads `gh project item-list` output, with closed dates from `gh issue list` matched by url. Both map work type, estimate, product line and objective only from fields the user names, and leave out and count an item with no estimate or no date. Guides: `connect-jira.md`, `connect-github-projects.md`. Tested on fixtures in the documented shapes; untested on a live Jira site or project.
- **Print to PDF (X.7).** The print stylesheet gives one A4 landscape slide per page, no navigation or guidance, kept status colours and the appendices, ledger first, at the end. `tools/print_pdf.py` prints a rendered deck with headless Chrome; without it, any browser's print to PDF uses the same stylesheet.
- 123 tests, up from 113.

## 0.4.0 (2026-11-23)

Most coding agents stop at merge. This release reports whether merged work landed.

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
