# Metrics glossary

Every metric `scripts/compute_metrics.py` computes, with its formula. The period is `period.start` to `period.end` from the intake. The prior period is the same length, ending the day before the period starts.

Every scorecard row prints a one-sentence definition under the metric's name, and the AI slide prints one under each figure, so a reader outside engineering knows what the number counts. Computed metrics take theirs from `DEFINITIONS` in `scripts/compute_metrics.py`, which matches the formulas below. Outcome metrics take the intake's `definition` first (the team's own words), then the `definition` column of the analytics rows. An outcome with neither renders without one, and `validate.py` warns (`undefined-metric`).

## Contents

- [Confidence labels](#confidence-labels)
- [Delivery: speed and its quality pairs](#delivery-speed-and-its-quality-pairs)
- [Investment](#investment)
- [Revenue](#revenue)
- [Outcomes](#outcomes)
- [AI in the product and in how we build](#ai-in-the-product-and-in-how-we-build)
- [People and signal](#people-and-signal)
- [Conflicts and staleness](#conflicts-and-staleness)

## Confidence labels

| Label | Meaning |
|---|---|
| Verified | Read as it stands from the system that owns the number |
| Derived | Computed in code from collected rows |
| Estimated | Supplied by a person |
| Unknown | Missing, or two sources disagree. Shown as a gap, never as a figure |

## Delivery: speed and its quality pairs

A speed metric never appears without a quality metric on the same slide.

| Metric | Formula | Source | Kind |
|---|---|---|---|
| Deploys per week | Deploys in the period, divided by weeks in the period | `source_control`, rows with kind `deploy` | Speed |
| Lead time for change | Median hours from `opened_at` to `merged_at`, pull requests merged in the period | `source_control`, kind `pull_request` | Speed |
| Change failure rate | Failed deploys as a percent of deploys in the period | `source_control`, `failed` | Quality |
| Deploys rolled back or followed by errors | Deploys flagged by `from_vercel.py` (rolled back, or a runtime error group first seen while the deploy was live) as a percent of deploys whose outcome is known. A proxy for change failure rate, never relabelled as one | `source_control`, `troubled` | Quality (proxy) |
| Time to restore | Median minutes from `started_at` to `restored_at`, incidents started in the period | `incidents` | Quality |
| Pull request review time | Median `review_hours`, pull requests merged in the period | `source_control` | Quality |
| Rework rate | Reworked pull requests as a percent of those merged in the period | `source_control`, `reworked` | Quality |
| Developer experience index | Mean `score` for the period | `survey` | Effectiveness |

Each takes a healthy range from `delivery_ranges` in the intake, such as "under 40h" or "3+". A metric with no range is left off the slide.

## Investment

| Metric | Formula | Source |
|---|---|---|
| Capacity split by work type | Each work type's `estimate` as a percent of all estimates, items completed in the period | `tracker` |
| Over plan | Actual share is more than 3 points above the planned share. The investment mix slide asks for an explanation of any variance over 3 points | `tracker` and the intake's `investment_plan` |
| Capacity traced to an objective | Estimates on items with an `objective`, as a percent of all estimates | `tracker` |
| Capacity by product line | Each product line's `estimate` as a percent of all estimates | `tracker` |
| R&D as a share of revenue | Sum of the actuals on the intake's `rd_lines`, as a percent of the `Revenue` line | `finance` |

## Revenue

| Metric | Formula | Source |
|---|---|---|
| ARR | Sum of `arr` in the period's last month | `billing` |
| Net revenue retention | This period's ARR from accounts that existed at the end of the prior period, as a percent of their prior ARR | `billing` |
| Gross revenue retention | The same, capping each account at its prior ARR | `billing` |
| Expansion ARR | Sum of ARR increases on accounts that existed at the end of the prior period | `billing` |

## Outcomes

Analytics and warehouse metrics are read as supplied, one row per metric and period, and are Verified. The prior value is the most recent earlier period. The status word compares the value to the target in the intake.

## AI in the product and in how we build

| Metric | Formula | Source |
|---|---|---|
| Eval pass rate | `passed` as a percent of `cases`, latest run against the run before | `evals` |
| Cost per successful task | `cost_per_task`, latest run against the run before | `evals` |
| AI tool spend | Sum of `cost` for the period | `ai_tools` |
| Seats used weekly | Sum of `weekly_active` as a percent of the sum of `seats` | `ai_tools` |

Use and spend are inputs. The deck reports no productivity figure unless it has a baseline and a window.

## People and signal

| Metric | Formula | Source |
|---|---|---|
| Headcount | Sum of `now` against the sum of `plan` | `hr` |
| Win and loss reasons | Count of deals by `reason`, top 5 | `crm` |
| Support themes | Count of tickets by `theme`, top 5 | `support` |

## Conflicts and staleness

- Two sources agree when their values are within 0.5%. Beyond that the figure is a conflict: it is recorded as Unknown with both values, and shown as a gap until the user says which source owns it.
- A figure is stale when it was retrieved more than 92 days before the deck's as-of date. `validate.py` blocks it unless its ledger row is marked `stale: true` and the slide says so.
