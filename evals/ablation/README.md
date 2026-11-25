# Ablation eval

Does the skill make a better product & engineering update than Claude alone, given the same data? This harness measures it. The results are in [docs/ablation.md](../../docs/ablation.md).

It calls the model and costs money, so it is not part of the unit tests or CI. `python3 -m unittest discover -s evals` does not find it: its folder has no `__init__.py` and no `test_*.py` files.

## Design

For each fixture company in `evals/fixtures/`, 2 conditions get the same files: the intake answers (`intake.json`), the system names (`systems.json`) and the CSV exports.

- **Condition A, Claude alone.** Headless `claude -p --setting-sources project` in an empty folder outside the repository, so no user setting, output style, plugin, hook, MCP server or CLAUDE.md reaches it. It gets the prompt in `prompts/task.md` and the files in `./input`, and has Read, Write, Edit, Bash, Glob, Grep and Skill (Claude Code's built-in skills only). The harness checks each transcript for any sign of the skill and reports it. The first measured run used `--safe-mode` here, which keeps user settings, so the operator's output style reached A; `--safe-mode` also blocks a skill loaded with `--plugin-dir`, so condition C cannot use it.
- **Condition C, Claude with the skill.** As A, plus the plugin (`.claude-plugin/` and `skills/`) copied to a temporary folder and loaded with `--plugin-dir`, as a user would install it. Claude may load the skill, run its scripts and edit the draft. The harness records each Skill call and each run of the skill's scripts.
- **Condition B, the skill.** The skill's pipeline, `scripts/run.py`, on the same files, with the full deck and the board cut rendered. No model is involved, so its decks are the same on every run; the harness hashes them to show it. The board cut is signed off as "the CEO", a role the intake names, because the sign-off prints on the slide and a label such as "eval" would count against the deck.

Each condition runs `--runs` times per fixture (default 3). `--conditions ABC` picks which to generate.

**Blind judge.** A separate `claude -p` call, with no tools, sees the fixture's data (intake and every CSV) and 2 decks labelled X and Y, and judges them on the rubric in `prompts/judge.md`: figures correct, no invented numbers, speed paired with quality, gaps shown, a usable board cut. It gives a verdict per criterion and overall, each with a reason. `--matchups CA,CB:2,BA:2` sets which conditions are judged against which, the tested one first, and how many runs per fixture (default all). Each pair is judged twice, once in each order, to cancel position bias. Judge and extraction calls run with `--safe-mode` and no skills, as in the first run. Two kinds of noise run alongside, for each condition in `--noise` (default AC): `--self-n` runs per fixture judged against themselves (a consistent judge says tie every time), and runs 1 and 2 of each fixture judged against each other in both orders, which shows how far the verdict moves between runs of one condition and with position.

Both decks reach the judge as plain text through `decktext.py`, which keeps what a reader sees and drops scripts, styles, the skill's hidden template guidance and the brand mark. Illustrative samples are kept and marked.

**Mechanical checks, no judge.**

- *Unmatched figures.* Every figure in a deck (outside illustrative samples) is matched against a pool of figures the data states or one named step produces, by kind (percent, money, time, count). A figure that matches nothing is unmatched: invented, or derived in a way the pool does not cover. Dates, years, IDs, versions, slide numbers and bare whole numbers of 20 or less are skipped. The pool cannot tell an invented figure from a true one that happens to equal a pool value, so the harness also measures how often a random figure of each shape matches by chance (`calibration.json`). Read the counts as a floor.
- *Arithmetic errors.* `truth.py` recomputes the headline metrics from the CSVs, written apart from the skill's `compute_metrics.py` so a shared bug cannot hide. An extraction call lists each metric the deck states and the figure as printed; code compares it with the recomputed value, within the printed rounding. Where a metric has more than one fair definition (median or mean, exact days or 13 weeks), any of them counts as correct.

## Run it

Run from the repository root, in a normal terminal where `claude -p` is signed in. A shell inside another Claude Code session may pass on credentials a nested call cannot use; set `ABLATION_DROP_API_KEY=1` to make `claude` fall back to its own login.

```bash
python3 evals/ablation/ablation.py all --out evals/ablation/results/latest
```

Or one step at a time: `generate`, `judge`, `check`, `report`. Each step skips work already on disk, so a stopped run resumes where it left off. Useful options: `--fixtures complete,sparse`, `--runs 3`, `--conditions`, `--matchups`, `--noise`, `--self-n`, `--model` (conditions A and C), `--judge-model`, `--jobs` (parallel calls, default 3), `--pairs-only`.

`--b-drop-sections sB,sC,sD` removes those elements from the skill's decks before judging. It is for a labelled counterfactual only (here, the template's appendices), never for the headline result.

`results/` is ignored by git. The measured runs that `docs/ablation.md` reports are kept in `measured/`: `2026-11-24/` (v0.7.4, A and B, with a first round and a counterfactual) and `2026-11-25/` (v0.8.0, A, B and C). Each holds the summary, every judgment with its reasons, the checks, the extractions, the chance-match rates and the model-made decks. Transcripts are not kept.

`report` writes `summary.json`: win rates per judgment and per pair with a 95% Wilson interval, per-criterion counts, position counts, the noise band, the check counts per condition, the chance-match rates and the token cost per stage.

## Mini eval per release

`mini.py` runs a small fixed version on every release: Claude with the skill against Claude alone on `complete` and `conflicting`, 1 run each, pairs only, 4 judgments. About $5 and 15 minutes. It appends one row to `trend.csv` (committed) and exits 1 with a REGRESSION line if the skill made an arithmetic error or won a smaller share of judgments than the last row on the same fixtures. The fixture set never changes, so the trend compares like with like.

```bash
python3 evals/ablation/mini.py --version 0.9.0
```

`--from-summary <summary.json> --fixtures all` adds a row from a full run already on disk and calls nothing; the first two rows came from the v0.8.0 and v0.8.3 full runs. The arithmetic counts are the raw mechanical checks, before the hand review that `docs/ablation.md` reports.

## Cost

The v0.8.0 run (6 fixtures, 3 runs, `--matchups CA,CB:2,BA:2 --noise AC --self-n 1`, Opus for every call) made 36 generation calls, 108 judge calls and 54 extraction calls, and cost $72.17 as `claude -p` reports it: $18.82 for A, $9.46 for C, $38.35 for the judge and $5.55 for extraction. It took about 1 hour at 4 parallel calls. The v0.7.4 run, A and B only, cost $38.25. The breakdown is in [docs/ablation.md](../../docs/ablation.md); `summary.json` reports it for every run. Each call has a `--max-budget-usd` cap: 15 for a generation, 5 for a judgment, 3 for an extraction.

## Limits

- The fixtures are synthetic companies made by `evals/make_fixtures.py`, and 5 of the 6 are variants of one company. A win here says nothing yet about real company data.
- One judge model, from the same family as condition A. It may favour prose written by its own family.
- Blinding is partial. The skill's deck has a fixed structure, a ledger and an appendix that names it, so a judge can often tell which is which. The judge is told to ignore that.
- Condition B is the pipeline without a model; condition C is Claude with the skill. Neither has a person to answer questions, so C cannot get the board cut sign-off the skill requires, while the harness signs off B's.
- Condition A has no interview either: it gets the same files and cannot ask questions.
- The pair counts are small and clustered by fixture, so the interval understates the real uncertainty.
