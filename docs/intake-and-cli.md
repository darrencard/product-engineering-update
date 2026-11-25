# Intake and CLI reference

This page has two parts. Part 1 lists every field in `intake.json`: its type, whether the code requires it, what it feeds and an example. Part 2 lists every script you can run from the command line, with each flag exactly as its parser defines it.

Every statement here comes from the scripts in `skills/product-engineering-update/scripts/` and the test fixture `evals/fixtures/complete/intake.json`. Where the code does not read a field, this page says so.

## Contents

- [Part 1: intake.json](#part-1-intakejson)
  - [How the intake works](#how-the-intake-works)
  - [Company and period](#company-and-period)
  - [Strategy and objectives](#strategy-and-objectives)
  - [Product lines and investment](#product-lines-and-investment)
  - [Outcomes and targets](#outcomes-and-targets)
  - [Delivery ranges](#delivery-ranges)
  - [AI features](#ai-features)
  - [Bets](#bets)
  - [Risks](#risks)
  - [Stopped work](#stopped-work)
  - [Decisions](#decisions)
  - [Commitments](#commitments)
  - [Status reasons](#status-reasons)
  - [Sources and provenance](#sources-and-provenance)
  - [Proposals (proposals.json)](#proposals-proposalsjson)
- [Part 2: command line](#part-2-command-line)
  - [Exit codes](#exit-codes)
  - [run.py](#runpy)
  - [intake.py](#intakepy)
  - [collect.py](#collectpy)
  - [compute_metrics.py](#compute_metricspy)
  - [draft.py](#draftpy)
  - [validate.py](#validatepy)
  - [review.py](#reviewpy)
  - [render.py](#renderpy)
  - [summary.py](#summarypy)
  - [ci.py](#cipy)
  - [landing_brief.py](#landing_briefpy)
  - [convert.py](#convertpy)
  - [from_*.py readers](#from_py-readers)

---

# Part 1: intake.json

## How the intake works

- `intake.py init` writes the empty template. Every field starts as `null`, `[]` or `{}`.
- A field that is `null`, `""`, `[]` or `{}` counts as Unknown. The slide it feeds shows a `data_needed` block with the gap owner and due date. The code never fills an Unknown with a guess.
- `intake.py check` lists what is still Unknown, by slide, and what blocks the run. A blocking problem makes it exit 1, and `run.py` and `ci.py` refuse to start.
- The file must be a JSON object, and `bets` must be a list of objects. Anything else is refused on read.

"Required" in the tables below means one of three things, as the code enforces it:

| Label | Meaning |
|---|---|
| **Blocking** | `intake.py check` reports it as BLOCKING when missing or malformed. `run.py` and `ci.py` will not start. |
| **Needed per item** | Each item in the list must have this key. `intake.py check` reports an item without it as blocking, for example `bets[0] has no "bet"`, and `draft.py` refuses with the same list. |
| **Optional** | The code works without it. The slide shows a gap, or a stated fallback such as "Not stated". |

Slide numbers refer to the deck in `assets/blank.deck.json`: 1 The answer, 2 Strategy on a page, 3 Line of sight, 4 Portfolio, 5 Investment mix, 8 Shipped vs impact, 9 Delivery system health, 11 Outcome scorecard, 12 AI in the product, 13 AI in how we build, 14 Risks & assumptions, 15 Stopped & won't do, 16 Next bets, 18 Decisions & asks.

## Company and period

These 7 fields (all but `author`) are the answers a run cannot start without. `run.py` asks for them, or takes them as flags.

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `company` | string | Blocking | Cover title, deck meta, footer, summary heading | `"Kestrel Labs"` |
| `author` | string | Optional | Cover line "By ...". Falls back to "the product and engineering leads" | `"the CPTO"` |
| `period.label` | string | Blocking | Cover, footer, gap text. `compute_metrics.py` matches analytics and AI tool rows to this label | `"2026-Q3"` |
| `period.start` | string, `YYYY-MM-DD` | Blocking, must be a date | The reporting window. The prior period is the same length, ending the day before | `"2026-07-01"` |
| `period.end` | string, `YYYY-MM-DD` | Blocking, must be a date | The reporting window. Also used by the "At this pace" projection on slide 11 | `"2026-09-30"` |
| `as_of` | string, `YYYY-MM-DD` | Blocking, must be a date | Slide 1 "Data as of", deck meta. `compute_metrics.py` stops if HR data is collected and `as_of` is missing | `"2026-09-30"` |
| `gap_owner` | string | Blocking | The owner on every `data_needed` block | `"the VP Engineering"` |
| `gap_due` | string | Blocking | The due date on every `data_needed` block. Free text | `"Q4"` |
| `voice` | string | Optional | How the author writes: a few lines, or a paragraph of a past update. Claude writes the prose in this voice; figures and checks never change | `"Short sentences. Numbers first. No adjectives."` |
| `gap_owners` | object | Optional | An owner per slide, keyed by slide ID. A listed slide's gaps go to that person; the rest go to `gap_owner` | `{"06": "Priya Shah, finance"}` |

## Strategy and objectives

Slide 2 fills only when all four `strategy` fields are present. Its title is `strategy.policy`.

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `strategy.diagnosis` | string | Optional | Slide 2, "Diagnosis" card | `"Dispatchers lose most of their day to exceptions that rules engines can't handle."` |
| `strategy.policy` | string | Optional | Slide 2 title and "Guiding policy" card | `"We win mid-market brokers by automating the exception, priced per load."` |
| `strategy.actions` | list of strings | Optional | Slide 2, "Coherent actions" card | `["Raise agent task success to 90%"]` |
| `strategy.non_goals` | list of strings | Optional | Slide 2, "We will not" card | `["Ship on-premise"]` |
| `objectives` | list of objects | Optional | `intake.py check` reports it Unknown for slide 3. No script reads its contents | `[{"name": "Grow ARR to $50M", "target": "$50M", "owner": "CEO"}]` |

The template comment gives each objective `name`, `target` and `owner`. Slide 3 groups bets by each bet's own `objective` string, not by this list.

## Product lines and investment

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `product_lines[].name` | string | Needed per item | Slide 4 table. Matched to the tracker's `product_line` values for each line's share of capacity | `"Dispatch Agent"` |
| `product_lines[].stage` | string | Optional | Slide 4 "Stage". Falls back to "Not stated". The template comment suggests Explore, Expand or Sustain; the code does not check it | `"Expand"` |
| `product_lines[].objective` | string | Optional | Slide 4 "Objective served". Falls back to "Not stated" | `"Grow ARR to $50M"` |
| `investment_plan` | object, work type to percent | Optional, but slide 5 stays a gap without it | Slide 5 plan against actual. Keys match the tracker's `work_type` values. A type is flagged over plan when its actual share is more than 3 points above plan | `{"New capabilities": 35, "Keep the lights on": 15}` |
| `rd_lines` | list of strings | Optional | Slide 5 row "R&D as a share of revenue". Matched to finance lines, ignoring case. Computed only when finance has a `Revenue` line and every named line | `["R&D payroll", "Cloud"]` |
| `capitalisation.work_types` | list of strings | Optional | Slide 5 capitalisable estimate. `investment_plan` work types that finance treats as capitalisable | `["New capabilities"]` |
| `capitalisation.cost_lines` | list of strings | Optional | Slide 5 capitalisable estimate. Finance lines the share applies to, matched ignoring case | `["R&D payroll"]` |
| `capitalisation.confirmed_by` | string or null | Optional | Slide 5 says "Confirmed by NAME", or "Not yet confirmed by finance." when null | `"Head of Finance"` |

Slide 4 also needs tracker data with product lines and work types. The capitalisable estimate appears only when both `work_types` and `cost_lines` are set, the tracker gives a work type mix and finance has every named cost line. It is always labelled an estimate for finance to confirm.

## Outcomes and targets

`north_star` and each item in `inputs` take the same keys. Each becomes one row of the slide 11 scorecard. The metric is found by name: first as an analytics or warehouse metric, then as any computed metric's label (for example `ARR` or `Change failure rate`). A name that matches nothing shows as "not collected" in a gap note.

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `north_star.metric` | string | Optional (Unknown for slide 11) | Slide 11 row. Also a candidate for slide 1 "What happened" | `"Loads cleared per week"` |
| `north_star.definition` | string | Optional | Slide 11 row definition. Wins over the analytics system's definition. Missing, it is reported Unknown and the validator flags the row (see [validator rules](validator-rules.md)) | `"Loads cleared with no manual touch"` |
| `north_star.target` | number | Optional (Unknown for slide 11) | Status word (landed, watch, stalled) and the "At this pace" projection. A target that is not a number is printed as given, its status shows watch and no projection is made | `22000` |
| `north_star.target_display` | string | Optional | The target as printed. Without it, the number plus `unit` | `"22K"` |
| `north_star.unit` | string | Optional | Unit for an analytics metric and for the printed target. Defaults to `count` in `compute_metrics.py` | `"%"` |
| `north_star.higher_is_better` | boolean | Optional, default `true` | Direction for status, projection and slide 8 "Moved" | `true` |
| `north_star.by` | string, `YYYY-MM-DD` | Optional | The "At this pace" note says whether the projection lands before or after this date. Ignored if not a date | `"2026-12-31"` |
| `north_star.owner` | string | Optional | Slide 11 "Owner" column. Falls back to "Owner not stated" | `"Agent team"` |
| `inputs[].metric` | string | Optional (an empty list is Unknown for slide 11) | Slide 11 row | `"Activation"` |
| `inputs[].definition` | string | Optional | As `north_star.definition`. `intake.py check` lists each input without one | `"Accounts with a first automated load inside 14 days"` |
| `inputs[].unit` | string | Optional | As `north_star.unit` | `"%"` |
| `inputs[].target` | number | Optional | As `north_star.target` | `50` |
| `inputs[].target_display` | string | Optional | As `north_star.target_display` | `"50%"` |
| `inputs[].higher_is_better` | boolean | Optional, default `true` | As `north_star.higher_is_better` | `true` |
| `inputs[].by` | string | Optional | As `north_star.by` | `"2026-12-31"` |
| `inputs[].owner` | string | Optional | As `north_star.owner` | `"Activation team"` |
| `inputs[].source` | string | Optional | Written by `intake.py import --targets`. No script reads it | `"Linear project brief"` |

`intake.py import --targets` adds inputs from a file. It refuses to import the North Star: change that in the interview.

## Delivery ranges

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `delivery_ranges` | object, metric label to range text | Optional (Unknown for slide 9) | Slide 9 scorecard "Healthy range" and status word | `{"Deploys per week": "3+", "Change failure rate": "under 5%"}` |
| `range_sources` | object | Written by `intake.py accept` | Slide 9 source line: "Healthy ranges for ... accepted from SOURCE." | see below |

A delivery metric shows on slide 9 only when its label has a range. The slide fills only when at least one speed metric and one quality metric show. The keys must match these labels exactly:

| Group | Labels |
|---|---|
| Speed | `Deploys per week`, `Lead time for change` |
| Quality | `Change failure rate`, `Deploys rolled back or followed by errors`, `Time to restore`, `Pull request review time`, `Rework rate` |
| Effectiveness | `Developer experience index` |

Range text is read as one of: `N+`, `over N`, `above N`, `at least N`, `under N`, `below N`, `at most N`, `up to N`, `N to M`, `between N and M`, or `N-M`. Inside the range is landed. Outside and improving is watch. Outside and not improving is stalled. Outside with no prior value, or a range the code cannot read, shows as watch.

Each `range_sources` entry, as `intake.py accept` writes it:

| Key | Type | Meaning |
|---|---|---|
| `range_sources.<metric>.suggested` | string | The suggested range |
| `range_sources.<metric>.accepted` | string | The range the user said yes to |
| `range_sources.<metric>.edited` | boolean | `true` when the user changed the suggestion |
| `range_sources.<metric>.source` | string | The citation for the suggestion |

## AI features

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `ai_features` | list of objects, or null | Optional | `[]` means none in production: slides 12 and 13 are removed. `null` means not asked yet: they stay as gaps | `[{"name": "Dispatch Agent", "eval_set": "v14"}]` |

The code only tests whether `ai_features` is exactly `[]`. No script reads `name` or `eval_set`.

## Bets

Every bet feeds slide 16. A bet with both `objective` and `cause` also feeds the slide 3 tree.

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `bets[].bet` | string | Needed per item | Slides 3 and 16 | `"Multi-stop reroutes"` |
| `bets[].commitment` | string | Optional | Slide 16 "Commitment". Falls back to "Not stated" | `"Promise"` |
| `bets[].appetite` | string | Blocking | Slide 16 "Appetite" | `"6 weeks, 5 engineers"` |
| `bets[].expected` | string | Optional | Slide 16 "Expected result", slide 3 outcome. Falls back to "Not stated" | `"Task success 86% to 90%"` |
| `bets[].confidence` | string | Blocking | Slides 3 and 16 | `"High"` |
| `bets[].stop_rule` | string | Blocking | Slide 16 "We stop if" | `"Evals gain under 2 points by week 3"` |
| `bets[].objective` | string | Optional | Slide 3 groups bets under this objective | `"Grow ARR to $50M"` |
| `bets[].cause` | string | Blocking | Slide 3, the stated reason the bet should move the objective | `"Higher task success lets accounts move more loads to the agent"` |
| `bets[].owner` | string | Optional | Slide 3. Falls back to "Owner not stated" | `"Agent team"` |

## Risks

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `risks[].risk` | string | Needed per item | Slide 14 table and title | `"One model provider carries most inference spend"` |
| `risks[].likelihood` | string | Optional | Slide 14. Falls back to "Not rated" | `"Medium"` |
| `risks[].impact` | string | Optional | Slide 14. Falls back to "Not rated" | `"High"` |
| `risks[].mitigation` | string | Optional | Slide 14 "Mitigation and owner". Falls back to "None yet" | `"Routing layer across 2 providers. Platform lead"` |
| `risks[].due` | string | Optional | Slide 14. Falls back to "No date" | `"Dec 2026"` |

## Stopped work

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `stopped[].what` | string | Needed per item | Slide 15 card title and slide title | `"Carrier marketplace"` |
| `stopped[].why` | string | Optional | Slide 15 card body. Falls back to "No reason recorded." | `"It did not serve the strategy"` |

## Decisions

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `decisions[].ask` | string | Needed per item | Slide 18 card title, and slide 1 "Now what" list | `"Approve a per-load pricing pilot"` |
| `decisions[].options` | string | Optional | Slide 18. Falls back to "not stated" | `"Pilot with 10 customers, or wait a quarter"` |
| `decisions[].recommendation` | string | Optional | Slide 18. Falls back to "No recommendation yet." | `"Run the pilot with 10 customers."` |
| `decisions[].deadline` | string | Optional | Slide 18. Falls back to "not set" | `"4 Nov 2026"` |

## Commitments

Last period's commitments, each with the outcome metric named before launch. They feed slide 8. `intake.py check` blocks on a malformed list.

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `commitments` | list of objects | Blocking if not a list | Slide 8 | see the rows below |
| `commitments[].commitment` | string, not blank | Blocking | Slide 8 row | `"Guided activation"` |
| `commitments[].shipped` | `"yes"` or `"no"` | Blocking. Case and spaces are ignored; anything else is refused | Slide 8 "Shipped" and the title count | `"yes"` |
| `commitments[].metric` | string or null | Blocking if neither a string nor null | Slide 8 "Metric, before to after" and "Result". Matched like a slide 11 metric | `"Activation"` |
| `commitments[].owner` | string | Optional | Slide 8. Falls back to "Owner not stated" | `"Activation team"` |
| `commitments[].source` | string | Optional | Slide 8 source line: "Commitments from ..." | `"Linear (Kestrel)"` |

The result is one of: Moved, Moved the wrong way, Flat, Too early to call (no prior period), Not shipped, or a "No movement" reason (no metric named, metric not collected, or two sources disagree). "Moved" never claims the commitment caused the change.

## Status reasons

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `status_reasons` | object, metric name to one line | Optional, but see below | Slide 1 "Since the last update", when `draft.py` runs with `--previous` | `{"Activation": "The new onboarding shipped in week 2"}` |

When a status word on slide 9 or 11 moved since the previous deck and this object has no reason for that metric, `draft.py` prints `[reason needed]` and `validate.py` blocks the deck. Write the reason yourself; the code never infers one.

## Sources and provenance

| Field | Type | Required | What it feeds | Example |
|---|---|---|---|---|
| `source_of_truth` | object, metric name to source | Optional. Only the user names it | When two sources disagree on an analytics metric, or finance and billing disagree on `ARR`, the named source is used and the other reading stays on the ledger row. The value matches a source key or system name, ignoring case | `{"ARR": "billing"}` |
| `connected` | list of source keys | Optional | No script in `scripts/` reads it. The test fixtures fill it | `["tracker", "billing"]` |
| `provenance` | object | Written by `intake.py confirm` | Records where each confirmed answer came from. No other script reads it | see below |

Each `provenance` entry, keyed by the dotted field name:

| Key | Type | Meaning |
|---|---|---|
| `provenance.<field>.evidence` | list of `{source, quote}` | The source and quote for each piece of evidence |
| `provenance.<field>.confirmed_by` | string | The name passed to `confirm --by` |
| `provenance.<field>.edited` | boolean | `true` when the user changed the value with `--edit` |

Example:

```json
"provenance": {
  "strategy.diagnosis": {
    "evidence": [{"source": "strategy.md", "quote": "Dispatchers lose most of their day to exceptions"}],
    "confirmed_by": "Sam Lee",
    "edited": false
  }
}
```

## Proposals (proposals.json)

Answers drafted from documents are held in `proposals.json`, beside the intake, and are never answers until confirmed.

The file you pass to `intake.py propose` is either `{"proposals": [...]}` or a bare list. Each proposal has:

| Key | Type | Rule |
|---|---|---|
| `field` | string | A top-level intake key, or one level down in an object field (`period.*`, `strategy.*`, `north_star.*`, `capitalisation.*`). `provenance`, `range_sources` and `source_of_truth` are refused |
| `value` | any | Must not be null or empty |
| `source` | string | A URL (`http://` or `https://`), or a file path. A path is read relative to the drafted file's folder; anything after `#` or `:` is ignored when finding the file |
| `quote` | string | At most 400 characters. For a file source it must appear in that file, ignoring case and spacing |
| `evidence` | list of `{source, quote}` | Optional, in place of `source` and `quote`, when a value draws on several places. Each item is checked the same way |

One bad proposal refuses the whole file. A new proposal for a field replaces a pending one for the same field. Each stored proposal has `field`, `value`, `evidence` and `status` (`pending` or `confirmed`).

---

# Part 2: command line

All scripts are in `skills/product-engineering-update/scripts/`. They use the Python standard library only and run on Python 3.9 or later. The examples assume you run them from the skill folder.

## Exit codes

| Code | When |
|---|---|
| 0 | Success |
| 1 | A script stops with a one-line message saying what to do (raised as `SystemExit` with a message, printed to stderr). Also: `intake.py check` with any blocking problem, and `validate.py` with any error |
| 2 | `argparse` rejected the arguments (an unknown flag, a missing positional, a value outside its choices) |

[Troubleshooting](troubleshooting.md) lists the messages and their fixes.

## run.py

One command from data to a rendered deck. It fills the 7 required answers, checks the intake, then runs collect, `compute_metrics.py`, `draft.py`, `validate.py` (stopping on any error) and `render.py`, in one process. It writes `run/intake.json` before it checks anything, so answers given as flags are kept. It makes no network calls.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--run` | path | `run` | The run folder. Created if missing |
| `--company` | string | none | Sets `company` |
| `--period-label` | string | none | Sets `period.label` |
| `--period-start` | `YYYY-MM-DD` | none | Sets `period.start` |
| `--period-end` | `YYYY-MM-DD` | none | Sets `period.end` |
| `--as-of` | `YYYY-MM-DD` | none | Sets `as_of` |
| `--gap-owner` | string | none | Sets `gap_owner` |
| `--gap-due` | string | none | Sets `gap_due` |
| `--no-ask` | switch | off | Never prompt. Stop if a required answer is missing. Without it, the script prompts only when stdin is a terminal |
| `--csv` | `SOURCE=FILE`, repeatable | `[]` | A CSV export for one source, passed to `collect.py` |
| `--system` | `SOURCE=NAME`, repeatable | `[]` | The system a `--csv` file came from, for the ledger. A CSV without one is recorded as "CSV export" |
| `--github-prs` | path | none | Merged pull requests as GitHub returns them. Needs `--repo` |
| `--github-deployments` | path | none | Deployments as GitHub returns them. Used with `--github-prs` |
| `--repo` | `owner/name` | none | The GitHub repository, for the ledger |
| `--vercel-deployments` | one or more paths | none | Production deployments as Vercel returns them. Needs `--vercel-project` |
| `--vercel-errors` | zero or more paths | `[]` | Runtime error reports as Vercel returns them. Needs `--vercel-errors-from` |
| `--vercel-errors-from` | `YYYY-MM-DD` | none | The first day the error reports cover |
| `--vercel-rollbacks` | zero or more paths | `[]` | Rolled-back deployment IDs, as JSON, one file per page |
| `--vercel-project` | string | none | The Vercel project name |
| `--linear-issues` | one or more paths | none | Completed issues as Linear returns them, one file per page |
| `--linear-work-type-prefix` | string | none | The label prefix that names a work type in Linear, for example `type:` |
| `--linear-work-type` | `LABEL=TYPE`, repeatable | `[]` | A Linear label that stands for a work type |
| `--posthog-query` | path | none | A PostHog HogQL query result with metric, period and value columns |
| `--retrieved-at` | `YYYY-MM-DD` | none | The day the data was pulled. Passed to every collector |
| `--previous` | path | none | The last update's `deck.json`. Slide 1 then lists what changed since it |
| `--agent-labels` | comma-separated string | `""` | GitHub labels that mark a pull request as written by an agent |
| `--agent-authors` | comma-separated string | `""` | GitHub logins that mark a pull request as written by an agent |
| `--staff` | switch | off | Also render the Staff cut to `run/staff.html` |
| `--board` | switch | off | Also render the Board cut to `run/board.html`. Needs `--signed-off-by` |
| `--signed-off-by` | string | none | The named person who gave an explicit yes to the Board cut |

Outputs: `run/data/`, `run/metrics.json`, `run/deck.json`, `run/update.html` and a `.ledger.csv` beside each HTML file. If no delivery ranges are set, it prints the suggested ranges to put to the user and does not apply them.

```sh
python3 scripts/run.py --run run --no-ask \
  --company "Kestrel Labs" --period-label 2026-Q3 \
  --period-start 2026-07-01 --period-end 2026-09-30 --as-of 2026-09-30 \
  --gap-owner "the VP Engineering" --gap-due Q4 \
  --csv tracker=linear.csv --system tracker=Linear \
  --github-prs prs.json --repo kestrel/dispatch --staff
```

## intake.py

Builds and checks `intake.json`. The first positional argument is the subcommand and the second is the intake path.

```
intake.py {init,check,suggest,accept,import,propose,confirm} path [metric] [flags]
```

| Argument or flag | Type | Default | Used by | Meaning |
|---|---|---|---|---|
| `command` | one of `init`, `check`, `suggest`, `accept`, `import`, `propose`, `confirm` | required | all | The subcommand |
| `path` | path | required | all | The intake file |
| `metric` | string, optional positional | none | `accept`, `propose` | `accept`: the metric whose range the user said yes to. `propose`: the drafted proposals file |
| `--range` | string | none | `accept` | The range as the user edited it, if they changed the suggestion |
| `--decisions` | path | none | `import` | A decision log with columns `ask`, `options`, `recommendation`, `deadline` |
| `--risks` | path | none | `import` | A risk register with columns `risk`, `likelihood`, `impact`, `mitigation`, `due` |
| `--stopped` | path | none | `import` | A stop list with columns `what`, `why` |
| `--commitments` | path | none | `import` | Last period's commitments with columns `commitment`, `shipped` (yes or no), `metric`, `owner`, `source` |
| `--targets` | path | none | `import` | Target metrics with columns `metric`, `target`, `better`, `by`, `owner`, `source`. Added to `inputs` |
| `--replace` | switch | off | `import` | Replace a list, or a target metric, the intake already holds |
| `--by` | string | none | `confirm` | The name of the person who said yes. Required by `confirm` |
| `--field` | string, repeatable | `[]` | `confirm` | A field to apply. None named means all pending proposals |
| `--edit` | `FIELD=JSON`, repeatable | `[]` | `confirm` | Apply a proposal as the user edited it. The value is parsed as JSON, or kept as plain text if it is not JSON |
| `--suggestions` | path | `assets/suggested_ranges.json` | `suggest`, `accept` | Hidden from `--help`. The suggested ranges file |

### init

Writes the empty template. Refuses if the file exists.

```sh
python3 scripts/intake.py init run/intake.json
```

### check

Prints each pending proposal, each BLOCKING problem and each Unknown field with the slide it leaves without data. Exits 1 if anything blocks, otherwise 0.

```sh
python3 scripts/intake.py check run/intake.json
```

### suggest

Prints a sourced suggested range for each delivery metric that has none yet, and names the metrics that have no sourced suggestion. Applies nothing.

```sh
python3 scripts/intake.py suggest run/intake.json
```

### accept

Records a range the user said yes to, in `delivery_ranges`, and records the suggestion in `range_sources`. With `--range`, records the user's edit. A metric with no suggestion needs `--range`.

```sh
python3 scripts/intake.py accept run/intake.json "Deploys per week" --range "3+"
```

### import

Reads the team's own documents into the intake. Each file is CSV or Markdown (`.md`, `.markdown`); the first table with every named column is used, column names ignoring case. Every row must fill the first column. A list the intake already holds is only replaced with `--replace`. For commitments, `shipped` is normalised to `yes` or `no`, and any bad row refuses the file. For targets, each `target` must be one number (such as `50%` or `40h`), `better` must be `higher` or `lower`, and one metric may not have 2 different targets.

```sh
python3 scripts/intake.py import run/intake.json --decisions decisions.md --risks risks.csv --commitments commitments.csv
```

### propose

Stores drafted answers in `proposals.json` beside the intake. See [Proposals](#proposals-proposalsjson) for the format and checks.

```sh
python3 scripts/intake.py propose run/intake.json drafted.json
```

### confirm

Applies the pending proposals the user said yes to, writes each into the intake and records `provenance`. With no `--field`, every pending proposal is applied, including when only `--edit` is given. A field named in `--field` or `--edit` with no pending proposal is refused.

```sh
python3 scripts/intake.py confirm run/intake.json --by "Sam Lee" --field strategy.diagnosis --edit 'strategy.policy="Sell the judgment"'
```

## collect.py

Normalises one source's data into `run/data/<source>.json`. It checks the columns, coerces numbers and dates, and records where the data came from. It calls no connector itself. A file over 50 MB or 500,000 rows is refused.

| Argument or flag | Type | Default | Meaning |
|---|---|---|---|
| `source` | optional positional, one of `ai_tools`, `analytics`, `billing`, `crm`, `customer_requests`, `docs`, `evals`, `finance`, `hr`, `incidents`, `research`, `security`, `source_control`, `support`, `survey`, `tracker`, `warehouse` | none | The source to write. With none, the sources are listed |
| `--csv` | path | none | A CSV file. Pass exactly one of `--csv` or `--json` |
| `--json` | path | none | A JSON file |
| `--system` | string | none | The system the data came from, for the ledger, for example `Linear`. The script refuses to run without it |
| `--query` | string | none | The query, report or URL that produced the data |
| `--retrieved-at` | `YYYY-MM-DD` | the file's modified date | The day the data was fetched |
| `--run` | path | `run` | The run folder |
| `--list` | switch | off | Print every source and its columns (a trailing `?` marks an optional column), then exit |

```sh
python3 scripts/collect.py tracker --csv issues.csv --system Linear --query "Completed issues, Q3" --retrieved-at 2026-09-30 --run run
```

## compute_metrics.py

Does all the arithmetic. Reads `run/intake.json` and every `run/data/<source>.json`, and writes `run/metrics.json`: each metric with its prior value, display text and ledger row ID, the ledger, and any conflicts. When two sources disagree on a figure, it is recorded as a conflict with confidence Unknown. For analytics metrics and ARR, a source named in `source_of_truth` is used instead.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--run` | path | `run` | The run folder |

```sh
python3 scripts/compute_metrics.py --run run
```

## draft.py

Drafts `run/deck.json` from `run/intake.json` and `run/metrics.json`, starting from `assets/blank.deck.json`. A slide without its data keeps a `data_needed` block. Slides 12 and 13 are removed when `ai_features` is `[]`.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--run` | path | `run` | The run folder |
| `--previous` | path | none | The last update's `deck.json`. Slide 1 then lists each status that moved, each target that moved, and each metric added or dropped |

```sh
python3 scripts/draft.py --run run --previous last-quarter/deck.json
```

## validate.py

Checks a deck before it renders: its shape against `assets/deck.schema.json`, its references, and the overclaim rules. Errors block the render; warnings do not. Exits 1 on any error. The rules are in [validator rules](validator-rules.md).

| Argument or flag | Type | Default | Meaning |
|---|---|---|---|
| `deck` | path, positional | required | The deck JSON file |
| `--json` | switch | off | Print the report as JSON instead of text |

```sh
python3 scripts/validate.py run/deck.json
```

## review.py

Writes `run/review.md` and prints it: the change in every computed metric against the prior period, what moved since the previous deck, the gaps, and a checklist. Show it to the person before anyone signs off the Board cut. Needs `run/deck.json`.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--run` | path | `run` | The run folder |
| `--previous` | path | none | Last period's `deck.json`, to compare against |

```sh
python3 scripts/review.py --run run --previous last-quarter/deck.json
```

## render.py

Renders a deck to one self-contained HTML file with inline CSS, JS and fonts, and writes the ledger as CSV beside it (`<name>.ledger.csv`). It refuses a deck with validator errors.

| Argument or flag | Type | Default | Meaning |
|---|---|---|---|
| `deck` | path, positional | required | The deck JSON file |
| `--out` | path | required | The HTML file to write |
| `--cut` | `L`, `B` or `S` | none (the full deck) | Render one audience's cut: Leadership, Board & investors, or All staff. Checked against the deck's audiences |
| `--signed-off-by` | string | none | The person who reviewed the change list. Required for `--cut B` |
| `--skip-validate` | switch | off | For tests of the renderer only |

```sh
python3 scripts/render.py run/deck.json --out run/board.html --cut B --signed-off-by "Sam Lee"
```

## summary.py

Writes a Markdown summary of the deck, ready to post to Linear: each slide's title, the ledger rows it cites, the gap slides, and the cited ledger rows. It writes a file and never posts. It refuses a deck with validator errors.

| Argument or flag | Type | Default | Meaning |
|---|---|---|---|
| `deck` | path, positional | required | The deck JSON file |
| `--out` | path | required | The Markdown file to write |
| `--cut` | `L`, `B` or `S` | none (the full deck) | Summarise one audience's cut. Any other value is refused |
| `--signed-off-by` | string | none | The person who said yes. Required for `--cut B` |
| `--link` | URL | none | Where the rendered update can be opened. Must start with `https://`, `http://` or `mailto:` |

```sh
python3 scripts/summary.py run/deck.json --out run/staff.md --cut S --link https://example.com/update.html
```

## ci.py

The GitHub Action's run step; it also runs on a laptop. It copies the intake into a temporary run folder (never writing back), passes every CSV in the data folder whose file name is a source key to `collect.py`, passes the GitHub exports to the GitHub reader, runs `run.py --no-ask`, and renders the Leadership and Staff cuts. It never renders the Board cut. It refuses an intake with blocking problems. A `source_control.csv` is skipped when the GitHub exports have rows. See [security](security.md) for the Action's permissions.

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `--intake` | path | `.update/intake.json` | The team's intake |
| `--data-dir` | path | `.update` | A folder of CSV exports named after their source, such as `tracker.csv` |
| `--prs` | path | none | Merged pull requests, as `gh pr list --json` wrote them. Needs `--repo` when it has rows |
| `--deployments` | path | none | Deployments, as `gh api .../deployments --paginate` wrote them |
| `--repo` | `owner/name` | none | For the ledger |
| `--retrieved-at` | `YYYY-MM-DD` | none | The day the exports were made |
| `--out` | path | `deck-out` | Where `leadership.html`, `staff.html`, their ledgers, `deck.json` and `SUMMARY.txt` are written |

```sh
python3 scripts/ci.py --intake .update/intake.json --data-dir .update \
  --prs prs.json --deployments deployments.json --repo kestrel/dispatch --out deck-out
```

## landing_brief.py

Reads a landing brief from a Linear project description and drafts the project update it implies. The input is a Markdown file, or the JSON Linear returns for a project. The brief sits under a heading named "Landing brief" as `Key: value` lines. A brief with any missing, unknown, repeated or unreadable part is refused whole. The status rule matches the deck's: landed (bar met), watch (moving the right way, or no prior value), stalled (flat or moving the wrong way). It prints text and makes no network calls.

| Argument or flag | Type | Default | Used by | Meaning |
|---|---|---|---|---|
| `command` | `check` or `update` | required | both | `check` parses the brief and prints it as JSON. `update` drafts the project update |
| `path` | path | required | both | A Markdown file with the project description, or Linear's JSON for the project |
| `--current` | number | none | `update` | The metric's value now, from the team's own data. Required by `update` |
| `--prior` | number | none | `update` | The value at the last reading. Leave it out when there is none |
| `--as-of` | `YYYY-MM-DD` | none | `update` | Today's date, to say when the brief's date has passed |
| `--json` | switch | off | `update` | Print `status`, `health` (Linear's `onTrack`, `atRisk` or `offTrack`) and `body` as JSON |

```sh
python3 scripts/landing_brief.py update project.md --current 46 --prior 41 --as-of 2026-11-23
```

## convert.py

Shared helpers for the `from_*.py` readers. It has no command line of its own and is not run directly.

## from_*.py readers

The 19 readers (`from_ai_spend.py`, `from_amplitude.py`, `from_gdrive.py`, `from_github.py`, `from_github_projects.py`, `from_hubspot.py`, `from_incidentio.py`, `from_intercom.py`, `from_jira.py`, `from_linear.py`, `from_mixpanel.py`, `from_notion.py`, `from_pagerduty.py`, `from_posthog.py`, `from_salesforce.py`, `from_sentry.py`, `from_stripe.py`, `from_vercel.py`, `from_zendesk.py`) turn a system's own export into a source file. Their flags are in [connectors](connectors.md).
