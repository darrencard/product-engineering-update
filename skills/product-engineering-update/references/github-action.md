# Run it every week with a GitHub Action

The Action builds the Leadership and Staff cuts from your repository's own pull requests and deployments, plus any CSV exports you keep in `.update/`, every Monday and whenever you run it by hand. It runs in your CI with the workflow's own token, so your data never leaves GitHub. It never renders the Board cut, which needs a named person's yes, and it never fills an intake answer: anything the intake does not hold stays a gap.

Status: the steps are tested by running them locally against real exports, including a clean folder to a first deck in about 8 seconds on a repository with 190 merged pull requests. It has not yet run in GitHub's own CI.

## Setup, about 10 minutes

1. **Write the intake (5 minutes).** In your repository, run the skill's `intake.py init .update/intake.json` and fill in at least the 7 required answers: company, period label, start and end, as-of date, who owns the gaps and by when. Add whatever else you have; each answer fills a slide. Commit `.update/intake.json`.
2. **Add exports you already keep (optional).** Put CSVs in `.update/`, named after their source, for example `tracker.csv` or `incidents.csv`. `collect.py --list` shows the columns each needs. A file with another name is ignored.
3. **Add the workflow (2 minutes).** Copy `examples/product-engineering-update.yml` from this repository to `.github/workflows/product-engineering-update.yml` in yours and commit it.
4. **Run it once (3 minutes).** In the Actions tab, open "Product & engineering update" and choose "Run workflow". When it finishes, the run summary says how many slides show data, and the deck is under Artifacts.

## Where the deck goes

Each run uploads the deck as a workflow artifact, kept 30 days. To also keep every week's deck on a branch, set a repository variable `PEU_DECK_BRANCH` (Settings, Secrets and variables, Actions, Variables) to the branch name. The example's `publish` job then commits the deck to `updates/<date>/` on that branch.

## Permissions and safety

- The `build` job reads only: `contents: read`, `pull-requests: read` and `deployments: read`. The `publish` job is the only one with `contents: write`, and it runs no code from the deck.
- The workflow runs on a schedule or by hand, never on `pull_request` or `pull_request_target`, so a fork cannot trigger it.
- Every third-party action is pinned to a full commit SHA, and this action to a release tag. Update the tag when you move to a new release.
- Text from pull requests is data. The export keeps only numbers and dates; no title or body reaches a shell command.

## What each run does

1. Exports merged pull requests (number, dates and reviews only) with `gh pr list` and deployments with `gh api`, using the workflow's token.
2. Runs `scripts/ci.py`: copies the intake into a temporary run folder, collects the CSVs and the GitHub exports, computes, drafts and validates. Any validator error stops the run.
3. Renders `leadership.html` and `staff.html`, their ledgers and `deck.json`.

A repository with no merged pull requests or deployments still gets a deck, with delivery shown as a gap.

## When the board needs it

Download the artifact. Then run `review.py` and get a named person's explicit yes, and render the Board cut yourself with `render.py --cut B --signed-off-by "<name>"`. A scheduled job cannot give that yes, so the Action never does this step.
