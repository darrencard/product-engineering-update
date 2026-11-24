# Connect Stripe

Stripe fills the revenue figures on slides 1, 5 and 11: ARR, net and gross revenue retention, and expansion. `scripts/from_stripe.py` turns Stripe's own JSON into the `billing` source (account, month, ARR), which the skill already computes from. It adds no new revenue figure.

Connector: Stripe has a Claude connector (Stripe MCP, `mcp.stripe.com`), listed in the connector directory, with read access to the API. Status: tested on fixtures shaped like Stripe's documented API, including rebuilding the Kestrel test company's billing and getting the same ARR, retention and expansion; not yet run on a live Stripe account.

## 1. Get the raw JSON

**Invoices (preferred).** `GET /v1/invoices` with `created` covering the prior and reporting periods, every page (`starting_after` while `has_more`). Each invoice should carry its `lines`. These amounts are what customers are billed, net of discounts.

**Subscriptions.** `GET /v1/subscriptions?status=all`, every page, with their `items`. Use this when invoices are not available. Stripe's discounts are not applied here.

Save each page as it stands. Stripe money is in cents and its times are epoch seconds; the script handles both.

## 2. Convert

```bash
python3 scripts/from_stripe.py --invoices run/stripe/invoices-*.json --months 2026-08..2026-11 --account "Acme" --run run
```

`--months` must cover the last month of both the prior and the reporting period. `--currency` sets the one currency counted (usd by default); another currency is refused, never converted.

## 3. What it counts

| From | Counted | Left out and counted |
|---|---|---|
| Invoices | Paid and open invoices' subscription lines, annualised by the whole months each covers, toward every month end inside the line's period | Prorations, lines that are not a whole number of months, one-off items, void and uncollectible invoices |
| Subscriptions | Active and past-due items, unit amount times quantity, annualised by the price's interval | Trials, usage-based (metered) prices, prices with no unit amount |
