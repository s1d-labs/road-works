"""Karnataka RDPR "NGSK" works portal (ngsk.karnataka.gov.in), report "Work-wise progress": every rural work of an agency (KRRDA,
PRED, RWS, ...) per financial year and district: division, subdivision, taluk, work name (often with km), work id, category,
head of account, AA number and date, approved amount, payment made, started, status. No contractor. No login (the site's
login box has a captcha; the reports do not).

Queue item {"year": 14, "year_name": "2025-26", "agency": 4, "agency_name": "PRED"}: the report form (cookie + anti-forgery
token), the district list for the agency, then one report call per district (the all-districts answer stops at 4,000 rows).
Records: one per row, id "<agency>-<work id>" (the work id carries the year). The answers go to the bucket as one .jsonl.gz."""
import gzip
import html
import json
import re

from adapters.common import clean, sha1

SITE = "https://ngsk.karnataka.gov.in"
FORM = f"{SITE}/Reports/WorkWiseProgressReport"
TOKEN = re.compile(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"')
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
COLS = ["sl", "district", "division", "subdivision", "work_name", "work_id", "category", "head_of_account", "aa_no", "aa_date",
        "approved_amount", "payment_made", "work_started", "status"]
YEARS = {11: "2012-13", 9: "2013-14", 10: "2014-15", 6: "2015-16", 7: "2016-17", 8: "2017-18", 3: "2018-19", 4: "2019-20",
         5: "2020-21", 1: "2021-22", 2: "2022-23", 12: "2023-24", 13: "2024-25", 14: "2025-26", 15: "2026-27"}
AGENCIES = {1: "KRRDA", 4: "PRED", 8: "RWS", 9: "TP", 10: "HD", 11: "NK", 12: "KTIL"}


def parse(page):
    """Report rows: [{column: value}]. Pure. Rows with another column count keep their cells as a list."""
    out = []
    for m in TR.finditer(page):
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", c))) for c in TD.findall(m.group(1))]
        if len(cells) == len(COLS):
            out.append(dict(zip(COLS, cells)))
        elif len(cells) > 3:
            out.append({"cells": cells})
    return out


def run(ctx, p):
    r = ctx.request("GET", FORM, timeout=90)
    if r is None:
        return None
    m = TOKEN.search(r.text)
    if not m:
        ctx.hub.failure("form", FORM, "no anti-forgery token on the report form")
        return None
    tok = m.group(1)
    hdr = {"Referer": FORM, "X-Requested-With": "XMLHttpRequest"}
    dists = ctx.get_json("POST", f"{SITE}/Reports/GetDistrictListForReports", data={"id": 1, "AgencyId": p["agency"],
                                                                                           "__RequestVerificationToken": tok}, headers=hdr)
    if not dists:
        return None
    if isinstance(dists, dict):
        dists = next((v for v in dists.values() if isinstance(v, list)), [])
    raw, n = [], 0
    for d in dists:
        did = d.get("Value") or d.get("value") or d.get("DistrictId") or d.get("Id")
        dname = d.get("Text") or d.get("text") or d.get("DistrictName") or ""
        if did in (None, "", "0", 0, "-1"):
            continue
        r = ctx.request("POST", f"{SITE}/Reports/GetWorkWiseProgressReport", headers=hdr, timeout=180,
                        data={"FinancialYear": p["year"], "Agency": p["agency"], "Scheme": -1, "reportType": 1, "Multiple": did,
                              "SchemeType": 1, "__RequestVerificationToken": tok})
        if r is None:
            ctx.hub.failure("district", f"{p['agency']}-{p['year']}-{did}", "report call failed")
            continue
        raw.append(json.dumps({"district": did, "name": dname, "html": r.text}, ensure_ascii=False))
        for i, row in enumerate(parse(r.text)):
            wid = row.get("work_id") or sha1(did, i)
            ctx.record(f"{p['agency']}-{p['year']}-{wid}", {**row, "district_id": did, "district_name": dname, "year": p["year_name"],
                                                            "agency": p["agency_name"], "source": "ka-ngsk-work-progress"})
            n += 1
    ctx.hub.upload_many([(f"raw/ngsk/{p['agency']}-{p['year']}.jsonl.gz", gzip.compress("\n".join(raw).encode(), 6), "application/gzip")])
    return n
