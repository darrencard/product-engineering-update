# Validator rules

`validate.py` checks a deck before it renders. It reports two kinds of finding:

- **Errors** block the render. `render.py`, `summary.py` and `run.py` all refuse a deck with any error.
- **Warnings** never block. They point at something a reader may trip over.

This page lists every rule the validator can emit: 21 that block and 4 that warn. Each entry gives the rule ID exactly as it prints, what triggers it in the code, an example that trips it, and the fix.

To clear an error, fix the data or downgrade the claim. Do not reword a claim just to get past a rule, and never replace a missing figure with prose: use a `data_needed` block with an owner and a due date.

## Contents

- [Run the validator](#run-the-validator)
- [Read the output](#read-the-output)
- [Who else runs it](#who-else-runs-it)
- [Layer 1: shape](#layer-1-shape)
  - [`shape`](#shape)
- [Layer 2: references and deck-wide checks](#layer-2-references-and-deck-wide-checks)
  - [`reference`](#reference)
  - [`board-cut-too-long`](#board-cut-too-long)
  - [`stale-figure`](#stale-figure)
  - [`unsafe-link`](#unsafe-link)
  - [`placeholder-left`](#placeholder-left)
- [Layer 3: claims, slide by slide](#layer-3-claims-slide-by-slide)
  - [`no-ledger-row`](#no-ledger-row)
  - [`status-change-unexplained`](#status-change-unexplained)
  - [`capex-not-estimate`](#capex-not-estimate)
  - [`missing-evidence`](#missing-evidence)
  - [`undefined-metric`](#undefined-metric) (warning)
  - [`adoption-as-outcome`](#adoption-as-outcome)
  - [`point-target`](#point-target)
  - [`speed-without-quality`](#speed-without-quality)
  - [`branch-without-cause`](#branch-without-cause)
  - [`bet-incomplete`](#bet-incomplete)
  - [`productivity-without-baseline`](#productivity-without-baseline)
  - [`banned-phrase`](#banned-phrase)
  - [`sample-not-illustrative`](#sample-not-illustrative)
  - [`sample-beside-data`](#sample-beside-data)
  - [`sample-cites-ledger`](#sample-cites-ledger)
  - [`coverage-unstated`](#coverage-unstated)
  - [`jargon-in-title`](#jargon-in-title) (warning)
  - [`illustrative`](#illustrative) (warning)
- [Deck-wide warning](#deck-wide-warning)
  - [`unknown-rows`](#unknown-rows) (warning)
- [review.py is not a gate](#reviewpy-is-not-a-gate)
- [Summary table](#summary-table)

## Run the validator

From the skill's folder (`skills/product-engineering-update/` in this repository):

```sh
python3 scripts/validate.py run/deck.json          # readable report
python3 scripts/validate.py run/deck.json --json   # the same report as JSON
```

The script takes one positional argument, the deck file, and one flag, `--json`. It uses the standard library only and runs on Python 3.9 or later.

It exits `0` when there are no errors (warnings allowed) and `1` when there is at least one error.

If the file itself cannot be read, the validator stops before any rule runs. See [Troubleshooting](troubleshooting.md#the-deck-file-cannot-be-read).

## Read the output

Each finding is one line: a level, the rule ID in brackets, the slide, and a message that says what to do.

```text
ERROR   [point-target] slide 09: "Deploys per week" has the target "40". Delivery metrics take a healthy range, for example "under 40h" or "80 to 90%".
warning [jargon-in-title] slide 09: the title uses deploys. Say what it means for a reader outside the team; keep the term in the table.
validate: 1 error(s), 1 warning(s). Fix the data or downgrade the claim, then run this again.
```

- `slide 09` is the slide's `id`. `slide -` means the finding is about the whole deck (the meta block, the ledger or the cuts), not one slide.
- Errors print first, then warnings, each in the order the checks found them.
- The last line counts both. With no errors it ends `The deck can render.`

With `--json` the report is one object:

```json
{
  "ok": false,
  "errors": [{"rule": "point-target", "slide": "09", "message": "..."}],
  "warnings": []
}
```

`ok` is `true` when `errors` is empty.

## Who else runs it

The same `check()` function runs inside other scripts, so the same errors stop them:

| Script | What happens on an error |
|---|---|
| `render.py` | Prints each error to stderr as `  [rule] slide ID: message`, then stops with `render: N blocking problem(s). Fix them or downgrade the claim, then render again.` No HTML is written. |
| `summary.py` | Stops with `summary: the deck has N validator error(s). Run validate.py and fix them first.` |
| `run.py` | Runs `validate.py` as a step and stops with `run: validate.py stopped the run.` followed by the report. |
| `ci.py` | Calls `run.py`, so it stops with `ci: the run stopped.` followed by the same report. |

`render.py` has a `--skip-validate` flag. Its help text says it is "for tests of the renderer only". Do not use it to ship a deck.

The rules run in three layers. If layer 1 finds any problem, layers 2 and 3 do not run, so fix shape errors first and run the validator again.

---

## Layer 1: shape

### `shape`

**Severity:** blocks the render.

**Trigger.** The deck does not match `assets/deck.schema.json`: a missing required field, an unknown field, a wrong type, a value outside an enum, an empty string where the schema sets `minLength: 1`, or a string that fails a pattern. The report shows at most the first 25 shape problems, and no other rule runs while any remain.

There is one more `shape` error that runs after the schema passes: `meta.as_of` matches `YYYY-MM-DD` but is not a real date, such as `2026-02-30`.

Some fields that look like claim rules are enforced here first. In a `tree` block, an empty `cause` or `confidence` is a shape error. In a `data_needed` block, an empty `owner` or `due` is a shape error.

**Example.**

```json
{"type": "scorecard", "target_kind": "goal", "labels": {}, "rows": []}
```

`target_kind` must be `range` or `target`, and `labels` is missing its required keys.

**Messages look like:**

```text
$.slides[3].blocks[1]: fits none of the allowed shapes (closest: ...)
$.meta.as_of: "2026-02-30" is not a real date. Use YYYY-MM-DD.
```

**Fix.** Follow the path in the message (`$.slides[3].blocks[1]` is the second block of the fourth slide) and make that part match the schema. For `meta.as_of`, use a real calendar date.

---

## Layer 2: references and deck-wide checks

### `reference`

**Severity:** blocks the render.

**Trigger.** Any of these:

- Two slides share an `id` (`two slides share an id`).
- Two ledger rows share an `id` (`two ledger rows share an id`).
- A slide cites a ledger ID that has no row (`ledger reference L07 has no row`). Citations are read from the slide's `ledger_refs` and from every `[[L07]]` in its title, `asof` line and blocks.
- A slide's `requires` names a source key that is not in `meta.source_types` (`requires unknown source "crm"`).
- A slide's `rolls_up` names a slide ID that does not exist (`rolls up slide 19, which does not exist`).
- For an audience in `meta.audiences`, `meta.cuts.<key>` is not exactly the list of core slide IDs, in order, whose `audiences` include that key (`meta.cuts.B lists 7 slides, the slides themselves give 8`).

**Example.** Adding `"B"` to slide 02's `audiences` without updating `meta.cuts.B`.

**Fix.** Make IDs unique, add the missing ledger row or remove the citation, add the source type, or rebuild `meta.cuts` from the slides. `draft.py` writes `meta.cuts` from the slides, so drafting again also fixes a cut mismatch.

### `board-cut-too-long`

**Severity:** blocks the render.

**Trigger.** More than 8 slides have `kind: "slide"` and `"B"` in `audiences`. Cover and appendix slides do not count.

**Example.** A deck whose board cut holds 9 core slides.

**Message:** `the board cut holds 9 slides, the limit is 8`

**Fix.** Remove `"B"` from the slides the board does not need, and update `meta.cuts.B` to match.

### `stale-figure`

**Severity:** blocks the render.

**Trigger.** A ledger row's `retrieved_at` is more than 92 days before `meta.as_of` and the row does not have `"stale": true`. It also fires when `retrieved_at` is set but its first 10 characters are not a `YYYY-MM-DD` date. A row with no `retrieved_at` is skipped.

**Example.** `meta.as_of` is `2026-09-30` and ledger row `L01` has `"retrieved_at": "2026-01-15"`.

**Message:** `L01 (ARR ...) was retrieved 258 days before 2026-09-30. Refresh it or set stale: true and say so on the slide.`

**Fix.** Pull the data again and collect it with a current `--retrieved-at`. If the old figure must stay, set `"stale": true` on the row and say on the slide that it is stale.

### `unsafe-link`

**Severity:** blocks the render.

**Trigger.** A link target anywhere in the deck (the meta block, the ledger, or any slide) is not an `http://`, `https://` or `mailto:` address. The check reads every `[label](target)` in any string and every card `cta.href`. It is an allowlist, so `javascript:`, `data:`, `file:` and relative paths are all refused.

**Example.**

```json
"See the [runbook](javascript:alert(1))."
"Read the [plan](docs/plan.md)."
```

**Message:** `the link "javascript:alert(1)" is not allowed. Links must start with http://, https:// or mailto:. Fix the link or remove it.`

**Fix.** Use a full `https://` URL, or remove the link and keep the label as text.

### `placeholder-left`

**Severity:** blocks the render.

**Trigger.** Only runs when `meta.company` is not the blank template's `[Company]`, because then the deck is someone's draft. On any slide (cover and appendix included) it fires when:

- the title starts with `Write the claim`, the blank template's title;
- the title, the slide's `meta` lines or its blocks still hold `[Company]`, `[Period]`, `[Author]` or the sentence `Fill in each slide from the sources it names`;
- a `data_needed` block's `owner` or `due` is `[owner]`, `[date]`, or only spaces.

**Example.** A deck with `"company": "Acme"` that still has a gap with `"owner": "[owner]"`.

**Message:** `the data needed block "Data needed" has no real owner ("[owner]"). Name the person.`

**Fix.** Write the slide's claim, replace the template text, and name a real person and date on every gap. Setting `gap_owner` and `gap_due` in the intake and drafting again fills the gaps `draft.py` writes.

---

## Layer 3: claims, slide by slide

These rules run on slides with `kind: "slide"` only, not on the cover or appendices.

"The slide's text" below means its title, its `asof` line, and every string in its own blocks (card bodies, table cells, column labels and so on). A `sample` block is not part of the slide's own blocks. Template guidance (`guide`) and reading lists (`dig_deeper`) are not claims and are not checked.

### `no-ledger-row`

**Severity:** blocks the render.

**Trigger.** The slide shows figures and cites no ledger row. A slide shows figures when its own blocks (including blocks nested in cards) hold a `scorecard`, `tiles` or `plan_vs_actual` block, or a `table` with at least one row and at least one column with `"align": "num"`. It cites a row through `ledger_refs` or any `[[L01]]` in its text. A slide with `rolls_up` is exempt, because it condenses slides that carry their own rows.

**Example.** Slide 17 with a numeric table and `"ledger_refs": []`.

**Message:** `shows figures and cites no ledger row. Add the row and reference it, for example [[L01]] or ledger_refs.`

**Fix.** Add the ledger row for each figure and cite it. If the figure has no source, remove it and show a `data_needed` block.

### `status-change-unexplained`

**Severity:** blocks the render.

**Trigger.** The slide's title or blocks contain the marker `[reason needed]`. `draft.py` writes that marker when the deck is drafted with `--previous`, a scorecard metric's status moved since the previous deck, and the intake's `status_reasons` holds no reason for that metric.

**Example.** `Activation: watch to landed. Reason: [reason needed]`

**Fix.** Ask the person why the status moved, add one line per metric to `status_reasons` in the intake (for example `{"Activation": "The new onboarding shipped in week 2"}`), then run `draft.py` again. Do not write the reason into `deck.json` by hand, and do not infer it.

### `capex-not-estimate`

**Severity:** blocks the render.

**Trigger.** The slide's title or blocks contain `capitalis` or `capitaliz` (any case) and nowhere contain the word `estimate`.

**Example.** A table row `["Capitalisable R&D", "$1.2M"]` on a slide that never says "estimate".

**Message:** `states a capitalisable figure without calling it an estimate. What may be capitalised is the company's accounting policy; label it an estimate for finance to confirm.`

**Fix.** Label the figure an estimate on the slide, for example "Capitalisable, estimated". `draft.py` writes it that way.

### `missing-evidence`

**Severity:** blocks the render.

**Trigger.** The slide's ID has a contract in `assets/contracts.json`, and the slide's own blocks (including blocks nested in cards) hold none of the contract's evidence block types and no `data_needed` block. Text alone never counts.

The evidence each slide needs, from `assets/contracts.json`:

| Slide | Needs one of |
|---|---|
| 01, 02 | `cards`, `table` |
| 03 | `tree` |
| 04 | `table` |
| 05 | `plan_vs_actual`, `table` |
| 06 | `table`, `tiles` |
| 07 | `tiles` |
| 08 | `table` |
| 09 | `scorecard` |
| 09b, 10 | `cards` |
| 11 | `scorecard` |
| 12 | `tiles` |
| 13, 14 | `table` |
| 15 | `cards` |
| 16, 17 | `table` |
| 18 | `cards` |

The slide specs in [`references/slides/`](../skills/product-engineering-update/references/slides/) say the same per slide.

**Example.** Slide 06 with only a `text` block: "We learned a great deal from customers and will share more soon."

**Message:** `needs one of table, tiles, or a data_needed block with an owner and a due date. Prose does not count.`

**Fix.** Add the evidence block from computed data, or put a `data_needed` block in its place.

### `undefined-metric`

**Severity:** warns only.

**Trigger.** A `scorecard` with `"target_kind": "target"` (an outcome scorecard) has a metric row with no `definition`. Delivery scorecards (`"target_kind": "range"`) are not checked.

**Example.** `{"metric": "Activation", "prior": "39%", "actual": "41%", "target": "50%", "status": "watch"}`

**Fix.** Add one plain-English sentence that says what the metric counts: `north_star.definition` or the input's `definition` in the intake. Then draft again.

### `adoption-as-outcome`

**Severity:** blocks the render.

**Trigger.** A `scorecard` with `"target_kind": "target"` has a metric whose name matches the adoption pattern: adoption, feature usage, usage count, pilots started, seats, sign-ups, logins, page views, downloads, prompts sent, tokens used, or licences (or licenses). The full pattern is `ADOPTION` in `validate.py`.

**Example.** A row `"metric": "AI adoption, prompts sent"` on the outcome scorecard.

**Message:** `"AI adoption, prompts sent" is an adoption or usage count in an outcome slot. Move it to an input slide or replace it with the outcome it should drive.`

**Fix.** Move the count to an input slide, or replace it with the outcome it is meant to move. Seats, sign-ups, prompts and pilots are inputs ([writing rules](../skills/product-engineering-update/references/writing-rules.md#claims-the-deck-will-not-make)).

### `point-target`

**Severity:** blocks the render.

**Trigger.** A `scorecard` with `"target_kind": "range"` (a delivery scorecard) has a row whose `target` contains none of these: the word `to`, `under`, `over`, `below`, `above`, `at least`, `at most`, `up to`, `between`, or the characters `<`, `>`, `+`, `≤`, `≥`, `-`.

The test is a text match. A target with a hyphen in it passes even if it is not really a range, so read your targets as well.

**Example.** `"target": "40"` for "Deploys per week". `"40 per week"` also fails.

**Message:** `"Deploys per week" has the target "40". Delivery metrics take a healthy range, for example "under 40h" or "80 to 90%".`

**Fix.** Ask the person for a healthy range and record it in the intake, then draft again:

```sh
python3 scripts/intake.py suggest run/intake.json
python3 scripts/intake.py accept run/intake.json "Deploys per week" --range "35+"
```

Leave out `--range` to accept the suggestion as it stands. Only record a range the person said yes to.

### `speed-without-quality`

**Severity:** blocks the render.

**Trigger.** A speed metric appears with no quality metric beside it. There are three ways in:

- **Delivery scorecard** (`"target_kind": "range"`): a row's metric names speed, or a group row's label contains "speed", and no row's metric names quality.
- **Tiles:** a tile label names speed and no quality term appears anywhere in the slide's own blocks.
- **Table:** a speed metric appears in the first column of a row and no quality term appears anywhere in the slide's own blocks. A plain table is no way round the rule.

Speed terms: deploy, deploys, deployment frequency, lead time, cycle time, throughput, velocity, merge frequency, pull request(s) merged, time to merge.

Quality terms: change failure, failure rate, time to restore, restore, rework, defect, incident, review time, rollback, rolled back, followed by errors, escaped, bug.

Naming an incident tool in the slide's sources line does not count as a quality metric, because that line is not one of the slide's blocks.

**Example.**

```json
{"type": "table",
 "columns": [{"label": "Metric"}, {"label": "This period", "align": "num"}],
 "rows": [["Deploys per week", "4"], ["Lead time for change", "38h"]]}
```

**Messages.** For this table: `shows a speed metric in a table with no quality metric on the slide.` For tiles: `shows a speed metric in a tile with no quality metric on the slide.` For a scorecard with the same two rows: `shows Deploys per week, Lead time for change with no quality metric beside it. Add change failure rate, time to restore, review time or rework.`

**Fix.** Collect a quality source and show its metric on the same slide. For example, GitHub reviews give review time and rework rate, and `from_vercel.py` with `--errors` or `--rollbacks` gives deploys rolled back or followed by errors. If there is no quality data, the speed figure stays off the slide; `draft.py` holds slide 9 back as a gap and says why.

### `branch-without-cause`

**Severity:** blocks the render.

**Trigger.** A bet in a `tree` block has a `cause` that is only spaces. An empty `cause` is caught earlier as a [`shape`](#shape) error.

**Example.** `{"bet": "Self-serve onboarding", "cause": " ", ...}`

**Message:** `"Self-serve onboarding" states no cause. Say why the bet should move the objective.`

**Fix.** Write why the bet should move the objective, from the intake's `bets[].cause`. `intake.py check` already blocks a bet with no cause.

### `bet-incomplete`

**Severity:** blocks the render.

**Trigger.** Any of these:

- A bet in a `tree` block has a `confidence` that is only spaces (an empty one is a `shape` error).
- A `table` whose first column is labelled `Bet` (any case) has no column whose label contains `stop`, `appetite` or `confidence`.
- In such a table, a row's cell in the first matching column is empty or only spaces.

**Example.** On slide 16's bets table, the `We stop if` cell of the first row is `""`.

**Message:** `"Self-serve onboarding" has no stop rule.` or `the bets table has no appetite column.`

**Fix.** Fill in the bet's `appetite`, `confidence` and `stop_rule` in the intake, then draft again. `intake.py check` lists any bet that lacks them as `BLOCKING`.

### `productivity-without-baseline`

**Severity:** blocks the render.

**Trigger.** One sentence of the slide's text (or of a sample's text) contains all three of:

1. a productivity word: `productiv`, `faster`, `speed-up` or `speedup`, `time saved`, `hours saved`, `efficien`;
2. a number followed by `%`, `x` or `×`;
3. no baseline word: `baseline`, `than a year`, `than last quarter` (and similar), `year ago`, `on Q3` (any quarter), `against`, `versus`, `vs`, `from ... to`, `compared with`, `compared to`, `before`.

Sentences are split at `.`, `!` or `?` followed by a space, so the baseline must sit in the same sentence as the number.

**Example.** Both of these trip it, because hedging does not add a baseline:

```text
AI made engineering 40% more productive.
Engineers are up to 40% faster with AI.
```

This passes: `Pull requests move 18% faster than a year ago.`

**Fix.** State what the figure is measured against and over what period, in the same sentence, from real data. If there is no baseline, cut the number. See [writing rules](../skills/product-engineering-update/references/writing-rules.md#when-the-user-pushes-for-a-stronger-claim).

### `banned-phrase`

**Severity:** blocks the render.

**Trigger.** A sentence of the slide's text (or of a sample's text) contains a multiplier, matched as digits followed by `x` as a whole word (`10x`, `3X`), or the phrase `AI-powered` (any case).

**Example.** Title: `Delivery is 10x faster.`

**Message:** `uses a multiplier claim such as "10x" in: "Delivery is 10x faster."`

**Fix.** Replace the multiplier with the measured change and its baseline, for example "Lead time fell from 52h to 38h against last quarter." Remove "AI-powered".

### `sample-not-illustrative`

**Severity:** blocks the render.

**Trigger.** A top-level `sample` block on the slide has `"illustrative"` set to anything but `true`.

**Example.** `{"type": "sample", "illustrative": false, "label": "...", "blocks": [...]}`

**Fix.** Set `"illustrative": true`. `draft.py` writes samples that way.

### `sample-beside-data`

**Severity:** blocks the render.

**Trigger.** A slide holds a `sample` block and also real data: its own blocks include any type other than `cards`, `data_needed` and `text`, or the slide has a non-empty `ledger_refs`.

**Example.** Slide 11 has a scorecard and also a sample, or a gap slide with a sample also has `"ledger_refs": ["L01"]`.

**Message:** `shows real data and a sample. A sample may only sit beside a data_needed block; remove it.`

**Fix.** Remove the sample once the slide has real data. A sample belongs only on a gap slide.

### `sample-cites-ledger`

**Severity:** blocks the render.

**Trigger.** Any string inside a `sample` block contains a ledger citation such as `[[L01]]`.

**Example.** A sample with `{"type": "text", "variant": "note", "text": "ARR rose.[[L01]]"}`

**Message:** `has a sample that cites a ledger row. Sample figures are made up and cite nothing.`

**Fix.** Remove the citation. Sample figures are made up and must never pass for evidence.

### `coverage-unstated`

**Severity:** blocks the render.

**Trigger.** The slide cites a ledger row that has a `coverage` object (the figure is built from less than the reporting window), and the row's `coverage.text` does not appear, ignoring case, anywhere in the slide's text.

`compute_metrics.py` adds `coverage` when only part of the data has a known outcome, for example deploys with a known rolled-back-or-errors outcome, or pull requests with a known agent-authored mark.

**Example.** A slide cites `L09`, whose coverage text says what share of releases it counts, and the slide never says so.

**Message:** `cites L09, which is built from less than the window, but does not say "...". Put it on the figure.`

**Fix.** Put the coverage text on the slide, beside the figure. On a scorecard, the row's `coverage` field prints under the value; `draft.py` fills it.

### `jargon-in-title`

**Severity:** warns only.

**Trigger.** The slide's title contains engineering or finance shorthand: change failure rate, lead time, cycle time, keep the lights on, KTLO, capacity, ARR, NRR, GRR, MTTR, SLO, DORA, p90, p95, p99, throughput, velocity, story points, rework rate, eval, eval pass rate, deploy, PR, pull request, tech debt.

**Example.** Title: `Change failure rate rose from 5.1% to 7.7%.`

**Fix.** Say what the number means for a reader outside the team, for example "The share of releases that caused a problem in production rose from 5.1% to 7.7%." Keep the precise term in the table. See [writing rules](../skills/product-engineering-update/references/writing-rules.md#titles).

### `illustrative`

**Severity:** warns only.

**Trigger.** `meta.notice.illustrative` is `true` and the slide has `"illustrative": false`.

**Fix.** If the whole deck is illustrative, mark the slide illustrative too. If the deck holds real data, set `meta.notice.illustrative` to `false`.

---

## Deck-wide warning

### `unknown-rows`

**Severity:** warns only.

**Trigger.** One or more ledger rows have `"confidence": "Unknown"`. This is reported once for the deck, listing the IDs.

**Message:** `2 ledger row(s) are Unknown: L04, L11. Check that each shows as a data needed block and nowhere as a figure.`

**Fix.** Nothing to fix if each Unknown row shows as a gap. If one shows as a figure, replace it with a `data_needed` block. An Unknown row often comes from two sources disagreeing; see [Troubleshooting](troubleshooting.md#two-sources-disagree).

---

## review.py is not a gate

`review.py` writes `run/review.md` and prints it: the change in every computed metric against the prior period, conflicts, what moved since the previous deck (with `--previous`), the gaps, the ledger rows marked Unknown, the board cut's slides, and a checklist.

```sh
python3 scripts/review.py --run run
python3 scripts/review.py --run run --previous last-period/deck.json
```

It differs from `validate.py` in three ways:

- **It blocks nothing.** It has no rules and no rule IDs. It exits `0` whenever `run/deck.json` exists. Its only refusal is `review: run/deck.json is missing. Run draft.py first.`
- **Its checklist is for a person.** Lines such as "Every title is a claim the slide's evidence supports" are ticked by the reader, not checked by code.
- **It feeds the sign-off.** The board cut renders only with `--signed-off-by` on `render.py` (or `run.py --board`, or `summary.py --cut B`). The name should be the person who read the review and said yes. That gate lives in those scripts, not in `review.py` or `validate.py`. See [Troubleshooting](troubleshooting.md#the-board-cut-needs---signed-off-by).

---

## Summary table

| Rule | Severity | Layer | In one line |
|---|---|---|---|
| `shape` | blocks | 1 | The deck does not match the schema, or `meta.as_of` is not a real date. |
| `reference` | blocks | 2 | An ID, source key, rollup or cut points at something that does not exist or does not match. |
| `board-cut-too-long` | blocks | 2 | The board cut holds more than 8 core slides. |
| `stale-figure` | blocks | 2 | A ledger row was retrieved more than 92 days before `as_of` and is not marked stale. |
| `unsafe-link` | blocks | 2 | A link is not http, https or mailto. |
| `placeholder-left` | blocks | 2 | A named company's deck still holds template text or a gap with no real owner or date. |
| `no-ledger-row` | blocks | 3 | A slide shows figures and cites no ledger row. |
| `status-change-unexplained` | blocks | 3 | A status moved and the intake gives no reason. |
| `capex-not-estimate` | blocks | 3 | A capitalisable figure is not called an estimate. |
| `missing-evidence` | blocks | 3 | A slide has neither its evidence block nor a `data_needed` block. |
| `undefined-metric` | warns | 3 | An outcome metric has no definition. |
| `adoption-as-outcome` | blocks | 3 | An adoption or usage count sits on the outcome scorecard. |
| `point-target` | blocks | 3 | A delivery metric has a single-point target. |
| `speed-without-quality` | blocks | 3 | A speed metric has no quality metric on the same slide. |
| `branch-without-cause` | blocks | 3 | A tree bet's cause is blank. |
| `bet-incomplete` | blocks | 3 | A bet has no stop rule, appetite or confidence. |
| `productivity-without-baseline` | blocks | 3 | A productivity figure has no baseline in the same sentence. |
| `banned-phrase` | blocks | 3 | A multiplier such as "10x", or "AI-powered". |
| `sample-not-illustrative` | blocks | 3 | A sample is not tagged illustrative. |
| `sample-beside-data` | blocks | 3 | A sample sits on a slide with real data. |
| `sample-cites-ledger` | blocks | 3 | A sample cites a ledger row. |
| `coverage-unstated` | blocks | 3 | A partial-coverage figure's slide does not say what it covers. |
| `jargon-in-title` | warns | 3 | A title uses shorthand a board member may not know. |
| `illustrative` | warns | 3 | The deck is marked illustrative but a slide is not. |
| `unknown-rows` | warns | deck | Ledger rows are marked Unknown. |
