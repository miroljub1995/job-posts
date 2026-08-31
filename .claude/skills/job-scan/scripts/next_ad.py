#!/usr/bin/env python3
"""Print the next Data/IT ad to judge, and nothing else.

Walks Platsbanken ads oldest-first from the stored cursor. Ads that provably
cannot meet the mandatory .NET requirement are skipped locally and logged, so
they never reach the model's context. Prints one ad per invocation.
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import scanlib as lib  # noqa: E402


def prune(ad, max_chars):
    text = (ad.get("description") or {}).get("text") or ""
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...truncated, %d chars total]" % len(text)
    return text


def fetch_keepers(cursor, limit, prescreen, extra, max_pages):
    """Page forward until at least one ad worth reading turns up."""
    seen = lib.known_ids()
    skipped = 0
    for _ in range(max_pages):
        hits = lib.search(cursor, limit, extra).get("hits") or []
        if not hits:
            return [], cursor, skipped, True
        fresh = [ad for ad in hits if ad["id"] not in seen]
        newest = max(ad["publication_date"] for ad in hits)
        keepers = []
        for ad in fresh:
            if prescreen and lib.prescreen_miss(ad):
                lib.append_log({
                    "ID": ad["id"],
                    "Posted": ad["publication_date"][:10],
                    "Decision": "skip",
                    "Match (%)": "",
                    "Reason": "prescreen: no .NET/C# mention",
                })
                skipped += 1
                seen.add(ad["id"])
            else:
                keepers.append(ad)
        if keepers:
            # Never advance the cursor past an ad still awaiting a decision.
            return keepers, min(ad["publication_date"] for ad in keepers), skipped, False
        if newest <= cursor:
            return [], cursor, skipped, True
        cursor = newest
        if len(hits) < limit:
            return [], cursor, skipped, True
    return [], cursor, skipped, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100,
                        help="ads per API page, 1-100 (default: 100)")
    parser.add_argument("--max-pages", type=int, default=10,
                        help="API pages to walk per invocation (default: 10)")
    parser.add_argument("--max-chars", type=int, default=6000,
                        help="truncate the ad description at N chars (default: 6000)")
    parser.add_argument("--from", dest="from_", metavar="YYYY-MM-DD",
                        help="start the scan here, ignoring the stored cursor")
    parser.add_argument("--q", action="append",
                        help="extra free-text narrowing passed to the API")
    parser.add_argument("--no-prescreen", action="store_true",
                        help="read every Data/IT ad, including ones with no .NET mention")
    args = parser.parse_args()

    state = lib.load_state()
    if args.from_:
        cursor = args.from_ + "T00:00:00"
        lib.save_json(lib.CACHE_PATH, [])
    else:
        cursor = lib.initial_cursor(state)

    cache = lib.load_json(lib.CACHE_PATH, [])
    skipped = 0
    if not cache:
        extra = {"q": args.q} if args.q else None
        cache, cursor, skipped, done = fetch_keepers(
            cursor, args.limit, not args.no_prescreen, extra, args.max_pages
        )
        state["cursor"] = cursor
        lib.save_state(state)
        lib.save_json(lib.CACHE_PATH, cache)
        if not cache:
            print("SCAN COMPLETE — no more ads to judge (cursor %s)." % cursor)
            if skipped:
                print("Prescreen skipped %d ad(s) this run; see scan-log.csv." % skipped)
            if not done:
                print("Page budget spent. Run again to keep walking.")
            return

    ad = cache[0]
    address = (ad.get("workplace_address") or {}).get("municipality") or "—"
    # The /search projection for must_have.languages is unreliable (often
    # null even when the employer set a required language), so this is
    # looked up directly against /ad/{id} instead. See fetch_required_languages.
    languages = lib.fetch_required_languages(ad["id"])
    if languages is None:
        languages_line = "unknown — language lookup failed, judge from description text only"
    else:
        languages_line = ", ".join(languages) or "none"
    if skipped:
        print("(prescreen skipped %d ad(s) to reach this one)" % skipped)
    print("=== AD %s === (%d cached, judge this one only)" % (ad["id"], len(cache)))
    print("URL:      %s" % ad.get("webpage_url", ""))
    print("Company:  %s" % ((ad.get("employer") or {}).get("name") or ""))
    print("Posted:   %s" % ad.get("publication_date", ""))
    print("Deadline: %s" % (ad.get("application_deadline") or "—"))
    print("Role:     %s | %s | %s" % (
        (ad.get("occupation") or {}).get("label") or "—",
        (ad.get("working_hours_type") or {}).get("label") or "—",
        address,
    ))
    print("Declared required languages: %s" % languages_line)
    print("Headline: %s" % ad.get("headline", ""))
    print("--- description ---")
    print(prune(ad, args.max_chars))
    print("--- end of ad %s ---" % ad["id"])


if __name__ == "__main__":
    main()
