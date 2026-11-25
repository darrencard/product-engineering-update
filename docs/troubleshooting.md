# Troubleshooting

Every script stops with one line that names the script, says what went wrong and what to do. This page lists those messages, grouped by the step that prints them, with the cause and the fix.

Commands run from the skill's folder (`skills/product-engineering-update/` in this repository) and assume the run folder is `run/`. Messages below are quoted from the code. Parts in angle brackets, such as `<path>`, stand for what the script fills in.

For what each validator rule means, see [Validator rules](validator-rules.md). For every flag, see the [Intake and CLI reference](intake-and-cli.md). For each system's export, see [Connectors](connectors.md).

## Contents

- [A note on `gh` and network access](#a-note-on-gh-and-network-access)
- [Intake](#intake)
- [run.py and ci.py before the run starts](#runpy-and-cipy-before-the-run-starts)
- [Collecting a CSV or JSON export](#collecting-a-csv-or-json-export)
- [Converters that find nothing](#converters-that-find-nothing)
- [Speed with no quality pair](#speed-with-no-quality-pair)
- [Computing metrics](#computing-metrics)
- [Two sources disagree](#two-sources-disagree)
- [Drafting, and a period with no data](#drafting-and-a-period-with-no-data)
- [The deck file cannot be read](#the-deck-file-cannot-be-read)
- [The render is blocked](#the-render-is-blocked)
- [The board cut needs `--signed-off-by`](#the-board-cut-needs---signed-off-by)
- [Other render and summary failures](#other-render-and-summary-failures)
- [Landing briefs](#landing-briefs)

## A note on `gh` and network access

No script runs `gh` or makes a network call. The scripts read files you, the session's connector or the GitHub Action have already saved, and write files. So there is no "gh not installed" or "not signed in" message from the skill itself. If `gh pr list` or `gh api` fails, that is `gh`'s own error: fix it with `gh auth login` and run the export again, then pass the saved file to the script.

---

## Intake

### The intake does not exist

```text
intake: run/intake.json does not exist. Run `intake.py init run/intake.json` to write an empty one.
```

**Fix.**

```sh
python3 scripts/intake.py init run/intake.json
```

### The intake already exists

```text
intake: run/intake.json already exists. It holds interview answers, so it is not overwritten. Edit it, or delete it first.
```

**Why.** `init` never overwrites answers. **Fix.** Edit the file you have.

### The intake cannot be read

| Message | Fix |
|---|---|
| `intake: <path> is not UTF-8 text. Save it as UTF-8 JSON, then run this again.` | Save the file as UTF-8. |
| `intake: <path> is not valid JSON (line N, column N: <reason>). Fix the file, then run this again.` | Fix the JSON at that line. |
| ``intake: <path> is not an intake: it must be a JSON object, and bets a list of objects. Start again from `intake.py init`.`` | The file is a list, or `bets` is not a list of objects. Fix `bets`, or start from `intake.py init`. |
| `intake: cannot write <path> (<reason>). Create the run folder first, then run this again.` | `mkdir -p run`, then `init` again. |

### `intake.py check` reports BLOCKING lines

```sh
python3 scripts/intake.py check run/intake.json
```

`check` prints `BLOCKING` lines for what a run cannot start without, and `unknown` lines for what will show as a gap. It exits `1` when anything blocks. The blocking lines are:

| Line | Why | Fix |
|---|---|---|
| `BLOCKING  company` (or `period.label`, `period.start`, `period.end`, `as_of`, `gap_owner`, `gap_due`) | One of the 7 required answers is empty. | Fill it in the intake, or pass it to `run.py` (see below). |
| `BLOCKING  period.start (must be YYYY-MM-DD, got '<value>')` (also `period.end`, `as_of`) | A date is not `YYYY-MM-DD`. | Write it as `2026-09-30`. |
| `BLOCKING  bet "<name>" has no appetite` (or `confidence`, `stop_rule`) | Every bet needs all three. The validator would block the deck anyway ([`bet-incomplete`](validator-rules.md#bet-incomplete)). | Ask the bet's owner and fill them in. |
| `BLOCKING  bet "<name>" states no cause linking it to an objective` | A bet has no `cause`. | Write why the bet should move the objective. |
| `BLOCKING  commitment N has no commitment` | A commitments row is unnamed. | Name it or remove the row. |
| `BLOCKING  commitment N ("<name>") has shipped '<value>'; write yes or no` | `shipped` is not `yes` or `no`. | Write `yes` or `no`. Anything else is refused, never guessed. |
| `BLOCKING  commitment N ("<name>") names its metric as <value>; write the metric's name, or leave it empty` | `metric` is not text. | Write the metric's name, or `null`. |
| `BLOCKING  commitment N is not an object` / `BLOCKING  commitments must be a list` | The commitments field has the wrong shape. | Make it a list of objects. |

`unknown` lines never block. Each says which slide will show a gap, for example `unknown   risks  (slide 14 will show data needed)`.

### Importing a document is refused

`intake.py import` reads a team's own decision log, risk register, stop list, commitments or targets. A file is refused whole, never read by guessing.

| Message | Why | Fix |
|---|---|---|
| `intake: import needs --decisions, --risks, --stopped, --commitments or --targets.` | No file was named. | Pass at least one. |
| `intake: <path> has no table with the columns <columns>. Found: <headers>. Rename the columns; nothing was imported.` | No table in the file has every required column. | Rename the columns. Decisions need `ask, options, recommendation, deadline`. Risks need `risk, likelihood, impact, mitigation, due`. Stopped needs `what, why`. Commitments need `commitment, shipped, metric, owner, source`. Targets need `metric, target, better, by, owner, source`. |
| `intake: <path> has rows with no <first column> (table rows N). Fill them in or delete them.` | The first column names the item and must be filled in every row. | Fill or delete those rows. |
| `intake: the intake already holds N <list>. Pass --replace to replace them with <file>.` | The intake already has that list. | Add `--replace` if the file should win. |
| `intake: <path> was not imported, because:` followed by one line per problem | Commitments: a `shipped` value is not yes or no. Targets: a target is not one number, `better` is not `higher` or `lower`, one metric has two targets, or a metric is already held. | Fix each listed row, then import again. |
| `intake: <path> names the North Star, <metric>. Change the North Star in the interview, not by import.` | A targets file tried to change the North Star. | Remove that row. |
| `intake: cannot read <path> (<reason>). Save it as UTF-8 CSV or Markdown.` | The file is not readable UTF-8. | Save it as UTF-8 CSV or Markdown. |

### Proposals and confirmations are refused

| Message | Fix |
|---|---|
| `intake: propose needs the drafted file, for example propose run/intake.json drafted.json.` | Pass the drafted proposals file. |
| `intake: <file> holds no proposals. Write {"proposals": [{"field", "value", "source", "quote"}]}.` | Use that shape. |
| `intake: no proposals were stored, because:` followed by lines such as `proposal 2: strategy.policy: its quote does not appear in plan.md. Quote the document word for word.` | Every proposal needs a known field, a value, a source and a quote of at most 400 characters. A quote from a local file must appear in that file. Fix each listed proposal. |
| `intake: confirm needs --by with the name of the person who said yes.` | `python3 scripts/intake.py confirm run/intake.json --by "Name"` |
| `intake: there are no proposals beside run/intake.json. Run propose first.` | Run `propose` first. |
| ``intake: no pending proposal for <field>. `intake.py check` lists them.`` | Run `intake.py check` to see what is pending. |
| `intake: --edit takes FIELD=VALUE, for example --edit "strategy.policy=Sell the judgment". Got '<value>'.` | Add the `=`. |

### Healthy ranges

| Message | Fix |
|---|---|
| `intake: accept needs the metric name, for example accept run/intake.json "Deploys per week".` | Name the metric. |
| `intake: there is no suggested range for "<metric>". Ask the user for one and pass it with --range.` | `python3 scripts/intake.py accept run/intake.json "<metric>" --range "under 40h"` with the range the person gave. |
| `intake: cannot read the suggested ranges in <path> (<reason>). Reinstall the skill.` | `assets/suggested_ranges.json` is missing or broken. Reinstall the skill. |

---

## run.py and ci.py before the run starts

| Message | Why | Fix |
|---|---|---|
| `run: still needed before the run can start: --company, --gap-owner. Pass them, or run in a terminal to be asked.` | A required answer is missing and `run.py` cannot prompt (no terminal, or `--no-ask`). | Pass the listed flags: `--company`, `--period-label`, `--period-start`, `--period-end`, `--as-of`, `--gap-owner`, `--gap-due`. |
| `run: the intake has blocking problems:` followed by the same lines as [`intake.py check`](#intakepy-check-reports-blocking-lines) | A date, bet or commitment is not usable. | Fix each line in `run/intake.json`. |
| `run: --csv takes SOURCE=FILE, for example --csv tracker=linear.csv. Got '<value>'.` (also for `--system`) | The `=` is missing. | Write `--csv tracker=linear.csv`. |
| `run: --github-prs needs --repo OWNER/NAME, for the ledger.` | The ledger must name the repository. | Add `--repo acme/app`. |
| `run: --vercel-deployments needs --vercel-project NAME, for the ledger.` | Same, for Vercel. | Add `--vercel-project <name>`. |
| `run: --vercel-errors needs --vercel-errors-from, the first day the error reports cover.` | Without it, older deploys would count as clean. | Add `--vercel-errors-from YYYY-MM-DD`. |
| `run: <script> stopped the run.` followed by that script's own message | A step failed. | Find the script's message on this page and fix that. |

For the GitHub Action:

| Message | Fix |
|---|---|
| `ci: <path> does not exist. Add the team's intake there first: references/github-action.md says how.` | Commit the intake at `.update/intake.json`, or pass `--intake`. |
| `ci: the intake cannot start a run yet. A scheduled job does not fill answers:` followed by the blocking lines | Fill those answers in the committed intake. A scheduled job never fills them. |
| `ci: --prs needs --repo OWNER/NAME, for the ledger.` | Pass `--repo`. |
| `ci: the run stopped.` followed by the step's message | Fix the step's message, found on this page. |

`ci.py` also prints, without stopping, `ci: the repository has no merged pull requests or deployments to read, so delivery shows as a gap.` That is expected for a repository with no activity in the exports.

---

## Collecting a CSV or JSON export

`collect.py` normalises one source's export. It never skips a bad row silently. To see every source and its columns (`?` marks an optional column):

```sh
python3 scripts/collect.py --list
```

| Message | Why | Fix |
|---|---|---|
| `collect: pass exactly one of --csv or --json` | Both or neither were given. | Pass one. |
| `collect: --system is required. The ledger must name where each figure came from.` | No system name. | Add `--system "Linear"` (or the real system). |
| `collect: <path> does not exist. Check the path, then run this again.` | Wrong path. | Fix the path. |
| `collect: <path> is not a file. Pass the exported CSV file itself.` | A folder was passed. | Pass the file. |
| `collect: <path> is not UTF-8 text. Export it again as UTF-8 CSV, then run this again.` | Wrong encoding. | Export again as UTF-8. |
| `collect: <path> is not a CSV this can read (<reason>). Export it again as plain UTF-8 CSV.` | Malformed CSV. | Export again as plain CSV. |
| `collect: <path> is not valid JSON (line N, column N: <reason>). Fix the file or export it again.` | Malformed JSON. | Fix or export again. |
| `collect: <path> must hold a list of rows, or an object with a rows list` | JSON is the wrong shape. | Save a list of row objects, or `{"rows": [...]}`. |
| `collect: every row in <path> must be an object of column: value, for example {"id": "A-1"}. Export it again as rows.` | A row is not an object. | Export as rows. |
| `collect: <path> has no rows. An empty source stays Unknown; do not create an empty file for it.` | The export is empty. | Leave the source out. Its slides show a gap. |
| `collect: <path> is missing the column(s) <columns>. <Source> needs: <columns>.` | A required column is absent. | Rename or add the columns, per `collect.py --list`. |
| `collect: <path> has N bad row(s). Fix the file; rows are not skipped silently.` followed by up to 10 lines such as `row <n>: <column> has '<value>', expected a date (YYYY-MM-DD)` or `row <n>: <column> is empty` | A value is empty where it is required, or is not a number, a date, or yes or no. | Fix each listed row. Booleans accept `yes`, `no`, `true`, `false`, `y`, `n`, `1`, `0`. |
| `collect: <path> has more than 500,000 rows. ...` or `collect: <path> is N MB; the limit is 50 MB. ...` | The export is far larger than one period. | Filter the export to the period. |
| `collect: --retrieved-at '<value>' is not a date. Use YYYY-MM-DD, for example 2026-09-30.` | Bad date. | Use `YYYY-MM-DD`. |
| `collect: cannot write <path> (<reason>). Check that --run names a folder you can write to.` | The run folder is not writable. | Check `--run`. |

---

## Converters that find nothing

Each `from_*.py` converter turns a system's raw export into a source file. When the export holds nothing usable, it stops and writes no file. That is on purpose: the source stays Unknown and its slides show a gap with an owner and a date. Do not create an empty file to get past it.

| Script | Message |
|---|---|
| `from_github.py` | `found no merged pull requests and no deployments. Check the export, then run this again.` |
| `from_vercel.py` | `found no live production deployments. Export with target production, then run this again.` |
| `from_linear.py` | `found no completed issues with an estimate. The tracker stays Unknown; do not create a file for it.` (it adds how many completed issues had no estimate) |
| `from_linear.py` | `found no project completed or due between <start> and <end>. Slide 8 stays a gap; do not create a file for it.` |
| `from_linear.py` | `found no customer requests linked to an issue or a project. The source stays Unknown; do not create a file for it.` |
| `from_jira.py` | `found no done issues with an estimate and a resolution date. The tracker stays Unknown; no file was written.` |
| `from_github_projects.py` | `found no done items with an estimate and a completion date. The tracker stays Unknown; no file was written.` |
| `from_pagerduty.py` | `found no resolved incidents. The incidents source stays Unknown; no file was written.` |
| `from_incidentio.py` | `found no incidents with both "<started>" and "<restored>". Check the timestamp names; no file was written.` |
| `from_sentry.py` | `found no release deployed to <environment>. Export releases with their lastDeploy, then run this again.` |
| `from_stripe.py` | `found no recurring revenue at any of those month ends. Billing stays Unknown; no file was written.` |
| `from_hubspot.py`, `from_salesforce.py` | `found no closed deals with a reason in the window.` / `found no closed opportunities with a reason in the window.` Both end `The CRM source stays Unknown; no file was written.` |
| `from_intercom.py`, `from_zendesk.py` | `found no conversations with a theme in the window.` / `found no tickets with a theme in the window.` Both end `Support stays Unknown; no file was written.` |
| `from_notion.py`, `from_gdrive.py` | `found no pages.` / `found no files.` Both end `The docs source stays Unknown; no file was written.` |

Each message starts with the script's name, for example `from_pagerduty: found no resolved incidents. ...`.

**Fix.** Check that the export covers the period and the right filter (completed, production, resolved). If the data truly does not exist, leave the source out.

Other converter refusals name their own fix in the message, for example `from_stripe: invoice <id> is in <currency>, not <currency>. Pass --currency, or export one currency at a time.` (a currency is refused, never converted) or `from_intercom: name the themes: --theme-prefix or --theme. The script does not choose a tag.` See [Connectors](connectors.md) for each system's export.

---

## Speed with no quality pair

Speed never shows without a quality metric beside it. Three places enforce this.

**`from_vercel.py` refuses deployments alone:**

```text
from_vercel: supply --errors or --rollbacks. Deployments alone say nothing about quality.
```

```text
from_vercel: --errors needs --errors-from, the first day the error files cover, so older deploys are not counted as clean.
```

Fix: pass the runtime error reports with their start date, or the rolled-back deployment IDs, or both:

```sh
python3 scripts/from_vercel.py --deployments deploys.json --errors errors.json --errors-from 2026-07-01 --project web --run run
```

**`from_github.py` warns, without stopping,** when no pull request has a review:

```text
from_github: no pull request has a review, so there is no review time or rework rate. Speed will be held back until a quality metric exists.
```

Fix: export pull requests with their `reviews` field (`gh pr list --state merged --json number,createdAt,mergedAt,reviews,labels,author`), or collect a quality source such as incidents.

**`draft.py` holds the delivery slide back.** When speed was measured but there is no quality metric, or no healthy range, slide 9 shows a gap that reads:

```text
Speed was measured (ledger L03) and is held back. This slide needs a quality metric to pair with speed (change failure rate, time to restore, review time, rework, or deploys rolled back or followed by errors) and a healthy range for each delivery metric.
```

Fix: collect a quality source, and record a healthy range for each delivery metric with `intake.py accept` (see [`point-target`](validator-rules.md#point-target)). `run.py` prints the suggested ranges to put to the person when the intake has none.

If a speed metric reaches a slide by hand, the validator blocks it: [`speed-without-quality`](validator-rules.md#speed-without-quality).

---

## Computing metrics

| Message | Why | Fix |
|---|---|---|
| `compute: run/intake.json is missing. Run intake.py first.` | No intake in the run folder. | `python3 scripts/intake.py init run/intake.json` |
| `compute: the intake has no period. Set period.label, period.start and period.end.` | The period is incomplete. | Fill all three. |
| ``compute: period.start and period.end must be dates (YYYY-MM-DD). Fix them, then check with `intake.py check`.`` | A period date is malformed. | Fix and run `intake.py check`. |
| `compute: the intake has no as_of date, and the headcount row needs one. Set as_of (YYYY-MM-DD), then run this again.` | An HR source was collected and `as_of` is empty. | Set `as_of`. |
| `compute: <path> is not a file collect.py wrote (it needs a system and a list of rows). Run collect.py for <source> again to rewrite it.` | A file in `run/data/` was edited or written by hand. | Run `collect.py` (or the converter) for that source again. |
| `compute: a data file in run/data has no '<column>' column. Run collect.py again for that source, then run this again.` | A data file is from an older run or was edited. | Collect that source again. |
| `compute: <path> is not valid JSON ...` / `is not UTF-8 text` / `cannot read <path> ...` | A file is unreadable. | Follow the fix in the message. |
| `compute: cannot write run/metrics.json (<reason>). Check that the run folder is writable, then run this again.` | The run folder is not writable. | Check permissions. |

If `compute` succeeds but ends `from no sources.`, nothing was collected. Every slide will show a gap. See [a period with no data](#drafting-and-a-period-with-no-data).

---

## Two sources disagree

`compute_metrics.py` does not stop on a conflict. It prints:

```text
  CONFLICT ARR: <system> says <value>; <system> says <value>. Recorded as Unknown. Ask which source owns the number.
```

**Why.** Two sources (for example billing and finance for ARR, or analytics and the warehouse for a metric) give values that differ beyond the tolerance. The figure becomes a gap and its ledger row is marked Unknown, which the validator reports as the [`unknown-rows`](validator-rules.md#unknown-rows) warning.

**Fix.** Ask the person which system owns the number. Never pick the higher one. Record their answer in the intake under `source_of_truth`, keyed by the metric's name, for example `{"ARR": "billing"}`, then compute and draft again:

```sh
python3 scripts/compute_metrics.py --run run
python3 scripts/draft.py --run run
```

---

## Drafting, and a period with no data

| Message | Fix |
|---|---|
| `draft: run/intake.json is missing. Run intake.py, collect.py and compute_metrics.py first.` (also for `metrics.json`) | Run the earlier steps first. |
| `draft: <path> is missing. Pass the deck.json from the last update, or leave --previous out.` | Fix the `--previous` path, or drop the flag. |

**A period with no data does not stop the draft.** `draft.py` reports how many core slides have data (`draft: wrote run/deck.json. N of M core slides across the 3 cuts have data (...). The rest show data needed.`). Each slide without data gets:

- the title `<Slide name> is not reported this period. The data is missing.`
- the line `No data collected for <period label>.`
- a `data_needed` block owned by the intake's `gap_owner`, due `gap_due`;
- where the skill has one, a greyed, illustrative sample of what the slide would show.

This is the intended result, not a failure. To fill a slide, collect its source for the period and run again. Check that the export covers the period: `compute_metrics.py` counts most rows by their dates against `period.start` and `period.end`, and analytics and survey rows by the period label. `run.py` ends with how many slides show data and how many show a gap, and `intake.py check` lists the open answers by slide.

---

## The deck file cannot be read

`validate.py`, `render.py` and `summary.py` share one loader. The message starts with the script's name.

| Message | Fix |
|---|---|
| `validate: <path> does not exist. Check the path, or run draft.py to write the deck first.` | Run `draft.py`, or fix the path. |
| `validate: <path> is a folder. Pass the deck JSON file inside it.` | Pass `run/deck.json`, not `run`. |
| `validate: <path> is not UTF-8 text. Save the deck as UTF-8 JSON, then run this again.` | Save as UTF-8. |
| `validate: <path> is not valid JSON (line N, column N: <reason>). Fix the file, then run this again.` | Fix the JSON. |
| `validate: cannot read <path> (<reason>). Check the file's permissions, then run this again.` | Check permissions. |
| `validate: cannot read <path> (<reason>). The skill's assets folder is incomplete; reinstall the skill.` | `assets/deck.schema.json` or `assets/contracts.json` is missing. Reinstall. |

---

## The render is blocked

```text
  [point-target] slide 09: "Deploys per week" has the target "40". ...
render: 1 blocking problem(s). Fix them or downgrade the claim, then render again.
```

**Why.** `render.py` runs the validator first and refuses on any error. Each error is listed above the last line. `summary.py` refuses the same way: `summary: the deck has N validator error(s). Run validate.py and fix them first.`

**Fix.** Look up each rule in [Validator rules](validator-rules.md), fix the data or downgrade the claim, then:

```sh
python3 scripts/validate.py run/deck.json
python3 scripts/render.py run/deck.json --out run/update.html
```

Do not reword a claim only to get past a rule. A hedge such as "up to 40% faster" is blocked the same way as "40% faster".

---

## The board cut needs `--signed-off-by`

| Script | Message |
|---|---|
| `render.py` | `render: the board cut needs --signed-off-by. Show the change list (review.py) and get an explicit yes first.` |
| `run.py` | `run: the board cut needs --signed-off-by with the name of the person who said yes to it, asked now.` |
| `summary.py` | `summary: the board cut needs --signed-off-by with the name of the person who said yes. Nothing was written.` |

**Why.** A person signs what a board sees. A yes from earlier in the conversation, or one implied by the request, does not count. `ci.py` never renders the board cut, because a scheduled job cannot give that yes.

**Fix.** Show the person the change list, ask for an explicit yes now, then pass their name:

```sh
python3 scripts/review.py --run run
python3 scripts/render.py run/deck.json --out run/board.html --cut B --signed-off-by "Jane Doe"
```

Or, with `run.py`: add `--board --signed-off-by "Jane Doe"`. `run.py` also refuses a name made only of spaces.

---

## Other render and summary failures

| Message | Fix |
|---|---|
| `render: --cut must be one of L, B, S` (the list comes from the deck's audiences) | Use one of the listed keys. |
| `summary: --cut must be one of <keys>.` | Use one of the listed keys. |
| `render: the link "<target>" is not allowed. Links must start with http://, https:// or mailto:. Fix the deck, then render again.` | Fix the link. The validator normally catches this first as [`unsafe-link`](validator-rules.md#unsafe-link). |
| `summary: --link must start with https://, http:// or mailto:, got '<value>'.` | Pass a full URL. |
| `render: unknown block type '<type>'. Use a block type from assets/deck.schema.json, then render again.` | Use a schema block type. |
| `render: cannot write <path> (<reason>). Check that the folder exists and is writable, then render again.` | Create the output folder or fix permissions. |
| `render: cannot read <path> (<reason>). The skill's assets folder is incomplete; reinstall the skill.` | `assets/template.html` is missing. Reinstall. |
| `review: run/deck.json is missing. Run draft.py first.` | Run `draft.py`. |

---

## Landing briefs

`landing_brief.py` reads a project's landing brief. A brief with any missing, unknown, repeated or unreadable part is refused whole, with every problem listed.

| Message | Fix |
|---|---|
| `landing_brief: there is no "Landing brief" heading. Paste the block from assets/project-template.md into the project description.` | Add the block. |
| `landing_brief: there are N "Landing brief" headings. Keep one.` | Remove the extras. |
| `landing_brief: the project description is empty.` | Write the description. |
| `landing_brief: the landing brief cannot be used:` followed by one line per problem | Fix each listed part. |
| `landing_brief: <path> is not valid JSON (<reason>, line N).` / `holds no project object.` / `has no description or content field.` | Save Linear's project JSON as it stands, or pass the description as Markdown. |
| `landing_brief: update needs --current, the metric's value now. Never estimate it.` | Pass `--current` from the team's own data. |
| `landing_brief: --as-of is '<value>'. Write it as YYYY-MM-DD.` | Fix the date. |
