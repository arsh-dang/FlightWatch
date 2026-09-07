# AVV to SYD fare watch

Polls Google Flights twice a day for Avalon to Sydney round trips across four
date combinations, and pushes your phone the moment the total drops under $200.

## Setup, about ten minutes

**1. Get a SerpApi key**

Sign up at serpapi.com. The free plan covers 250 searches a month; this uses
about 240 at four date pairs twice daily. Copy the key from your dashboard.

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

**5. Set your dates**

Edit `OUT_DATE` and `BACK_DATE` in `.github/workflows/flight-watch.yml`.

**6. Test it**

Actions tab, pick "Flight watch", then "Run workflow". Check the log output and
confirm the push lands on your phone.

## Tuning

| Variable | Does what |
|---|---|
| `FLEX_DAYS` | How many days after each target to also check. 1 gives four combinations, 2 gives nine and triples your API usage. |
| `BUDGET` | The alert threshold in dollars. |
| `NONSTOP_ONLY` | Set to `false` to include connections. |

## How the alerts behave

You get an urgent push the first time the total falls under budget, then again
only if it falls further. Prices above budget stay quiet unless they set a new
all-time low, so you can see the trend without being spammed.

`state.json` holds the lowest price seen and gets committed back after each run.

## Cost

Free. GitHub Actions gives private repos 2,000 minutes a month and this uses
maybe 30 seconds a run. SerpApi's free tier covers the searches.
