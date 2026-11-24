# Connect Vercel

A solo repository has no pull request reviews, so GitHub alone gives speed with nothing to pair it with, and the delivery slide stays a gap. If the product runs on Vercel, its own records give a quality signal: releases that were rolled back, or after which the live site logged a new error.

The metric is **Deploys rolled back or followed by errors**. It is a proxy for change failure rate and says so on the slide and in the ledger. It is never relabelled change failure rate: a runtime error is not always a failed change, and a site can fail without logging one.

`scripts/from_vercel.py` turns Vercel's own JSON into flags on the `source_control` deploys. Do not retype, summarise or reshape the exports: save what Vercel returns to a file and pass the file.

## 1. Get the raw exports

**The Vercel connector in the session.** Find the team and project with `list_teams` and `list_projects`, then:

1. `list_deployments` with `target: production`, `since` the start of the prior period, `limit: 100`. Save each page as it stands. If the session saves a large result to a file, copy that file. For the next page pass `until` as the page's `pagination.next`.
2. `get_runtime_errors` for the project, one call per 7-day window (its limit) across the reporting period. Save each report as it stands, one file per window.
3. Rollbacks, if the connector can read team events. Many accounts return 403 here; then leave rollbacks out and say so.

**The Vercel command line.** `vercel api "/v6/deployments?projectId=<id>&target=production&limit=100"` and save the output.

Note the first day the error reports cover. Deploys before it are left Unknown, never counted as clean.

## 2. Convert

Run `from_github.py` first if you have GitHub data, so speed and the pull request metrics are there. Then:

```bash
python3 scripts/from_vercel.py --deployments run/vercel/deployments-01.json --errors run/vercel/errors-*.md --errors-from YYYY-MM-DD --project NAME --retrieved-at YYYY-MM-DD --run run
```

With GitHub data already collected, each GitHub deploy that matches a Vercel deploy within 10 minutes takes the flag; the rest stay Unknown and the rate is over the deploys Vercel covers. Without it, the Vercel deploys become the deploy rows.

## 3. What to expect

| The exports have | The delivery slide shows |
|---|---|
| Deploys and error reports, and a healthy range for the proxy | Speed beside the proxy, labelled as a proxy |
| Deploys and error reports, no healthy range | A gap: every delivery metric needs a range from the intake |
| Deploys only | Refused: deployments alone say nothing about quality |

Ask for the range the same way as the others: "What share of releases rolled back or followed by errors is healthy for your team?" Do not supply it yourself.
