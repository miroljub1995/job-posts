# Search playbook

How to find LinkedIn job posts and score them. Used by the `populate-jobs` skill; also usable manually in any Claude Code session with the LinkedIn MCP server connected.

Countries currently tracked: **Sweden**, **Denmark** (one Google Sheet tab each; a new country just needs its queries added here).

## Target profile

Fullstack / backend developer centered on **.NET / C#**, with frontend experience in **Vue** and **React**. See `CV-SUMMARY.md` for the full skill list used in scoring.

## Queries

LinkedIn search behaves best with short queries, so run **multiple narrow searches** per country rather than one long one. For each country (`Sweden`, `Denmark`), run `search_jobs` with each of:

1. `.NET developer`
2. `C# developer`
3. `fullstack .NET`
4. `C# Vue`
5. `C# React`
6. `dotnet backend`

Notes:
- Use the country name as the `location` parameter (e.g. `Sweden`, `Denmark`). Results may include city-level locations within the country — that's fine.
- Fetch up to ~25 results per query. Later queries mostly return duplicates of earlier ones; that's expected, dedupe handles it.
- If a query errors or returns nothing, continue with the remaining queries — don't abort the run.

## Dedupe

The LinkedIn job ID (the number in the URL, e.g. `4012345678` in `https://www.linkedin.com/jobs/view/4012345678/`) is the identity of a post:

- Normalize every URL to `https://www.linkedin.com/jobs/view/<id>/` (strip tracking query params).
- Skip any ID already present in **any** tab of the sheet (`scripts/sheet.py list`), regardless of status — a job that was denied or applied to must not reappear. The bridge also drops exact URL duplicates on append as a backstop.

## Scoring (`match`)

For each new job, call `get_job_details` to get the description, then score 0–100 against `CV-SUMMARY.md`:

- **90–100** — Core stack match: .NET/C# role that also wants Vue or React (or explicitly fullstack). Seniority fits (medior/senior). No hard blockers.
- **70–89** — Strong: .NET/C# is the primary stack but frontend differs (Angular/Blazor) or the role is backend-only.
- **50–69** — Partial: .NET/C# is one of several accepted stacks, or the role centers on an adjacent skill from the CV (e.g. TypeScript/Node fullstack).
- **25–49** — Weak: different primary stack, but transferable (Java, Go); or heavy domain mismatch.
- **0–24** — Poor: unrelated stack or role.

Apply modifiers after picking the band: −10 if the posting requires fluent Swedish/Danish, −10 if it requires on-site relocation with no flexibility, +5 for explicitly remote/hybrid-friendly.

**Only add jobs scoring ≥ 50.** Round to the nearest 5.

## Adding entries

Append via the sheet bridge with `status: "open"` and `added` set to today's date (`yyyy-mm-dd`):

```bash
python3 scripts/sheet.py append < rows.json
```

where `rows.json` is an array of `{country, url, company, match, status, title, added}` (`country` lowercase, matching the tab name). The bridge sorts each tab by match descending automatically.
