# Connect incident.io

incident.io gives the delivery slide its time to restore, the quality pair that pairs with speed. `scripts/from_incidentio.py` turns incidents into the `incidents` source (id, started_at, restored_at, severity).

Connector: incident.io has a Claude connector in the directory (`mcp.incident.io`). Status: tested on fixtures shaped like the documented `GET /v2/incidents` response; not yet run on a live account.

## Get the raw JSON

`GET /v2/incidents`, every page (pass `pagination_meta.after` as `after`), saved as it stands. Each incident's times are in `incident_timestamp_values`, and their names are set per account. Ask the user which marks the start (for example "Impact started") and which marks service restored (for example "Resolved"). `created_at`, when the incident was declared, is also allowed as the start.

## Convert

```bash
python3 scripts/from_incidentio.py --incidents run/incidentio/incidents-*.json --started "Impact started" --restored "Resolved" --organization "Acme" --run run
```

An incident without both times is left out and counted. Severity is the incident's severity name.

## What it measures, and what it does not

Time to restore is measured over every incident in the period. DORA's failed deployment recovery time and change failure rate count only failures a deployment caused, and these exports do not say which deployment caused an incident. So the slide shows time to restore, under that name, and change failure rate stays a gap unless the team records failed deploys (`failed` in source control) or uses the labelled Vercel or Sentry proxy.
