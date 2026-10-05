"""Diagnose why prices.py found nothing: compare a known-good page with your registry URLs."""
import csv, re
import tf

KNOWN_GOOD = "https://studentsunionucl.org/clubs-societies/photography-society"

with open("registry.csv", encoding="utf-8") as f:
    rows = [r for r in csv.DictReader(f)]
print("URLs in registry.csv:")
for r in rows:
    print(f"  {r['your_name']:<32}{r['status']:<11}{r['url']}")


def probe(label, url, fmt="markdown"):
    print(f"\n=== {label}: {url}  (format={fmt}) ===")
    try:
        d = tf.fetch([url], fmt)
    except Exception as e:
        print("FETCH ERROR:", e); return
    if isinstance(d, dict):
        print("errors field:", str(d.get("errors"))[:300])
    t = tf.page_text(d).replace("\\n", "\n")
    print("text length:", len(t))
    print("contains '£':", "£" in t, "| 'Join' count:", len(re.findall(r"join", t, re.I)),
          "| 'membership' count:", len(re.findall(r"membership", t, re.I)))
    print("--- last 500 chars ---")
    print(t[-500:])


probe("KNOWN GOOD", KNOWN_GOOD)
probe("KNOWN GOOD (html)", KNOWN_GOOD, "html")
if rows and rows[0]["url"]:
    probe("YOUR FIRST REGISTRY URL", rows[0]["url"])
