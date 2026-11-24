# Connect GitHub Projects

A GitHub project board fills the investment slides the same way an issue tracker does, when its items carry an estimate and a work type.

`scripts/from_github_projects.py` turns `gh project item-list` output into the `tracker` source. Do not retype or reshape it: save what `gh` writes and pass the file.

Status: tested on fixtures shaped like `gh project item-list --format json` output. It has not yet run on a live project.

## 1. Get the raw export

```bash
gh project item-list 3 --owner acme --format json --limit 1000 > run/gh-project/items.json
```

```bash
gh issue list --repo acme/app --state closed --json url,closedAt --limit 1000 > run/gh-project/closed.json
```

A project item records no completion date, so the second export gives each closed issue's date, matched by its url. Run it for each repository on the board, and `gh pr list --state merged --json url,closedAt` if the board holds pull requests. If the project has its own date field for completion, name it with `--completed-field` instead.

Custom fields appear in the export under the field's name in lower case. Ask the user which field holds the estimate and which names the type of work. Do not decide either for them.

## 2. Convert

```bash
python3 scripts/from_github_projects.py --items run/gh-project/items.json --closed run/gh-project/closed.json --estimate-field Estimate --work-type-field Type --product-line-field repository --project "Acme roadmap" --run run
```

`--done-status` sets the status that means done (default "Done"). `--work-type-prefix "type:"` reads the work type from labels instead of a field.

## 3. What to expect

| The export has | The result |
|---|---|
| Done items with an estimate and a closed date | One tracker row each |
| Done items with no estimate or no date | Left out and counted; nothing is filled in |
| Items with no work type | Counted as "Unlabelled" |
