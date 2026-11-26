# Design: how the report looks

The reference is the outcome scorecard on dacard.ai/update: a scorecard on the left, plan against actual on the right, in one frame. Every slide should read like it. `scripts/render.py` and `assets/template.html` apply these rules, so a deck gets them without anyone choosing them.

## Rules

1. **Numbers get a picture.** Any figure with something to compare it with gets a small chart next to it. The words and figures never change. The chart adds no number of its own.
2. **Labels in mono capitals, content in sans.** Section labels, column heads, owners, dates and the status word use Geist Mono at 10 to 12px. Sentences use Geist.
3. **Hairlines, not boxes.** Rows are split by 1px lines. Cards placed side by side share one frame with a hairline between them. A box inside a box is a mistake.
4. **Colour means something.**
   - Green, grey-white and red are status only: landed, watch, stalled. The word always prints next to the colour.
   - Brass marks a person's call: an owner who owes data, a decision's deadline, a sign-off.
   - Grey is plan and agent work. Ink (near white) is actual.
   - Hatching means over plan.
5. **One line per figure:** `prior → actual · TARGET x`, in mono, with the actual in ink.

## Pictures and when they appear

| Data | Picture | Rule in render.py |
|---|---|---|
| Scorecard row (prior, actual, target) | Range line: grey dot for prior, status dot for actual, a green band for the healthy range or a tick for a target | `bullet()`, drawn only when all three are figures in one unit |
| Plan against actual | Paired bars, plan grey above actual ink, scaled to the largest value; hatched when over | `plan_vs_actual()` |
| A table column where every cell is a % of 100 or less | A share bar before the figure | `share_columns()` |
| A tile showing `22 of 39` or `86%` | A proportion bar under the figure | `tile_share()` |
| A list item ending `Owner: X. Due: Y.` | Owner and due date in their own columns, owner in brass; a leading `Label:` becomes a mono tag | `list_item()` |
| `Yes` / `No` cells | Mono capitals, `NO` muted | `styled_cell()` |
| A `Result` column | A status dot before the word: moved (green), moved the wrong way (red), not shipped or no movement (ring) | `styled_cell()` |
| `Options: A, or B. Deadline: D.` | Options as rows, the deadline in brass | `paragraph()` |
| A one-item list | Set larger, in ink, as the slide's single ask | CSS `li:only-child` |

## Checks before a change ships

- Render `examples/harborline.html` and the `complete` fixture, then look at slides 1, 5, 8, 9, 11 and 18 at 1200px and 375px.
- No slide has a box inside a box.
- Every colour on a slide maps to a status, a person's call, plan or actual.
- Print (A4 landscape) still reads in light ink.
