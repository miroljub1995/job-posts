---
name: job-scan
description: Walk new Arbetsförmedlingen (Platsbanken) software developer ads one at a time, judge each against the C#/.NET profile, and record the keepers in arbetsformedlingen.se/jobs.csv. Use when asked to scan, populate, refresh, or continue the job list, or to score Swedish job ads.
---

# job-scan

Walks Platsbanken software developer ads oldest-first from a stored cursor,
judges one ad per step, and writes the result to disk before moving on.

## Files

| Path | Role |
| --- | --- |
| `arbetsformedlingen.se/jobs.csv` | Accepted ads. Sorted by `Posted` ascending, rewritten on every insert. |
| `arbetsformedlingen.se/scan-log.csv` | Every decision, including prescreen skips. The audit trail and the dedupe set. |
| `arbetsformedlingen.se/.scan-state.json` | The cursor. Committed — it is how a later session resumes. |
| `arbetsformedlingen.se/.scan-cache.json` | Prefetched ads. Gitignored, derived, safe to delete. |
| `.claude/skills/job-scan/scripts/` | `next_ad.py`, `record_ad.py`, `scanlib.py`. |

## The loop

Two commands, repeated. Run them from the repo root.

```sh
.claude/skills/job-scan/scripts/next_ad.py
.claude/skills/job-scan/scripts/record_ad.py --id <ID> --decision <include|exclude> ...
```

1. `next_ad.py` prints exactly one ad, or `SCAN COMPLETE`.
2. Judge it against the rules below. Decide from the printed text alone.
3. `record_ad.py` writes the row, advances the cursor, drops the ad.
4. Repeat until `SCAN COMPLETE` or the user's stopping point.

The ad must be recorded before the next one is fetched — `record_ad.py` refuses
any `--id` that is not the queue head, so the walk cannot silently skip an ad.

On the very first run, or to restart from a chosen date:

```sh
.claude/skills/job-scan/scripts/next_ad.py --from 2026-08-01
```

## Context discipline

The point of one-ad-at-a-time is that **the ad leaves your context once it is
recorded**. After each `record_ad.py`:

- Do not restate, summarise, or quote the ad you just judged.
- Do not keep a running tally, list, or table of what you have processed —
  `jobs.csv` and `scan-log.csv` already are that record.
- Do not re-read `jobs.csv` to check your work. It is written and sorted for you.
- Say at most one short line per ad, or nothing at all, then fetch the next.

Everything needed to continue is on disk, so the scan survives a `/clear`, a
compaction, or a brand new session: just run `next_ad.py` again. If context is
running short mid-scan, stop after a `record_ad.py`, tell the user where the
cursor is, and let a fresh session pick it up.

## Mandatory gate

Exclude the ad — `--decision exclude` — the moment any of these fails. Do not
score it, do not add it to `jobs.csv`.

| Reason code | Exclude when |
| --- | --- |
| `no-dotnet` | The role does not involve C#/.NET development. |
| `swedish-required` | The ad requires the Swedish language. |
| `no-visa-sponsorship` | The ad states it will not sponsor a visa. |

**.NET is the only stack requirement.** The role must have the person writing
C#/.NET. A backend-only .NET role qualifies — it is not excluded for lacking a
frontend, it just scores lower than one that also names Vue or React. It
qualifies too if C#/.NET is simply named among the role's required or
preferred skills, even if the ad also lists other languages/stacks
(Python, Java, C++, etc.) as alternatives or complements — the person may end
up writing C#/.NET some or all of the time, and that's enough. Excluded are
roles where C#/.NET is not part of the role's own skill list at all — it's
mentioned only as something the company or a *different* team/position uses
(a Java position at a .NET shop, a pure QA or support role).

**Swedish.** An ad *written* in Swedish is not an ad that *requires* Swedish —
most Swedish ads are written in Swedish. Exclude when either of two signals
says Swedish is required:

- Prose stating it explicitly: "flytande svenska", "svenska i tal och skrift",
  "du talar och skriver svenska". Phrases like "Swedish is a plus" or "English
  is our working language" are not exclusions.
- `Declared required languages` naming Swedish. This is looked up per-ad
  directly against the Arbetsförmedlingen ad-detail API (not the search
  results) because the employer's structured language requirement is often
  present there even when the prose never mentions it — the MCT Brattberg ad
  (31166878) is a confirmed case: no language requirement anywhere in the
  text, but `must_have.languages` listed Swedish at weight 10. Treat this
  field as authoritative when present, even if it contradicts your prose
  reading. If the line instead reads "unknown — language lookup failed",
  the API call itself failed; fall back to prose-only judgment for that ad
  and don't treat the failure as "no requirement".

**Visa.** Exclude when the ad rules sponsorship out: "we do not sponsor visas",
"we cannot support relocation or work permits", "you must already hold a valid
work permit", "EU citizenship required". A security-clearance or residency
requirement that amounts to the same thing counts too.

## Scoring

Only ads that clear the gate get a score. A .NET role starts at 40; the
remaining 60 points are earned by how much of the wanted stack the ad names.

    Match (%) = 40 + 60 x (bonus items named / 9)

The nine bonus items, each worth the same:

`vue or react` · `aws` · `rabbitmq` · `postgresql` · `mongodb` · `kubernetes` ·
`docker` · `github` · `redis`

`vue or react` is one item, not two — an ad naming both scores it once.

Use the table rather than doing the arithmetic:

| items | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Match (%)** | 40 | 47 | 53 | 60 | 67 | 73 | 80 | 87 | 93 | 100 |

Count an item only if the ad actually names it. Near misses do not count: Azure
or GCP is not AWS, SQL Server is not PostgreSQL, Kafka or Azure Service Bus is
not RabbitMQ, Memcached is not Redis, Angular or Blazor is not Vue/React, plain
"Git" or GitLab is not GitHub, "containers" without Docker is not Docker. K8s
counts as kubernetes; EKS/AKS implies kubernetes. Count an item once however
often the ad repeats it, and count it whether it is listed as required or as a
merit.

Pass the items you counted as `--reason`, so the number can be checked later:

```sh
record_ad.py --id 31414342 --decision include --match 73 --visa false \
             --reason "react,aws,docker,postgresql,redis"
```

## The Visa column

- `true` — the ad says it sponsors visas, relocates, or supports work permits.
- `false` — the ad says nothing about it. This is the common case.

Silence means `false`, never blank. An ad that rules sponsorship out is excluded
by the gate and so never reaches this column.

## What the scripts do for you

`next_ad.py` only surfaces ads that could plausibly pass. Before printing, it
skips any ad whose headline and description never mention the .NET stack
(`c#`, `.net`, `dotnet`, `asp.net`, `blazor`, `entity framework`, and similar) —
such an ad cannot meet the mandatory backend requirement, so reading it is
wasted context. Skips are logged to `scan-log.csv` as `prescreen: no .NET/C#
mention`. In practice this drops ~90% of ads; a typical page of 100 yields ~7 to
read. Pass `--no-prescreen` to read every in-scope ad instead.

The search is narrowed at the API to two occupation groups, so nothing else is
ever fetched:

| Group | SSYK | conceptId |
| --- | --- | --- |
| Mjukvaru- och systemutvecklare m.fl. | 2512 | `DJh5_yyF_hEM` |
| Övriga IT-specialister | 2519 | `UxT1_tPF_Kbg` |

That is roughly 40% of the Data/IT field — it drops support technicians,
operations engineers, testers, sysadmins and IT architects. To change the scope,
edit `OCCUPATION_GROUPS` in `scripts/scanlib.py`.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--from YYYY-MM-DD` | Restart at a date, clearing the queue. |
| `--q "<text>"` | Extra API-side narrowing, e.g. `--q .NET`. Faster, but the API's free-text ranking may hide ads the gate would have accepted. |
| `--max-chars N` | Description truncation, default 6000. Raise it if an ad is cut off exactly where the decision hinges. |
| `--no-prescreen` | Read every in-scope ad. |
| `--max-pages N` | API pages to walk per invocation, default 10. |

## Judgement calls

- **Consultancy ads** ("we place consultants at client X") count if the work
  described is a .NET role; score the frontend half from the work described,
  not from the consultancy's general technology list.
- **Truncated descriptions.** If the text is cut off and the missing part
  decides the outcome, re-run `next_ad.py --max-chars 20000`; the queue head
  does not move, so the same ad prints again in full.
- **When genuinely torn on whether the role is really .NET, include it at 40.**
  The gate is deliberately wide now; the score, not the filter, is what sorts
  the shortlist. Stay strict on the Swedish and visa exclusions.
- Never edit `jobs.csv` by hand to fix a decision — re-run the ad or correct the
  row deliberately, and remember the user's `Status` column is theirs.
