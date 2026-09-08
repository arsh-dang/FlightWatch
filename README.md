<img src="icon.svg" alt="" width="72" align="left" hspace="14" vspace="4">

# Flight tracker

**[Live dashboard →](https://arsh-dang.github.io/FlightWatch/)**

<br clear="left">

Tracks spontaneous short-notice trips. No fixed dates — every run checks
leaving today or tomorrow, coming back any day up to a few nights out, and
prices every workable combination. Twice a day it pushes your phone the moment
the cheapest combo drops under budget, with priority escalating the better the
deal.

Which flights get tracked is chosen **on the dashboard**: add or remove routes
in the picker, hit Apply, and submit the issue it opens for you. Each route is
priced and alerted on its own, and gets its own tab on the dashboard.

## Setup, about ten minutes

**1. Get a SerpApi key**

Sign up at serpapi.com. Copy the key from your dashboard.

Mind the quota. One route costs `(DEPART_AHEAD + 1) + (DEPART_AHEAD +
MAX_NIGHTS + 1)` searches per run — 6 at the defaults. Twice daily that is
**~360 searches a month, which overruns SerpApi's 250/month free tier**. To
stay inside it, drop to one run a day (~180), or set `MAX_NIGHTS=1` for 5 per
run. `SEARCH_BUDGET` caps each run so a long `ROUTES` list can't quietly burn
a month of credit in an afternoon.

**2. Set up push notifications**

Install the ntfy app (iOS or Android). Pick a topic name nobody would guess —
a long random string — and subscribe to it in the app. No account needed.

The topic name is effectively a password: anyone who knows it can read your
alerts *and* push notifications to your phone. Never commit it; keep it in
`.env` locally and in GitHub Actions secrets for CI.

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

## Choosing which flights to track

The dashboard is a static page, so it cannot write to the repo by itself.
Rather than putting a GitHub token in the browser, the picker hands the change
to GitHub and lets your own session authorise it:

1. Open **Tracked flights** on the dashboard, add or remove routes.
2. **Apply changes** opens a new issue, prefilled and labelled `set-routes`.
3. Submitting it runs [`set-routes.yml`](.github/workflows/set-routes.yml),
   which writes `routes.json`, closes the issue, and kicks off a check.

`routes.json` is the source of truth once it exists; `ROUTES` is the fallback,
then the `HOME_AIRPORT`/`AWAY_AIRPORT` pair.

Two guards, because the repo is public and anyone can file an issue:

- the workflow ignores issues not opened by the repo owner, so no one else can
  redirect what your API credit is spent on;
- `apply_routes.py` accepts only `ORIGIN-DEST` codes of three letters, capped
  at `MAX_ROUTES`, and fails the run on anything else rather than guessing.

## Dashboard

Every run appends its result to `history.json` and regenerates
`docs/index.html` — a static dashboard with the current cheapest fare, the
lowest ever seen, and a price trend chart across every logged run.

No build step and no CDN: the history is inlined as JSON and the chart is
drawn into an SVG at load, so the file opens straight from disk.

```bash
python3 build_dashboard.py && open docs/index.html
```

To serve it publicly, enable GitHub Pages on the `docs/` folder of the
default branch (Settings → Pages). Pages from a private repo needs a paid
plan; on a public repo it's free.

## Tuning

All of these have defaults baked into `spontaneous_watch.py` and can be
overridden by env var (locally via `.env`, not read from GitHub Actions
secrets unless you add them back into the workflow's `env:` block).

| Variable | Default | Does what |
|---|---|---|
| `ROUTES` | *(from HOME/AWAY)* | Fallback route list when `routes.json` is absent, e.g. `AVV-SYD,MEL-BNE` |
| `ROUTES_FILE` | `routes.json` | Routes chosen from the dashboard picker; takes precedence over `ROUTES` |
| `MAX_ROUTES` | `6` | Most routes the picker workflow will accept in one change |
| `SEARCH_BUDGET` | `12` | Hard cap on API searches per run. The run stops rather than overspending |
| `HOME_AIRPORT` | `AVV` | Departure airport, used when `ROUTES` is unset |
| `AWAY_AIRPORT` | `SYD` | Destination airport, used when `ROUTES` is unset |
| `TIMEZONE` | `Australia/Melbourne` | IANA timezone for "today"/departure cutoffs |
| `DEPART_AHEAD` | `1` | How many days ahead to consider leaving. 0 = today only |
| `MAX_NIGHTS` | `2` | Max nights away, counted from the departure day |
| `MIN_LEAD_HOURS` | `1` | Skip departures leaving sooner than this |
| `CHECKIN_CLOSES_MIN` | `40` | Minutes before departure that check-in/bag-drop closes |
| `DRIVE_MIN` | `25` | Drive time to the airport, used in urgency warnings |
| `STATE_FILE` | `state.json` | Where last-seen price/tier state is persisted |
| `HISTORY_FILE` | `history.json` | Append-only log of every run, powers the dashboard |
| `HISTORY_LIMIT` | `750` | Runs kept in the log (~1 year of twice-daily checks) |
| `DASHBOARD_FILE` | `docs/index.html` | Where the generated dashboard is written |

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
