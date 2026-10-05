"""Tiny TinyFish helper. Errors are raised with the full server message (no silent failures)."""
import os, sys, json
import requests

# Windows consoles choke on £ and accents unless we force UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEY = os.environ.get("TINYFISH_API_KEY")
if not KEY:
    sys.exit('TINYFISH_API_KEY is not set. In PowerShell run:\n  $env:TINYFISH_API_KEY="your_key_here"')

H = {"X-API-Key": KEY}
SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"


class TFError(Exception):
    pass


def _check(r):
    if r.status_code >= 400:
        raise TFError(f"HTTP {r.status_code} from {r.url.split('?')[0]}: {r.text[:500]}")


def search(query, **params):
    r = requests.get(SEARCH_URL, headers=H, params={"query": query, **params}, timeout=60)
    _check(r)
    return r.json()


def fetch(urls, fmt="markdown"):
    r = requests.post(FETCH_URL, headers=H, json={"urls": urls, "format": fmt}, timeout=120)
    _check(r)
    return r.json()


def page_text(data):
    """Pull the page text out of a Fetch response; fall back to the raw JSON so links still survive."""
    if isinstance(data, dict):
        for key in ("results", "data", "pages", "contents"):
            items = data.get(key)
            if isinstance(items, list) and items and isinstance(items[0], dict):
                for k in ("text", "content", "markdown", "html"):
                    if isinstance(items[0].get(k), str):
                        return items[0][k]
    return json.dumps(data, ensure_ascii=False)


AGENT_SSE = "https://agent.tinyfish.ai/v1/automation/run-sse"


def agent(url, goal, use_profile=False, on_live=None, timeout=600):
    """Run a TinyFish web agent and return {'status','result','live_view','run_id'}.
    on_live(url) is called when the live browser-view link arrives (handy for screenshots)."""
    body = {"url": url, "goal": goal}
    if use_profile:
        body["use_profile"] = True
    live = None
    with requests.post(AGENT_SSE, headers=H, json=body, stream=True, timeout=timeout) as r:
        _check(r)
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except ValueError:
                continue
            if ev.get("streaming_url") and not live:
                live = ev["streaming_url"]
                if on_live:
                    on_live(live)
            if ev.get("type") == "COMPLETE":
                res = ev.get("result")
                if isinstance(res, dict) and set(res) == {"result"}:
                    res = res["result"]
                return {"status": ev.get("status"), "result": res,
                        "live_view": live, "run_id": ev.get("run_id")}
    raise TFError("Agent stream ended without a COMPLETE event")
