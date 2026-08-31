# arbetsformedlingen.se

Tracking of Swedish job ads from [Platsbanken](https://arbetsformedlingen.se/platsbanken).

- `jobs.csv` — the tracked ads, sorted by `Posted` ascending.
- `scan-log.csv` — one row per decision made by the `job-scan` skill, including
  the ads it skipped and why. The audit trail, and what keeps a rescan from
  re-judging the same ad.
- `.scan-state.json` — the scan cursor. Committed, so any session can resume.
- `fetch_jobs.py` — bulk fills `jobs.csv` from the API with no judgement applied.

Two ways to fill the file:

- **`job-scan` skill** (`.claude/skills/job-scan/`) — walks new software
  developer ads one at a time, scores each against the C#/.NET profile, and
  keeps only the ones that pass. This is the normal path; ask Claude to scan or
  continue the job list.
- **`fetch_jobs.py`** — a raw dump of whatever a search returns, unscored.
  Useful for ad-hoc queries, not for maintaining the shortlist.

## jobs.csv

| Column | Source | Notes |
| --- | --- | --- |
| `ID` | API `id` | Last path segment of the ad URL: `.../platsbanken/annonser/30948618` → `30948618`. The upsert key. |
| `Post URL` | API `webpage_url` | `https://arbetsformedlingen.se/platsbanken/annonser/{ID}` |
| `Company` | API `employer.name` | |
| `Posted` | API `publication_date` | Date only, `YYYY-MM-DD`. |
| `Match (%)` | `job-scan` skill | 0–100 against the target profile: 40 for a C#/.NET role, plus 60 spread evenly over nine bonus items it names (vue or react, aws, rabbitmq, postgresql, mongodb, kubernetes, docker, github, redis). `fetch_jobs.py --relevance-as-match` instead fills it with the API's query relevance, which is a different thing. |
| `Visa` | `job-scan` skill | `true` only when the ad states it sponsors visas; `false` when it says nothing. Ads that state they do *not* sponsor are excluded outright. |
| `Status` | manual | Free text, e.g. `applied`, `rejected`, `interview`. |

Rows are keyed by `ID`. Re-running the script only appends ads that are not already
in the file, so anything typed by hand into `Match (%)` and `Status` survives.

## Usage

```sh
./fetch_jobs.py --q python --limit 100
./fetch_jobs.py --q python --municipality AvNB_uwa_6n6 --published-after 1440
./fetch_jobs.py --q java --remote true --pages 5 --sort pubdate-desc
./fetch_jobs.py --q "data engineer" --limit 10 --dry-run   # preview, writes nothing
```

Every API query parameter below is exposed as a flag of the same name. Script-only
flags: `--pages` (how many pages of `--limit` to fetch), `--relevance-as-match`,
`--dry-run`.

## The API

Base URL `https://jobsearch.api.jobtechdev.se`, no key or registration, JSON only.
Swagger UI: <https://jobsearch.api.jobtechdev.se/>. Rate limited (HTTP 429).
It only serves ads that are **currently open for application**; for a full dump of
everything use the [Stream API](https://jobstream.api.jobtechdev.se) instead —
paging `/search` to harvest everything is explicitly discouraged and capped anyway.

### Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /search?q={text}` | Ads matching a query. All filters below apply here. |
| `GET /complete?q={text}` | Typeahead: common terms starting with the typed string. Takes the same filters, plus `limit` (default 5) and `contextual` (default true). |
| `GET /ad/{id}` | One ad by ID, with all metadata. |
| `GET /ad/{id}/logo` | Employer logo; a 1×1 white pixel if there is none. |

### `/search` inputs

**Free text**

| Parameter | Type | Meaning |
| --- | --- | --- |
| `q` | string | Free text over headline, description and employer name. Supports `*` wildcards (`muse*`), `"quoted phrases"`, and negation with a leading minus (`unix -linux`). |
| `qfields` | string, repeatable | Extra fields to free-text search: `occupation`, `skill`, `trait`, `location`, `employer`. |

**Occupation** — values are taxonomy `conceptId`s from the [Taxonomy API](https://jobtechdev.se/sv/produkter/jobtech-taxonomy), e.g. `occupation-field=apaJ_2ja_LuF` for Data/IT.

| Parameter | Type |
| --- | --- |
| `occupation-name` | string, repeatable |
| `occupation-group` | string, repeatable |
| `occupation-field` | string, repeatable |
| `occupation-collection` | string, repeatable — narrows the three above; excludes non-matching ones |
| `skill` | string, repeatable |
| `language` | string, repeatable |

**Location** — also taxonomy concept IDs. A leading `-` negates (`country=-i46j_HmG_v64` = not Sweden).

| Parameter | Type | Meaning |
| --- | --- | --- |
| `municipality` / `region` / `country` | string, repeatable | Taxonomy codes. |
| `position` | string, repeatable | `"59.329,18.068"` (lat,long). |
| `position.radius` | integer, repeatable | Km from `position`; pairs positionally with it. |
| `workplace-model` | string, repeatable | Arbetsplatstyp code. |
| `unspecified-sweden-workplace` | boolean | `true` returns ads with unspecified Swedish workplace; `false` is a no-op. |
| `abroad` | boolean | `true` also returns work outside Sweden when filtering on Swedish places; `false` is a no-op. |

**Employment terms**

| Parameter | Type | Meaning |
| --- | --- | --- |
| `employment-type` | string, repeatable | Taxonomy code. |
| `duration` | string, repeatable | Employment-duration code. |
| `worktime-extent` | string, repeatable | Taxonomy code. |
| `parttime.min` / `parttime.max` | number | Extent in percent, e.g. `50` / `100`. |
| `experience` | boolean | `false` filters to ads not requiring experience. |
| `driving-license-required` | boolean | |
| `driving-license` | string, repeatable | Licence type code. |

**Employer**

| Parameter | Type | Meaning |
| --- | --- | --- |
| `employer` | string, repeatable | Name, or Swedish org number (digits only). Prefix match — `employer=2` hits every public-sector employer. |

**Phrase-matched flags** — all boolean; `true` returns likely matches, `false` returns only ads that do *not* match the phrases.

`remote`, `trainee`, `larling`, `franchise`, `hire-work-place`, `open_for_all`
(the last matches the phrase "Öppen för alla").

**Dates**

| Parameter | Type | Meaning |
| --- | --- | --- |
| `published-after` | string | `YYYY-mm-ddTHH:MM:SS`, or a number of minutes (`60` = last hour). |
| `published-before` | string | `YYYY-mm-ddTHH:MM:SS`. |

**Result shaping**

| Parameter | Type | Meaning |
| --- | --- | --- |
| `offset` | integer | 0–2000, default 0. |
| `limit` | integer | 0–100, default 10. |
| `sort` | string | `relevance` (default), `pubdate-desc`, `pubdate-asc`, `applydate-desc`, `applydate-asc`, `updated`. |
| `relevance-threshold` | number | 0–1. |
| `resdet` | string | `full` (default) or `brief`. |
| `stats` | string, repeatable | Facet counts for `occupation-name`, `occupation-group`, `occupation-field`, `country`, `municipality`, `region`. |
| `stats.limit` | integer | Max rows per stats field. |
| `label` | string, repeatable | Filter by ad label. |

**Headers**

| Header | Meaning |
| --- | --- |
| `X-Fields` | Field mask trimming the response, e.g. `total{value},hits{id,headline,employer{name}}`. This script uses one. |
| `x-feature-disable-smart-freetext` | `true` makes `q` a plain text search over headline and description. |
| `x-feature-freetext-bool-method` | `and` / `or` (default `or`) for unclassified free-text words. |
| `x-feature-enable-false-negative` | Extra search pass to avoid false negatives. |

### Errors

`400` bad request · `404` ad not available · `429` rate limit exceeded · `500` server error.
