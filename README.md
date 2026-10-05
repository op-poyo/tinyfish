# SocietyBot

Give it a list of UCL Students' Union societies. It finds each society's page on the live web, reads the membership prices and upcoming events, and saves everything to CSV files.

Built for the TinyFish hackathon (TinyBounties).

## How TinyFish is used

| Endpoint | Used for |
|---|---|
| **Search** | Finds each society's own page (`<name> site:studentsunionucl.org`) so we never have to crawl the directory, which is loaded by JavaScript |
| **Fetch** | Plumbing check and page reads (`check.py`, `tf.py`) |
| **Agent** | Opens the real society page in a browser to read the Join section (prices, closed or waitlist) and the Events tab, which Fetch does not return |

The Agent only **reads**. It never logs in, joins or pays.

## What it produces

- `registry.csv`: your rough society names matched to confirmed Students' Union page URLs
- `societies.csv`: one row per society (membership tiers, cheapest paid price, free option, open or closed)
- `events.csv`: one row per upcoming event (date, time, price, free or paid, event link)

Each run updates the CSVs and keeps earlier rows for societies it could not refresh. Marks such as `signed_up` and `booked` are preserved.

## Quick start (Windows PowerShell)

```powershell
py -m pip install requests
$env:TINYFISH_API_KEY="your_key_here"   # from agent.tinyfish.ai/api-keys

py check.py            # confirm the key and endpoints work
py resolve.py          # societies.txt -> registry.csv
py prices.py --limit 1 # try ONE society first (the Agent costs credits)
py prices.py           # all confirmed societies -> societies.csv
py events.py --limit 1
py events.py           # all confirmed societies -> events.csv
py events.py --deep    # also open each event page to find its price (slower, costs more)
```

Put one society per line in `societies.txt` (rough names are fine). Edit `registry.csv` by hand to fix any `check` or `not_found` rows. Re-running keeps rows already marked `confirmed` or `skip`.

The API key is read from the environment and is never stored in the repo.

## Files

| File | Purpose |
|---|---|
| `tf.py` | Small helper for TinyFish Search, Fetch and Agent calls; errors print in full |
| `check.py` | Tests Search and Fetch and prints the raw results |
| `resolve.py` | Matches `societies.txt` to society pages and writes `registry.csv` |
| `prices.py` | Agent reads each society's membership options and prices into `societies.csv` |
| `events.py` | Agent reads each society's events into `events.csv` |
| `diag.py` | Debugging helper |

## Design notes

- **Free calls first.** Search and Fetch are used where they work; the paid Agent is used only for content they cannot reach.
- **Read-only.** No login, no sign-ups, no payments.
- **CSV as saved state.** Re-runs update rows instead of starting over.
- **Low volume.** Two Agent runs at a time, and `--limit N` for cheap test runs.

## Limitations

- Prices and event lists come from an Agent reading a web page, so results can occasionally be incomplete or mis-parsed. Check the `notes` and `page_status` columns.
- Some society pages may use a different URL pattern (the site now has a "Groups A-Z" menu), and `events.py` assumes `<society page>/events`.
- Dates are only parsed when shown as `dd/mm/yyyy`; others are kept as text.

## Planned, not built

- Saved login profile, to see which societies you are already in
- Joining free societies and booking free events (dry run first, behind a flag, with a cap per run)
- Daily refresh, Monitor alerts for closed societies, and a weekly report page
