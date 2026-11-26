# Sources

Each source, the columns `scripts/collect.py` needs, and the slides it feeds. A column marked optional may be left empty.

Get the rows from whatever connector the session has, or from a CSV export. `collect.py` does not call any system itself.

Systems with a converter read the system's own export and write the source for you, mapping only fields that exist. Every other system works through a CSV with the columns below.

| Source | Converters |
|---|---|
| docs | [Notion](connect-notion.md) (`from_notion.py`), [Google Drive](connect-gdrive.md) (`from_gdrive.py`) |
| tracker | [Linear](connect-linear.md) (`from_linear.py`), [Jira](connect-jira.md) (`from_jira.py`), [GitHub Projects](connect-github-projects.md) (`from_github_projects.py`) |
| finance | [Anthropic and OpenAI API costs (plan added by you)](connect-ai-spend.md) (`from_ai_spend.py`) |
| billing | [Stripe](connect-stripe.md) (`from_stripe.py`) |
| analytics | [PostHog](connect-posthog.md) (`from_posthog.py`), [Amplitude](connect-amplitude.md) (`from_amplitude.py`), [Mixpanel](connect-mixpanel.md) (`from_mixpanel.py`) |
| crm | [HubSpot](connect-hubspot.md) (`from_hubspot.py`), [Salesforce](connect-salesforce.md) (`from_salesforce.py`) |
| support | [Intercom](connect-intercom.md) (`from_intercom.py`), [Zendesk](connect-zendesk.md) (`from_zendesk.py`) |
| source_control | [GitHub](connect-github.md) (`from_github.py`), [Vercel (labelled quality proxy)](connect-vercel.md) (`from_vercel.py`), [Sentry (labelled quality proxy)](connect-sentry.md) (`from_sentry.py`) |
| incidents | [incident.io](connect-incidentio.md) (`from_incidentio.py`), [PagerDuty](connect-pagerduty.md) (`from_pagerduty.py`) |
| ai_tools | [GitHub Copilot and Cursor](connect-ai-spend.md) (`from_ai_spend.py`) |
| customer_requests | [Linear customer requests](connect-linear.md) (`from_linear.py`) |

## Contents

- [Documents](#docs)
- [Issue tracker](#tracker)
- [Finance actuals](#finance)
- [Billing](#billing)
- [Product analytics](#analytics)
- [Warehouse](#warehouse)
- [CRM](#crm)
- [Support desk](#support)
- [Research and call notes](#research)
- [Source control and CI](#source_control)
- [Incidents and status](#incidents)
- [Security tracker](#security)
- [Evals and traces](#evals)
- [AI tool admin data](#ai_tools)
- [Developer survey](#survey)
- [HR and hiring](#hr)
- [Sources with no table](#sources-with-no-table)

<a id="docs"></a>
## Documents (`docs`)

Examples: Notion, Google Drive. Feeds slides: 2, 10, 14, 15, 16, 9b. Converters: Notion, Google Drive.

| Column | Type | Required |
|---|---|---|
| `document` | str | Yes |
| `kind` | str | Yes |
| `updated_at` | date | No |
| `location` | str | No |

What the slides read from it:

- A decision log
- A one-page brief per bet with appetite, expected result, confidence and a stop rule
- A risk register with likelihood, impact, owner and date
- The architecture decision log and debt register
- The strategy document

<a id="tracker"></a>
## Issue tracker (`tracker`)

Examples: Linear, Jira, GitHub Projects. Feeds slides: 3, 4, 5, 8, 9b. Converters: Linear, Jira, GitHub Projects.

| Column | Type | Required |
|---|---|---|
| `id` | str | Yes |
| `title` | str | Yes |
| `work_type` | str | Yes |
| `status` | str | Yes |
| `estimate` | num | Yes |
| `completed_at` | date | No |
| `product_line` | str | No |
| `objective` | str | No |
| `owner` | str | No |

What the slides read from it:

- A work-type label on every issue or epic
- Capacity by product line
- Initiatives or epics tagged to an objective, each with an owner
- Last period's commitments, each with one target metric named before launch

<a id="finance"></a>
## Finance actuals (`finance`)

Examples: Finance close, Provider invoices, Anthropic and OpenAI cost reports. Feeds slides: 4, 5, 12. Converters: Anthropic and OpenAI API costs (plan added by you).

| Column | Type | Required |
|---|---|---|
| `line` | str | Yes |
| `period` | str | Yes |
| `plan` | num | Yes |
| `actual` | num | Yes |

What the slides read from it:

- AI revenue and cost of revenue
- ARR by product line
- Cash balance, net burn and runway
- Plan and actual spend, with model provider and tooling invoices

<a id="billing"></a>
## Billing (`billing`)

Examples: Stripe. Feeds slides: 11. Converters: Stripe.

| Column | Type | Required |
|---|---|---|
| `account` | str | Yes |
| `month` | str | Yes |
| `arr` | num | Yes |

What the slides read from it:

- Retention and expansion ARR

<a id="analytics"></a>
## Product analytics (`analytics`)

Examples: PostHog, Amplitude, Mixpanel. Feeds slides: 8, 11, 9b. Converters: PostHog, Amplitude, Mixpanel.

| Column | Type | Required |
|---|---|---|
| `metric` | str | Yes |
| `period` | str | Yes |
| `value` | num | Yes |
| `definition` | str | No |

What the slides read from it:

- One North Star and 3 to 5 input metrics, each with a definition, owner, target and prior period
- The result for each target metric

<a id="warehouse"></a>
## Warehouse (`warehouse`)

Examples: Snowflake, BigQuery, MotherDuck. Feeds slides: 11.

| Column | Type | Required |
|---|---|---|
| `metric` | str | Yes |
| `period` | str | Yes |
| `value` | num | Yes |
| `query` | str | Yes |

What the slides read from it:

- The query behind each metric

<a id="crm"></a>
## CRM (`crm`)

Examples: HubSpot, Salesforce. Feeds slides: 7, 11. Converters: HubSpot, Salesforce.

| Column | Type | Required |
|---|---|---|
| `deal` | str | Yes |
| `outcome` | str | Yes |
| `reason` | str | Yes |

What the slides read from it:

- Customer accounts behind the retention measures
- Win and loss reasons with counts

<a id="support"></a>
## Support desk (`support`)

Examples: Intercom, Zendesk. Feeds slides: 7. Converters: Intercom, Zendesk.

| Column | Type | Required |
|---|---|---|
| `ticket` | str | Yes |
| `theme` | str | Yes |
| `account` | str | No |

What the slides read from it:

- Support themes

<a id="research"></a>
## Research and call notes (`research`)

Examples: Research repository, Call notes. Feeds slides: 6, 7.

| Column | Type | Required |
|---|---|---|
| `id` | str | Yes |
| `date` | date | Yes |
| `finding` | str | Yes |
| `kind` | str | No |

What the slides read from it:

- Call notes
- Interview notes, prototype and experiment results

<a id="source_control"></a>
## Source control and CI (`source_control`)

Examples: GitHub, Vercel, Sentry. Feeds slides: 9, 13, 9b. Converters: GitHub, Vercel (labelled quality proxy), Sentry (labelled quality proxy).

| Column | Type | Required |
|---|---|---|
| `kind` | str | Yes |
| `id` | str | Yes |
| `opened_at` | date | No |
| `merged_at` | date | No |
| `review_hours` | num | No |
| `deployed_at` | date | No |
| `failed` | bool | No |
| `reworked` | bool | No |
| `troubled` | bool | No |
| `agent_authored` | bool | No |

What the slides read from it:

- A baseline from before the tools, and the quality metrics from slide 9
- Deploys, lead time, review time and change failures

<a id="incidents"></a>
## Incidents and status (`incidents`)

Examples: incident.io, PagerDuty. Feeds slides: 9, 10, 9b. Converters: incident.io, PagerDuty.

| Column | Type | Required |
|---|---|---|
| `id` | str | Yes |
| `started_at` | date | Yes |
| `restored_at` | date | Yes |
| `severity` | str | No |

What the slides read from it:

- Availability objectives, error budgets and incident data
- Time to restore

<a id="security"></a>
## Security tracker (`security`)

Examples: Your security tool. Feeds slides: 10, 9b.

| Column | Type | Required |
|---|---|---|
| `finding` | str | Yes |
| `severity` | str | Yes |
| `opened_at` | date | Yes |
| `status` | str | Yes |

What the slides read from it:

- Audit status and vulnerability ageing

<a id="evals"></a>
## Evals and traces (`evals`)

Examples: Eval harness, Production traces. Feeds slides: 6, 12.

| Column | Type | Required |
|---|---|---|
| `version` | str | Yes |
| `run_at` | date | Yes |
| `cases` | num | Yes |
| `passed` | num | Yes |
| `cost_per_task` | num | No |
| `tasks` | num | No |
| `tasks_unassisted` | num | No |

What the slides read from it:

- A versioned eval set, production traces with tasks run and tasks finished with no person stepping in, and cost per request
- Eval error analysis

<a id="ai_tools"></a>
## AI tool admin data (`ai_tools`)

Examples: GitHub Copilot, Cursor. Feeds slides: 13, 9b. Converters: GitHub Copilot and Cursor.

| Column | Type | Required |
|---|---|---|
| `tool` | str | Yes |
| `period` | str | Yes |
| `seats` | num | Yes |
| `weekly_active` | num | Yes |
| `cost` | num | Yes |

What the slides read from it:

- Usage and cost per engineer by tool

<a id="survey"></a>
## Developer survey (`survey`)

Examples: Quarterly survey. Feeds slides: 9, 13, 9b.

| Column | Type | Required |
|---|---|---|
| `question` | str | Yes |
| `period` | str | Yes |
| `score` | num | Yes |

What the slides read from it:

- Developer sentiment
- The developer experience index

<a id="hr"></a>
## HR and hiring (`hr`)

Examples: HR system, Hiring tracker. Feeds slides: 17.

| Column | Type | Required |
|---|---|---|
| `function` | str | Yes |
| `now` | num | Yes |
| `plan` | num | Yes |
| `open_roles` | str | No |

What the slides read from it:

- Headcount against plan by function, open senior roles and attrition

<a id="sources-with-no-table"></a>
## Sources with no table

The intake interview is recorded in `run/intake.json` by `scripts/intake.py`. It needs no export.
