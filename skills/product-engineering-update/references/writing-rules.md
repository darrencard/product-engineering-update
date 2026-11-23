# Writing rules

## Titles

A title is one assertion sentence that the slide's evidence supports. A reader who sees only the title should know the answer.

- State the change, with its numbers: "Deploys per week rose from 34 to 41. Change failure rate rose from 3.1% to 3.4%."
- Use only figures that are on the slide and in the ledger.
- Do not add a cause the data does not show. "Activation rose from 39% to 41%" is a claim. "Activation rose because of the new onboarding" needs evidence for the "because".
- A label is not a title. "Outcome scorecard" claims nothing.
- When a slide has no data, say so: "Platform & security is not reported this period. The data is missing."
- Write the first slide's title last. It restates the most important change and adds nothing new.

`draft.py` writes a plain title from the computed change. Improve the wording if you can. Do not change what it claims.

## Status words

Only these 3, always printed as a word beside the mark:

- **landed**: the target is met, or the metric is inside its healthy range.
- **watch**: not there yet and moving the right way, or too early to call.
- **stalled**: not there and flat or moving the wrong way.

`draft.py` chooses the word by comparing the value to its target or range. Do not override it. If the word looks wrong, the target or the data is wrong: fix that.

## Claims the deck will not make

- A multiplier ("10x faster").
- "N% more productive", or any productivity, speed-up or time-saved figure, without a baseline and a window in the same sentence. Good: "Pull requests move 18% faster than a year ago."
- "AI-powered".
- An adoption or usage count presented as an outcome. Seats, sign-ups, prompts sent and pilots started are inputs.
- A speed metric with no quality metric beside it.
- A single-point target for a delivery metric. Use a range: "under 40h", "80 to 90%".
- A benchmark with no source and date. Where none exists, write "None external".

## When the user pushes for a stronger claim

Say what the data supports, what it does not, and what evidence would change that. Offer the supported claim. Do not soften the refusal into a hedge on the slide ("up to 40% more productive" is the same overclaim).

## Style

- Plain English, short active sentences, numerals for numbers.
- No em dashes or en dashes.
- One idea per card. Lists of 3 or fewer points where 2 carry the meaning.
- Every external claim keeps its source and date.
