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
| Scorecard row (prior, actual, target) | Range line: a grey dot for prior, a status dot for actual, and a target tick; no coloured band. Green, grey-white and red stay for the status word only. | `bullet()`, drawn only when all three are figures in one unit |
| Plan against actual | Paired bars, plan grey above actual ink, scaled to the largest value; hatched when over | `plan_vs_actual()` |
| A table column where every cell is a % of 100 or less, or every cell a whole count | A bar before the figure: against 100 for shares, against the column's largest for counts | `share_columns()` |
| A tile showing `22 of 39` or `86%` | A proportion bar under the figure | `tile_share()` |
| A list item ending `Owner: X. Due: Y.` | Owner and due date in their own columns, owner in brass; a leading `Label:` becomes a mono tag | `list_item()` |
| `Yes` / `No` cells | Mono capitals, `NO` muted | `styled_cell()` |
| `High` / `Medium` / `Low` cells | Three pips, filled to the level | `styled_cell()` |
| Confidence and commitment words (Verified, Derived, Estimated, Unknown, Promise, Experiment) | A mono chip; Verified and Promise in ink, Estimated and Unknown dashed | `styled_cell()` |
| `Window` and `Due` columns | Mono, on one line | `styled_cell()` |
| Cover facts like `18 core slides`, `Board cut 8` | The figure large, its label in mono beneath | `fact()` |
| Data needed | Owner and due date in their own columns, owner in brass | `data_needed()` |
| A `Result` column | A status dot before the word: moved (green), moved the wrong way (red), not shipped or no movement (ring) | `styled_cell()` |
| `Options: A, or B. Deadline: D.` | Options as rows, the deadline in brass | `paragraph()` |
| A one-item list | Set larger, in ink, as the slide's single ask | CSS `li:only-child` |

## Space

Give elements room. Cards pad 22 to 26px; rows pad 12 to 18px; blocks on a slide sit 20px apart; columns in a row sit 32 to 36px apart. When in doubt, add space, never a border.

## Checks before a change ships

- Render `examples/harborline.html` and the `complete` fixture, then look at slides 1, 5, 8, 9, 11 and 18 at 1200px and 375px.
- No slide has a box inside a box.
- Every colour on a slide maps to a status, a person's call, plan or actual.
- Print (A4 landscape) still reads in light ink.
