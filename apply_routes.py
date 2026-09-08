"""
Turns a "set routes" issue body into routes.json.

The body is written by the dashboard's picker, but it arrives as text a human
could have edited, so nothing is trusted: only ORIGIN-DEST pairs of three
letters survive, capped in count, and anything else fails the run rather than
being guessed at.
"""

import json
import os
import re
import sys
from pathlib import Path

ROUTES_FILE = Path(os.environ.get("ROUTES_FILE", "routes.json"))
MAX_ROUTES = int(os.environ.get("MAX_ROUTES") or "6")

PAIR = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")


def parse(body):
    fenced = re.search(r"```(.*?)```", body, re.S)
    raw = fenced.group(1) if fenced else body

    routes = []
    for chunk in raw.replace("\n", ",").split(","):
        token = chunk.strip().upper()
        if not token:
            continue
        if not PAIR.match(token):
            raise SystemExit(f"::error::{token!r} is not an ORIGIN-DEST pair")
        origin, dest = token.split("-")
        if origin == dest:
            raise SystemExit(f"::error::{token} goes nowhere")
        if token not in routes:
            routes.append(token)

    if not routes:
        raise SystemExit("::error::no routes found in the issue body")
    if len(routes) > MAX_ROUTES:
        raise SystemExit(
            f"::error::{len(routes)} routes exceeds MAX_ROUTES={MAX_ROUTES}; "
            "each one costs API credit every run"
        )
    return routes


def main():
    routes = parse(os.environ.get("ISSUE_BODY") or "")
    ROUTES_FILE.write_text(json.dumps({"routes": routes}, indent=2) + "\n")

    joined = ",".join(routes)
    print(f"tracking {joined}")
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as fh:
            fh.write(f"routes={joined}\n")


if __name__ == "__main__":
    main()
