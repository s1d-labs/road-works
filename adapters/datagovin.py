"""data.gov.in (Open Government Data platform) road datasets through its API (api.data.gov.in), with the public sample API key that
data.gov.in prints in its own page script (VUE_APP_APIKEY, the same for every visitor; no login, OTP or captcha; owner OK
2026-11-14). The key is read from a 0600 file on the worker host (dev-vps-3) and kept in memory only; it is never logged or
committed. File downloads on data.gov.in need a login: not used.

Queue items:
  {"kind": "catalog"}: the catalog search (api /lists) for each road word in the title, plus the Road Transport sector and MoRTH;
      every hit's metadata goes to raw/datagovin/catalog.jsonl.gz (with "road" = the title matches ROAD); one record per road
      resource (id "cat-<index_name>"); one queue item per road resource is added.
  {"kind": "resource", "id": "<index_name>", "title": ...}: every row of that resource (pages of 1000), stored as
      raw/datagovin/res/<index_name>/<offset>.json.gz (the API answer as it came: metadata, fields, records); one record per resource
      (id "res-<index_name>": title, org, sector, fields, total, rows stored, files). Rows are not hub records: the files keep them all.
"""
import gzip
import json
import os
import re

API = "https://api.data.gov.in"
APIKEY = re.compile(r'VUE_APP_APIKEY:"([0-9a-f]{20,})"')
TITLE_WORDS = ["road", "roads", "highway", "highways", "pmgsy", "sadak", "nh", "bridge", "bridges", "expressway", "pwd", "flyover",
               "toll", "culvert", "chainage", "street", "carriageway", "bypass", "overbridge", "rob", "mdr", "lane"]
OTHER_FILTERS = [{"filters[sector]": "Road Transport"}, {"filters[sector]": "Transport"},
                 {"filters[org]": "Ministry of Road Transport and Highways"}]
ROAD = re.compile(r"(?i)road|highway|pmgsy|sadak|\bnh\s*-?\d|\bnhs?\b|bridge|expressway|\bpwd\b|flyover|\btoll|culvert|chainage|"
                  r"street|carriageway|by-?pass|\brob\b|\bmdr\b|\bodr\b|four.?lan|two.?lan|six.?lan|\blanes?\b|\bpath\b|marg\b")
PAGE = 1000
_KEY = {}


def page_key(texts):
    """The sample key printed in data.gov.in's page script, or None. Pure."""
    for t in texts:
        m = APIKEY.search(t or "")
        if m:
            return m.group(1)
    return None


def key(ctx):
    """The sample key from a 0600 file on the worker's host (DATAGOVIN_KEY_FILE, default ~/.config/road-keys/datagovin-sample.key).
    www.data.gov.in answers 403 to the family's User-Agent, so the key is not read from the page at run time."""
    if "k" not in _KEY:
        path = os.path.expanduser(os.environ.get("DATAGOVIN_KEY_FILE", "~/.config/road-keys/datagovin-sample.key"))
        try:
            k = open(path).read().strip()
        except OSError:
            k = ""
        if not re.fullmatch(r"[0-9a-f]{20,}", k):
            ctx.hub.failure("key", "datagovin", "no sample key file on this host: the project runs only on dev-vps-3")
            return None
        _KEY["k"] = k
    return _KEY["k"]


def api(ctx, path, params):
    k = key(ctx)
    if k is None:
        return None, None
    r = ctx.request("GET", f"{API}/{path}", params={**params, "api-key": k, "format": "json"}, timeout=180)
    if r is None:
        return None, None
    try:
        return r.json(), r.content
    except ValueError:
        ctx.hub.error()
        return None, None


def catalog(ctx):
    hits, raw = {}, []
    queries = [{"filters[title]": w} for w in TITLE_WORDS] + OTHER_FILTERS
    for q in queries:
        off, total = 0, None
        while total is None or off < total:
            d, _ = api(ctx, "lists", {**q, "filters[active]": "1", "notfilters[source]": "visualize.data.gov.in",
                                      "limit": PAGE, "offset": off})
            if d is None:
                ctx.hub.failure("catalog", json.dumps(q)[:100], f"catalog page {off} did not load")
                return None
            total = int(d.get("total") or 0)
            recs = d.get("records") or []
            for rec in recs:
                rid = rec.get("index_name")
                if rid and rid not in hits:
                    rec["road"] = bool(ROAD.search(f"{rec.get('title', '')} {rec.get('desc', '')}"))
                    rec["found_by"] = [q]
                    hits[rid] = rec
                elif rid:
                    hits[rid]["found_by"].append(q)
            if not recs:
                break
            off += PAGE
    raw = [json.dumps(r, ensure_ascii=False) for r in hits.values()]
    ctx.hub.upload_many([("raw/datagovin/catalog.jsonl.gz", gzip.compress("\n".join(raw).encode(), 6), "application/gzip")])
    road = [r for r in hits.values() if r["road"]]
    for r in road:
        ctx.record(f"cat-{r['index_name']}", {**{k: v for k, v in r.items() if k != "field"}, "fields": r.get("field"),
                                             "source": "data.gov.in"})
    if ctx.seed:
        ctx.seed([{"key": f"r-{r['index_name']}", "payload": {"kind": "resource", "id": r["index_name"], "title": r.get("title", "")[:200]}}
                  for r in road])
    return len(road)


def resource(ctx, p):
    rid, off, total, n, files, meta = p["id"], 0, None, 0, [], {}
    while total is None or off < total:
        d, content = api(ctx, f"resource/{rid}", {"limit": PAGE, "offset": off})
        if d is None:
            ctx.hub.failure("resource", rid, f"page {off} did not load")
            return None
        if d.get("status") not in (None, "ok") and not d.get("records"):
            ctx.hub.failure("resource", rid, str(d.get("message") or d.get("status"))[:200])
            break
        total = int(d.get("total") or 0)
        recs = d.get("records") or []
        path = f"raw/datagovin/res/{rid}/{off:08d}.json.gz"
        ctx.hub.upload_many([(path, gzip.compress(content, 6), "application/gzip")])
        files.append(path)
        n += len(recs)
        if not meta:
            meta = {k: v for k, v in d.items() if k not in ("records", "field", "params")}
            meta["fields"] = d.get("field")
        if not recs:
            break
        off += PAGE
    ctx.record(f"res-{rid}", {**meta, "index_name": rid, "total": total, "stored": n, "files": files, "source": "data.gov.in"})
    return n


def run(ctx, p):
    return catalog(ctx) if p.get("kind") == "catalog" else resource(ctx, p)
