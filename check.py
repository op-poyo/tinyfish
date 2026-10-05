"""PART 0: does TinyFish work from your machine? Prints raw results so we can fix anything odd."""
import json, re
import tf

print("=== 1. SEARCH ===")
try:
    d = tf.search("UCL Students Union Photography Society")
    res = d.get("results", []) if isinstance(d, dict) else []
    print(f"OK, {len(res)} results. Top 3:")
    for x in res[:3]:
        print("  -", x.get("title"), "|", x.get("url"))
    if not res:
        print("Raw response:", json.dumps(d)[:600])
except Exception as e:
    print("FAILED:", e)

print("\n=== 2. FETCH (societies directory, page 1) ===")
try:
    d = tf.fetch(["https://studentsunionucl.org/clubs-societies"])
    print("Response top-level keys:", list(d.keys()) if isinstance(d, dict) else type(d))
    text = tf.page_text(d)
    print("Text length:", len(text))
    links = set(re.findall(r"/clubs-societies/([A-Za-z0-9\-_%]+)", text))
    print(f"Society links found in the response: {len(links)}")
    print("Sample:", sorted(links)[:8])
    print("\nFirst 400 characters of the page text:\n", text[:400])
except Exception as e:
    print("FAILED:", e)
