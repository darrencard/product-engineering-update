# Connect Zendesk

Zendesk fills the support themes on slide 7. `scripts/from_zendesk.py` turns tickets into the `support` source (ticket, theme, account).

Connector: no Zendesk connector is in the Claude directory (checked 2026-11-24). Use the API or an export. Status: tested on fixtures shaped like the documented tickets and search responses, including rebuilding the Kestrel test company's tickets; not yet run on a live account.

## Get the raw JSON

Any of these, every page, saved as it stands:
- `GET /api/v2/tickets` with cursor pagination (`page[size]`, then `links.next`).
- `GET /api/v2/search?query=type:ticket created>=2026-08-08` (offset pages, at most 1,000 results).
- `GET /api/v2/search/export?filter[type]=ticket` for more than 1,000.

Ask the user how a ticket's theme is recorded: a tag prefix, a list of theme tags, or a custom field.

## Convert

```bash
python3 scripts/from_zendesk.py --tickets run/zendesk/tickets-*.json --theme-prefix "theme_" --period-start 2026-08-08 --period-end 2026-11-23 --subdomain acme --run run
```

`--theme-field <id>` reads a custom field instead. A ticket with no theme is left out and counted. The account is the ticket's organization.
