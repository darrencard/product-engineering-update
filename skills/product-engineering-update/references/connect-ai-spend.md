# Connect AI spend

Slide 13 shows how the team uses AI tools: seats, people active each week, and what it costs. Slide 5's spend table can carry model API spend. `scripts/from_ai_spend.py` reads each vendor's own admin export. It never writes a productivity figure: no lines of code, acceptance rate or request count, because the deck reports no productivity claim without a baseline and a window, and these exports hold neither.

Connectors: none of these four has a Claude connector in the directory (checked 2026-11-24). Use the vendor's admin API or console export. Status: tested on fixtures shaped like each vendor's documented response; not yet run on a live account.

## What maps where

| Vendor | Export | Becomes |
|---|---|---|
| GitHub Copilot | `GET /orgs/{org}/copilot/billing` (`seat_breakdown.total`) and the organization usage report records (`day`, `weekly_active_users`) | An `ai_tools` row. The API states no price, so pass `--copilot-seat-price` (per seat per month, from your invoice); without it no row is written |
| Cursor | Admin API `/teams/members`, `/teams/daily-usage-data` (every page) and `/teams/spend` | An `ai_tools` row: members not removed, people active in the period's last 7 days, and `overallSpendCents` for the billing cycle the spend export covers |
| Anthropic | Admin API cost report (`amount` is a decimal string in cents) | A finance line, "Model API: Anthropic", with the plan left empty |
| OpenAI | `/v1/organization/costs` (`amount.value` in dollars) | A finance line, "Model API: OpenAI", with the plan left empty |

The old Copilot metrics endpoint (`/orgs/{org}/copilot/metrics`) was closed down on 2026-04-02; use the organization usage reports.

## Convert

Run once for each period, the reporting period and the one before:

```bash
python3 scripts/from_ai_spend.py --period "2026-Q4=2026-10-01..2026-12-31" --copilot-billing run/ai/copilot-billing.json --copilot-report run/ai/copilot-report.ndjson --copilot-seat-price 19 --cursor-members run/ai/cursor-members.json --cursor-daily run/ai/cursor-daily-*.json --cursor-spend run/ai/cursor-spend.json --anthropic-cost run/ai/anthropic-*.json --openai-costs run/ai/openai-*.json --run run
```

Model API spend has no seats, so it is not an `ai_tools` row. It goes to `run/ai_spend/finance.csv` with the actual filled. Add each line's plan with the person, then collect the file as `finance`.
