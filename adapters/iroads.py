"""Kerala PWD iROADS citizen portal (pwdrmms.kerala.gov.in/citizen/portal/): one answer per PWD road section (the map's
kstp-network-sections tiles; section ids 1..9080 at zoom 11, 2026-11-14): road start and end place, measured length, PWD division,
subdivision and section with the engineers' phone and e-mail, and every defect liability period (DLP) on that section: work name,
contractor name and phone, DLP start and end date, agreed PAC, work record id.

The portal page sends a fixed "shared-public-key" header that is printed in its own page script, the same for every visitor; no
login, OTP, captcha or session is involved (owner OK 2026-11-14 for fixed public-page keys). The adapter reads that value from the
public page at the start of each run and keeps it in memory only; it is never stored, logged or committed.

Queue item {"from": 1, "to": 100}: sections from..to-1. Records: one per section that answers, id "sec-<id>", with the API answer as
it came plus section_id. The answers of the item also go to the bucket as raw/kl-iroads/dlp/<from>.jsonl.gz. Section geometry is in
the bucket already (road-works-national raw/files/kl-iroads-11-*.mvt.gz, layer "all", property id = section id)."""
import gzip
import json
import re
import time

PORTAL = "https://pwdrmms.kerala.gov.in/citizen/portal/"
API = "https://apipwdrmms.kerala.gov.in/identity/api/v1/shared-data/network-sections/{}/defect-liability-period-details"
KEY = re.compile(r"""['"]shared-public-key['"]\s*:\s*['"]([0-9a-fA-F]{20,})['"]""")
TENANT = re.compile(r"""['"]TenantId['"]\s*:\s*['"]([A-Za-z0-9_-]+)['"]""")
_HEADERS = {}
GAP = 1.0


def page_key(text):
    """(key, tenant) printed in the portal page script, or (None, None). Pure."""
    k, t = KEY.search(text or ""), TENANT.search(text or "")
    return (k.group(1) if k else None), (t.group(1) if t else None)


def headers(ctx):
    if not _HEADERS:
        r = ctx.request("GET", PORTAL, timeout=90)
        if r is None:
            return None
        key, tenant = page_key(r.text)
        if not key:
            ctx.hub.failure("page", PORTAL, "the portal page no longer prints the public key")
            return None
        _HEADERS.update({"shared-public-key": key, "TenantId": tenant or "kstp", "Origin": "https://pwdrmms.kerala.gov.in",
                         "Referer": PORTAL, "Accept": "application/json"})
    return _HEADERS


def run(ctx, p):
    h = headers(ctx)
    if h is None:
        return None
    n, miss_run, misses, raw = 0, 0, [], []
    for sid in range(int(p["from"]), int(p["to"])):
        time.sleep(GAP)                             # at least ~1.5 s between calls, whatever the hub's delay (direct project)
        d = ctx.get_json("GET", API.format(sid), params={"unit": "KM"}, headers=h, timeout=60)
        if not isinstance(d, dict):
            misses.append(sid)
            miss_run += 1
            if miss_run >= 25:                      # 25 sections in a row without an answer: the API is down or refuses us
                ctx.hub.failure("api", f"sections {sid - 24}-{sid}", "25 sections in a row without an answer: item stopped")
                return None
            continue
        miss_run = 0
        raw.append(json.dumps({"section_id": sid, "answer": d}, ensure_ascii=False))
        ctx.record(f"sec-{sid}", {**d, "section_id": sid, "dlp_count": len(d.get("defectLiabilityPeriodDetails") or []),
                                  "source": "kerala-iroads-dlp"})
        n += 1
    ctx.hub.upload_many([(f"raw/kl-iroads/dlp/{int(p['from']):05d}.jsonl.gz", gzip.compress("\n".join(raw).encode(), 6),
                          "application/gzip")])
    if misses:
        ctx.record(f"miss-{int(p['from']):05d}", {"from": p["from"], "to": p["to"], "no_answer": misses, "source": "kerala-iroads-dlp"})
    return n
