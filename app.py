"""SocietyBot web app: enter your TinyFish key once, press Run, see the events.

    py app.py

Opens http://127.0.0.1:8000. Runs your existing scripts in order
(check.py, resolve.py, prices.py, events.py) and shows the results live.
Standard library only. Listens on localhost only. The key is kept in memory
for as long as the app runs, and is never sent back to the browser.
"""
import csv, json, os, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
KEYFILE = HERE / ".tinyfish.key"  # only written if you tick "remember"; ignored by git (*.key)


def _initial_key():
    k = os.environ.get("TINYFISH_API_KEY", "").strip()
    if not k and KEYFILE.exists():
        k = KEYFILE.read_text(encoding="utf-8").strip()
    return k


S = {"key": _initial_key(), "running": False, "stop": False, "proc": None,
     "stages": [], "log": [], "started": "", "finished": ""}


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def set_stage(i, status):
    S["stages"][i]["status"] = status


def run_script(script, args, env):
    key = S["key"]
    p = subprocess.Popen([sys.executable, "-u", script, *args], cwd=HERE, env=env,
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    S["proc"] = p
    for line in p.stdout:
        S["log"].append(line.rstrip().replace(key, "***") if key else line.rstrip())
        del S["log"][:-400]
    p.wait()
    return p.returncode


def pipeline(limit, deep):
    env = {**os.environ, "TINYFISH_API_KEY": S["key"], "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    lim = ["--limit", str(limit)] if limit else []
    plan = [("Check key and connection", "check.py", [], True),
            ("Find society pages", "resolve.py", [], True),
            ("Read membership prices", "prices.py", lim, False),
            ("Read events", "events.py", lim + (["--deep"] if deep else []), False)]
    S["stages"] = [{"name": n, "status": "pending"} for n, *_ in plan]
    for i, (name, script, args, fatal) in enumerate(plan):
        if S["stop"]:
            break
        set_stage(i, "running")
        S["log"].append(f"--- {name} ({script}) ---")
        try:
            code = run_script(script, args, env)
        except Exception as e:
            S["log"].append(f"Could not run {script}: {e}")
            code = 1
        if S["stop"]:
            set_stage(i, "stopped")
            break
        set_stage(i, "done" if code == 0 else "failed")
        if code != 0 and fatal:
            break
    for st in S["stages"]:
        if st["status"] == "pending":
            st["status"] = "skipped"
    S["running"], S["proc"], S["finished"] = False, None, stamp()


def _clean(v):
    # a stray "Â" before £ is a double-encoding glitch in the scraped text
    return v.replace("Â£", "£").replace("Â", "") if isinstance(v, str) else v


def read_csv(name):
    p = HERE / name
    if not p.exists():
        return {"cols": [], "rows": []}
    with open(p, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        rows = [{k: _clean(v) for k, v in row.items()} for row in r]
        return {"cols": r.fieldnames or [], "rows": rows}


def state_json():
    k = S["key"]
    return {"has_key": bool(k), "masked": k[-4:] if k else "", "running": S["running"],
            "stages": S["stages"], "log": S["log"][-200:], "started": S["started"], "finished": S["finished"]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def ok_origin(self):
        host = self.headers.get("Host", "").split(":")[0]
        if host not in ("127.0.0.1", "localhost"):
            return False
        o = self.headers.get("Origin")
        return not o or o.split("://", 1)[-1].split(":")[0] in ("127.0.0.1", "localhost")

    def do_GET(self):
        if not self.ok_origin():
            return self.send(403, "{}")
        if self.path == "/":
            return self.send(200, PAGE, "text/html")
        if self.path == "/api/state":
            return self.send(200, json.dumps(state_json()))
        if self.path == "/api/data":
            return self.send(200, json.dumps({"events": read_csv("events.csv"), "societies": read_csv("societies.csv")}))
        if self.path == "/api/societies":
            p = HERE / "societies.txt"
            return self.send(200, json.dumps({"text": p.read_text(encoding="utf-8") if p.exists() else ""}))
        self.send(404, "{}")

    def do_POST(self):
        if not self.ok_origin():
            return self.send(403, "{}")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self.send(400, json.dumps({"error": "bad request"}))
        if self.path == "/api/key":
            k = str(body.get("key", "")).strip()
            S["key"] = k
            if k and body.get("remember"):
                KEYFILE.write_text(k, encoding="utf-8")
            elif not k and KEYFILE.exists():
                KEYFILE.unlink()
            return self.send(200, json.dumps(state_json()))
        if self.path == "/api/run":
            if S["running"]:
                return self.send(409, json.dumps({"error": "A run is already in progress."}))
            if not S["key"]:
                return self.send(400, json.dumps({"error": "Enter your TinyFish API key first."}))
            text = str(body.get("societies", "")).strip()
            if text:
                (HERE / "societies.txt").write_text(text + "\n", encoding="utf-8")
            elif not (HERE / "societies.txt").exists():
                return self.send(400, json.dumps({"error": "Add at least one society."}))
            try:
                limit = int(body.get("limit") or 0)
            except ValueError:
                limit = 0
            S.update(running=True, stop=False, log=[], started=stamp(), finished="")
            threading.Thread(target=pipeline, args=(max(limit, 0), bool(body.get("deep"))), daemon=True).start()
            return self.send(200, json.dumps(state_json()))
        if self.path == "/api/stop":
            S["stop"] = True
            p = S["proc"]
            if p:
                p.terminate()
            return self.send(200, json.dumps(state_json()))
        self.send(404, "{}")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SocietyBot</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#1b1f2a;--mute:#667085;--line:#e4e7ee;--ac:#4f46e5;--soft:#eceafd;--ok:#12805c;--bad:#c0392b}
@media(prefers-color-scheme:dark){:root{--bg:#12141b;--card:#1b1e28;--ink:#e8eaf1;--mute:#9aa3b5;--line:#2a2e3b;--ac:#8b85ff;--soft:#272a46;--ok:#4cc9a0;--bad:#ff8a7a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:26px 18px 60px}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}h1{margin:0;font-size:26px}
.sub{color:var(--mute);margin:2px 0 18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
.card h2{margin:0 0 10px;font-size:16px}
input,textarea,select{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:9px 12px}
textarea{width:100%;min-height:110px;resize:vertical}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:9px;padding:9px 16px;cursor:pointer}
button.pri{background:var(--ac);border-color:var(--ac);color:#fff}button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:10px}.mute{color:var(--mute);font-size:13px}
.stages{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.st{border:1px solid var(--line);border-radius:999px;padding:4px 12px;font-size:13px}
.st.running{border-color:var(--ac);color:var(--ac)}.st.done{color:var(--ok);border-color:var(--ok)}.st.failed{color:var(--bad);border-color:var(--bad)}
pre{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:10px;max-height:240px;overflow:auto;font-size:12px;white-space:pre-wrap;margin:10px 0 0}
.tabs{display:flex;gap:8px;margin:18px 0 12px}.tab{border-radius:999px}.tab.on{background:var(--ac);border-color:var(--ac);color:#fff}
.month{margin:20px 0 8px;font-size:14px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.ev{display:flex;gap:14px;align-items:center;justify-content:space-between;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:8px}
.ev b{display:block}.when{min-width:110px;color:var(--ac);font-weight:600}.grow{flex:1;min-width:0}
.badge{font-size:12px;border-radius:999px;padding:2px 9px;background:var(--soft);color:var(--ac);white-space:nowrap}
a.go{color:#fff;background:var(--ac);padding:7px 14px;border-radius:9px;text-decoration:none;white-space:nowrap}
a{color:var(--ac)}.empty{padding:30px;text-align:center;color:var(--mute)}
.box{overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:12px}table{border-collapse:collapse;width:100%}
th,td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:13px;color:var(--mute);white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.sc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;display:flex;flex-direction:column;gap:10px;min-width:0}
.sch{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}.sch b{font-size:16px;overflow-wrap:anywhere}
.facts{display:flex;gap:18px}.facts div{display:flex;flex-direction:column}.facts b{font-size:15px}
.tiers{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:4px;font-size:14px}
.tiers li{background:var(--bg);border-radius:8px;padding:5px 9px;overflow-wrap:anywhere}
.lnk{margin-top:auto;font-size:14px;text-decoration:none}
.badge.ok{background:rgba(18,128,92,.13);color:var(--ok)}.badge.warn{background:rgba(214,137,16,.16);color:#b7791f}
</style></head><body><div class="wrap">
<header><h1>SocietyBot</h1><div id="keychip" class="mute"></div></header>
<div class="sub">UCL Students' Union societies and events, read from the live web with TinyFish.</div>

<div class="card" id="keycard" hidden><h2>1. TinyFish API key</h2>
<div class="row" style="margin-top:0"><input id="key" type="password" placeholder="Paste your key" size="44" autocomplete="off">
<button class="pri" id="savekey">Save</button></div>
<label class="mute"><input type="checkbox" id="remember"> Remember on this computer (saved to a git-ignored file)</label>
<div class="mute">Get a key at agent.tinyfish.ai/api-keys. It stays on this computer and is never shown again.</div></div>

<div class="card"><h2>Run</h2>
<div class="mute" style="margin-bottom:6px">Societies, one per line (rough names are fine)</div>
<textarea id="soc" placeholder="Computer Science Society&#10;Hiking Society"></textarea>
<div class="row"><label>Only first <input id="limit" type="number" min="1" style="width:70px" placeholder="all"> societies (for testing)</label>
<label><input type="checkbox" id="deep"> Also open each event page for its price (slower)</label></div>
<div class="row"><button class="pri" id="run">Run everything</button><button id="stop" hidden>Stop</button><span class="mute" id="when"></span></div>
<div class="mute" style="margin-top:8px">The prices and events steps use TinyFish Agent credits. Try a limit of 1 first.</div>
<div class="stages" id="stages"></div><pre id="log" hidden></pre></div>

<div class="tabs"><button class="tab on" data-t="events">Events <span id="ne"></span></button><button class="tab" data-t="societies">Societies &amp; prices <span id="ns"></span></button></div>
<div id="filters" class="row" style="margin:0 0 6px"></div>
<div id="out"></div></div>

<script>
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const api=async(p,b)=>(await fetch(p,b===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b)})).json();
let S={},D={events:{cols:[],rows:[]},societies:{cols:[],rows:[]}},tab="events",q="",soc="",freeOnly=false,past=false,lastFin="",loaded=false;

function renderState(){
  $("#keycard").hidden=S.has_key;
  $("#keychip").innerHTML=S.has_key?`Key set (…${esc(S.masked)}) · <a href="#" id="forget">forget</a>`:"No key yet";
  $("#run").disabled=!S.has_key||S.running; $("#stop").hidden=!S.running;
  $("#run").textContent=S.running?"Running…":"Run everything";
  $("#stages").innerHTML=(S.stages||[]).map(s=>`<span class="st ${s.status}">${esc(s.name)}: ${s.status}</span>`).join("");
  $("#when").textContent=S.finished?`Finished ${S.finished}`:S.started?`Started ${S.started}`:"";
  const lg=$("#log"); lg.hidden=!(S.log&&S.log.length); lg.textContent=(S.log||[]).join("\n"); if(S.running)lg.scrollTop=lg.scrollHeight;
}
async function tick(){
  S=await api("/api/state"); renderState();
  if(S.running||!loaded||S.finished!==lastFin){D=await api("/api/data");lastFin=S.finished;loaded=true;renderData();}
  setTimeout(tick,S.running?1500:4000);
}
const pick=(cols,res)=>{for(const re of res){const c=cols.find(c=>re.test(c));if(c)return c}return null};
const isHttp=v=>/^https?:\/\//i.test(v||"");
function evCols(c){
  const noUrl=c.filter(x=>!/url|link|live/i.test(x));
  return{title:pick(noUrl,[/^title$/i,/event.?name/i,/^name$/i,/title/i,/event/i]),
    iso:pick(c,[/date_iso/i]),date:pick(noUrl,[/^date$/i,/date/i,/when/i]),time:pick(noUrl,[/time/i]),
    soc:pick(noUrl,[/^society$/i,/society/i]),price:pick(noUrl,[/price|cost/i]),free:pick(noUrl,[/free/i]),
    link:pick(c.filter(x=>!/society|live/i.test(x)),[/event.?(url|link)/i,/^link$/i,/link/i,/^url$/i,/url/i])};
}
function isFree(r,k){
  if(k.free&&/^(true|yes|y|free|1)/i.test(r[k.free]||""))return true;
  if(k.price&&/free|^£?0(\.0+)?$/i.test((r[k.price]||"").trim()))return true;
  return false;
}
function renderFilters(k){
  const t=D[tab]; const socs=[...new Set(t.rows.map(r=>r[k.soc||"society"]).filter(Boolean))].sort();
  $("#filters").innerHTML=`<input id="q" type="search" placeholder="Search…" value="${esc(q)}">`+
   (tab==="events"?`<select id="socsel"><option value="">All societies</option>${socs.map(s=>`<option ${s===soc?"selected":""}>${esc(s)}</option>`).join("")}</select>
    <label><input type="checkbox" id="fo" ${freeOnly?"checked":""}> Free only</label><label><input type="checkbox" id="pa" ${past?"checked":""}> Include past</label>`:"");
}
function renderData(){
  $("#ne").textContent=`(${D.events.rows.length})`;$("#ns").textContent=`(${D.societies.rows.length})`;
  const keep=document.activeElement&&document.activeElement.id==="q";
  tab==="events"?renderEvents():renderSocieties();
  if(keep){const e=$("#q");if(e){e.focus();e.setSelectionRange(q.length,q.length)}}
}
function renderEvents(){
  const t=D.events,k=evCols(t.cols);renderFilters(k);
  if(!t.rows.length){$("#out").innerHTML=`<div class="empty">No events yet. Press “Run everything”.</div>`;return}
  const today=new Date().toISOString().slice(0,10),ql=q.toLowerCase();
  let rows=t.rows.filter(r=>(!ql||t.cols.some(c=>String(r[c]||"").toLowerCase().includes(ql)))
    &&(!soc||r[k.soc]===soc)&&(!freeOnly||isFree(r,k))&&(past||!k.iso||!r[k.iso]||r[k.iso]>=today));
  rows.sort((a,b)=>{const x=k.iso?a[k.iso]||"9999":"",y=k.iso?b[k.iso]||"9999":"";return x<y?-1:x>y?1:0});
  let html="",cur=null;
  rows.forEach(r=>{
    const iso=k.iso?r[k.iso]:"";const mo=iso?new Date(iso+"T00:00").toLocaleDateString("en-GB",{month:"long",year:"numeric"}):"Date to be confirmed";
    if(mo!==cur){html+=`<div class="month">${esc(mo)}</div>`;cur=mo}
    const d=iso&&!isNaN(new Date(iso))?new Date(iso+"T00:00").toLocaleDateString("en-GB",{weekday:"short",day:"numeric",month:"short"}):(k.date?r[k.date]:"");
    const tm=k.time&&r[k.time]?` · ${esc(r[k.time])}`:"";
    const free=isFree(r,k),pr=k.price&&r[k.price]?r[k.price]:"";
    const link=isHttp(r[k.link])?r[k.link]:"";
    html+=`<div class="ev"><div class="when">${esc(d)}${tm}</div><div class="grow"><b>${esc(r[k.title]||"(untitled event)")}</b><span class="mute">${esc(r[k.soc]||"")}</span></div>
      ${free?'<span class="badge">Free</span>':pr?`<span class="badge">${esc(pr)}</span>`:""}
      ${link?`<a class="go" href="${esc(link)}" target="_blank" rel="noopener">Open ↗</a>`:'<span class="mute">no link</span>'}</div>`;
  });
  $("#out").innerHTML=html||`<div class="empty">Nothing matches.</div>`;
}
let stat="",freeSoc=false;
const stLabel=v=>/^closed/i.test(v)?"Closed or waitlist":v?v.charAt(0).toUpperCase()+v.slice(1):"";
const stCls=v=>/^open/i.test(v)?"ok":/closed|login/i.test(v)?"warn":"";
function renderSocieties(){
  const t=D.societies;renderFilters({});
  if(!t.rows.length){$("#out").innerHTML=`<div class="empty">No societies read yet. Press “Run everything”.</div>`;return}
  const sts=[...new Set(t.rows.map(r=>r.page_status).filter(Boolean))].sort();
  $("#filters").insertAdjacentHTML("beforeend",`<select id="stsel"><option value="">Any status</option>${sts.map(x=>`<option value="${esc(x)}" ${x===stat?"selected":""}>${esc(stLabel(x))}</option>`).join("")}</select><label><input type="checkbox" id="fo2" ${freeSoc?"checked":""}> Has a free option</label>`);
  const ql=q.toLowerCase();
  const rows=t.rows.filter(r=>(!ql||t.cols.some(c=>String(r[c]||"").toLowerCase().includes(ql)))&&(!stat||r.page_status===stat)&&(!freeSoc||(r.free_option&&r.free_option!=="no")))
    .sort((a,b)=>String(a.society||"").localeCompare(String(b.society||"")));
  $("#out").innerHTML=rows.length?`<div class="grid">`+rows.map(r=>{
    const tiers=(r.tiers||"").split(";").map(x=>x.trim()).filter(Boolean);
    const free=r.free_option&&r.free_option!=="no";
    return `<div class="sc"><div class="sch"><b>${esc(r.society)}</b>${r.page_status?`<span class="badge ${stCls(r.page_status)}">${esc(stLabel(r.page_status))}</span>`:""}</div>
      <div class="facts"><div><span class="mute">Cheapest paid</span><b>${r.cheapest_paid?esc(r.cheapest_paid):"–"}</b></div><div><span class="mute">Free option</span><b>${free?esc(r.free_option):"None"}</b></div></div>
      ${tiers.length?`<ul class="tiers">${tiers.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>`:`<div class="mute">No membership options found</div>`}
      ${isHttp(r.url)?`<a class="lnk" href="${esc(r.url)}" target="_blank" rel="noopener">View society page ↗</a>`:""}</div>`}).join("")+`</div>`:`<div class="empty">Nothing matches.</div>`;
}
document.addEventListener("click",async e=>{
  const t=e.target;
  if(t.id==="savekey"){S=await api("/api/key",{key:$("#key").value,remember:$("#remember").checked});$("#key").value="";renderState()}
  if(t.id==="forget"){e.preventDefault();S=await api("/api/key",{key:""});renderState()}
  if(t.id==="run"){const r=await api("/api/run",{societies:$("#soc").value,limit:$("#limit").value,deep:$("#deep").checked});if(r.error)alert(r.error);S=r.error?S:r;renderState()}
  if(t.id==="stop"){S=await api("/api/stop",{});renderState()}
  if(t.classList.contains("tab")){tab=t.dataset.t;document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("on",b===t));renderData()}
});
document.addEventListener("input",e=>{
  if(e.target.id==="q"){q=e.target.value;renderData()}
  if(e.target.id==="socsel"){soc=e.target.value;renderData()}
  if(e.target.id==="fo"){freeOnly=e.target.checked;renderData()}
  if(e.target.id==="pa"){past=e.target.checked;renderData()}
  if(e.target.id==="stsel"){stat=e.target.value;renderData()}
  if(e.target.id==="fo2"){freeSoc=e.target.checked;renderData()}
});
api("/api/societies").then(r=>{$("#soc").value=r.text||""});
tick();
</script></body></html>
"""


def main():
    port = 8000
    while True:
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), H)
            break
        except OSError:
            port += 1
            if port > 8010:
                raise SystemExit("Ports 8000-8010 are all busy.")
    url = f"http://127.0.0.1:{port}"
    print(f"SocietyBot is running at {url}  (Ctrl+C to stop)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
