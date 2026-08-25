#!/usr/bin/env python3
"""Client for the Apps Script sheet bridge (apps-script/Code.gs).

Usage:
  scripts/sheet.py list
  scripts/sheet.py append < rows.json   # rows.json: JSON array of
                                        # {country, url, company, match, status, title, added}

Reads endpoint + secret from sheet-config.json in the repo root.
Prints the bridge's JSON response to stdout; exits non-zero on transport
errors or an {"error": ...} response.
"""
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / "sheet-config.json"


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "append"):
        print(__doc__, file=sys.stderr)
        return 2
    if not CONFIG.exists():
        print(f"error: {CONFIG} missing — see SHEET-SETUP.md", file=sys.stderr)
        return 1
    cfg = json.loads(CONFIG.read_text())
    if not cfg.get("endpoint"):
        print("error: sheet-config.json has no endpoint — see SHEET-SETUP.md", file=sys.stderr)
        return 1

    payload = {"secret": cfg["secret"], "action": sys.argv[1]}
    if sys.argv[1] == "append":
        payload["rows"] = json.load(sys.stdin)

    req = urllib.request.Request(
        cfg["endpoint"],
        data=json.dumps(payload).encode(),
        # text/plain keeps Apps Script from mangling the body
        headers={"Content-Type": "text/plain"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # follows the 302 Apps Script issues
        body = resp.read().decode()
    print(body)
    try:
        if "error" in json.loads(body):
            return 1
    except json.JSONDecodeError:
        print("error: non-JSON response (is the deployment set to 'anyone with the link'?)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
