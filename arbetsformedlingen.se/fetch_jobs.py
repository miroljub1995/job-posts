#!/usr/bin/env python3
"""Fetch job ads from the Arbetsformedlingen JobSearch API into jobs.csv.

The CSV is an upsert target: rows are keyed by ID, and any value you have typed
by hand into "Match (%)" or "Status" is preserved across runs. Only ads that are
not already in the file get appended.

Docs: https://jobsearch.api.jobtechdev.se/  (Swagger UI, no API key needed)

Examples:
    ./fetch_jobs.py --q python --limit 100
    ./fetch_jobs.py --q "python" --municipality AvNB_uwa_6n6 --published-after 1440
    ./fetch_jobs.py --q java --remote true --pages 5 --sort pubdate-desc
"""

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://jobsearch.api.jobtechdev.se/search"
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.csv")
FIELDS = ["ID", "Post URL", "Company", "Posted", "Match (%)", "Visa", "Status"]

# Only ask the API for what ends up in the CSV; keeps responses small.
X_FIELDS = "total{value},hits{id,headline,publication_date,relevance,webpage_url,employer{name}}"

# Every query parameter the /search endpoint accepts. Values are passed through
# verbatim; the ones marked True may be repeated (--skill a --skill b).
SEARCH_PARAMS = {
    "q": False, "qfields": True,
    "published-before": False, "published-after": False,
    "occupation-name": True, "occupation-group": True, "occupation-field": True,
    "occupation-collection": True, "skill": True, "language": True,
    "worktime-extent": True, "parttime.min": False, "parttime.max": False,
    "driving-license-required": False, "driving-license": True,
    "employment-type": True, "duration": True, "experience": False,
    "municipality": True, "region": True, "country": True,
    "workplace-model": True, "unspecified-sweden-workplace": False, "abroad": False,
    "position": True, "position.radius": True,
    "employer": True, "label": True,
    "remote": False, "open_for_all": False, "trainee": False, "larling": False,
    "franchise": False, "hire-work-place": False,
    "relevance-threshold": False, "resdet": False, "sort": False,
    "stats": True, "stats.limit": False,
}

DEFAULT_URL = "https://arbetsformedlingen.se/platsbanken/annonser/{id}"


def arg_dest(name):
    """argparse turns '-' into '_' on its own but leaves '.' alone."""
    return name.replace(".", "_").replace("-", "_")


def ad_id_from_url(url):
    """Parse the ad ID out of a Platsbanken URL (last path segment)."""
    return urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def search(params, offset, limit):
    query = []
    for key, values in params.items():
        for value in values:
            query.append((key, value))
    query += [("offset", str(offset)), ("limit", str(limit))]
    url = API + "?" + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url, headers={"accept": "application/json", "X-Fields": X_FIELDS}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit("API error %s for %s\n%s" % (exc.code, url, exc.read().decode(errors="replace")[:500]))


def read_csv():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(rows):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        # "\n" rather than the csv default "\r\n": the file is hand-edited and
        # diffed in git alongside the rest of the repo.
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def row_from_hit(hit, with_match):
    employer = hit.get("employer") or {}
    url = hit.get("webpage_url") or DEFAULT_URL.format(id=hit.get("id", ""))
    match = ""
    if with_match and hit.get("relevance") is not None:
        match = str(round(hit["relevance"] * 100))
    return {
        "ID": str(hit.get("id", "")),
        "Post URL": url,
        "Company": employer.get("name") or "",
        # Date only; the API returns an ISO timestamp.
        "Posted": (hit.get("publication_date") or "")[:10],
        "Match (%)": match,
        # Left blank: only the job-scan skill, which reads the ad text, can
        # tell whether visa sponsorship is mentioned.
        "Visa": "",
        "Status": "",
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    for name, repeatable in SEARCH_PARAMS.items():
        parser.add_argument(
            "--" + name,
            dest=arg_dest(name),
            action="append" if repeatable else "store",
            help="JobSearch API parameter '%s'" % name,
        )
    parser.add_argument("--limit", type=int, default=100,
                        help="hits per request, 0-100 (default: 100)")
    parser.add_argument("--pages", type=int, default=1,
                        help="how many pages of --limit to fetch (default: 1)")
    parser.add_argument("--offset", type=int, default=0,
                        help="offset of the first hit, 0-2000 (default: 0)")
    parser.add_argument("--relevance-as-match", action="store_true",
                        help="prefill Match (%%) from the API relevance score")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be added without writing jobs.csv")
    args = parser.parse_args()

    params = {}
    for name in SEARCH_PARAMS:
        value = getattr(args, arg_dest(name))
        if value in (None, []):
            continue
        params[name] = value if isinstance(value, list) else [value]
    if not params:
        parser.error("give at least one search parameter, e.g. --q python")

    rows = read_csv()
    known = {row["ID"] for row in rows}
    added = 0

    for page in range(args.pages):
        offset = args.offset + page * args.limit
        if offset > 2000:
            print("offset %d exceeds the API maximum of 2000, stopping" % offset)
            break
        result = search(params, offset, args.limit)
        hits = result.get("hits") or []
        if not hits:
            break
        for hit in hits:
            row = row_from_hit(hit, args.relevance_as_match)
            if not row["ID"] or row["ID"] in known:
                continue
            known.add(row["ID"])
            rows.append(row)
            added += 1
        if len(hits) < args.limit:
            break

    print("%d new ad(s); %d total in jobs.csv" % (added, len(rows)))
    if args.dry_run:
        for row in rows[-added:] if added else []:
            print("  ", row["ID"], row["Company"], row["Post URL"])
        return
    if added:
        write_csv(rows)


if __name__ == "__main__":
    main()
