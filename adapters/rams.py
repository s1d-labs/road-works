"""MPRDC road asset management system (rams.mp.gov.in, ArcGIS 10.9, folder mprams): public map layers that are database query
layers without an object-id field, so road-maps' arcgis task cannot page them. This adapter pages them by offset, ordered by the
layer's first attribute fields. No login (the folder's other service MPRDC_IMPS_API asks for one: not used). The server's
certificate chain fails: verify off, records say tls_unverified.

Queue item {"layer": "WORKSHISTORY", "url": ".../WORKSHISTORY/MapServer/0"}: the layer description, the count, then pages of
Esri JSON with geometry in EPSG:4326 (raw/rams/<layer>/<offset>.json.gz). One record per feature with every attribute
(id "<layer>-<n>", n = position in that order), and one record for the layer (fields, count, files)."""
import gzip
import json

PAGE = 1000


def run(ctx, p):
    url, name = p["url"], p["layer"]
    meta = ctx.get_json("GET", url, params={"f": "json"}, verify=False, timeout=120)
    if not meta or "error" in meta:
        return None
    fields = [f["name"] for f in meta.get("fields") or [] if f.get("type") != "esriFieldTypeGeometry"]
    size = min(PAGE, int(meta.get("maxRecordCount") or PAGE))
    c = ctx.get_json("GET", f"{url}/query", params={"where": "1=1", "returnCountOnly": "true", "f": "json"}, verify=False, timeout=120)
    if not c or "count" not in c:
        return None
    total, n, files = c["count"], 0, []
    order = ",".join(fields[:3])
    for off in range(0, total, size):
        r = ctx.request("GET", f"{url}/query", verify=False, timeout=300,
                        params={"where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 4326, "orderByFields": order,
                                "resultOffset": off, "resultRecordCount": size, "f": "json"})
        if r is None:
            return None
        d = r.json()
        if "error" in d:
            ctx.hub.failure("page", f"{name}-{off}", json.dumps(d["error"])[:200])
            return None
        path = f"raw/rams/{name}/{off:07d}.json.gz"
        ctx.hub.upload_many([(path, gzip.compress(r.content, 6), "application/gzip")])
        files.append(path)
        for i, f in enumerate(d.get("features") or []):
            ctx.record(f"{name}-{off + i:07d}", {**(f.get("attributes") or {}), "layer": name, "file": path, "tls_unverified": True,
                                                 "source": "mp-rams"})
            n += 1
    ctx.record(f"{name}-layer", {"layer": name, "url": url, "count": total, "stored": n, "fields": fields, "order": order, "files": files,
                                 "geometry": meta.get("geometryType"), "copyright": meta.get("copyrightText") or "",
                                 "tls_unverified": True, "source": "mp-rams"})
    return n
