"""Madhya Pradesh PWD "LPPP" dashboard (Softtech PWIMS), the public overview grids. No login, no captcha. The server is a bare IP
with a self-signed certificate (verify off; records say tls_unverified).

Queue item {"method": "GetCompletedWorks_PWDBR"} or {"method": "GetMISReportData", "org": "1,2,3"}: one SOAP call gives the
whole grid (no paging). Every grid row becomes a record with every attribute:
  GetCompletedWorks_PWDBR   completed PWD (B&R) works 2011-2025: division, road type, work name, length, AA / TS / PAC amounts,
                            tender %, CONTRACTOR, contract amount, work order no. and date, scheduled and actual completion, BT/CC km.
  GetCompletedWorks_PWDBHAWAN  the same for PWD buildings.
  GetMISReportData          live works (MIS list): district, division, sector, WIN no., work id, work name, estimated and accepted
                            cost, AGENCY, LOA / start / completion dates, present status, target / achieved %, proposal and TS ids.
The answer goes to the bucket as it came (raw/<method>-<org>.xml.gz).
"""
import gzip
import html
import re

import urllib3

URL = "https://52.172.154.79:8055/SEPL.PWIMS.Dashboard/Dashboard/overviewService.asmx"
MIS_EMPTY = ["psCircle", "psRegion", "psSectorID", "psDistrictID", "psContractorID", "psFromDate", "psToDate", "psOfficeCategory",
             "psScheme", "psULBID", "psStatus", "psBudgetYear", "PsProjectType", "PsSoucefund"]
ITEM = re.compile(r"<I\s([^>]*?)/?>", re.S)
ATTR = re.compile(r"([A-Za-z_][\w.-]*)=\"([^\"]*)\"")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def envelope(method, org=None):
    params = ""
    if method == "GetMISReportData":
        params = "<psGridType>tgMIS</psGridType>" + "".join(f"<{k}></{k}>" for k in MIS_EMPTY)
        params += f"<psRangeToAmt>0</psRangeToAmt><psRange>0</psRange><psRangeAmt>0</psRangeAmt><psOrgid>{org or '1,2,3'}</psOrgid>"
    return ('<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<{method} xmlns="overviewService"><Data>&lt;Grid&gt;&lt;IO/&gt;&lt;/Grid&gt;</Data>{params}</{method}></soap:Body></soap:Envelope>')


def parse(xml):
    """Rows of the TreeGrid answer: [{attribute: value}]. Pure."""
    body = html.unescape(xml)
    return [{k: html.unescape(v).strip() for k, v in ATTR.findall(m.group(1))} for m in ITEM.finditer(body)]


def run(ctx, p):
    method, org = p["method"], p.get("org")
    r = ctx.request("POST", URL, data=envelope(method, org).encode(), verify=False, timeout=300,
                    headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"overviewService/{method}"'})
    if r is None:
        return None
    tag = f"{method}-{(org or 'all').replace(',', '_')}"
    ctx.hub.upload_many([(f"raw/{tag}.xml.gz", gzip.compress(r.content, 6), "application/gzip")])
    rows = parse(r.text)
    for i, row in enumerate(rows):
        rid = row.get("id") or row.get("WorkID") or str(i)
        ctx.record(f"{tag}-{i:06d}", {**row, "grid_row": i, "grid_id": rid, "method": method, "org": org, "tls_unverified": True,
                                      "source": "mp-lppp"})
    return len(rows)
