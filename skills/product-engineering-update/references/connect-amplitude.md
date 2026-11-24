# Connect Amplitude

Amplitude fills the outcome scorecard (slide 11): the North Star and its inputs, this period against the last. `scripts/from_amplitude.py` turns an event segmentation result into the `analytics` source (metric, period, value, definition).

Connector: Amplitude has a Claude connector in the directory, with chart and taxonomy tools. Status: tested on fixtures shaped like the Dashboard REST API's documented segmentation response; not yet run on a live project.

## 1. Get the raw JSON

`GET /api/2/events/segmentation` for the event behind the metric, daily, covering the prior and reporting periods. Save the response as it stands: `data.series` (one list of values per group), `data.seriesLabels` and `data.xValues` (dates). The chart query endpoint (`/api/3/chart/{id}/query`) varies by chart type and is not read.

Ask the user which event and which group define each metric. Do not choose them.

## 2. Convert

```bash
python3 scripts/from_amplitude.py --chart run/amplitude/wad.json --series "Dispatchers" --metric "Weekly active dispatchers" --period "2026-Q3=2026-07-01..2026-09-30" --period "2026-Q4=2026-10-01..2026-12-31" --aggregate mean --definition "Dispatchers who cleared a load in a week" --project "Acme web" --run run
```

`--aggregate` says how a period's daily values become one: `sum` for counts, `mean` for a level, `last` for a running total. The script does not pick it. Run it once per metric; other metrics' rows are kept. The metric name must match the intake's `north_star.metric` or an input's.
