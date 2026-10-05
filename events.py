"""
PART 5: read each confirmed society's events into events.csv. No login needed.

The Agent opens the society's Events tab and reads the list. It only READS: it does not log in,
book, or buy anything.

  py events.py --limit 1     # try ONE society first
  py events.py               # all confirmed societies
  py events.py --deep        # also open each event page to find its price (slower, costs more)
"""
import argparse, csv, datetime, os, re
from concurrent.futures import ThreadPoolExecutor
import tf

BASE_GOAL = (
    "This is the Events page of a UCL Students' Union society. Do NOT log in, book, or buy anything. "
    "List every upcoming event shown. For each event give: its name, its date, its start time, "
    "its price exactly as shown (e.g. \"Free\" or \"£5.00\"; empty string if the list does not show a price), "
    "any note about booking requirements (for example needing a membership first), and the link to the event page. "
)
SHALLOW = ('Do not open individual event pages. ')
DEEP = ('If the price is not shown in the list, open that event\'s page to find it (at most 10 events). ')
SHAPE = ('Return JSON only, exactly: {"events": [{"name": str, "date": str, "time": str, "price": str, '
         '"note": str, "url": str}]}. If there are no upcoming events, return {"events": []}.')


def iso(date_str):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str or "")
    if not m:
        return ""
    d, mo, y = map(int, m.groups())
    try:
        return datetime.date(y, mo, d).isoformat()
    except ValueError:
        return ""


def free_status(price, note):
    p = (price or "").lower()
    if "free" in p or re.fullmatch(r"£?\s*0(\.0+)?", p.strip() or "x"):
        return "free"
    if "£" in p:
        return "paid"
    return "unknown"


def work(args):
    row, deep = args
    name, base = row["your_name"], row["url"].rstrip("/")
    goal = BASE_GOAL + (DEEP if deep else SHALLOW) + SHAPE
    try:
        out = tf.agent(base + "/events", goal, on_live=lambda u: print(f"  [live view] {name}: {u}"))
    except Exception as e:
        return name, [], f"error: {str(e)[:150]}"
    if out["status"] != "COMPLETED" or not isinstance(out["result"], dict):
        return name, [], f"agent {out['status']}: {str(out['result'])[:150]}"
    evs = out["result"].get("events")
    if not isinstance(evs, list):
        return name, [], "no events list in result"
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for e in evs:
        if not isinstance(e, dict):
            continue
        date, time_ = str(e.get("date", "")), str(e.get("time", ""))
        if not time_ and "|" in date:
            date, time_ = [s.strip() for s in date.split("|", 1)]
        price, note = str(e.get("price", "")), str(e.get("note", ""))
        rows.append({
            "society": name, "event": str(e.get("name", "")).strip(), "date": date.strip(),
            "date_iso": iso(date), "time": time_.strip(), "price": price,
            "free_status": free_status(price, note), "note": note[:200],
            "event_url": str(e.get("url", "")), "booked": "",
            "society_url": base, "live_view": out.get("live_view") or "", "checked_at": now,
        })
    return name, rows, f"{len(rows)} event(s)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only the first N societies (to test)")
    ap.add_argument("--deep", action="store_true", help="open each event page to find prices")
    a = ap.parse_args()

    with open("registry.csv", encoding="utf-8") as f:
        todo = [r for r in csv.DictReader(f) if r["status"] == "confirmed" and r["url"]]
    if a.limit:
        todo = todo[: a.limit]
    if not todo:
        raise SystemExit("No confirmed rows in registry.csv. Run resolve.py first.")

    prev = []
    if os.path.exists("events.csv"):
        with open("events.csv", encoding="utf-8-sig") as f:
            prev = list(csv.DictReader(f))

    print(f"Agent reading events for {len(todo)} society page(s)...\n")
    with ThreadPoolExecutor(max_workers=2) as ex:
        results = list(ex.map(work, [(r, a.deep) for r in todo]))

    refreshed = {name for name, _, msg in results if not msg.startswith(("error", "agent", "no events list"))}
    # keep 'booked' marks from earlier runs, and keep old rows for societies we couldn't refresh
    booked = {(p["society"], p["event"], p["date"]): p.get("booked", "") for p in prev}
    new_rows = []
    for name, rows, msg in results:
        print(f"{name}: {msg}")
        for r in rows:
            r["booked"] = booked.get((r["society"], r["event"], r["date"]), "")
            new_rows.append(r)
    all_rows = new_rows + [p for p in prev if p["society"] not in refreshed]
    all_rows.sort(key=lambda r: (r.get("date_iso") or "9999", r.get("time", "")))

    cols = ["society", "event", "date", "date_iso", "time", "price", "free_status", "note",
            "event_url", "booked", "society_url", "live_view", "checked_at"]
    with open("events.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(all_rows)

    print(f"\n{'DATE':<12}{'TIME':<14}{'PRICE':<10}{'SOCIETY':<28}EVENT")
    for r in all_rows:
        print(f"{(r['date_iso'] or r['date']):<12}{r['time'][:13]:<14}{(r['price'] or r['free_status'])[:9]:<10}{r['society'][:27]:<28}{r['event'][:50]}")
    free = sum(r["free_status"] == "free" for r in all_rows)
    print(f"\nWrote events.csv: {len(all_rows)} event(s), {free} marked free.")


if __name__ == "__main__":
    main()
