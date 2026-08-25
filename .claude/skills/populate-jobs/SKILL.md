---
name: populate-jobs
description: Search LinkedIn for .NET/C#/fullstack jobs per country, score them against the CV, and append new open rows to the Google Sheet tracker. Stops once 100 jobs are open in total. Use for the daily populate run or when the user asks to find/refresh jobs.
---

# Populate jobs

Follow these steps exactly. `SEARCHING.md` (repo root) holds the countries, queries, dedupe rules, and scoring rubric; `CLAUDE.md` holds the data flow and conventions.

## 1. Preflight

1. Fetch the current state: `python3 scripts/sheet.py list`.
   - If it fails because `sheet-config.json` is missing or has no endpoint, stop and tell the user to complete `SHEET-SETUP.md`. Do not store jobs anywhere else.
   - If the **open** count is **≥ 100**, stop: report "target reached (N open jobs), nothing to do" and remind the user they can delete the 10:00 daily schedule.
2. Ensure `CV-SUMMARY.md` exists. If missing, regenerate it from `cv/cv.pdf` (run `git submodule update --init` first if the submodule is empty).
3. Compute the budget: `remaining = 100 - open`. This run appends **at most `remaining`** new jobs.

## 2. Search

For each country in `SEARCHING.md`, run every listed query via the LinkedIn MCP `search_jobs` tool (location = country name). Normalize URLs and drop any job ID already present in the `list` output (any tab, any status).

If the LinkedIn MCP server is unavailable or errors on every call (e.g. session expired), stop and report that the LinkedIn session needs re-authentication — do not fabricate entries.

## 3. Score

For each surviving candidate, fetch the description with `get_job_details` and score it 0–100 against `CV-SUMMARY.md` using the rubric in `SEARCHING.md`. Discard scores below 50.

If more candidates survive than the remaining budget, keep the highest-scoring ones (balance countries roughly equally when truncating).

## 4. Append

Write the new rows (`status: "open"`, `added: <today yyyy-mm-dd>`, lowercase `country`) to a temp file and run:

```bash
python3 scripts/sheet.py append < rows.json
```

Confirm the response reports the expected `added` count; the bridge handles per-tab placement, final URL dedupe, and match-descending sorting.

## 5. Report

Summarize: new jobs per country with company + match score, total open count after the run, and how many remain until 100. If nothing new was found, say so plainly. Never modify existing rows or statuses — those belong to the user in Google Sheets.
