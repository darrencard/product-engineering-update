# Connect GitHub

GitHub alone can fill the delivery slide (slide 9): lead time is a speed metric, and review time and rework are the quality metrics that pair with it. It is the fastest way to a real slide from a company's own data.

`scripts/from_github.py` turns GitHub's own JSON into the `source_control` source. It derives review time and rework in code. Do not retype, summarise or reshape the JSON yourself: save what GitHub returns to a file and pass the file.

## 1. Get the raw JSON

Use whichever is available. Check before you choose.

**The `gh` command line** (Claude Code, or any shell signed in to GitHub). The output goes straight to a file:

```bash
gh pr list --repo OWNER/NAME --state merged --limit 1000 --json number,createdAt,mergedAt,reviews > run/github-prs.json
```

```bash
gh api "repos/OWNER/NAME/deployments?per_page=100" --paginate > run/github-deployments.json
```

**A GitHub connector in the session.** Ask it for the merged pull requests of the repository with these fields for each: `number`, `createdAt` (or `created_at`), `mergedAt` (or `merged_at`), and `reviews`, each with `submittedAt` and `state`. Save the result as a JSON array in `run/github-prs.json`, exactly as returned. Do the same for deployments (`id`, `environment`, `created_at`) if the connector offers them. If the connector pages its results, fetch every page: a partial list gives a wrong median.

**Neither.** Ask the user to run the two `gh` commands above and upload the files, or to export a CSV with the `source_control` columns in [sources.md](sources.md).

Cover the reporting period and the period before it. The prior period is the same length, ending the day before the period starts.

## 2. Convert

```bash
python3 scripts/from_github.py --prs run/github-prs.json --deployments run/github-deployments.json --repo OWNER/NAME --retrieved-at YYYY-MM-DD --run run
```

Leave out `--deployments` if there are none. If deploys go to an environment with another name, pass `--environment "<name>"`.

It prints how many pull requests and deploys it found and how many pull requests had a review. Then run `compute_metrics.py` as usual.

## 3. What to expect

| The export has | The delivery slide shows |
|---|---|
| Pull requests with reviews | Lead time, review time and rework rate, plus deploys per week if deployments were supplied |
| Pull requests with no reviews (a solo repository) | A gap. Speed is measured and held back, because nothing pairs with it |
| Deployments only | A gap, for the same reason |

The slide also needs a healthy range for each metric, from `delivery_ranges` in the intake. Run `intake.py suggest` and put its sourced suggestions to the user to accept or edit; ask for the rest: "What is a healthy lead time, review time and rework rate for your team?" Do not set a range yourself.

## What GitHub cannot tell you

- **Change failure rate.** A failed build is not a change that failed in production. `from_github.py` leaves `failed` empty. Collect incident data for it.
- **Time to restore.** That comes from the `incidents` source.
