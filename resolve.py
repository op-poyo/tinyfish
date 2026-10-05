"""
PART 1: turn your rough society names into confirmed Students' Union page URLs.

For each line of societies.txt, use TinyFish Search (free) to find its page on the SU site,
score how well the page title matches, and write registry.csv.
You then fix any 'check' rows by hand. Re-running keeps rows you already confirmed or skipped.
"""
import csv, os, re, difflib
from urllib.parse import urlparse
import tf

STOP = {"society", "soc", "club", "ucl", "the", "of", "and", "for", "students", "union"}
SKIP_SLUGS = {"directory", "page", ""}


def slug_of(url):
    u = urlparse(url)
    if "studentsunionucl.org" not in u.netloc:
        return None
    path = u.path.replace("/index.php", "")
    m = re.fullmatch(r"/clubs-societies/([^/]+)/?", path)
    if not m or m.group(1) in SKIP_SLUGS:
        return None
    return m.group(1)


def clean_title(t):
    return re.sub(r"\s*[-|–]\s*Students'? ?Union.*$", "", t or "", flags=re.I).strip()


def norm(s):
    return " ".join(t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP)


def sim(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    return 1.0 if na == nb else difflib.SequenceMatcher(None, na, nb).ratio()


def candidates(want):
    """Search for the society; return [(score, name, url)] for SU society pages only."""
    seen, out = set(), []
    for q in (f"{want} site:studentsunionucl.org", f"{want} UCL Students' Union society"):
        data = tf.search(q)
        for x in (data.get("results", []) if isinstance(data, dict) else []):
            url = (x.get("url") or "").split("?")[0].split("#")[0]
            slug = slug_of(url)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            name = clean_title(x.get("title", "")) or slug.replace("-", " ").title()
            score = max(sim(want, name), sim(want, slug.replace("-", " ")))
            out.append((score, name, f"https://studentsunionucl.org/clubs-societies/{slug}"))
        if out:
            break
    out.sort(reverse=True)
    return out


def main():
    kept = {}
    if os.path.exists("registry.csv"):
        with open("registry.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["status"] in ("confirmed", "skip"):
                    kept[row["your_name"]] = row

    wanted = [l.strip() for l in open("societies.txt", encoding="utf-8")
              if l.strip() and not l.startswith("#")]
    rows = []
    print(f"Resolving {len(wanted)} societies via Search...\n")
    print(f"{'YOUR NAME':<30}{'STATUS':<11}{'MATCHED TO':<38}SCORE")
    for want in wanted:
        if want in kept:
            row = kept[want]
        else:
            try:
                top = candidates(want)
            except Exception as e:
                top = []
                print("  search error:", e)
            if not top:
                row = {"your_name": want, "status": "not_found", "matched_name": "",
                       "url": "", "score": "0.00", "alternatives": ""}
            else:
                s, name, url = top[0]
                alts = " | ".join(f"{n} ({u})" for _, n, u in top[1:3])
                row = {"your_name": want, "status": "confirmed" if s >= 0.9 else "check",
                       "matched_name": name, "url": url, "score": f"{s:.2f}", "alternatives": alts}
        rows.append(row)
        print(f"{row['your_name']:<30}{row['status']:<11}{row['matched_name']:<38}{row['score']}")

    cols = ["your_name", "status", "matched_name", "url", "score", "alternatives"]
    with open("registry.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader(); w.writerows(rows)
    n = sum(r["status"] in ("check", "not_found") for r in rows)
    print(f"\nWrote registry.csv. {n} row(s) need attention." if n else "\nWrote registry.csv. All matched.")


if __name__ == "__main__":
    main()
