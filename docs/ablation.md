# Ablation: the skill against Claude alone

Measured on 24 November 2026 with v0.7.4. The harness is in [evals/ablation/](../evals/ablation/README.md). The raw verdicts, checks and Claude-alone decks are in `evals/ablation/measured/2026-11-24/`.

## The answer

On 6 synthetic companies, a blind judge preferred Claude alone to the skill in every comparison: 36 of 36 judgments and 18 of 18 pairs. The skill's pipeline was more exact: 0 figures it could not account for and 0 arithmetic errors. But Claude alone was close to as exact (1 clear error in 1,049 checked figures), and the judge found its decks more useful: it reconciled the data, flagged more gaps and wrote a board cut that could be sent.

So this eval does not support "the skill beats Claude alone". It supports a narrower claim: the skill's figures are always traceable, and Claude alone's are nearly always right.

## What was compared

| | Condition A: Claude alone | Condition B: the skill |
|---|---|---|
| What ran | Headless `claude -p --safe-mode`, Opus 5.5. No skill, plugin, MCP server or CLAUDE.md. A check of every transcript found no use of the skill. | The skill's pipeline, `scripts/run.py`, with the full deck and the board cut. No model. |
| Input | The fixture's `intake.json`, `systems.json` and CSVs, and one prompt: build an update for leadership, plus a board cut | The same files |
| Runs | 3 per fixture, 18 in all | 3 per fixture, 18 in all. The 3 decks per fixture are the same, apart from the render time |

The 6 fixtures are `complete`, `conflict_resolved`, `conflicting`, `no_ai`, `single_product` and `sparse` (tracker data only). 5 of the 6 are variants of one made-up company.

The judge was Opus 5.5 with no tools. It saw the fixture's data and 2 decks as plain text, labelled X and Y. It judged each of 5 criteria and gave an overall verdict, each with a reason. Each pair was judged in both orders.

## Results

### The blind judge

| Criterion | Claude alone | The skill | Tie |
|---|---|---|---|
| **Overall** | **36** | **0** | **0** |
| Every figure correct | 20 | 4 | 12 |
| No invented numbers | 18 | 15 | 3 |
| Speed paired with quality | 14 | 7 | 15 |
| Gaps shown, not filled | 36 | 0 | 0 |
| Board cut usable | 36 | 0 | 0 |

36 judgments over 18 pairs. Both orders of every pair named the same winner. The skill's win rate is 0 of 18 pairs, with a 95% Wilson interval of 0% to 18%. Every fixture went 6 to 0. The pairs are clustered (5 of 6 fixtures are one company), so the real uncertainty is wider than that interval.

### The noise band

| Test | Result |
|---|---|
| A deck against itself (24 judgments: 18 Claude alone, 6 the skill) | Tie every time, on every criterion |
| 2 different Claude-alone runs of the same fixture (12 judgments, 6 pairs) | 12 of 12 picked a winner. In 2 of 6 pairs the winner flipped when the order flipped |
| Position of the winner across the 36 A and B judgments | X 18, Y 18 |

The judge tells two Claude-alone decks apart, and its verdict between them is sometimes set by position. Between Claude alone and the skill it never flipped, so the 36 to 0 result is well outside that noise.

### Mechanical checks, no judge

| | Claude alone | The skill |
|---|---|---|
| Figures in the decks | 3,265 | 3,603 |
| Figures that no one-step derivation from the data produces | 204 | 0 |
| ... of those, invented on a reading of each one | 0 | 0 |
| Printed metrics checked against values recomputed from the CSVs | 1,049 | 717 |
| Arithmetic errors flagged | 2 | 0 |
| ... of those, real on a reading of each one | 1 | 0 |

The figure counts exclude dates, IDs, versions and bare whole numbers of 20 or less, and the skill's greyed illustrative samples (537 figures, all in the `sparse` decks).

I read all 54 distinct values behind the 204 unmatched figures. None was invented. All were derivations more than one step from the data, which the check does not cover: total R&D plan ($4.245M), churn printed as a negative, cost per successful task ($0.41 ÷ 0.82 = $0.50), monthly completions, the gap to the $50M objective, and quarterly revenue annualised to $41M. A few were account IDs read as numbers. So the count measures how much a deck derives, not how much it invents.

Of the 2 arithmetic flags, 1 is a real error: a `no_ai` deck counted 8 customer requests where the period holds 7, because it included one from May. The other is a June account count (40) printed beside September figures, which is ambiguous. The judge's reasons name 2 more small errors in Claude-alone decks that the check missed: "one deploy failed in each month" (July had 2) and "only Dispatch Agent completed work in September" (Platform completed an item on 2 September).

The check's blind spot: a random whole-number percentage matches some figure in the data 63% of the time, and a percentage to 1 decimal 39%. Dollar figures (2% to 5%) and 4-digit counts (5%) are tested properly. The rates for each fixture are in `calibration.json`.

### Why the skill lost

These are counts of the 36 judge reasons that mention each point. One reason can mention several.

| What the judge held against the skill | Mentions |
|---|---|
| The deck and board cut carry the template's Appendix C, a pitch for the skill, and a "Book a call" link | 36 |
| The decision is framed as "for you today", with a 4 Nov deadline | 24 |
| It does not reconcile quarterly revenue ($10.3M) with ARR ($10.9M), and uses the revenue line for R&D share | 23 |
| The board cut carries the full ledger, with empty rows | 22 |
| Template scaffolding prints, such as "Keys J and K move between slides" | 20 |
| The board cut prints a sign-off with no evidence one was given | 20 |
| Lead time is pull request open to merge, labelled "lead time for change" | 6 |
| In `sparse`, greyed samples name Kestrel Labs, which is also the fixture's company | 6 |

Some of these are fair, some are not. The revenue and ARR mismatch is real: the fixtures carry it, and Claude alone found it while the pipeline did not. Appendix C, the scaffolding text and the ledger in the board cut are real and fixable. The sample name is a fixture artefact: the fixtures reuse the sample company's name. The deadline point is contestable: the data is as of 30 September, when 4 November is still ahead.

**Counterfactual, not the shipped skill.** With Appendices B, C and D removed from the skill's decks before judging, the result was the same: 36 to 0, 18 of 18 pairs. The pitch alone does not explain the loss.

## Since this run

Version 0.8.0 fixes 4 of the judge's points: the template appendices and the pitch no longer print in a team's deck, the cover drops the template's reader instructions, the board cut carries only the ledger rows it cites, and revenue is checked against ARR. The eval has not been rerun on 0.8.0. The numbers on this page are for 0.7.4.

## What the skill did better

- Every figure it printed traces to a ledger row and the data, on every fixture.
- 0 arithmetic errors, against 1 clear error and 2 small slips in Claude-alone decks.
- The same deck on every run. Claude alone's decks differ from run to run, enough for the judge to pick between them.
- On "no invented numbers" it was close to even with Claude alone (15 to 18 judgments). In the first round, before the sign-off fix below, it led 22 to 10.

## What this eval does not show

- **Synthetic data only.** 6 fixtures, 5 of them variants of one company, all built by `evals/make_fixtures.py`. Nothing here says how either condition does on real company data.
- **The skill without Claude.** Condition B is the pipeline with no model: no intake interview and no rewritten titles. In real use Claude runs the skill and edits the draft. Claude with the skill installed was not measured. That is the comparison that would settle "the skill beats Claude alone".
- **One judge model**, from the same family as condition A. It may prefer prose written by its own family. No person judged the decks.
- **Partial blinding.** The skill's deck has a fixed structure and a ledger, so the judge can tell which is which. It was told to ignore that.
- **A first round with a confound I added.** In the first round the harness signed the board cut "Ablation eval, synthetic data", and the judge counted that against the skill. The rerun used "the CEO", the owner the intake names. Both rounds gave 36 to 0. The tables above are the rerun.
- **The arithmetic check depends on an extraction call** that maps printed figures to metrics. I read every flag it raised, but it may miss figures it did not extract.

## Cost

| Stage | Calls | Output tokens | Input tokens, incl. cache | Cost |
|---|---|---|---|---|
| Claude-alone decks | 18 | 298,990 | 2,969,001 | $10.42 |
| Judge | 72 | 178,108 | 2,689,540 | $23.73 |
| Extraction | 36 | 94,628 | 460,875 | $4.10 |
| **Measured run** | **126** | **571,726** | **6,119,416** | **$38.25** |

Costs are as `claude -p` reports them. With the first round, the counterfactual and a pilot, the work cost about $70 in all. Condition B uses no model and costs nothing to run.
