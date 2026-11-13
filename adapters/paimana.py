"""MoSPI PAIMANA public dashboard (paimana-proj.mospi.gov.in): central infrastructure projects of Rs 150 crore and more, as frozen
each month: project id, name (often with NH number and km), ministry, agency (NHAI, MoRTH, NHIDCL ...), original and revised cost,
expenditure, physical progress %, sanction date, original and revised end date. No login (an anti-forgery token from the page).

Queue item {"month": "2026-09", "sector": 107} (107 = Roads & Highways; "sector": "" = every sector): one call per month.
Records: one per project and month, id "<month>-<sector>-<project id>". Answers to the bucket as they came."""
import gzip
import json
import re

SITE = "https://paimana-proj.mospi.gov.in"
PAGE = f"{SITE}/Home/PublicDashboardNew"
TOKEN = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')


def run(ctx, p):
    r = ctx.request("GET", PAGE, timeout=90)
    if r is None:
        return None
    m = TOKEN.search(r.text)
    if not m:
        ctx.hub.failure("form", PAGE, "no anti-forgery token")
        return None
    year, month = p["month"].split("-")
    r = ctx.request("POST", f"{SITE}/Home/GetTileData", timeout=180,
                    headers={"X-Requested-With": "XMLHttpRequest", "Referer": PAGE},
                    data={"__RequestVerificationToken": m.group(1), "Month": month, "Year": year, "SectorId": p.get("sector", ""),
                          "PROJ_MINISTRY_ID": "", "StateId": p.get("state", ""), "MonthYear": p["month"]})
    if r is None:
        return None
    try:
        d = r.json()
    except ValueError:
        ctx.hub.failure("json", p["month"], "answer is not JSON")
        return None
    tag = f"{p['month']}-{p.get('sector') or 'all'}"
    ctx.hub.upload_many([(f"raw/paimana/{tag}.json.gz", gzip.compress(r.content, 6), "application/gzip")])
    data = d.get("data") or {}
    rows = data.get("ProjectsCountTabDetails") or []
    for row in rows:
        ctx.record(f"{tag}-{row.get('ProjectId')}", {**row, "month": p["month"], "sector_id": p.get("sector"), "source": "mospi-paimana"})
    ctx.record(f"{tag}-totals", {"totals": data.get("totalProjectsTabData"), "month": p["month"], "sector_id": p.get("sector"),
                                 "projects": len(rows), "source": "mospi-paimana"})
    return len(rows)
