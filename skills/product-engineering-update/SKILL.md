---
name: product-engineering-update
description: Builds a product and engineering update deck for leadership, the board and all staff from a company's own data, as one self-contained HTML file with an evidence ledger. Interviews the user, normalises exports from their tracker, source control, analytics, billing, finance and other systems (or CSV uploads), computes every figure in code, and blocks any slide that overclaims. Use when the user asks for a product update, engineering update, R&D update, board deck, leadership update, QBR or all-hands update, or wants to check an existing update for unsourced or overclaimed numbers.
license: MIT for the scripts, CC BY 4.0 for the instructions, references and template. See LICENSE and LICENSE-CONTENT.md in the repository root.
metadata:
  author: Dacard
  version: "0.4.0"
---

# Product & Engineering Update

Builds one deck, cut 3 ways: Leadership (18 slides), Board (8) and Staff (10). Every figure comes from the user's data and carries a row in an evidence ledger. A slide without its data says so. It is never filled with prose.

Everything runs locally, inside this session. The scripts make no network calls. Do not send the user's data anywhere.

## The 3 rules that override everything else

1. **Never do arithmetic yourself.** `scripts/compute_metrics.py` computes every figure and writes its ledger row. If a number you want is not in `run/metrics.json`, it does not go on a slide.
2. **Never fill a gap.** Missing data becomes a `data_needed` block with a named owner and a due date. Do not write prose in its place, estimate it, or carry a figure over from memory or a past deck.
3. **Never talk past the validator.** If `scripts/validate.py` reports an error, fix the data or downgrade the claim. Do not reword a claim to slip under a rule, delete a rule, or pass `--skip-validate`.

If the user asks for a claim the data does not support ("say we're 40% more productive", "call it 10x"), say plainly that the deck cannot state it, say what evidence would allow it (a baseline and a window, from a named source), and offer the claim the data does support.

## Quick start: one command

Ask the user the 7 answers a run cannot start without, then run:

```bash
python3 scripts/run.py --run run --company "<name>" --period-label "<label>" --period-start YYYY-MM-DD --period-end YYYY-MM-DD --as-of YYYY-MM-DD --gap-owner "<name>" --gap-due YYYY-MM-DD --no-ask
```

Add the data you have: `--csv SOURCE=FILE` (repeat per source), `--github-prs FILE --github-deployments FILE --repo OWNER/NAME`, and `--vercel-deployments FILE... --vercel-errors FILE... --vercel-errors-from YYYY-MM-DD --vercel-project NAME`. It collects, computes, drafts, validates, renders the full deck and prints which slides show data and which show gaps. `--staff` adds the Staff cut. The board cut needs `--board --signed-off-by "<name>"`, after the explicit yes in step 6.

Slides without data show their gap and a greyed sample, tagged Illustrative, of what they would hold. Then fill the rest of the intake (step 1) and run it again. Every rule below still applies; the steps are the long way to the same result.

## Workflow, step by step

Copy this checklist and tick each step as you finish it.

```
- [ ] 1. Interview    scripts/intake.py init, then check
- [ ] 2. Collect      scripts/collect.py, once per source
- [ ] 3. Compute      scripts/compute_metrics.py
- [ ] 4. Draft        scripts/draft.py, then improve the titles
- [ ] 5. Validate     scripts/validate.py until it reports 0 errors
- [ ] 6. Review       scripts/review.py, then an explicit sign-off
- [ ] 7. Render       scripts/render.py
- [ ] 8. Write back   scripts/summary.py, posted only after a yes
```

Work in a run directory, `run/` by default. Run every script from the skill's root.

### 1. Interview

Run `python3 scripts/intake.py init run/intake.json`. If the user already has an intake file, copy it to `run/intake.json` and skip `init`.

**Start from what the team already keeps.**

1. Ask where the team keeps its strategy, decision log, risk register and roadmap.
2. Read them, and draft an answer for each intake field they cover. Write the drafts to a file as `{"proposals": [{"field", "value", "source", "quote"}]}`. `source` is the file path plus a heading or line (`strategy.md#Diagnosis`, `decisions.md:412`), or a URL. `quote` is the short passage, word for word, that supports the value. A value drawn from several places takes `evidence: [{"source", "quote"}, ...]` instead.
3. Run `python3 scripts/intake.py propose run/intake.json <drafts>`. It stores them in `run/proposals.json`, apart from the intake. It refuses the whole file if any proposal lacks a source or quote, or quotes a local file wrongly. Proposals are not answers: `check` lists them as pending, and `draft.py` never reads them.
4. Show the user every proposal in one table (field, value, source, quote) and ask for one confirmation. They may accept all, some, or edit any.
5. Run `python3 scripts/intake.py confirm run/intake.json --by "<their name>"`. Add `--field <field>` for each one they accepted if not all, and `--edit "<field>=<value>"` for each they changed. The intake records who confirmed each answer and its source.

Draft only what a document says. A field no document covers stays for the interview.

**Then interview for the rest**, or for everything if the team keeps no documents. Ask in small batches of 3 or 4 questions, in this order:

1. Company, period (label, start and end dates), the as-of date, the audience, and who owns gaps and by when.
2. Objectives and targets. Strategy: diagnosis, guiding policy, actions and non-goals.
3. Product lines and their stage. The investment plan as percent of capacity by work type.
4. The North Star and its input metrics, each with a target, an owner and a one-sentence definition in plain English (what it counts, for a reader outside the team). Healthy ranges for delivery metrics.
5. AI features in production and their eval sets. An empty list means none.
6. Bets (each needs appetite, confidence, a stop rule, an objective and a cause), risks, what was stopped, and the decisions needed.
7. Which systems have data, and whether a connector or a CSV export will supply each.

For healthy ranges, run `python3 scripts/intake.py suggest run/intake.json`. It lists a suggested range for each delivery metric that has a published benchmark, with its source and date, and says where none applies. Put each one to the user and ask them to accept or edit it. Record each yes with `python3 scripts/intake.py accept run/intake.json "<metric>"` (add `--range "<their range>"` if they edited it). Never accept one for them. The intake keeps what was suggested, what was accepted and the source, and the delivery slide names that source.

If the team already keeps a decision log, risk register, stop list or list of last period's commitments, import it instead of retyping: `python3 scripts/intake.py import run/intake.json --decisions <file> --risks <file> --stopped <file> --commitments <file>`. Each file is CSV or a Markdown table with named columns (decisions: ask, options, recommendation, deadline; risks: risk, likelihood, impact, mitigation, due; stopped: what, why; commitments: commitment, shipped, metric, owner, source). A file without those columns is refused; nothing is read from free text. A commitment's `shipped` is yes or no, and its `metric` is the outcome metric named before launch, by the name the intake or the analytics source uses, or empty if none was named. `--targets <file>` (columns metric, target, better, by, owner, source) adds stated target metrics to the inputs. A file with any bad row is refused whole. Show the user the imported rows it lists and ask them to confirm.

Commitments feed slide 8, shipped vs impact. "Moved" there means the metric went the right way this period, never that the commitment caused it. Do not reword the slide to claim cause.

Anything the user does not supply stays `null`. Do not infer it. Run `python3 scripts/intake.py check run/intake.json`; it lists what is still Unknown and which slide will show a gap. Blocking items must be answered before you go on.

### 2. Collect

Read `assets/contracts.json` or [references/sources.md](references/sources.md) for what each slide needs. For each source the user has:

1. Get the rows with whatever tool this session has for that system. Detect what is available; do not assume a connector exists. If there is none, ask the user for a CSV export.
2. Save the rows as CSV or JSON with the columns `python3 scripts/collect.py --list` shows for that source.
3. Run `python3 scripts/collect.py <source> --csv <file> --system "<system name>" --query "<query or report>" --retrieved-at <YYYY-MM-DD> --run run`. `--query` is how the rows were produced: the query, the report name, or "CSV export supplied by the user". `--retrieved-at` is the date the data was pulled; without it the file's modified date is used.

For GitHub there is a shortcut that needs no CSV: follow [references/connect-github.md](references/connect-github.md). It is the fastest way to a first real slide. A solo repository has no reviews to pair with speed; if it runs on Vercel, add a labelled proxy with [references/connect-vercel.md](references/connect-vercel.md). Linear and PostHog have converters too: [connect-linear.md](references/connect-linear.md) and [connect-posthog.md](references/connect-posthog.md). The Linear converter also reads projects (commitments for slide 8, and stated targets for slide 11), initiatives (slide 3) and customer requests (slides 6 and 7). Its projects and targets come out as files for `intake.py import`, so the person confirms each row.

`collect.py` rejects a file with missing columns or bad rows and says what to fix. Fix the file. Do not edit rows to make them pass, and do not create a file for a source the user does not have.

### 3. Compute

Run `python3 scripts/compute_metrics.py --run run`. It writes `run/metrics.json`.

If it reports a **conflict** (two sources disagree on one figure), the figure is recorded as Unknown and shown as a gap. Tell the user both values and ask which source owns the number. Do not pick one, and do not accept "the higher one" or "the better-looking one" as an answer: ask which system is the record for that figure.

When the user names the owner, record it in `source_of_truth` in `run/intake.json`, for example `{"ARR": "billing"}` (a source key or the system's name), and run `compute_metrics.py` again. The ledger row then states the figure, who owns it and what the other source said.

Definitions and formulas are in [references/metrics-glossary.md](references/metrics-glossary.md).

### 4. Draft

Run `python3 scripts/draft.py --run run`. It writes `run/deck.json`: slides with data get their blocks, ledger references and a plain title; the rest keep a `data_needed` block.

Titles are drafted in plain board language. Improve them, following [references/writing-rules.md](references/writing-rules.md); `validate.py` warns (`jargon-in-title`) on engineering shorthand in a title. A title is a claim someone can check. You may change the wording. You may not change what the title claims, add a figure that is not on the slide, or add a cause the data does not show.

Titles are the only thing you edit in `run/deck.json`. Do not change blocks, figures, status words or the ledger by hand. If a slide looks wrong, the intake or the data is wrong: fix that and run the steps again, or tell the user what you found.

Slide IDs in the files are `00` (cover), `01` to `18`, `09b` (the board's delivery slide) and `A` to `D` (appendices). The deck has 19 core slides in all; no single cut shows more than 18.

For a slide's question, required data and a good and bad title, read its contract: `references/slides/NN.md`, where NN is `01` to `18` or `09b`.

### 5. Validate

Run `python3 scripts/validate.py run/deck.json`. Repeat until it reports 0 errors.

| Rule | It blocks |
|---|---|
| `no-ledger-row` | A slide showing figures that cites no ledger row |
| `speed-without-quality` | A speed metric with no quality metric on the same slide |
| `productivity-without-baseline` | An AI productivity claim with no baseline and window |
| `adoption-as-outcome` | An adoption or usage count in an outcome slot |
| `stale-figure` | A figure older than the reporting window, not marked stale |
| `bet-incomplete` | A bet with no stop rule, appetite or confidence |
| `branch-without-cause` | A line-of-sight branch with no stated cause |
| `point-target` | A delivery metric with a single-point target where it needs a range |
| `banned-phrase` | "10x" style multipliers, "AI-powered" |
| `missing-evidence` | A slide with neither its evidence block nor a `data_needed` block |
| `placeholder-left` | An unwritten title, or a gap with no real owner or date |
| `unsafe-link` | A link that is not http, https or mailto |
| `board-cut-too-long` | A board cut of more than 8 slides |
| `sample-not-illustrative` | A sample block not tagged illustrative |
| `sample-beside-data` | A sample on a slide that shows real data |
| `sample-cites-ledger` | A sample that cites a ledger row |
| `coverage-unstated` | A figure built from less than the reporting window, on a slide that does not say what it covers |

### 6. Review

Run `python3 scripts/review.py --run run` (add `--previous <last deck.json>` if there is one). It prints the change list, the gaps and a checklist, and saves them as `run/review.md`. Show them to the user.

Ask a named person for an explicit yes before the board cut renders. A yes from earlier in the conversation, or one implied by the request, does not count. Ask again, now.

### 7. Render

```
python3 scripts/render.py run/deck.json --out run/update.html
python3 scripts/render.py run/deck.json --out run/board.html --cut B --signed-off-by "<name>"
python3 scripts/render.py run/deck.json --out run/staff.html --cut S
```

Render the cuts the user asked for; with no cut named, render the full deck (the first command). Only the board cut needs a sign-off. If nobody is available to give it, render the other cuts, do not render the board cut, and say that it is waiting on a named person's yes.

Each render writes the HTML file and the ledger as CSV beside it.

To hand someone a PDF, open the HTML in a browser and print to PDF: the deck's print stylesheet gives one landscape slide per page, no navigation or guidance, and the appendices (the ledger first) at the end. With Chrome installed, `python3 ../../tools/print_pdf.py run/staff.html run/staff.pdf` does the same headless from the repository root. A Board cut is only printed after its sign-off. Give the user the HTML, `run/deck.json` and the ledger CSV. Tell them how many slides show data and how many show gaps.

### 8. Write back

To share the update in Linear, run `python3 scripts/summary.py run/deck.json --out run/summary.md` (add `--cut L` or `--cut S`, and `--link <url>` if the HTML is shared somewhere). It lists each slide's title with its ledger IDs, the gaps, and the cited ledger rows. It refuses a deck with validator errors, and refuses the board cut without `--signed-off-by "<name>"`.

Show the user the summary word for word. Post it only after they say yes, through the Linear connector: `save_document` for a document, or `save_status_update` for a project update. Never auto-post the board cut, not even from a scheduled run: a named person signs it off in that session, and you post it only after they say yes to posting.

To run the draft every week, follow [references/weekly-rhythm.md](references/weekly-rhythm.md). The schedule lives outside the scripts and never renders, summarises or posts the board cut.

## Reference files

- [references/writing-rules.md](references/writing-rules.md): titles, status words, banned claims.
- [references/audience-cuts.md](references/audience-cuts.md): what each cut includes and leaves out, and the cadence.
- [references/metrics-glossary.md](references/metrics-glossary.md): every computed metric, its formula and its quality pair.
- [references/sources.md](references/sources.md): each source, the columns it needs and the slides it feeds.
- [references/connect-github.md](references/connect-github.md): pull delivery data straight from GitHub.
- [references/github-action.md](references/github-action.md): a weekly GitHub Action that builds the Leadership and Staff cuts in the team's own CI.
- [references/connect-vercel.md](references/connect-vercel.md): a labelled quality proxy from Vercel, for repositories with no reviews.
- [references/connect-linear.md](references/connect-linear.md): the investment slides, shipped vs impact, line of sight and customer requests from Linear.
- [references/weekly-rhythm.md](references/weekly-rhythm.md): drafting the update every week on a schedule.
- [references/connect-posthog.md](references/connect-posthog.md): the outcome scorecard from PostHog.
- [references/connect-jira.md](references/connect-jira.md): the investment slides, and commitments from epics or versions, from Jira.
- [references/connect-github-projects.md](references/connect-github-projects.md): the investment slides from a GitHub project board.
- [references/frameworks.md](references/frameworks.md): the reading behind each slide.
- Slide contracts: [01](references/slides/01.md), [02](references/slides/02.md), [03](references/slides/03.md), [04](references/slides/04.md), [05](references/slides/05.md), [06](references/slides/06.md), [07](references/slides/07.md), [08](references/slides/08.md), [09](references/slides/09.md), [09b](references/slides/09b.md), [10](references/slides/10.md), [11](references/slides/11.md), [12](references/slides/12.md), [13](references/slides/13.md), [14](references/slides/14.md), [15](references/slides/15.md), [16](references/slides/16.md), [17](references/slides/17.md), [18](references/slides/18.md).

## Requirements

Python 3.9 or later. Standard library only: nothing to install, and no network access needed.
