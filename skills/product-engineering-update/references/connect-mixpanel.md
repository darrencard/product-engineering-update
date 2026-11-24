# Connect Mixpanel

Mixpanel fills the outcome scorecard (slide 11). `scripts/from_mixpanel.py` turns a Query API result into the `analytics` source (metric, period, value, definition).

Connector: Mixpanel has a Claude connector in the directory (`mcp.mixpanel.com`). Status: tested on fixtures shaped like the documented insights and segmentation responses; not yet run on a live project.

## 1. Get the raw JSON

- **Insights (preferred):** `GET /api/query/insights?project_id=...&bookmark_id=...` for a saved report, daily, covering the prior and reporting periods. The response's `series` maps each event to dates and counts.
- **Segmentation:** `GET /api/query/segmentation`. Mixpanel has put it in maintenance mode; it still reads.

Save the response as it stands. Ask the user which report and event define each metric.

## 2. Convert

```bash
python3 scripts/from_mixpanel.py --chart run/mixpanel/signups.json --series "Signed up" --metric "Signups" --period "2026-Q3=2026-07-01..2026-09-30" --period "2026-Q4=2026-10-01..2026-12-31" --aggregate sum --project "Acme" --run run
```

`--aggregate` is the user's choice (`sum`, `mean` or `last`); the script refuses to run without it. Run once per metric; other metrics' rows are kept.
