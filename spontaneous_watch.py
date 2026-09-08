"""
Rolling watch for a spontaneous Avalon -> Sydney trip.

No fixed dates. Every run it looks at leaving today or tomorrow, coming back
any day up to a few days out, and prices every workable combination.

Alerts escalate by how good the deal is:
    under $200   normal push
    under $150   high priority
    under $100   max priority, bypasses your phone's quiet hours

Costs 4 API searches per run instead of 6, because one-way legs get priced
once each and then combined. Jetstar prices one-ways independently, so the
sum is the real round-trip cost.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------- config

HOME = os.environ.get("HOME_AIRPORT") or "AVV"
AWAY = os.environ.get("AWAY_AIRPORT") or "SYD"
_tz_env = (os.environ.get("TIMEZONE") or "").strip()
if _tz_env:
    TZ = ZoneInfo(_tz_env)
else:
    TZ = ZoneInfo("Australia/Melbourne")

# How far ahead to consider leaving. 0 = today only, 1 = today or tomorrow.
DEPART_AHEAD = int(os.environ.get("DEPART_AHEAD") or "1")
# How many nights away you'd accept, counted from the departure day.
MAX_NIGHTS = int(os.environ.get("MAX_NIGHTS") or "2")
# Skip departures leaving sooner than this.
MIN_LEAD_HOURS = float(os.environ.get("MIN_LEAD_HOURS", "1"))

# Jetstar domestic: online check-in and bag drop both shut 40 minutes before
# departure, gate shuts at 20. Miss the first one and the fare is gone.
CHECKIN_CLOSES_MIN = int(os.environ.get("CHECKIN_CLOSES_MIN", "40"))
# Door to Avalon terminal, from Geelong.
DRIVE_MIN = int(os.environ.get("DRIVE_MIN", "25"))

TIERS = [
    (100.0, "max", "rotating_light", "Drop everything"),
    (150.0, "high", "fire", "Very good"),
    (200.0, "default", "airplane", "Under budget"),
]

SERPAPI_KEY = os.environ["SERPAPI_KEY"]
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
HISTORY_FILE = Path(os.environ.get("HISTORY_FILE", "history.json"))
# Roughly a year of twice-daily runs. Keeps the dashboard payload small.
HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT") or "750")


# ---------------------------------------------------------------- helpers

def today():
    return datetime.now(TZ).date()


def now():
    return datetime.now(TZ)


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def tier_for(total):
    """Returns (threshold, priority, tag, headline) or None if over budget."""
    for tier in TIERS:
        if total <= tier[0]:
            return tier
    return None


# ---------------------------------------------------------------- fetching

def one_way(origin, destination, day):
    """Cheapest nonstop one-way on a given day. Returns a list of options."""
    params = {
        "engine": "google_flights",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": day.isoformat(),
        "type": "2",          # one way
        "stops": "1",         # nonstop
        "currency": "AUD",
        "hl": "en",
        "gl": "au",
        "api_key": SERPAPI_KEY,
    }
    try:
        r = requests.get("https://serpapi.com/search", params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"  {origin}->{destination} {day}: request failed, {e}", file=sys.stderr)
        return []

    if "error" in data:
        print(f"  {origin}->{destination} {day}: {data['error']}", file=sys.stderr)
        return []

    out = []
    for opt in (data.get("best_flights") or []) + (data.get("other_flights") or []):
        price = opt.get("price")
        legs = opt.get("flights") or []
        if not isinstance(price, (int, float)) or not legs:
            continue
        leg = legs[0]
        dep_raw = (leg.get("departure_airport") or {}).get("time", "")
        dep_dt = None
        if dep_raw:
            try:
                dep_dt = datetime.strptime(dep_raw, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            except ValueError:
                pass
        out.append({
            "day": day,
            "price": float(price),
            "airline": leg.get("airline", "?"),
            "flight_no": leg.get("flight_number", ""),
            "departs": dep_dt,
            "departs_text": dep_raw.split(" ")[-1] if dep_raw else "",
        })
    return out


def bookable(option):
    """Drop flights leaving too soon to actually get on."""
    if option["departs"] is None:
        return True
    return option["departs"] >= now() + timedelta(hours=MIN_LEAD_HOURS)


def cheapest(options):
    usable = [o for o in options if bookable(o)]
    return min(usable, key=lambda o: o["price"]) if usable else None


# ---------------------------------------------------------------- notifying

def push(title, body, priority, tag):
    if not NTFY_TOPIC:
        print(f"(no NTFY_TOPIC set)\n{title}\n{body}")
        return
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": tag,
        "Click": "https://www.jetstar.com/au/en/home",
    }
    if priority == "max":
        # Cuts through Do Not Disturb on both iOS and Android.
        headers["Tags"] = tag + ",bangbang"
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers=headers,
            timeout=20,
        )
        print(f"pushed: {title}")
    except requests.RequestException as e:
        print(f"push failed: {e}", file=sys.stderr)


def urgency(out_leg):
    """How long is left to book, check in and drive. Empty if there's no rush."""
    if out_leg["departs"] is None:
        return ""

    minutes_out = (out_leg["departs"] - now()).total_seconds() / 60
    if minutes_out > 240:
        return ""

    # You must hold a boarding pass before online check-in shuts.
    to_checkin = int(minutes_out - CHECKIN_CLOSES_MIN)
    # And you must physically be there before the same deadline.
    to_leave_home = int(minutes_out - CHECKIN_CLOSES_MIN - DRIVE_MIN)

    lines = [f"Book and check in within {to_checkin} min"]
    if to_leave_home > 0:
        lines.append(f"Leave Geelong within {to_leave_home} min")
    else:
        lines.append("Check in online first, then drive")
    lines.append("Carry-on only, bag drop is already too tight")
    return "\n" + "\n".join(lines)


def format_trip(trip):
    out, back = trip["out"], trip["back"]
    nights = (back["day"] - out["day"]).days
    stay = "same day" if nights == 0 else f"{nights} night" + ("s" if nights > 1 else "")
    return (
        f"Out {out['day'].strftime('%a %d %b')} {out['departs_text']}  ${out['price']:.0f}\n"
        f"Back {back['day'].strftime('%a %d %b')} {back['departs_text']}  ${back['price']:.0f}\n"
        f"{stay} in Sydney"
        + urgency(out)
    )


# ---------------------------------------------------------------- main

def main():
    state = load_state()
    start = today()

    depart_days = [start + timedelta(days=i) for i in range(DEPART_AHEAD + 1)]
    return_days = [start + timedelta(days=i) for i in range(DEPART_AHEAD + MAX_NIGHTS + 1)]

    print(f"leaving {depart_days[0]} through {depart_days[-1]}, "
          f"back by {return_days[-1]}\n")

    outbound = {}
    for day in depart_days:
        best = cheapest(one_way(HOME, AWAY, day))
        if best:
            outbound[day] = best
            print(f"{HOME}->{AWAY} {day}: ${best['price']:.0f} at {best['departs_text']}")

    inbound = {}
    for day in return_days:
        best = cheapest(one_way(AWAY, HOME, day))
        if best:
            inbound[day] = best
            print(f"{AWAY}->{HOME} {day}: ${best['price']:.0f} at {best['departs_text']}")

    trips = []
    for out_day, out_leg in outbound.items():
        for back_day, back_leg in inbound.items():
            nights = (back_day - out_day).days
            if nights < 0 or nights > MAX_NIGHTS:
                continue
            if nights == 0 and out_leg["departs"] and back_leg["departs"]:
                # A same-day return has to actually leave after you land.
                if back_leg["departs"] <= out_leg["departs"] + timedelta(hours=3):
                    continue
            trips.append({
                "out": out_leg,
                "back": back_leg,
                "total": out_leg["price"] + back_leg["price"],
            })

    if not trips:
        print("\nno workable combinations right now")
        record_history(None)
        return

    trips.sort(key=lambda t: t["total"])
    best = trips[0]
    record_history(best)
    print(f"\ncheapest workable trip: ${best['total']:.0f}")

    tier = tier_for(best["total"])
    if not tier:
        print(f"nothing under ${TIERS[-1][0]:.0f}")
        save(state, best["total"])
        return

    threshold, priority, tag, headline = tier
    key = f"tier_{int(threshold)}"
    previous = state.get(key)
    stale = state.get("date") != str(start)

    if previous is not None and best["total"] >= previous and not stale:
        print(f"already alerted at ${previous:.0f} in this tier")
        save(state, best["total"])
        return

    body = format_trip(best)
    runners_up = [t for t in trips[1:3] if t["total"] <= TIERS[-1][0]]
    if runners_up:
        body += "\n\nOther options:\n" + "\n".join(
            f"${t['total']:.0f}  {t['out']['day'].strftime('%a')} to "
            f"{t['back']['day'].strftime('%a')}" for t in runners_up
        )

    push(f"{headline}: ${best['total']:.0f} to see her", body, priority, tag)
    state[key] = best["total"]
    save(state, best["total"])


def save(state, best_total):
    state["date"] = str(today())
    state["last_seen"] = best_total
    state["checked_at"] = now().strftime("%Y-%m-%d %H:%M")
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def record_history(trip):
    """Append this run's result so the dashboard can chart the trend."""
    try:
        entries = json.loads(HISTORY_FILE.read_text())
        if not isinstance(entries, list):
            entries = []
    except (OSError, json.JSONDecodeError):
        entries = []

    entry = {"checked_at": now().strftime("%Y-%m-%d %H:%M"), "route": f"{HOME}-{AWAY}"}
    if trip:
        out, back = trip["out"], trip["back"]
        entry.update({
            "total": trip["total"],
            "out_day": out["day"].isoformat(),
            "out_time": out["departs_text"],
            "out_price": out["price"],
            "out_airline": out["airline"],
            "back_day": back["day"].isoformat(),
            "back_time": back["departs_text"],
            "back_price": back["price"],
            "back_airline": back["airline"],
            "nights": (back["day"] - out["day"]).days,
        })
    else:
        entry["total"] = None

    entries.append(entry)
    HISTORY_FILE.write_text(
        json.dumps(entries[-HISTORY_LIMIT:], indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
