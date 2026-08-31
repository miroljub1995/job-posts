"""Shared state for the job-scan skill.

All scan state lives on disk so the walk can be resumed by any session:

  arbetsformedlingen.se/jobs.csv          accepted ads, sorted by Posted asc
  arbetsformedlingen.se/scan-log.csv      one row per decision, including skips
  arbetsformedlingen.se/.scan-state.json  the cursor (committed, tiny)
  arbetsformedlingen.se/.scan-cache.json  prefetched ads (gitignored, derived)
"""

import csv
import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

API = "https://jobsearch.api.jobtechdev.se/search"

# Taxonomy conceptIds (SSYK level 4) for the two occupation groups worth
# scanning. Narrower than the whole Data/IT field, which also sweeps in support
# technicians, testers, sysadmins and IT architects.
OCCUPATION_GROUPS = [
    "DJh5_yyF_hEM",  # Mjukvaru- och systemutvecklare m.fl. (2512)
    "UxT1_tPF_Kbg",  # Övriga IT-specialister (2519)
]

REPO = pathlib.Path(
    os.environ.get("JOB_POSTS_DIR") or pathlib.Path(__file__).resolve().parents[4]
)
DATA_DIR = REPO / "arbetsformedlingen.se"
JOBS_CSV = DATA_DIR / "jobs.csv"
LOG_CSV = DATA_DIR / "scan-log.csv"
STATE_PATH = DATA_DIR / ".scan-state.json"
CACHE_PATH = DATA_DIR / ".scan-cache.json"

JOB_FIELDS = ["ID", "Post URL", "Company", "Posted", "Match (%)", "Visa", "Status"]
LOG_FIELDS = ["ID", "Posted", "Decision", "Match (%)", "Reason"]

# Fields worth transferring. text_formatted is deliberately absent: it is the
# same prose as text, wrapped in HTML, and doubles the size of every ad.
X_FIELDS = (
    "total{value},hits{id,headline,publication_date,webpage_url,employer{name},"
    "description{text},occupation{label},working_hours_type{label},"
    "workplace_address{municipality},must_have{languages{label}},"
    "application_deadline}"
)

# An ad that never names the .NET stack cannot clear the mandatory bar, so it is
# skipped without being read. Deliberately broad — false keeps are cheap (the
# model reads one extra ad), false skips are not. Matched case-insensitively
# against headline + description.
DOTNET_TOKENS = [
    "c#", "csharp", "c-sharp", ".net", "dotnet", "asp.net", "aspnet",
    "net core", "netcore", "blazor", "entity framework", "efcore",
]


def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def parse_ts(value):
    return dt.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")


def load_json(path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    tmp.replace(path)


def load_state():
    return load_json(STATE_PATH, {})


def save_state(state):
    save_json(STATE_PATH, state)


def initial_cursor(state, days_back=7):
    """Where to resume: the state file, else the newest Posted in jobs.csv,
    else days_back days ago."""
    if state.get("cursor"):
        return state["cursor"]
    posted = [row["Posted"] for row in read_jobs() if row.get("Posted")]
    if posted:
        return max(posted) + "T00:00:00"
    return (utcnow() - dt.timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%S")


def read_csv_rows(path, fields):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [{key: row.get(key, "") or "" for key in fields}
                for row in csv.DictReader(fh)]


def write_csv_rows(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        # "\n" rather than the csv default "\r\n": these files are hand-edited
        # and diffed in git.
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_jobs():
    return read_csv_rows(JOBS_CSV, JOB_FIELDS)


def write_jobs(rows):
    # jobs.csv is kept sorted by publication date ascending; ID breaks ties so
    # the order is stable across runs.
    rows.sort(key=lambda row: (row["Posted"], row["ID"]))
    write_csv_rows(JOBS_CSV, JOB_FIELDS, rows)


def append_log(row):
    rows = read_csv_rows(LOG_CSV, LOG_FIELDS)
    rows.append(row)
    write_csv_rows(LOG_CSV, LOG_FIELDS, rows)


def known_ids():
    """Every ad already decided on — accepted, excluded or skipped."""
    ids = {row["ID"] for row in read_jobs()}
    ids |= {row["ID"] for row in read_csv_rows(LOG_CSV, LOG_FIELDS)}
    return ids


def prescreen_miss(ad):
    """True when the ad provably cannot meet the mandatory .NET requirement."""
    haystack = ((ad.get("headline") or "") + " " +
                ((ad.get("description") or {}).get("text") or "")).lower()
    return not any(token in haystack for token in DOTNET_TOKENS)


def search(cursor, limit, extra=None):
    """One page of in-scope ads published at or after cursor, oldest first."""
    since = parse_ts(cursor) - dt.timedelta(seconds=1)
    query = [("occupation-group", group) for group in OCCUPATION_GROUPS]
    query += [
        ("sort", "pubdate-asc"),
        ("published-after", since.strftime("%Y-%m-%dT%H:%M:%S")),
        ("limit", str(limit)),
        ("offset", "0"),
    ]
    for key, values in (extra or {}).items():
        for value in values:
            query.append((key, value))
    url = API + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url, headers={"accept": "application/json", "X-Fields": X_FIELDS}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:400]
        raise SystemExit("API error %s for %s\n%s" % (exc.code, url, body))
