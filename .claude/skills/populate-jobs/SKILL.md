---
name: populate-jobs
description: Search LinkedIn for .NET/C#/fullstack jobs in each country under jobs/, score them against the CV, and append new open entries to jobs/<country>/jobs.json. Stops once 100 jobs are open in total. Use for the daily populate run or when the user asks to find/refresh jobs.
---

# Populate jobs

Follow these steps exactly. `SEARCHING.md` (repo root) holds the queries, dedupe rules, and scoring rubric; `CLAUDE.md` holds the data schema and conventions.

## 1. Preflight

1. `git pull --rebase` so status changes made through the Pages UI are picked up first. If the pull fails, stop and report — do not run on a stale tree.
2. Count jobs with `status == "open"` across all `jobs/*/jobs.json`.
   - If the count is **≥ 100**, stop: report "target reached (N open jobs), nothing to do" and remind the user they can delete the 10:00 daily schedule. Do not search.
3. Ensure `CV-SUMMARY.md` exists. If missing, regenerate it by reading `cv/cv.pdf` (run `git submodule update --init` first if the submodule is empty).
4. Compute the remaining budget: `remaining = 100 - open_count`. This run adds **at most `remaining`** new jobs.

## 2. Search

For each country directory under `jobs/`, run every query listed in `SEARCHING.md` via the LinkedIn MCP `search_jobs` tool (location = country name). Collect results, normalize URLs, and drop any job ID already present in any country file (see the dedupe section of `SEARCHING.md`).

If the LinkedIn MCP server is unavailable or errors on every call (e.g. session expired), stop and report that the LinkedIn session needs re-authentication — do not fabricate entries.

## 3. Score

For each new candidate, fetch the description with `get_job_details` and score it 0–100 against `CV-SUMMARY.md` using the rubric in `SEARCHING.md`. Discard scores below 50.

If more candidates survive than the remaining budget, keep the highest-scoring ones (balance countries roughly equally when truncating).

## 4. Write & push

1. Append the new entries (`status: "open"`, `added: <today>`) to the right country file, re-sort each touched file by `match` descending.
2. Validate every touched file: `python3 -m json.tool jobs/<country>/jobs.json`.
3. Commit as `populate: <n> new jobs (<country>: <n>, ...)` and push to `main`.

## 5. Report

Summarize: new jobs per country with their match scores, total open count after the run, and how many remain until 100. If nothing new was found, say so plainly.
