# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo automates collecting LinkedIn job posts for Miroljub and scoring them against his CV. Jobs are found via the LinkedIn MCP server (`stickerdaniel/linkedin-mcp-server`, tools prefixed `mcp__MCP_Server_for_LinkedIn__`), scored 0–100 against the CV, and stored in a **Google Sheet** in the user's Drive — one tab per country (currently `sweden`, `denmark`). The user manages application status (`open`, `applied`, `in-progress`, `denied`) directly in Google Sheets; this repo never changes an existing row's status.

There is no build, lint, or test setup — the repo is documentation, one Apps Script, and one Python client with no dependencies beyond python3 stdlib.

## Data flow

- **Store:** Google Sheet, accessed through an Apps Script web app bound to it ([apps-script/Code.gs](apps-script/Code.gs), deployed per [SHEET-SETUP.md](SHEET-SETUP.md)). Columns: `Post URL | Company | Match (%) | Status | Title | Added`. The Post URL is the dedupe key across all tabs.
- **Client:** [scripts/sheet.py](scripts/sheet.py) — the only way code here touches the sheet:
  ```bash
  python3 scripts/sheet.py list              # all rows + open/total counts
  python3 scripts/sheet.py append < rows.json # append; bridge dedupes by URL, sorts by match desc
  ```
  `rows.json` is an array of `{country, url, company, match, status, title, added}`.
- **Config:** `sheet-config.json` (repo root, gitignored) holds the web-app `endpoint` and the shared `secret`, which must match `SECRET` in `Code.gs`. If it's missing or empty, the sheet isn't set up — point the user to SHEET-SETUP.md instead of improvising another storage.
- **CV:** `cv/` is a git submodule of https://github.com/miroljub1995/cv (`git submodule update --init` after fresh clone). [CV-SUMMARY.md](CV-SUMMARY.md) is the extracted text used for scoring; regenerate it from `cv/cv.pdf` if the submodule updates.

## The populate flow

The `populate-jobs` skill (`.claude/skills/populate-jobs/`) runs daily at 10:00 via a scheduled task and on demand. It stops permanently once **100 jobs are `open`** in total. [SEARCHING.md](SEARCHING.md) is the playbook: per-country queries, URL normalization/dedupe rules, and the match-scoring rubric. Follow it rather than inventing queries or scores.

Adding a country = add its queries to `SEARCHING.md`; the tab appears automatically on first append.

## Conventions

- New rows always get `status: "open"` and `added: <today, yyyy-mm-dd>`. Only add jobs with match ≥ 50.
- Never edit the sheet through any path other than `scripts/sheet.py` (no Drive UI automation, no direct Sheets API).
- If `Code.gs` changes, the user must redeploy it manually in the Apps Script editor — tell them, don't assume the deployed version updated.
