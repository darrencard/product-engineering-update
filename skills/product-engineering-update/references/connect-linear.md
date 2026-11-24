# Connect Linear

Linear fills the investment slides: how the team's time split by type of work against the plan (slide 5), by product line (slide 4), and how much of it traces to an objective (slide 3).

`scripts/from_linear.py` turns Linear's own JSON into the `tracker` source. Do not retype, summarise or reshape the export: save what Linear returns to a file and pass the file.

## 1. Get the raw JSON

**The Linear connector in the session.** Call `list_issues` with `completedAt` set to the start of the prior period, `limit: 250`, and `fields`: `id`, `title`, `estimate`, `completedAt`, `status`, `statusType`, `labels`, `project`, `assignee`. Save each page as it stands. While `hasNextPage` is true, call again with `cursor` and save that page too. A partial list gives a wrong split.

**The Linear API.** A GraphQL `issues` query filtered to completed issues, returning `identifier`, `title`, `estimate`, `completedAt`, `state { name type }`, `labels { nodes { name } }`, `project { name }` and `assignee { name }`. Save the response as it stands.

Ask the user how their labels name a type of work. Most teams use a prefix (`type: Bug`) or a few labels (`Bug`, `Feature`). Do not decide it for them.

## 2. Convert

```bash
python3 scripts/from_linear.py --issues run/linear/page-1.json run/linear/page-2.json --work-type-prefix "type:" --workspace "Acme" --retrieved-at YYYY-MM-DD --run run
```

Or name labels one by one: `--work-type "Bug=Keep the lights on" --work-type "Feature=New capabilities"`. Use the same work-type names as the intake's `investment_plan`, or the plan and the actual will not line up. Add `--objective-prefix "objective:"` if objectives are labels.

## 3. What to expect

| The export has | The slides show |
|---|---|
| Completed issues with estimates and work-type labels | The capacity split, by work type and product line |
| Issues with no estimate | Left out and counted. They are never given an estimate |
| Issues with no work-type label | Counted as "Unlabelled", so the untyped share shows |
| No completed issues in the period | Refused; the tracker stays a gap |

The cycle is not used: the deck reads the period from the intake, not Linear's cycles.
