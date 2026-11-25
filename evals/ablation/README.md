# Ablation eval

Does the skill make a better product & engineering update than Claude alone, given the same data? This harness measures it. The results are in [docs/ablation.md](../../docs/ablation.md).

It calls the model and costs money, so it is not part of the unit tests or CI. `python3 -m unittest discover -s evals` does not find it: its folder has no `__init__.py` and no `test_*.py` files.

## Design

For each fixture company in `evals/fixtures/`, 2 conditions get the same files: the intake answers (`intake.json`), the system names (`systems.json`) and the CSV exports.

- **Condition A, Claude alone.** Headless `claude -p --safe-mode`, which loads no skill, plugin, MCP server, hook or CLAUDE.md. It gets the prompt in `prompts/task.md` and the files in `./input`, and has Read, Write, Edit, Bash, Glob and Grep. The harness checks each transcript for any sign of the skill and reports it.
- **Condition B, the skill.** The skill's pipeline, `scripts/run.py`, on the same files, with the full deck and the board cut rendered. No model is involved, so its decks are the same on every run; the harness hashes them to show it. The board cut is signed off as "the CEO", a role the intake names, because the sign-off prints on the slide and a label such as "eval" would count against the deck.

Each condition runs `--runs` times per fixture (default 3).

**Blind judge.** A separate `claude -p` call, with no tools, sees the fixture's data (intake and every CSV) and 2 decks labelled X and Y, and judges them on the rubric in `prompts/judge.md`: figures correct, no invented numbers, speed paired with quality, gaps shown, a usable board cut. It gives a verdict per criterion and overall, each with a reason. Each A and B pair is judged twice, once in each order, to cancel position bias. Two kinds of noise run alongside. Each A deck, and the first B deck, is judged against itself: a consistent judge says tie every time. And 2 different A runs of each fixture are judged against each other in both orders, which shows how far the judge's verdict moves between runs of one condition and with position.

Both decks reach the judge as plain text through `decktext.py`, which keeps what a reader sees and drops scripts, styles, the skill's hidden template guidance and the brand mark. Illustrative samples are kept and marked.

**Mechanical checks, no judge.**

- *Unmatched figures.* Every figure in a deck (outside illustrative samples) is matched against a pool of figures the data states or one named step produces, by kind (percent, money, time, count). A figure that matches nothing is unmatched: invented, or derived in a way the pool does not cover. Dates, years, IDs, versions, slide numbers and bare whole numbers of 20 or less are skipped. The pool cannot tell an invented figure from a true one that happens to equal a pool value, so the harness also measures how often a random figure of each shape matches by chance (`calibration.json`). Read the counts as a floor.
- *Arithmetic errors.* `truth.py` recomputes the headline metrics from the CSVs, written apart from the skill's `compute_metrics.py` so a shared bug cannot hide. An extraction call lists each metric the deck states and the figure as printed; code compares it with the recomputed value, within the printed rounding. Where a metric has more than one fair definition (median or mean, exact days or 13 weeks), any of them counts as correct.

## Run it

Run from the repository root, in a normal terminal where `claude -p` is signed in. A shell inside another Claude Code session may pass on credentials a nested call cannot use; set `ABLATION_DROP_API_KEY=1` to make `claude` fall back to its own login.

```bash
python3 evals/ablation/ablation.py all --out evals/ablation/results/latest
```

Or one step at a time: `generate`, `judge`, `check`, `report`. Each step skips work already on disk, so a stopped run resumes where it left off. Useful options: `--fixtures complete,sparse`, `--runs 3`, `--model` (condition A), `--judge-model`, `--jobs` (parallel calls, default 3), `--self-b`, `--pairs-only`.

`--b-drop-sections sB,sC,sD` removes those elements from the skill's decks before judging. It is for a labelled counterfactual only (here, the template's appendices), never for the headline result.

`results/` is ignored by git. The measured run that `docs/ablation.md` reports is kept in `measured/2026-11-24/`: the summary, every judgment with its reasons, the checks, the extractions, the chance-match rates, the Claude-alone decks, the first round and the counterfactual.

`report` writes `summary.json`: win rates per judgment and per pair with a 95% Wilson interval, per-criterion counts, position counts, the noise band, the check counts per condition, the chance-match rates and the token cost per stage.

## Cost

At the defaults (6 fixtures, 3 runs, Opus for every call) a full run makes 18 generation calls, 72 judge calls (36 pair, 24 self, 12 between A runs) and 36 extraction calls. The measured run used 571,726 output tokens and 6.1M input tokens, most of them cached, and cost $38.25 as `claude -p` reports it. It takes about 45 minutes at 3 to 4 parallel calls. The breakdown is in [docs/ablation.md](../../docs/ablation.md); `summary.json` reports it for every run. Each call has a `--max-budget-usd` cap: 15 for a generation, 5 for a judgment, 3 for an extraction.

## Limits

- The fixtures are synthetic companies made by `evals/make_fixtures.py`, and 5 of the 6 are variants of one company. A win here says nothing yet about real company data.
- One judge model, from the same family as condition A. It may favour prose written by its own family.
- Blinding is partial. The skill's deck has a fixed structure, a ledger and an appendix that names it, so a judge can often tell which is which. The judge is told to ignore that.
- Condition B is the pipeline without a model. In real use Claude also runs the intake interview and rewrites the drafted titles. This measures the skill's floor, not Claude with the skill.
- Condition A has no interview either: it gets the same files and cannot ask questions.
- The pair counts are small and clustered by fixture, so the interval understates the real uncertainty.
