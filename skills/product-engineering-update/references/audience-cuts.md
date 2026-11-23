# Audience cuts and cadence

One deck, one set of facts, 3 cuts. The slides change between cuts. The numbers never do.

| Audience | Key | Slides | Leaves out | Leads with | Rhythm |
|---|---|---|---|---|---|
| Leadership team | `L` | All 18 | Nothing | Decisions and constraints | Monthly |
| Board and investors | `B` | 1, 5, 9b, 11, 12, 14, 16, 18 | Team-level detail, backlog, tooling. Strategy returns when it changes | Why now, economics, risk, asks | Quarterly, sent 5 business days ahead |
| All staff | `S` | 1, 2, 3, 4, 6, 8, 11, 15, 16, 17 | Margin detail, confidential risks | Why this problem, how your work connects | Monthly or quarterly |

## Rules

- The board cut holds at most 8 slides. `validate.py` blocks a longer one.
- Slide 9b exists only in the board cut. It condenses slides 8, 9, 10 and 13, so the board cut needs their sources too.
- If the company has no AI features in production, slides 12 and 13 are removed and the board cut has 7 slides.
- Do not write a different number, status word or title for a different audience. Remove a slide from a cut; do not edit it for the cut.
- The board cut needs an explicit sign-off from a named person before it renders: `render.py --cut B --signed-off-by "<name>"`.

## Cadence

- Weekly: written project updates in the tracker. They are the input.
- Monthly: regenerate the leadership cut and review it.
- Quarterly: board and staff cuts. Reset plan against actual. Review the bets.
- Yearly: refresh slides 2, 3 and 4 and the plan on slide 5.

## Pre-read

Send the board cut 5 business days before the meeting. Spend the meeting on slide 18, the decisions.
