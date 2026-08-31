#!/usr/bin/env python3
"""Record the decision for the ad at the head of the queue and advance.

Writes jobs.csv (accepted ads only, sorted by Posted ascending), appends to
scan-log.csv, moves the cursor forward and drops the ad from the cache. After
this returns, nothing about the ad needs to stay in context.
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import scanlib as lib  # noqa: E402

REASONS = {
    "no-dotnet": "not a C#/.NET role",
    "swedish-required": "Swedish language required",
    "no-visa-sponsorship": "states it does not sponsor visas",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="ad ID, must be the queue head")
    parser.add_argument("--decision", required=True, choices=["include", "exclude"])
    parser.add_argument("--match", type=int,
                        help="0-100, required when including")
    parser.add_argument("--visa", choices=["true", "false"],
                        help="true only if the ad states it sponsors visas; "
                             "required when including")
    parser.add_argument("--reason", required=True,
                        help="excluding: %s. including: what scored, "
                             "e.g. 'react,aws,docker,postgresql,redis'"
                             % "/".join(REASONS))
    args = parser.parse_args()

    if args.decision == "include":
        if args.match is None or not 0 <= args.match <= 100:
            parser.error("--match 0..100 is required when including")
        if args.visa is None:
            parser.error("--visa true|false is required when including")
    elif args.reason not in REASONS:
        parser.error("--reason must be one of: %s" % ", ".join(REASONS))

    cache = lib.load_json(lib.CACHE_PATH, [])
    if not cache:
        raise SystemExit("queue is empty — run next_ad.py first")
    ad = cache[0]
    if ad["id"] != args.id:
        raise SystemExit(
            "queue head is %s, not %s — judge ads in order" % (ad["id"], args.id)
        )

    posted = ad["publication_date"]
    if args.decision == "include":
        rows = lib.read_jobs()
        if not any(row["ID"] == ad["id"] for row in rows):
            rows.append({
                "ID": ad["id"],
                "Post URL": ad.get("webpage_url") or "",
                "Company": (ad.get("employer") or {}).get("name") or "",
                "Posted": posted[:10],
                "Match (%)": str(args.match),
                "Visa": args.visa,
                "Status": "",
            })
            lib.write_jobs(rows)

    lib.append_log({
        "ID": ad["id"],
        "Posted": posted[:10],
        "Decision": args.decision,
        "Match (%)": str(args.match) if args.match is not None else "",
        "Reason": args.reason,
    })

    state = lib.load_state()
    state["cursor"] = posted
    lib.save_state(state)
    lib.save_json(lib.CACHE_PATH, cache[1:])

    print("%s %s%s | jobs.csv: %d | queued: %d" % (
        args.decision, ad["id"],
        " match=%d visa=%s" % (args.match, args.visa)
        if args.decision == "include" else " (%s)" % args.reason,
        len(lib.read_jobs()), len(cache) - 1,
    ))


if __name__ == "__main__":
    main()
