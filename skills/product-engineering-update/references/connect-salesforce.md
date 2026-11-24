# Connect Salesforce

Salesforce fills the win and loss reasons on slide 7. `scripts/from_salesforce.py` turns closed opportunities into the `crm` source (deal, outcome, reason).

Connector: Salesforce has a Claude connector in the directory. Status: tested on fixtures shaped like a REST query response; Salesforce's developer documentation could not be read for this release (it returned 403), so the shape follows the standard query result (`records`, `done`, `nextRecordsUrl`) and is not checked against the page. Not yet run on a live org.

## Get the raw JSON

Run a SOQL query through the REST API or the connector, for example `SELECT Id, IsClosed, IsWon, CloseDate, Loss_Reason__c FROM Opportunity WHERE CloseDate >= 2026-08-08`, and save each page as it stands (follow `nextRecordsUrl` until `done` is true).

We could not confirm a standard win or loss reason field on Opportunity. Ask the user which field their team keeps it in.

## Convert

```bash
python3 scripts/from_salesforce.py --records run/salesforce/opps-*.json --reason-field Loss_Reason__c --period-start 2026-08-08 --period-end 2026-11-23 --org "Acme" --run run
```

An opportunity counts when `IsClosed` is true and `CloseDate` is in the window; `IsWon` gives the outcome. One with the reason field empty is left out and counted. Records without the named field are refused.
