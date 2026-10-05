"""Build dashboard.html from societies.csv and events.csv.

Usage:
    py dashboard.py          # writes dashboard.html
    py dashboard.py --open   # ...and opens it in your browser

No extra packages needed. The page is one self-contained file (data embedded),
so you can double-click it, screenshot it, or commit it as evidence.
"""
import csv
import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent


def load(name):
    p = HERE / name
    if not p.exists():
        return {"cols": [], "rows": []}
    with open(p, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return {"cols": reader.fieldnames or [], "rows": rows}


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SocietyBot dashboard</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#1b1f2a;--mute:#667085;--line:#e4e7ee;--accent:#4f46e5;--accent-soft:#eceafd}
@media (prefers-color-scheme:dark){:root{--bg:#12141b;--card:#1b1e28;--ink:#e8eaf1;--mute:#9aa3b5;--line:#2a2e3b;--accent:#8b85ff;--accent-soft:#272a46}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1280px;margin:0 auto;padding:28px 20px 60px}
h1{margin:0;font-size:26px}
.sub{color:var(--mute);margin:4px 0 22px}
.tabs{display:flex;gap:8px;margin-bottom:16px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 16px;border-radius:999px;cursor:pointer;font:inherit}
.tab.on{background:var(--accent);border-color:var(--accent);color:#fff}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px;min-width:130px}
.stat b{display:block;font-size:24px}
.stat span{color:var(--mute);font-size:13px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px;align-items:center}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:5px 12px;border-radius:999px;cursor:pointer;font:inherit;font-size:13px}
.chip.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent)}
.chiplabel{color:var(--mute);font-size:13px}
input[type=search]{width:100%;max-width:420px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit;margin-bottom:14px}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:auto;max-height:68vh}
table{border-collapse:collapse;width:100%}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{position:sticky;top:0;background:var(--card);cursor:pointer;white-space:nowrap;font-size:13px;color:var(--mute);user-select:none}
th:hover{color:var(--ink)}
td{max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
tr:hover td{background:var(--accent-soft)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.empty{padding:40px;text-align:center;color:var(--mute)}
.count{color:var(--mute);font-size:13px;margin:8px 2px}
</style>
</head>
<body>
<div class="wrap">
  <h1>SocietyBot</h1>
  <div class="sub">UCL Students' Union societies and events, read from the live web with TinyFish. Generated __WHEN__.</div>
  <div class="tabs" id="tabs"></div>
  <div class="stats" id="stats"></div>
  <div class="chips" id="chips"></div>
  <input type="search" id="q" placeholder="Search everything...">
  <div class="box" id="box"></div>
  <div class="count" id="count"></div>
</div>
<script>
const D = __DATA__;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const state = {tab: D.societies.rows.length || !D.events.rows.length ? "societies" : "events", q: "", filter: {}, sort: {}};

const T = () => D[state.tab];
function filterCols(t) {
  const out = [];
  t.cols.forEach(c => {
    if (/status|free|paid|type/i.test(c) && !/date|url|link/i.test(c)) {
      const u = new Set(t.rows.map(r => r[c] || ""));
      if (u.size > 1 && u.size <= 12) out.push(c);
    }
  });
  return out.slice(0, 2);
}
function num(v) { const n = parseFloat(String(v).replace(/[^0-9.\-]/g, "")); return isNaN(n) ? null : n; }
function defaultSort(tab) {
  const c = D[tab].cols.find(c => /date_iso/i.test(c));
  return c ? {col: c, dir: 1} : null;
}
function rowsNow() {
  const t = T(); let rows = t.rows;
  const q = state.q.trim().toLowerCase();
  if (q) rows = rows.filter(r => t.cols.some(c => String(r[c] || "").toLowerCase().includes(q)));
  const f = state.filter[state.tab] || {};
  Object.keys(f).forEach(c => { rows = rows.filter(r => (r[c] || "") === f[c]); });
  const s = state.sort[state.tab] || defaultSort(state.tab);
  if (s) {
    rows = [...rows].sort((a, b) => {
      const x = a[s.col] || "", y = b[s.col] || "";
      if (!x && !y) return 0; if (!x) return 1; if (!y) return -1;
      const nx = num(x), ny = num(y);
      const r = (nx !== null && ny !== null && /^[£$€]?\s*[0-9]/.test(x) && /^[£$€]?\s*[0-9]/.test(y)) ? nx - ny : String(x).localeCompare(String(y));
      return r * s.dir;
    });
  }
  return rows;
}
function cell(v) {
  v = String(v ?? "");
  if (/^https?:\/\//.test(v)) return `<a href="${esc(v)}" target="_blank" rel="noopener">open ↗</a>`;
  return `<span title="${esc(v)}">${esc(v)}</span>`;
}
function render() {
  const t = T();
  document.getElementById("tabs").innerHTML = ["societies", "events"].map(k =>
    `<button class="tab ${k === state.tab ? "on" : ""}" data-t="${k}">${k[0].toUpperCase() + k.slice(1)} (${D[k].rows.length})</button>`).join("");
  const fc = filterCols(t);
  const stats = [`<div class="stat"><b>${t.rows.length}</b><span>${state.tab}</span></div>`];
  const chips = [];
  fc.forEach(c => {
    const counts = {};
    t.rows.forEach(r => { const v = r[c] || ""; counts[v] = (counts[v] || 0) + 1; });
    const top = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 4);
    top.forEach(([v, n]) => { if (v) stats.push(`<div class="stat"><b>${n}</b><span>${esc(c)}: ${esc(v)}</span></div>`); });
    const cur = (state.filter[state.tab] || {})[c];
    chips.push(`<span class="chiplabel">${esc(c)}</span><button class="chip ${!cur ? "on" : ""}" data-c="${esc(c)}" data-v="">All</button>` +
      Object.keys(counts).filter(v => v).sort().map(v => `<button class="chip ${cur === v ? "on" : ""}" data-c="${esc(c)}" data-v="${esc(v)}">${esc(v)}</button>`).join(""));
  });
  document.getElementById("stats").innerHTML = stats.slice(0, 6).join("");
  document.getElementById("chips").innerHTML = chips.join("");
  const rows = rowsNow();
  const s = state.sort[state.tab] || defaultSort(state.tab);
  const box = document.getElementById("box");
  if (!t.cols.length) {
    box.innerHTML = `<div class="empty">No ${state.tab}.csv found yet. Run the scripts first, then re-run dashboard.py.</div>`;
  } else {
    box.innerHTML = `<table><thead><tr>${t.cols.map(c => `<th data-s="${esc(c)}">${esc(c)}${s && s.col === c ? (s.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("")}</tr></thead><tbody>` +
      rows.map(r => `<tr>${t.cols.map(c => `<td>${cell(r[c])}</td>`).join("")}</tr>`).join("") + `</tbody></table>` +
      (rows.length ? "" : `<div class="empty">Nothing matches.</div>`);
  }
  document.getElementById("count").textContent = `${rows.length} of ${t.rows.length} rows`;
}
document.addEventListener("click", e => {
  const tab = e.target.closest(".tab"); if (tab) { state.tab = tab.dataset.t; render(); return; }
  const chip = e.target.closest(".chip");
  if (chip) {
    const f = state.filter[state.tab] = state.filter[state.tab] || {};
    if (chip.dataset.v) f[chip.dataset.c] = chip.dataset.v; else delete f[chip.dataset.c];
    render(); return;
  }
  const th = e.target.closest("th");
  if (th) {
    const cur = state.sort[state.tab] || defaultSort(state.tab);
    state.sort[state.tab] = {col: th.dataset.s, dir: cur && cur.col === th.dataset.s ? -cur.dir : 1};
    render();
  }
});
document.getElementById("q").addEventListener("input", e => { state.q = e.target.value; render(); });
render();
</script>
</body>
</html>
"""


def main():
    data = {"societies": load("societies.csv"), "events": load("events.csv")}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", blob).replace(
        "__WHEN__", datetime.now().strftime("%d %b %Y, %H:%M")
    )
    out = HERE / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(
        f"Wrote {out.name}: {len(data['societies']['rows'])} societies, "
        f"{len(data['events']['rows'])} events"
    )
    if "--open" in sys.argv:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
