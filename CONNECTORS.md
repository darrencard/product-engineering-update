# Connectors

The skill names categories of system, not products, so it works with whatever you have connected. Where no connector exists, export a CSV and the skill uses that.

| Category | In the skill | Examples | Without a connector |
|---|---|---|---|
| Issue tracker | `tracker` | Linear, Jira | CSV of issues or epics |
| Source control and CI | `source_control` | GitHub, your CI | CSV of deploys and pull requests |
| Product analytics | `analytics` | PostHog, Amplitude, Mixpanel | CSV with one row per metric and period |
| Warehouse | `warehouse` | Snowflake, BigQuery, MotherDuck | CSV of query results, with the query text |
| Billing | `billing` | Stripe | CSV of ARR by account and month |
| Finance actuals | `finance` | Your finance close, provider invoices | CSV of plan and actual by line |
| CRM | `crm` | Your CRM | CSV of closed deals with outcome and reason |
| Support desk | `support` | Your support tool | CSV of tickets with a theme |
| Incidents and status | `incidents` | Your incident tool, status page | CSV of incidents with start and restore times |
| Evals and traces | `evals` | Your eval harness | CSV of eval runs |
| AI tool admin data | `ai_tools` | Tool admin exports | CSV of seats, weekly use and cost |
| Developer survey | `survey` | Your quarterly survey | CSV of question, period and score |
| HR and hiring | `hr` | Your HR system | CSV of headcount and plan by function |

This plugin ships no connector configuration of its own. It uses the connectors already in your session. The exact columns for each source are in `skills/product-engineering-update/references/sources.md`, or run `python3 scripts/collect.py --list` from the skill folder.

## Where your data goes

Nowhere. The scripts read files in your run folder and write files back to it. They hold no network code, and a test checks that. Each reader and whether it has run on a live account is in [docs/connectors.md](docs/connectors.md). Whatever a connector fetches stays in your own session.
