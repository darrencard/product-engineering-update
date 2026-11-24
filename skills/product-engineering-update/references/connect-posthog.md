# Connect PostHog

PostHog fills the outcome scorecard (slide 11): the North Star and its input metrics, this period against the last.

`scripts/from_posthog.py` turns PostHog's own JSON into the `analytics` source. Do not retype or reshape the result: save what PostHog returns to a file and pass the file.

Status: built against PostHog's documented query and insight response shapes, and tested on fixtures of those shapes only. It has not yet run on a live PostHog project.

## 1. Get the raw JSON

**A HogQL query (preferred).** Write one query that returns one row per metric and period, with columns named `metric`, `period` and `value` (and `definition` if you have one). Make `period` hold the intake's period labels, for example `'2026-Q3'`, for this period and the one before. Run it through the PostHog connector or the query API and save the response, which holds `columns` and `results`.

**A trends insight.** Save the insight's result as it stands. It holds a `result` list of series, each with `days` and `data`.

Ask the user which events or insights define each metric. Do not choose them.

## 2. Convert

```bash
python3 scripts/from_posthog.py --query run/posthog/outcomes.json --project "Acme web" --retrieved-at YYYY-MM-DD --run run
```

```bash
python3 scripts/from_posthog.py --insight run/posthog/wad.json --metric "Weekly active dispatchers" --period "2026-Q2=2026-04-01..2026-06-30" --period "2026-Q3=2026-07-01..2026-09-30" --aggregate mean --definition "Dispatchers who cleared a load in a week" --run run
```

`--aggregate` says how a period's daily values become one: `sum` for counts, `mean` for a weekly or daily level, `last` for a running total. The script does not pick it. Run it once per insight; the rows for other metrics are kept.

## 3. What to expect

The metric names must match the intake's `north_star.metric` and `inputs[].metric`. A metric in both PostHog and a warehouse with different values is a conflict, shown as a gap until the user names the source that owns it.
