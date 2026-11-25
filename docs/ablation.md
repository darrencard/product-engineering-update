# Ablation: the skill against Claude alone

Three measured runs, on synthetic fixtures only. The harness is in [evals/ablation/](../evals/ablation/README.md).

- **25 November 2026, v0.8.3**, Claude with the skill against Claude alone, both told the CEO signs off the board cut. Raw data in `evals/ablation/measured/2026-11-25-v083/`.
- **25 November 2026, v0.8.0**, 3 conditions: Claude alone, the skill's pipeline with no model, and Claude with the skill installed. Raw data in `evals/ablation/measured/2026-11-25/`.
- **24 November 2026, v0.7.4**, 2 conditions: Claude alone and the pipeline. Raw data in `evals/ablation/measured/2026-11-24/`.

## v0.8.3: Claude with the skill against Claude alone, with a named signer

### The answer

No, and the gap did not close. On the same 6 synthetic companies, the judge preferred Claude alone in 34 of 34 judgments and 17 of 17 pairs (95% Wilson interval for the skill 0% to 18% per pair). One Claude-with-skill run wrote no deck, so 17 pairs, not 18. Both conditions were told, in the task, that the CEO signs off the board cut; the skill still lost the board cut 0 to 34.

| Criterion | Claude with the skill | Claude alone | Tie |
|---|---|---|---|
| Overall | 0 | 34 | 0 |
| Figures correct | 0 | 30 | 4 |
| No invented numbers | 8 | 16 | 10 |
| Speed paired with quality | 0 | 18 | 16 |
| Gaps shown | 0 | 34 | 0 |
| Board cut usable | 0 | 34 | 0 |

Mechanical checks (raw, before hand review): the skill made 0 arithmetic errors in 715 checked figures; Claude alone 4 in 986. Run cost: $41.41 ($16.65 Claude alone, $9.05 with the skill, $11.53 judging, $4.19 extraction).

### Why it lost, from the judge's reasons

1. **One wrong figure, repeated.** The skill annualised a quarter's $10.3M revenue by days ($40.9M); the judge counted 4 times a quarter ($41.2M) as right. It appears on slides 1 and 5, so it cost "figures correct" in most pairs.
2. **The board cut is not sendable.** It carries the internal "Check before the board sees this" card, the ledger appendix, and a duplicated slide 1 and 11; Claude alone wrote one page that leads with the answer, the ARR bridge and the overdue decision.
3. **Gaps are thinner.** Claude alone listed about 8 data caveats per deck, each with an owner (a partial billing export, a proxy for lead time, undated exports, an unexplained overrun, unmeasured stop rules). The skill lists missing slides only, gives its conflict lines no owner, and slide 10 says incident data is missing while slide 9 uses it.
4. **Sparse data.** On the sparse company the skill's cover said 0 of 19 slides show data while its ledger held tracker figures.

The 0.8.3 changes (checks first on slide 1, every gap with an owner) were present but not enough: the judge weighed the wrong annualised figure, the unsendable board cut and the thinner caveats more.

## v0.8.0: Claude with the skill against Claude alone

### The answer

No. On 6 synthetic companies, a blind judge preferred Claude alone to Claude with the skill in 36 of 36 judgments and 18 of 18 pairs. The skill's win rate is 0%, with a 95% Wilson interval of 0% to 18% per pair. Claude with the skill was more exact: 0 arithmetic errors in 792 checked figures, against 2 real errors for Claude alone. It lost on the board cut and on showing gaps.

The biggest single cause is the board cut. The skill renders one only after a named person says yes in the session. This run was unattended, so in all 18 runs Claude with the skill held it back: 11 wrote a holding page, 2 wrote a review note and 5 wrote nothing. Claude alone wrote a board cut in all 18. That is the skill working as designed, but it loses the board cut criterion every time.

### What was compared

| | A: Claude alone | B: the pipeline | C: Claude with the skill |
|---|---|---|---|
| What ran | Headless `claude -p`, Opus 5.5, project settings only: no user setting, output style, plugin, hook, MCP server or CLAUDE.md | `scripts/run.py`, full deck and board cut, signed off as "the CEO". No model | As A, plus the v0.8.0 plugin, loaded with `--plugin-dir` from a copy outside the repository |
| Input | The fixture files and the same prompt as the first run | The same files | The same files and prompt |
| Runs | 3 per fixture | 3 per fixture, the same deck each time | 3 per fixture |

All 18 C transcripts show the skill loaded and its scripts run. No A transcript touched it. A was regenerated for this run; the limits below say why.

### The blind judge

Same judge and rubric as the first run. Every pair was judged in both orders. C vs B and B vs A used 2 runs per fixture, to save cost.

| Criterion | C vs A | C vs B | B vs A |
|---|---|---|---|
| **Overall** | **C 0, A 36** | **C 10, B 14** | **B 0, A 24** |
| Every figure correct | C 2, A 22, tie 12 | tie 24 | B 1, A 19, tie 4 |
| No invented numbers | C 14, A 9, tie 13 | C 5, tie 19 | B 4, A 14, tie 6 |
| Speed paired with quality | C 12, A 7, tie 17 | C 13, tie 11 | B 4, A 11, tie 9 |
| Gaps shown, not filled | C 1, A 35 | C 9, B 1, tie 14 | A 24 |
| Board cut usable | A 36 | C 5, B 19 | A 24 |
| Pairs won, both orders agreeing | A 18 of 18 | B 7, C 5 of 12 | A 12 of 12 |

Both orders of every pair named the same winner in all 3 matchups. B beat C mainly because the harness signed off B's board cut and C held its own back.

Topics in the 36 C vs A reasons, by keyword count (a mention can favour either deck): the board cut or sign-off 34, gaps 32, revenue against ARR 32, lead time 29, a decision due "today" 23, conflicts between sources 17. The appendix pitch and template scaffolding that the judge named in all 36 of the 0.7.4 reasons are gone: 2 mentions of an appendix, none of the pitch. Read in full, the reasons say Claude alone named more gaps with owners, reconciled revenue with ARR rather than leading with ARR, and wrote a board cut that could be sent.

### The noise band

| Test | Result |
|---|---|
| A deck against itself (6 A, 6 C) | Tie every time, on every criterion |
| 2 different A runs of one fixture (12 judgments) | 12 of 12 picked a winner; 2 of 6 pairs flipped with order |
| 2 different C runs of one fixture (12 judgments) | 11 of 12 picked a winner; 1 of 6 pairs flipped with order |

36 to 0 is well outside that noise.

### Mechanical checks, no judge

| | A | B | C |
|---|---|---|---|
| Figures in the decks | 3,369 | 3,546 | 2,506 |
| Figures no one-step derivation produces | 194 | 48 | 29 |
| Printed metrics checked against recomputed values | 1,008 | 717 | 792 |
| Arithmetic flags | 14 | 0 | 0 |
| ... real errors, on a reading of each | 2 | 0 | 0 |

All 77 unmatched B and C figures are revenue annualised ($40.9M or $41M), which 0.8.0 prints when it checks revenue against ARR. Of A's 14 flags, 10 are costs per AI tool where the check knows only the total, 2 are lead time measured to first deploy (a fair definition the check lacks), and 2 are real: 8 customer requests where the period holds 7, the same slip as the first run.

### Cost

| Stage | Calls | Cost |
|---|---|---|
| A, Claude alone | 18 | $18.82 |
| C, Claude with the skill | 18 | $9.46 |
| Judge | 108 | $38.35 |
| Extraction | 54 | $5.55 |
| **Total** | **198** | **$72.17** |

Claude with the skill cost half as much per deck as Claude alone ($0.53 against $1.05), because the scripts do the arithmetic and the drafting.

### What this run does not show

- **Synthetic data only.** The same 6 fixtures, 5 of them variants of one company.
- **No person in the loop.** In real use the person running the skill gives the board cut sign-off. Here no one could, so C never produced a board cut. A run with the sign-off given was not measured.
- **One judge model**, the same family as A and C, with partial blinding.
- **A changed between runs.** `--safe-mode` keeps user settings, so the first run's A, and both runs' judge and extraction calls, carried the operator's "Concise" output style. This run's A and C read project settings only and had none; A's decks grew longer and cost more. Compare A only within a run.

## v0.7.4: the pipeline against Claude alone

### The answer

On 6 synthetic companies, a blind judge preferred Claude alone to the skill in every comparison: 36 of 36 judgments and 18 of 18 pairs. The skill's pipeline was more exact: 0 figures it could not account for and 0 arithmetic errors. But Claude alone was close to as exact (1 clear error in 1,049 checked figures), and the judge found its decks more useful: it reconciled the data, flagged more gaps and wrote a board cut that could be sent.

So this eval does not support "the skill beats Claude alone". It supports a narrower claim: the skill's figures are always traceable, and Claude alone's are nearly always right.

### What was compared

| | Condition A: Claude alone | Condition B: the skill |
|---|---|---|
| What ran | Headless `claude -p --safe-mode`, Opus 5.5. No skill, plugin, MCP server or CLAUDE.md, but the operator's "Concise" output style reached it through `--safe-mode`. A check of every transcript found no use of the skill. | The skill's pipeline, `scripts/run.py`, with the full deck and the board cut. No model. |
| Input | The fixture's `intake.json`, `systems.json` and CSVs, and one prompt: build an update for leadership, plus a board cut | The same files |
| Runs | 3 per fixture, 18 in all | 3 per fixture, 18 in all. The 3 decks per fixture are the same, apart from the render time |

The 6 fixtures are `complete`, `conflict_resolved`, `conflicting`, `no_ai`, `single_product` and `sparse` (tracker data only). 5 of the 6 are variants of one made-up company.

The judge was Opus 5.5 with no tools. It saw the fixture's data and 2 decks as plain text, labelled X and Y. It judged each of 5 criteria and gave an overall verdict, each with a reason. Each pair was judged in both orders.

### Results

#### The blind judge

| Criterion | Claude alone | The skill | Tie |
|---|---|---|---|
| **Overall** | **36** | **0** | **0** |
| Every figure correct | 20 | 4 | 12 |
| No invented numbers | 18 | 15 | 3 |
| Speed paired with quality | 14 | 7 | 15 |
| Gaps shown, not filled | 36 | 0 | 0 |
| Board cut usable | 36 | 0 | 0 |

36 judgments over 18 pairs. Both orders of every pair named the same winner. The skill's win rate is 0 of 18 pairs, with a 95% Wilson interval of 0% to 18%. Every fixture went 6 to 0. The pairs are clustered (5 of 6 fixtures are one company), so the real uncertainty is wider than that interval.

#### The noise band

| Test | Result |
|---|---|
| A deck against itself (24 judgments: 18 Claude alone, 6 the skill) | Tie every time, on every criterion |
| 2 different Claude-alone runs of the same fixture (12 judgments, 6 pairs) | 12 of 12 picked a winner. In 2 of 6 pairs the winner flipped when the order flipped |
| Position of the winner across the 36 A and B judgments | X 18, Y 18 |

The judge tells two Claude-alone decks apart, and its verdict between them is sometimes set by position. Between Claude alone and the skill it never flipped, so the 36 to 0 result is well outside that noise.

#### Mechanical checks, no judge

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

#### Why the skill lost

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

### Since this run

Version 0.8.0 fixed 4 of these points. The v0.8.0 run above measures it.

### What the skill did better

- Every figure it printed traces to a ledger row and the data, on every fixture.
- 0 arithmetic errors, against 1 clear error and 2 small slips in Claude-alone decks.
- The same deck on every run. Claude alone's decks differ from run to run, enough for the judge to pick between them.
- On "no invented numbers" it was close to even with Claude alone (15 to 18 judgments). In the first round, before the sign-off fix below, it led 22 to 10.

### What this eval does not show

- **Synthetic data only.** 6 fixtures, 5 of them variants of one company, all built by `evals/make_fixtures.py`. Nothing here says how either condition does on real company data.
- **The skill without Claude.** Condition B is the pipeline with no model: no intake interview and no rewritten titles. In real use Claude runs the skill and edits the draft. Claude with the skill installed was not measured. That is the comparison that would settle "the skill beats Claude alone".
- **One judge model**, from the same family as condition A. It may prefer prose written by its own family. No person judged the decks.
- **Partial blinding.** The skill's deck has a fixed structure and a ledger, so the judge can tell which is which. It was told to ignore that.
- **A first round with a confound I added.** In the first round the harness signed the board cut "Ablation eval, synthetic data", and the judge counted that against the skill. The rerun used "the CEO", the owner the intake names. Both rounds gave 36 to 0. The tables above are the rerun.
- **The arithmetic check depends on an extraction call** that maps printed figures to metrics. I read every flag it raised, but it may miss figures it did not extract.

### Cost

| Stage | Calls | Output tokens | Input tokens, incl. cache | Cost |
|---|---|---|---|---|
| Claude-alone decks | 18 | 298,990 | 2,969,001 | $10.42 |
| Judge | 72 | 178,108 | 2,689,540 | $23.73 |
| Extraction | 36 | 94,628 | 460,875 | $4.10 |
| **Measured run** | **126** | **571,726** | **6,119,416** | **$38.25** |

Costs are as `claude -p` reports them. With the first round, the counterfactual and a pilot, the work cost about $70 in all. Condition B uses no model and costs nothing to run.
