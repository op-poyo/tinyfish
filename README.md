# SocietyBot

Give it a list of UCL Students' Union societies. It finds each society's page on the live web, reads the membership prices and upcoming events, saves everything to CSV, and builds a single-file HTML dashboard you can search, filter and sort.

Built for the TinyFish hackathon (TinyBounties).

## How TinyFish is used

| Endpoint | Used for |
|---|---|
| **Search** | `resolve.py` finds each society's own page (`<name> site:studentsunionucl.org`, with a second query as fallback) so we never have to crawl the directory, which is loaded by JavaScript |
| **Fetch** | Plumbing and debugging only (`check.py`, `diag.py`). The Join section and Events tab sit outside the main content block Fetch returns, so the main pipeline does not rely on it |
| **Agent** | Opens the real society page in a browser (streamed over SSE) to read the Join section (membership tiers, prices, closed or waitlist) and the Events tab. Each run exposes a `live_view` link, saved to the CSVs |

The Agent only **reads**. It never logs in, joins or pays.

## What it produces

- `registry.csv`: your rough society names matched to Students' Union page URLs (`your_name`, `status`, `matched_name`, `url`, `score`, `alternatives`)
- `societies.csv`: one row per society (membership tiers, cheapest paid price, free option, page status, notes, live view link, `signed_up`)
- `events.csv`: one row per upcoming event, sorted by date (date, ISO date, time, price, `free_status`, note, event link, `booked`, live view link)
- `dashboard.html`: a self-contained page with both tables embedded. Tabs for societies and events, text search, filter chips, click-to-sort columns, and light/dark theme. No server and no extra packages; double-click it, screenshot it, or commit it as evidence

Each run updates the CSVs and keeps earlier rows for societies it could not refresh. Marks such as `signed_up` and `booked` are preserved.

## Quick start (Windows PowerShell)

```powershell
py -m pip install requests
$env:TINYFISH_API_KEY="your_key_here"   # from agent.tinyfish.ai/api-keys

py check.py            # confirm the key and Search/Fetch work
py resolve.py          # societies.txt -> registry.csv
py prices.py --limit 1 # try ONE society first (the Agent costs credits)
py prices.py           # all confirmed societies -> societies.csv
py events.py --limit 1
py events.py           # all confirmed societies -> events.csv
py events.py --deep    # also open each event page to find its price (slower, costs more)
py dashboard.py --open # build dashboard.html and open it in your browser
```

Put one society per line in `societies.txt` (rough names are fine; lines starting with `#` are ignored).

`resolve.py` marks a match `confirmed` when the title similarity score is 0.90 or higher, `check` for anything lower, and `not_found` when Search returns no society page. Edit `registry.csv` by hand to fix `check` or `not_found` rows (set `status` to `confirmed`, or `skip` to ignore a row). Re-running keeps rows already marked `confirmed` or `skip`. `prices.py` and `events.py` only process `confirmed` rows.

The API key is read from the `TINYFISH_API_KEY` environment variable and is never stored in the repo. Keep any key file out of version control (see `.gitignore`).

## Files

| File | Purpose |
|---|---|
| `tf.py` | Small helper for TinyFish Search, Fetch and Agent calls. Errors are raised with the full server message; forces UTF-8 output so `£` prints on Windows |
| `check.py` | Tests Search and Fetch and prints the raw results |
| `resolve.py` | Matches `societies.txt` to society pages and writes `registry.csv` |
| `prices.py` | Agent reads each society's membership options and prices into `societies.csv` |
| `events.py` | Agent reads each society's events into `events.csv` |
| `dashboard.py` | Builds `dashboard.html` from the two CSVs (`--open` to launch it) |
| `diag.py` | Debugging helper: compares a known-good society page against your registry URLs in Fetch (markdown and HTML) to see why prices were not found |
| `societies.txt` | Your input list |

## Design notes

- **Free calls first.** Search is used to locate pages; the paid Agent is used only for content Search and Fetch cannot reach.
- **Read-only.** No login, no sign-ups, no payments.
- **CSV as saved state.** Re-runs update rows instead of starting over.
- **Low volume.** Two Agent runs at a time, and `--limit N` for cheap test runs.
- **Excel-friendly.** `societies.csv` and `events.csv` are written as UTF-8 with BOM so `£` displays correctly.
- **Derived fields.** `free_status` (`free`, `paid`, `unknown`) is worked out from the price text; `page_status` is `open`, `closed?`, `no options found`, or an agent/error state.

## Limitations

- Prices and event lists come from an Agent reading a web page, so results can occasionally be incomplete or mis-parsed. Check the `notes` and `page_status` columns.
- Agent text can come back with encoding artefacts (for example `Â£` in `tiers` and `notes`). `cheapest_paid` is rebuilt from the parsed number, so it is clean.
- Some society pages may use a different URL pattern (the site now has a "Groups A-Z" menu), and `events.py` assumes `<society page>/events`.
- Event prices are often not shown in the list, so `free_status` is frequently `unknown` unless you run `events.py --deep`.
- Dates are only parsed into `date_iso` when shown as `dd/mm/yyyy`; others are kept as text and sort last.
- `signed_up` stays `unknown` and `booked` stays empty until the login features below exist.

## Planned, not built

- Saved login profile (the `use_profile` option already exists in `tf.agent`), to see which societies you are already in
- Joining free societies and booking free events (dry run first, behind a flag, with a cap per run)
- Daily refresh, Monitor alerts for closed societies, and a weekly report page
