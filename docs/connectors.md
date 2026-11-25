# Connectors

Every system the skill can read, what each reader needs, and how far each has been tested.

There are 19 readers, one per `skills/product-engineering-update/scripts/from_*.py` file, plus the CSV path through `collect.py` for anything else. All scripts run from `skills/product-engineering-update`.

## How the readers get data

No reader signs in to anything. Each one reads a file you saved (the system's own API response or export, as it stands) and writes one source into the run folder. The fetching is done by you, by a command line tool signed in as you (`gh`, `vercel`), or by a connector already in your Claude session, with your own access. The "Reads" column below says which export each reader expects and how to get it. The linked guide for each system has the exact request.

Each reader writes one of the sources that `collect.py` defines (run `python3 scripts/collect.py --list` to see them all, with their columns), and checks the columns the same way a CSV is checked. A row the reader can't place (no estimate, no date, no reason, no theme) is left out and counted, never filled in.

## Matrix

| System | Script | Reads | Source it feeds | Fields or files it uses | CSV fallback | Tested |
|---|---|---|---|---|---|---|
| GitHub | `from_github.py` ([guide](../skills/product-engineering-update/references/connect-github.md)) | `gh pr list --state merged --json number,createdAt,mergedAt,reviews,labels,author` and, optionally, `gh api repos/OWNER/NAME/deployments --paginate`. Needs `gh` signed in, or a GitHub connector returning the same fields | `source_control` | Pull requests: `number`, `createdAt`, `mergedAt`, each review's `submittedAt` and `state`; `labels` and `author` only when you pass `--agent-labels` or `--agent-authors`. Deployments: `id`, `environment`, `created_at` | `collect.py source_control --csv` | Run on a live account |
| Vercel | `from_vercel.py` ([guide](../skills/product-engineering-update/references/connect-vercel.md)) | Production deployments from the Vercel connector's `list_deployments` or `vercel api /v6/deployments`; optional runtime error reports from `get_runtime_errors` (Markdown or JSON); optional rolled-back deployment IDs | `source_control` (flags deploys as a labelled quality proxy) | Deployment id, created time, state and target; each error group's first-seen time; rollback IDs. Reads `run/intake.json` for the period, and merges into an existing `source_control.json` from `from_github.py` | `collect.py source_control --csv` with the `troubled` column | Run on a live account |
| Sentry | `from_sentry.py` ([guide](../skills/product-engineering-update/references/connect-sentry.md)) | `GET /api/0/organizations/{org}/releases/` and `GET /api/0/organizations/{org}/issues/`, every page, from the API or the Sentry connector | `source_control` (flags releases as a labelled quality proxy) | Release `version` and `lastDeploy` (`environment`, `dateFinished`); issue `level`, `firstSeen`, `firstRelease` | `collect.py source_control --csv` with the `troubled` column | Fixtures only |
| Linear | `from_linear.py` ([guide](../skills/product-engineering-update/references/connect-linear.md)) | The Linear connector's `list_issues` and `list_projects` results, or the GraphQL API response; project updates, initiatives and customer requests | `tracker`, `customer_requests`; also writes `run/linear/commitments.csv`, `targets.csv` and `initiatives.csv` for you to confirm and import | Issues: `id`, `title`, `estimate`, `completedAt`, status type, `labels`, `project`, `assignee`. Projects: name, description (its "Landing brief" block only), url, status, `targetDate`, `completedAt`, lead, initiatives | `collect.py tracker --csv`; `--projects` also reads a projects CSV by column name | Fixtures only |
| Jira | `from_jira.py` ([guide](../skills/product-engineering-update/references/connect-jira.md)) | REST search pages (`/rest/api/3/search` or the Jira connector), or Jira's own CSV export | `tracker`; optionally `run/jira/commitments.csv` from fix versions or epics | Key, summary, issue type, status, resolution date, labels, components, assignee, project, due date, fix versions, and the estimate field you name | Reads Jira's own CSV export (`--csv`), or `collect.py tracker --csv` | Fixtures only |
| GitHub Projects | `from_github_projects.py` ([guide](../skills/product-engineering-update/references/connect-github-projects.md)) | `gh project item-list --format json` and, for completion dates, `gh issue list --json url,closedAt` (or `gh pr list`). Needs `gh` signed in | `tracker` | Item title, status, labels, content url, assignees, and the custom fields you name for estimate, work type, product line, objective and completion date | `collect.py tracker --csv` | Fixtures only |
| PostHog | `from_posthog.py` ([guide](../skills/product-engineering-update/references/connect-posthog.md)) | A HogQL query result (`columns`, `results`) or a trends insight result, from the PostHog connector or API | `analytics` | Query: columns `metric`, `period`, `value`, optional `definition`. Insight: each series' `label`, `days`, `data` | `collect.py analytics --csv` | Fixtures only |
| Amplitude | `from_amplitude.py` ([guide](../skills/product-engineering-update/references/connect-amplitude.md)) | `GET /api/2/events/segmentation` result | `analytics` | `data.series`, `data.seriesLabels`, `data.xValues` | `collect.py analytics --csv` | Fixtures only |
| Mixpanel | `from_mixpanel.py` ([guide](../skills/product-engineering-update/references/connect-mixpanel.md)) | `GET /api/query/insights` or `GET /api/query/segmentation` result | `analytics` | Insights `series`, or segmentation `data.values`: event, date, count | `collect.py analytics --csv` | Fixtures only |
| Stripe | `from_stripe.py` ([guide](../skills/product-engineering-update/references/connect-stripe.md)) | `GET /v1/invoices` (preferred) or `GET /v1/subscriptions?status=all`, every page, from the Stripe connector or API | `billing` | Invoices: status, customer, currency, subscription lines and their periods and amounts. Subscriptions: status, customer, start and end, items' unit amount, quantity and recurring interval | `collect.py billing --csv` | Fixtures only |
| GitHub Copilot, Cursor, Anthropic, OpenAI | `from_ai_spend.py` ([guide](../skills/product-engineering-update/references/connect-ai-spend.md)) | Each vendor's admin export: Copilot billing and usage reports, Cursor Admin API members, daily usage and spend, Anthropic Admin API cost report, OpenAI `/v1/organization/costs` | `ai_tools` (Copilot, Cursor); model API spend goes to `run/ai_spend/finance.csv` with the plan left empty | Copilot `seat_breakdown.total`, `day`, `weekly_active_users`, plus `--copilot-seat-price` from your invoice; Cursor members, daily activity, `overallSpendCents`; Anthropic and OpenAI cost amounts | `collect.py ai_tools --csv` and `collect.py finance --csv` | Fixtures only |
| HubSpot | `from_hubspot.py` ([guide](../skills/product-engineering-update/references/connect-hubspot.md)) | `POST /crm/v3/objects/deals/search` pages, or the HubSpot connector | `crm` | `id`, `hs_is_closed`, `hs_is_closed_won`, `closedate`, `closed_won_reason`, `closed_lost_reason` | `collect.py crm --csv` | Fixtures only |
| Salesforce | `from_salesforce.py` ([guide](../skills/product-engineering-update/references/connect-salesforce.md)) | A SOQL query result on Opportunity (REST API or the Salesforce connector) | `crm` | `Id`, `IsClosed`, `IsWon`, `CloseDate` and the reason field you name | `collect.py crm --csv` | Fixtures only |
| Zendesk | `from_zendesk.py` ([guide](../skills/product-engineering-update/references/connect-zendesk.md)) | `GET /api/v2/tickets`, `GET /api/v2/search` or `GET /api/v2/search/export` pages | `support` | `id`, `created_at`, `tags`, `organization_id`, `result_type`; the custom field you name with `--theme-field` | `collect.py support --csv` | Fixtures only |
| Intercom | `from_intercom.py` ([guide](../skills/product-engineering-update/references/connect-intercom.md)) | `POST /conversations/search` pages, or the Intercom connector | `support` | `id`, `created_at`, tag names; the custom attribute you name for the account | `collect.py support --csv` | Fixtures only |
| PagerDuty | `from_pagerduty.py` ([guide](../skills/product-engineering-update/references/connect-pagerduty.md)) | `GET /incidents` pages, or the PagerDuty connector | `incidents` | `incident_number` or `id`, `created_at`, `resolved_at`, `urgency` or `priority.summary`, `service.summary` | `collect.py incidents --csv` | Fixtures only |
| incident.io | `from_incidentio.py` ([guide](../skills/product-engineering-update/references/connect-incidentio.md)) | `GET /v2/incidents` pages, or the incident.io connector | `incidents` | `id`, `created_at`, the two `incident_timestamp_values` you name for start and restore, severity name | `collect.py incidents --csv` | Fixtures only |
| Notion | `from_notion.py` ([guide](../skills/product-engineering-update/references/connect-notion.md)) | Page objects or search results from the Notion API or connector, or a folder from Notion's "Export as Markdown & CSV" | `docs` | Title property, `last_edited_time`, `url`; for the Markdown export, each file's first `# ` heading or file name | `collect.py docs --csv` | Fixtures only |
| Google Drive | `from_gdrive.py` ([guide](../skills/product-engineering-update/references/connect-gdrive.md)) | Drive API v3 `files.list` pages, with `fields=nextPageToken,files(id,name,mimeType,modifiedTime,webViewLink)`, or the Google Drive connector | `docs` | `name`, `mimeType`, `modifiedTime`, `webViewLink`, `trashed` | `collect.py docs --csv` | Fixtures only |
| Anything else | `collect.py` | A CSV or JSON file with the source's columns | Any source in `collect.py --list` | The columns listed for that source | Not applicable | Tested on the bundled fixture companies in `evals/fixtures/` |

## What the tested levels mean

- **Run on a live account.** GitHub and Vercel have been run on the maintainer's own public repository and Vercel project. No other reader has.
- **Fixtures only.** The reader has tests in `evals/` (`test_pipeline.py`, `test_sources.py`, `test_landed.py`, `test_injection.py`, `test_since_last.py`) that feed it fixtures built in the vendor's documented response shape. It has not run on a live account.

Notes on specific readers:

- **Linear.** The readers for issues, projects, project updates, initiatives and customer requests are untested on a real workspace.
- **Google Drive.** The first live run was blocked by connector permissions, so it remains fixtures only.
- **Salesforce.** Salesforce's developer documentation could not be fetched for this release, so the fixture follows the standard query result shape (`records`, `done`, `nextRecordsUrl`) and is not checked against the published docs.

Every one of the 19 readers has at least one test in `evals/`. The full suite runs with `python3 -m unittest discover -s evals -v` from the repository root.

## Add your own data with a CSV

Any system without a reader works through a CSV. Export the rows, name the columns to match the source, and collect it. From `skills/product-engineering-update`:

```bash
python3 scripts/collect.py --list
```

```bash
python3 scripts/collect.py tracker --csv issues.csv --system Linear --run run
```

Replace `tracker` with the source and `--system` with the name of the system the rows came from (it goes in the ledger). `collect.py` also takes:

- `--json` instead of `--csv`, for a JSON file of rows.
- `--query`, the query, report or URL that produced the data, for the ledger.
- `--retrieved-at YYYY-MM-DD`, which otherwise defaults to the file's modified date.

It checks the columns, coerces numbers and dates, and records where the data came from. A file with missing columns is refused with the list of what is missing, and nothing is written. Rows are never invented or filled in. A file over 50 MB or 500,000 rows is refused.

In the GitHub Action, put the CSV in `.update/` named after its source (for example `tracker.csv` or `incidents.csv`) and the Action collects it. A file with another name is ignored. See [`references/github-action.md`](../skills/product-engineering-update/references/github-action.md).

The columns for each source, and the slides each one feeds, are in [`references/sources.md`](../skills/product-engineering-update/references/sources.md). For how the intake and command line fit together, see [intake-and-cli.md](intake-and-cli.md). If a reader refuses a file, see [troubleshooting.md](troubleshooting.md).
