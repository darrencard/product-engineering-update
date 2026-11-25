# Review: Kestrel Labs, 2026-Q3

## Computed changes, this period against the prior one

| Metric | Prior | Now | Ledger |
|---|---|---|---|
| Capacity traced to an objective | no prior | 78% | L02 |
| Deploys per week | 3 | 4 | L03 |
| Lead time for change | 52h | 38h | L04 |
| Change failure rate | 5.1% | 7.7% | L05 |
| Pull request review time | 9h | 13h | L06 |
| Rework rate | 11.7% | 15% | L07 |
| Time to restore | 46m | 41m | L08 |
| ARR | $10.4M | sources disagree | L09 |
| Net revenue retention | no prior | 96.4% | L10 |
| Gross revenue retention | no prior | 89.3% | L11 |
| Expansion ARR in period | no prior | $741K | L12 |
| Activation | 39% | 41% | L13 |
| Loads cleared per week | no prior | sources disagree | L14 |
| Weekly active dispatchers | 5,890 | 6,120 | L15 |
| R&D as a share of revenue | no prior | 40.8% | L17 |
| Eval pass rate (v14) | 82% | 86% | L18 |
| Cost per successful task | $0.41 | $0.33 | L19 |
| AI tool spend in period | no prior | $90K | L20 |
| Seats used weekly | no prior | 75% | L21 |
| Developer experience index | 68 | 71 | L23 |

## Conflicts

- Loads cleared per week: PostHog says 23,100; Warehouse says 21,400. Shown as a gap until someone says which source owns it.
- ARR: Stripe says 10,911,000; Finance close says 10,100,000. Shown as a gap until someone says which source owns it.

## Gaps shown as data needed (3)

- Slide 10: Service-level objectives and error budgets, incident data, audit status, vulnerability ageing, the debt register. Owner: the VP Engineering. Due: Q4.
- Slide 11: Loads cleared per week: two sources disagree. See ledger row L14. Owner: the VP Engineering. Due: Q4.
- Slide 12: AI revenue and cost of revenue, for AI gross margin. Owner: the VP Engineering. Due: Q4.

## Ledger rows marked Unknown

- L09: ARR: sources disagree (Stripe says $10.9M, Finance close says $10.1M)
- L14: Loads cleared per week: sources disagree (PostHog says 23100, Warehouse says 21400)

## Board cut (8 slides)

- 1. The AI feature passes more of its quality tests (82% to 86%), but more releases caused production problems (5.1% to 7.7%). One decision needed: a per-load pricing pilot.
- 5. Basic upkeep was planned at 15% of the team's time and took 22%.
- 9b. Releases rose from 3 to 4 a week, but the share that caused a production problem rose from 5.1% to 7.7%.
- 11. Weekly active dispatchers reached 6,120, above the 6,000 target. Activation reached 41%, short of its 50% target.
- 12. The share of quality tests the AI feature passes rose from 82% to 86%. The cost of each task the AI feature completes fell from $0.41 to $0.33.
- 14. One risk: one model provider carries most inference spend.
- 16. We are making 2 bets, each with a set budget of time and people and a stated point at which we stop.
- 18. One decision for you today: approve a per-load pricing pilot.

## Checklist

- [ ] Every title is a claim the slide's evidence supports.
- [ ] Every figure on a slide has a ledger row, and the row names its source.
- [ ] Each speed metric sits beside a quality metric on the same slide.
- [ ] No AI productivity figure appears without a baseline and a window.
- [ ] Every data needed block has a real owner and a real date.
- [ ] Anything marked Unknown or in conflict is shown as a gap, not as a number.
- [ ] The asks on the last slide match the answer on the first.
- [ ] The board cut holds 8 slides or fewer.

Sign-off: ask a named person for an explicit yes, then pass their name to render.py --signed-off-by.
