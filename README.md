# AVV to SYD fare watch

Rolling watch for a spontaneous Avalon (AVV) to Sydney (SYD) trip. No fixed
dates — every run checks leaving today or tomorrow, coming back any day up
to a few nights out, and prices every workable combination. Twice a day it
pushes your phone the moment the cheapest combo drops under budget, with
priority escalating the better the deal.

## Setup, about ten minutes

**1. Get a SerpApi key**

Sign up at serpapi.com. The free plan covers 250 searches a month; this uses
4 searches per run, twice daily (~240/month). Copy the key from your
dashboard.

**2. Set up push notifications**

Install the ntfy app (iOS or Android). Pick a topic name nobody would guess,
something like `arsh-avv-syd-8823`, and subscribe to it in the app. No account
needed. Anyone who knows the topic name can read it, so make it random.

**3. Put it on GitHub**

```bash
git init
git add .
git commit -m "flight watch"
gh repo create flight-watch --private --source=. --push
```

**4. Add your secrets**

In the repo: Settings, then Secrets and variables, then Actions.

- `SERPAPI_KEY` — your key
- `NTFY_TOPIC` — your topic name

These are the only two secrets the workflow reads. Everything else below is
tuned by editing `spontaneous_watch.py` defaults directly, or exported as
env vars if you run it locally.

**Optional: local .env file**

If you want to run `spontaneous_watch.py` locally, copy `.env.example` to a
file named `.env` and fill in your values. Do not commit your `.env` file to
the repository.

```bash
cp .env.example .env
# edit .env and add your keys
```

**5. Test it**

Actions tab, pick "Flight watch", then "Run workflow". Check the log output and
confirm the push lands on your phone.

## Tuning

All of these have defaults baked into `spontaneous_watch.py` and can be
overridden by env var (locally via `.env`, not read from GitHub Actions
secrets unless you add them back into the workflow's `env:` block).

| Variable | Default | Does what |
|---|---|---|
| `HOME_AIRPORT` | `AVV` | Departure airport code |
| `AWAY_AIRPORT` | `SYD` | Destination airport code |
| `TIMEZONE` | `Australia/Melbourne` | IANA timezone for "today"/departure cutoffs |
| `DEPART_AHEAD` | `1` | How many days ahead to consider leaving. 0 = today only |
| `MAX_NIGHTS` | `2` | Max nights away, counted from the departure day |
| `MIN_LEAD_HOURS` | `1` | Skip departures leaving sooner than this |
| `CHECKIN_CLOSES_MIN` | `40` | Minutes before departure that check-in/bag-drop closes |
| `DRIVE_MIN` | `25` | Drive time to the airport, used in urgency warnings |
| `STATE_FILE` | `state.json` | Where last-seen price/tier state is persisted |

Alert tiers (in `spontaneous_watch.py`, `TIERS`): under $200 normal push,
under $150 high priority, under $100 max priority (bypasses phone quiet
hours).

## How the alerts behave

You get a push the first time the cheapest workable trip falls under a tier
threshold, then again only if it falls further within that tier. Prices
above $200 stay quiet. `state.json` holds the last-seen price per tier and
gets committed back to the repo after each run.

## Cost

Free. GitHub Actions gives private repos 2,000 minutes a month and this uses
maybe 30 seconds a run. SerpApi's free tier covers the searches.
