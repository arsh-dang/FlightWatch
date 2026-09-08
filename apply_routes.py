"""
Turns a "set routes" issue body into routes.json and flights.json.

The body is written by the dashboard's picker, but it arrives as text a human
could have edited, so nothing is trusted: only well-formed route pairs and
flight numbers survive, both capped, and anything else fails the run rather
than being guessed at.

Expected inside a fenced block:

    routes: AVV-SYD,MEL-BNE
    flights: JQ 610,QF 802

An empty or absent `flights` line means "whatever is cheapest".
"""

import json
import os
import re
from pathlib import Path

ROUTES_FILE = Path(os.environ.get("ROUTES_FILE", "routes.json"))
FLIGHTS_FILE = Path(os.environ.get("FLIGHTS_FILE", "flights.json"))
MAX_ROUTES = int(os.environ.get("MAX_ROUTES") or "6")
MAX_FLIGHTS = int(os.environ.get("MAX_FLIGHTS") or "40")

PAIR = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")
FLIGHT = re.compile(r"^([A-Z][A-Z0-9]|[A-Z0-9][A-Z]|[A-Z]{3})\s?(\d{1,4})$")


def fail(message):
    raise SystemExit(f"::error::{message}")


def fields(body):
    fenced = re.search(r"```(.*?)```", body, re.S)
    raw = fenced.group(1) if fenced else body

    found = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        name = name.strip().lower()
        if name in ("routes", "flights"):
            found[name] = value
    return found


def parse_routes(value):
    routes = []
    for chunk in value.split(","):
        token = chunk.strip().upper()
        if not token:
            continue
        if not PAIR.match(token):
            fail(f"{token!r} is not an ORIGIN-DEST pair")
        origin, dest = token.split("-")
        if origin == dest:
            fail(f"{token} goes nowhere")
        if token not in routes:
            routes.append(token)

    if not routes:
        fail("no routes found in the issue body")
    if len(routes) > MAX_ROUTES:
        fail(f"{len(routes)} routes exceeds MAX_ROUTES={MAX_ROUTES}; "
             "each one costs API credit every run")
    return routes


def parse_flights(value):
    flights = []
    for chunk in value.split(","):
        token = " ".join(chunk.split()).upper()
        if not token:
            continue
        match = FLIGHT.match(token)
        if not match:
            fail(f"{token!r} is not a flight number like 'JQ 610'")
        normalised = f"{match.group(1)} {match.group(2)}"
        if normalised not in flights:
            flights.append(normalised)

    if len(flights) > MAX_FLIGHTS:
        fail(f"{len(flights)} flights exceeds MAX_FLIGHTS={MAX_FLIGHTS}")
    return flights


def main():
    found = fields(os.environ.get("ISSUE_BODY") or "")
    if "routes" not in found:
        fail("issue body has no 'routes:' line")

    routes = parse_routes(found["routes"])
    flights = parse_flights(found.get("flights", ""))

    ROUTES_FILE.write_text(json.dumps({"routes": routes}, indent=2) + "\n")
    FLIGHTS_FILE.write_text(json.dumps({"flights": flights}, indent=2) + "\n")

    summary = ",".join(routes)
    if flights:
        summary += f" ({len(flights)} picked flights)"
    print(f"tracking {summary}")
    if out := os.environ.get("GITHUB_OUTPUT"):
        with open(out, "a") as fh:
            fh.write(f"routes={summary}\n")


if __name__ == "__main__":
    main()
