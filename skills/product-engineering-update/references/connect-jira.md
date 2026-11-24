# Connect Jira

Jira fills the investment slides: how the team's time split by type of work against the plan (slide 5), by product line (slide 4), and how much traces to an objective (slide 3). Its epics or versions can also give slide 8 its commitments.

`scripts/from_jira.py` turns Jira's own export into the `tracker` source. Do not retype or reshape the export: save what Jira returns and pass the file.

Status: tested on fixtures shaped like Jira's documented REST search response and its CSV export. It has not yet run on a live Jira site.

## 1. Get the raw export

**REST search or the Jira connector (preferred).** Search with JQL for issues resolved in the prior and reporting periods, for example `resolved >= 2026-08-08 AND resolved <= 2026-11-23`. Ask for the fields `summary`, `issuetype`, `status`, `resolutiondate`, `labels`, `components`, `assignee`, `project`, `duedate`, `fixVersions` and the estimate field (story points are usually a custom field such as `customfield_10016`). Save each page as it stands, and keep paging until `startAt + maxResults` reaches `total`.

**CSV export.** From an issue search, export CSV with all fields. Jira repeats a column for each label, component and version; the script reads every copy.

Ask the user which field is their estimate and which field names a type of work (issue type, a label prefix, or a component). Do not decide either for them.

## 2. Convert

```bash
python3 scripts/from_jira.py --search run/jira/page-*.json --estimate-field customfield_10016 --work-type-from issuetype --work-type "Bug=Keep the lights on" --work-type "Story=New capabilities" --product-line-from component --site "acme.atlassian.net" --run run
```

Add `--commitments-from versions` (search export only: the CSV carries no release dates) or `--commitments-from epics`, with `--period-start` and `--period-end`, to write `run/jira/commitments.csv`. Jira holds no target metric, so the metric column is empty. Fill it with the person, show them the rows, then `intake.py import --commitments`.

## 3. What to expect

| The export has | The result |
|---|---|
| Done issues with an estimate and a resolution date | One tracker row each |
| Done issues with no estimate or no resolution date | Left out and counted; nothing is filled in |
| Issues with no value in the work-type field | Counted as "Unlabelled" |
| A CSV without the estimate column | Refused |
