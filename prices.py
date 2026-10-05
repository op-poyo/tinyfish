"""
PART 2: read each confirmed society's membership options and prices into societies.csv.

Why the Agent: the Join/price section is outside the main content block that Fetch returns,
so a real browser (the Agent) is needed. It only READS. It does not log in, join or pay.
No login needed yet. signed_up stays 'unknown' until Part 3.

  py prices.py --limit 1     # try ONE society first to see cost and behaviour
  py prices.py               # all confirmed societies
"""
import argparse, csv, datetime, os, re
from concurrent.futures import ThreadPoolExecutor
import tf

GOAL = (
    "This is a UCL Students' Union society page. Do NOT log in, join, or buy anything. "
    "Scroll to the 'Join' section of the page and read the membership types and their prices. "
    "Also note whether the page says membership is closed, full, or has a waiting list. "
    'Return JSON only, in exactly this shape: {"society": str, "options": [{"name": str, "price": str}], '
    '"closed_or_waitlist": bool, "notes": str}. '
    'Use the price text as shown (e.g. "£10.00" or "Free"). If there is no Join section, return options as [] and explain in notes.'
)


def price_value(p):
    m = re.search(r"\d+(?:\.\d+)?", p or "")
    return float(m.group()) if m else None


def summarise(result):
    """Turn the agent's JSON into CSV fields."""
    opts = result.get("options") if isinstance(result, dict) else None
    opts = opts if isinstance(opts, list) else []
    tiers, paid, free = [], [], ""
    for o in opts:
        if not isinstance(o, dict):
            continue
        name, price = str(o.get("name", "")).strip(), str(o.get("price", "")).strip()
        tiers.append(f"{name} {price}".strip())
        v = price_value(price)
        if "free" in price.lower() or v == 0:
            free = free or name
        elif v is not None:
            paid.append(v)
    closed = bool(result.get("closed_or_waitlist")) if isinstance(result, dict) else False
    status = "closed?" if closed else ("open" if tiers else "no options found")
    return {
        "tiers": "; ".join(tiers),
        "cheapest_paid": f"£{min(paid):.2f}" if paid else "",
        "free_option": free or ("no" if tiers else ""),
        "page_status": status,
        "notes": (result.get("notes", "") if isinstance(result, dict) else "")[:200],
    }


def work(row):
    name, url = row["your_name"], row["url"]
    base = {"society": name, "url": url, "live_view": ""}
    try:
        out = tf.agent(url, GOAL, on_live=lambda u: print(f"  [live view] {name}: {u}"))
        base["live_view"] = out.get("live_view") or ""
        if out["status"] == "COMPLETED" and isinstance(out["result"], dict):
            return {**base, **summarise(out["result"])}
        return {**base, "tiers": "", "cheapest_paid": "", "free_option": "",
                "page_status": f"agent {out['status']}", "notes": str(out["result"])[:200]}
    except Exception as e:
        return {**base, "tiers": "", "cheapest_paid": "", "free_option": "",
                "page_status": "error", "notes": str(e)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="only do the first N societies (to test)")
    a = ap.parse_args()

    with open("registry.csv", encoding="utf-8") as f:
        todo = [r for r in csv.DictReader(f) if r["status"] == "confirmed" and r["url"]]
    if a.limit:
        todo = todo[: a.limit]
    if not todo:
        raise SystemExit("No confirmed rows in registry.csv. Run resolve.py first.")

    prev = {}
    if os.path.exists("societies.csv"):
        with open("societies.csv", encoding="utf-8-sig") as f:
            prev = {r["society"]: r for r in csv.DictReader(f)}

    print(f"Agent reading {len(todo)} society page(s). This takes a minute or two each...\n")
    with ThreadPoolExecutor(max_workers=2) as ex:
        rows = list(ex.map(work, todo))

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for r in rows:
        r["signed_up"] = prev.get(r["society"], {}).get("signed_up", "unknown")
        r["checked_at"] = now
    # keep rows from earlier runs for societies we didn't re-read this time
    done = {r["society"] for r in rows}
    rows += [r for s, r in prev.items() if s not in done]

    cols = ["society", "signed_up", "tiers", "cheapest_paid", "free_option",
            "page_status", "notes", "url", "live_view", "checked_at"]
    with open("societies.csv", "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig so Excel shows £
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    print()
    for r in rows:
        if r["society"] in done:
            print(f"{r['society']}\n   options: {r['tiers'] or '-'}\n   status: {r['page_status']}   free option: {r['free_option'] or '-'}\n   {r['notes']}\n")
    print("Wrote societies.csv")


if __name__ == "__main__":
    main()
