# Connect Intercom

Intercom fills the support themes on slide 7. `scripts/from_intercom.py` turns conversations into the `support` source (ticket, theme, account).

Connector: Intercom has a Claude connector in the directory (`mcp.intercom.com`), with conversation search. Status: tested on fixtures shaped like the documented conversation search response; not yet run on a live workspace.

## Get the raw JSON

`POST /conversations/search` for conversations created in the prior and reporting periods. Follow `pages.next.starting_after` until it is gone, and save each page as it stands. `created_at` is epoch seconds.

Ask the user how their tags name a theme: a prefix such as `theme:`, or a list of tags that are themes.

## Convert

```bash
python3 scripts/from_intercom.py --conversations run/intercom/conv-*.json --theme-prefix "theme:" --account-attribute "Account" --period-start 2026-08-08 --period-end 2026-11-23 --workspace "Acme" --run run
```

A conversation with no theme tag is left out and counted; the script never takes the first tag as a theme. `--account-attribute` names the custom attribute that holds the customer account, if there is one.
