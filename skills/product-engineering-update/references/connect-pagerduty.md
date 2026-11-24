# Connect PagerDuty

PagerDuty gives the delivery slide its time to restore. `scripts/from_pagerduty.py` turns incidents into the `incidents` source (id, started_at, restored_at, severity).

Connector: PagerDuty has an official Claude connector in the directory (`mcp.pagerduty.com`). Status: tested on fixtures shaped like the documented `GET /incidents` response, including rebuilding the Kestrel test company's incidents; not yet run on a live account.

## Get the raw JSON

`GET /incidents?since=...&until=...` covering the prior and reporting periods, every page (`offset` and `limit` while `more` is true), saved as it stands.

## Convert

```bash
python3 scripts/from_pagerduty.py --incidents run/pagerduty/incidents-*.json --severity-from priority --service "Checkout API" --account "Acme" --run run
```

An incident starts at `created_at` and is restored at `resolved_at`; one not resolved is left out and counted. `--severity-from` takes the urgency or the priority's summary. `--service` keeps only the services the product runs on (repeat it), so unrelated alerts stay out.

## What it measures, and what it does not

As with incident.io: this is time to restore over every incident counted, not DORA's failed deployment recovery time, because PagerDuty does not say which deployment caused an incident. Change failure rate stays a gap unless the team records failed deploys or uses the labelled Vercel or Sentry proxy.
