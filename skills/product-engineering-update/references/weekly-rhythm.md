# Weekly rhythm

Run the update every week as a draft, so the quarter's deck is a week's edit, not a month's scramble. The schedule lives outside the scripts. The scripts stay the same deterministic steps: the same files in give the same deck out.

## What the recurring job does

Each week, the job:

1. Pulls fresh exports with the connectors the session has (Linear, GitHub, PostHog and so on) and saves them as they stand into a dated run folder, for example `runs/2026-11-23/`.
2. Copies the last confirmed `intake.json` into it. The job never answers an intake question, never confirms a proposal and never accepts a suggested range: those need a person.
3. Runs the converters, then `compute_metrics.py`, `draft.py`, `validate.py` and `review.py --previous <last week's deck.json>`.
4. Renders the Leadership and Staff cuts only, and writes `summary.py` output for them.
5. Tells the owner what changed, which slides gained or lost data, and any validator errors. It stops there.

## What the job never does

- **It never renders or summarises the board cut as final.** The board cut needs `--signed-off-by` with the name of a person who said yes after reading the change list, in that session. A schedule has no one to ask, so it skips the board cut and says it is waiting on a named person.
- **It never posts.** A summary is posted to Linear only after a person reads it and says yes. Never auto-post the board cut, under any schedule.
- **It never fills a gap.** A source that failed to export this week stays a gap this week. Do not carry last week's figure forward.
- **It never edits the intake or the data to clear a validator error.** It reports the error.

## Where to schedule it

Any scheduler that can start a Claude session with this skill and the connectors works, for example:

- A scheduled Claude task (in Claude Code, `/schedule`; in the desktop app, a scheduled task) with a prompt such as: "Run the weekly product and engineering update draft for Acme into runs/<today>/, following references/weekly-rhythm.md. Render the Leadership and Staff cuts. Do not render or post the board cut. Send me the change list."
- A recurring agent run started from Linear, if your workspace has one, with the same prompt.

Whichever you use, check that it runs with the same skill version each week, and that its run folder is kept, so `review.py --previous` has last week's deck to compare against.

## Cadence

Weekly drafts, a monthly Leadership read, and a quarterly board cut signed off by a named person. See [audience-cuts.md](audience-cuts.md) for what each cut holds.
