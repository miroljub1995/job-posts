# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo tracks LinkedIn job posts matched against Miroljub's CV. Jobs are collected via the LinkedIn MCP server (`stickerdaniel/linkedin-mcp-server`, tools prefixed `mcp__MCP_Server_for_LinkedIn__`), scored against the CV, and stored as JSON per country. A GitHub Pages UI (`docs/index.html`) reads the JSON via the GitHub API and writes status changes back as commits.

## Layout

- `jobs/<country>/jobs.json` — one file per country (currently `sweden`, `denmark`). A flat JSON array; each entry:
  ```json
  {
    "url": "https://www.linkedin.com/jobs/view/<id>/",
    "title": "Job title",
    "company": "Company name",
    "match": 85,
    "status": "open",
    "added": "2026-08-25"
  }
  ```
  - `url` is the canonical LinkedIn job URL and the **dedupe key** — never add an entry whose job ID already exists in any country file.
  - `match` is 0–100, scored against the CV (see `SEARCHING.md` for the rubric).
  - `status` is one of `open`, `applied`, `in-progress`, `denied`. New entries always start as `open`. **Only the user (via the Pages UI or explicitly in chat) moves a job out of `open`** — never change an existing entry's status during a populate run.
- `cv/` — git submodule of https://github.com/miroljub1995/cv containing `cv.pdf`. Run `git submodule update --init` after a fresh clone.
- `CV-SUMMARY.md` — extracted text summary of the CV used for match scoring (regenerate from `cv/cv.pdf` if the submodule is updated).
- `SEARCHING.md` — the search playbook: which queries to run per country, dedupe rules, and the match-scoring rubric.
- `.claude/skills/populate-jobs/` — the skill the daily scheduled run invokes.
- `docs/` — the GitHub Pages status board. Served from the `main` branch `/docs` folder. It reads `jobs/*/jobs.json` through the GitHub Contents API and commits status changes back, so **always push after modifying job files** or the UI shows stale data (and a later UI commit could clobber unpushed local edits).

## Common tasks

- **Populate jobs** (the daily task): invoke the `populate-jobs` skill. It stops when the total count of `open` jobs across all countries reaches 100.
- **Validate JSON** after edits:
  ```bash
  for f in jobs/*/jobs.json; do python3 -m json.tool "$f" > /dev/null && echo "OK $f"; done
  ```
- **Count open jobs**:
  ```bash
  python3 -c "import json,glob; print(sum(sum(1 for j in json.load(open(f)) if j['status']=='open') for f in glob.glob('jobs/*/jobs.json')))"
  ```

## Conventions

- Keep each `jobs.json` sorted by `match` descending so the best matches are on top.
- Commit messages for populate runs: `populate: <n> new jobs (<country>: <n>, ...)`. Push to `main` after every populate run.
- Adding a country = create `jobs/<country>/jobs.json` with `[]` and add search queries for it in `SEARCHING.md`; the Pages UI discovers country folders automatically.
- The status-change commits made by the Pages UI touch only one country file at a time; pull before local edits to avoid conflicts.
