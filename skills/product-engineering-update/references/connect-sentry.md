# Connect Sentry

Sentry gives the delivery slide a quality pair on any host: the share of releases followed by a new error. It is the same proxy as the Vercel signal, "Deploys rolled back or followed by errors", labelled as a proxy for change failure rate and never relabelled as one. The slide states which releases it covers.

`scripts/from_sentry.py` turns Sentry's own JSON into flags on the `source_control` deploys.

Connector: Sentry has a Claude connector (Sentry MCP, `mcp.sentry.dev`), listed in the connector directory, with `find_releases` and `find_issues`. Status: tested on fixtures shaped like Sentry's documented API; not yet run on a live Sentry organization.

## 1. Get the raw JSON

- **Releases.** `GET /api/0/organizations/{org}/releases/?project=<id>`, every page (follow the `Link` header while `results="true"`). Each release carries `lastDeploy` with its `environment` and `dateFinished`.
- **Issues.** `GET /api/0/organizations/{org}/issues/?project=<id>` over the prior and reporting periods, every page. The project-level issues endpoint still works but is deprecated. An issue's details add `firstRelease`, which ties it to a release directly.

Save each page as it stands. Note the first day the issue export covers.

## 2. Convert

Run `from_github.py` first if you have GitHub data. Then:

```bash
python3 scripts/from_sentry.py --releases run/sentry/releases-*.json --issues run/sentry/issues-*.json --errors-from YYYY-MM-DD --organization acme --run run
```

`--environment` names the deploy environment that counts (production by default). `--levels` sets which issue levels count (error and fatal by default).

## 3. What it can and cannot say

- A release is flagged when an issue at a counted level was first seen while it was live, or when Sentry names it as the issue's `firstRelease`. Releases before `--errors-from` stay Unknown.
- Sentry records only the last deploy per release in the release list, so a release deployed twice counts once.
- **Incidents:** Sentry's public API reference documents no incident list, so nothing goes to the `incidents` source. Time to restore needs incident.io or PagerDuty.
