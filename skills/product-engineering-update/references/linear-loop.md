# The weekly landing check, as a Linear Loop

A Linear Loop runs Linear Agent on a schedule inside your workspace. This one reads every project that carries a landing brief, writes one draft document saying where each stands against its bar, and stops for a person. It does the weekly part of [weekly-rhythm.md](weekly-rhythm.md) where the work already lives.

Linear creates Loops only in its own app; there is no API for them. Copy the fields below into **Loops → New loop → Start from scratch**. Loops need the feature turned on (Settings → Features → Loops) and use the workspace's AI credits.

## What the Loop may and may not do

The Loop is a model, not the skill's scripts, so it is held to less than the scripts are:

- It copies readings exactly as a project update or comment states them, with a link. It never estimates, rounds, averages or carries a figure forward.
- It applies the status rule only when a project has both a stated reading and a bar. Otherwise the project shows as **no reading**.
- It writes one draft document. It never posts a project update, changes a project's health or status, or edits a brief.
- The person confirms each status with `landing_brief.py update` (the landing-brief skill), which applies the rule in code, before anything is posted. The Loop's word is a draft until then.

## Fields to paste

**Name** (64 characters at most)

```text
Weekly landing check
```

**Description** (255 characters at most)

```text
Every Monday, reads each project's landing brief and latest stated reading, and drafts one document: landed, watch, stalled or no reading against the bar. Posts nothing. A person confirms each status in code before any project update goes out.
```

**Trigger:** Schedule, weekly, Monday, 07:30, your timezone. First run: next Monday.

**Instructions**

```text
Goal: a draft landing check for the person who owns product updates, so they can confirm each project's status before anything is posted.

1. Find projects in your team access that are started, or completed in the last 90 days, and whose description contains a "Landing brief" block. From each brief read: Metric, Bar, Better (higher or lower), By (a date), and Decides the next step. If any of these is missing, list the project under "Brief incomplete" with what is missing, and do not give it a status.

2. For each project with a complete brief, find the latest reading of its Metric: a number stated in a project update or a comment on the project, by a person, that names the metric. Copy the number and its unit exactly as written, with a link to where it is stated and its date. Also find the reading before it, the same way. Never estimate, round, average, convert units, or use a number from anywhere else. If there is no stated reading, the project's status is "no reading".

3. Apply this rule only where there is a reading and a bar:
   - landed: the reading meets the bar (at or above it when Better is higher; at or below it when Better is lower).
   - watch: it does not meet the bar, and it moved the better way since the previous reading, or there is no previous reading.
   - stalled: it does not meet the bar, and it is flat or moved the worse way since the previous reading.
   Never say the project caused the change.

4. Create one new document in the team, titled "Landing check, week of <Monday's date> (draft)". Open it with: "Draft by a Loop. Each status is model-applied and is confirmed in code with landing_brief.py before any project update is posted." Then one table with these columns: Project (linked), Metric, Bar and By, Latest reading (as stated, linked, dated), Previous reading, Status, Decides the next step. Under the table, list "Brief incomplete" and "No reading" projects with what each needs.

5. Mention the document's owner in a comment on it, once, with the counts: landed, watch, stalled, no reading, brief incomplete.

Do not post or edit project updates. Do not change any project's status, health, description or brief. Do not create issues. Do not use the web. If you are unsure whether a number is a reading of the metric, leave it out and say why in the document.
```

**Connectors:** none. Everything it reads is in Linear.

**Capabilities & access**

| Setting | Value | Why |
|---|---|---|
| Team access | Only the teams whose projects carry briefs | It reads and writes nothing else |
| Reasoning level | Medium | Matching a reading to a metric needs some care; nothing here needs High |
| Web access | Off | It must not send workspace content out, and needs nothing from the web |
| Access code | Disabled | It reads no code |
| Externally synced issues and comments | Off | It writes no comments outside its own document |

## After each run

1. Open the document. Check each reading against its link.
2. For each project you want to update, run the landing-brief skill's `landing_brief.py update` with the reading as `--current` and the previous one as `--prior`. If its word differs from the Loop's, the script's word stands. Tell the Loop's owner, and fix the instructions if the Loop misread something.
3. Post a project update only after you have read it, as the landing-brief skill says.
4. Check Run history and Settings → Usage & limits for what the run cost.

## Test it before you schedule it

Linear's own advice is to get the outcome right in a Linear Agent chat first (⌘/Ctrl + J), then turn it into a Loop. Paste the instructions into a chat, check the document it drafts against two or three projects you know, then create the Loop with **Run now** once before the first scheduled Monday.
