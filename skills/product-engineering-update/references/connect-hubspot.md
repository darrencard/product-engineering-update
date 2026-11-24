# Connect HubSpot

HubSpot fills the win and loss reasons on slide 7. `scripts/from_hubspot.py` turns its closed deals into the `crm` source (deal, outcome, reason).

Connector: HubSpot has a Claude connector in the directory (`mcp.hubspot.com`), with CRM search. Status: tested on fixtures shaped like the documented deals search response, including rebuilding the Kestrel test company's deals; not yet run on a live portal.

## Get the raw JSON

`POST /crm/v3/objects/deals/search` for deals closed in the prior and reporting periods, with `properties` set to `hs_is_closed`, `hs_is_closed_won`, `closedate`, `closed_won_reason` and `closed_lost_reason` (search returns only a few properties unless asked). Follow `paging.next.after` until it is gone, and save each page as it stands.

## Convert

```bash
python3 scripts/from_hubspot.py --deals run/hubspot/deals-*.json --period-start 2026-08-08 --period-end 2026-11-23 --portal "Acme" --run run
```

A closed deal counts in the window by its close date; `hs_is_closed_won` gives won or lost, and the matching reason property gives the reason. A closed deal with no reason is left out and counted: the slide counts reasons, so none is invented.
