# Connect Linear

Linear fills the investment slides: how the team's time split by type of work against the plan (slide 5), by product line (slide 4), and how much of it traces to an objective (slide 3). Its projects fill shipped vs impact (slide 8) and, where a project states a target, the outcome scorecard (slide 11). Its customer requests fill what we learned (slide 6) and customer and market signal (slide 7).

`scripts/from_linear.py` turns Linear's own JSON into the update's sources. Do not retype, summarise or reshape the export: save what Linear returns to a file and pass the file.

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

## Projects: shipped vs impact (slide 8)

Most coding agents stop at merge. Slide 8 asks whether the merged work landed: for each commitment, did it ship, and did the metric it named before launch move.

**Get the raw JSON.** With the Linear connector, call `list_projects` with `fields`: `id`, `name`, `description`, `url`, `status`, `targetDate`, `completedAt`, `canceledAt`, `lead`, `initiatives`, and `includeArchived: true` so finished projects are not missed. Save each page; follow `cursor` while `hasNextPage` is true. Optionally save each project's latest updates with `get_status_updates`. A CSV export works too, read by column name: `Name` and `Status` are required; `Target date`, `Completed` (or `Completed at`), `Lead`, `Description`, `URL` and `Initiatives` (separated by `;`) are read when present. A CSV without name and status columns is refused. With the API, query `projects { nodes { name description content url status { name type } targetDate completedAt lead { name } initiatives { nodes { name } } } }`.

```bash
python3 scripts/from_linear.py --projects run/linear/projects-1.json --project-updates run/linear/updates.json --period-start YYYY-MM-DD --period-end YYYY-MM-DD --workspace "Acme" --run run
```

| A project | On slide 8 |
|---|---|
| Completed inside the period | A commitment, shipped |
| Due inside the period, not completed (started, paused or cancelled) | A commitment, not shipped |
| Completed or due outside the period, or with no dates | Left out: not this period's commitment |
| With a complete "Landing brief" block in its description | Its target metric is the brief's metric, and the brief's bar goes to `targets.csv` |
| With no brief, or an incomplete one | No metric. The slide lists it under "No movement" and says why |

The metric is never read from anything else: not the title, the summary, the labels or the update text. The latest update is listed beside each row so the person can check it, but its words are never a result: the result comes from the team's metric data. The landing-brief skill in this repository has the template and a checker.

It writes `run/linear/commitments.csv` and, when any brief states a metric and a bar, `run/linear/targets.csv`. It never writes the intake. Show the person both files, then import:

```bash
python3 scripts/intake.py import run/intake.json --commitments run/linear/commitments.csv --targets run/linear/targets.csv
```

A target goes to the slide 11 scorecard only when a brief states both a metric and a bar. A metric the intake already holds is only replaced with `--replace`, and two projects with different bars for one metric are refused until the person picks one.

## Initiatives: line of sight (slide 3)

Call `list_initiatives` (with their projects) and save it. Pass it with `--initiatives`. An issue with no objective label then takes its project's initiative as its objective, which feeds the share of the team's time tied to an objective. An issue whose project sits under two initiatives gets none: the script does not pick one.

It also writes `run/linear/initiatives.csv` with each initiative, its owner and projects. Linear holds no cause or confidence, and slide 3 needs both for every branch, so ask the person for them in the interview. Never fill them in.

## Customer requests: what we learned and customer signal (slides 6 and 7)

Save the customer requests (customer needs) with their customer, created date and the issue or project each is linked to: `get_project` with `includeCustomerNeeds: true` per project, or the API's `customerNeeds { nodes { id createdAt customer { name } issue { identifier title url } project { name url } } }`. Pass the files with `--customer-needs` (project files with embedded requests also work with `--projects`).

The script writes the `customer_requests` source. `compute_metrics.py` counts the requests made inside the period by linked issue or project, and how many customers asked, in code. Slide 6 lists the most requested items, each linked to its issue or project, and says that requests are not a tested result. Slide 7 adds the top item beside the win and loss and support counts. A request linked to no issue or project is left out and counted.

## What is not yet tested on live data

The projects, updates, initiatives and customer requests readers are tested on fixtures built from the connector's documented fields and the API's field names, not on a real workspace's response. If a real export is refused, save it as it stands and report the shape. A workspace with no project completed or due in the period gets a refusal, and slide 8 stays a gap.
