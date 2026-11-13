"""Maharashtra BEAMS (Finance Department, NIC Pune): the Public Works Department's capital works report, linked from
pwd.maharashtra.gov.in ("real-time report"). No login, no captcha: a session cookie and a Referer, like the browser sends.

Queue items:
  {"kind": "list", "dept": "H"|"T", "year": "2025-2026", "dist": 61, "dist_name": "AMRAVATI"}
      One district and budget year, all work types (road, bridge, building, other). One record per row, id
      "<dept>-<year>-<work id>", with every column of the report (work number, head of account, work name in English and Marathi,
      AA / TS / agreement cost and dates, % above or below, expenditure, physical progress, pending bill, work order date, time
      limit, work category, ROAD CATEGORY (SH / MDR number), CHAINAGE FROM / TO, taluka, constituency, division, circle, region).
      The page goes to the bucket as it came (raw/list/<dept>/<year>/<dist>.html.gz). Each work id is queued once as a "detail" item.
  {"kind": "detail", "work": "121214603083", "y1": "2024", "y2": "2025"}
      The work's one-page note: AA number, MAIN AGENCY (contractor), scope rows with chainage, and every RA bill (year, type, date,
      bill no., agency, gross, cumulative expenditure, remark). Record id "work-<work id>".
"""
import gzip
import html
import re

from adapters.common import clean

BASE = "https://beams.mahakosh.gov.in/Beams5/BudgetMVC/MISRPT/PWDWorkReports"
FORM = f"{BASE}/pwd_capitalWorkRpt.jsp"
LIST = f"{BASE}/PWDCapWorkListRpt.jsp?dept=H"
DETAIL = f"{BASE}/PWDCapitalWorkIDDtls.jsp"
DISTRICTS = {54: "AHILYANAGAR", 62: "AKOLA", 61: "AMRAVATI", 33: "BEED", 47: "BHANDARA", 63: "BULDHANA", 48: "CHANDRAPUR",
             31: "CHHATRAPATI SAMBHAJINAGAR", 35: "DHARASHIV", 52: "DHULE", 49: "GADCHIROLI", 44: "GONDIA", 38: "HINGOLI",
             53: "JALGAON", 36: "JALNA", 26: "KOLHAPUR", 37: "LATUR", 71: "MUMBAI", 46: "NAGPUR", 34: "NANDED", 55: "NANDURBAR",
             51: "NASHIK", 16: "PALGHAR", 32: "PARBHANI", 22: "PUNE", 13: "RAIGAD", 14: "RATNAGIRI", 24: "SANGLI", 23: "SATARA",
             15: "SINDHUDURG", 25: "SOLAPUR", 12: "THANE", 45: "WARDHA", 65: "WASHIM", 64: "YAVATMAL"}   # the form's list, 2026-11-14
YEARS = ["2026-2027", "2025-2026", "2024-2025", "2023-2024", "2022-2023"]

ROW = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<td\b[^>]*\btitle=\"([^\"]*)\"[^>]*>(.*?)</td>", re.S | re.I)
WORKID = re.compile(r"jFunWorkBillDetails\('(\d+)','[^']*','(\d{4})','(\d{4})'\)")
TAG = re.compile(r"<[^>]+>")
CELLS = re.compile(r"<(th|td)\b[^>]*>(.*?)(?=<(?:/?th|/?td|/?tr|/?table)\b)", re.S | re.I)


def text(s):
    return clean(html.unescape(TAG.sub(" ", s or "")))


def key(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")


def form(dept, year, dist):
    return {"Tid": "", "deptCd": dept, "adminDept": dept, "bb": "Road", "selFinYear": year, "selWorkType": "ALL", "selCategory": "0",
            "selStatutoryReg": "0", "selRegion": "0", "selCO": "0", "selDist": str(dist), "constORtaluka": "1", "selConst": "0",
            "selTaluka": "", "selUserDeptId": "0", "selScheme": "0", "selDDO": "0"}


def parse_list(page):
    """Rows of the work list: [{column: value, ..., "work_id", "y1", "y2"}]. Pure."""
    out = []
    for m in ROW.finditer(page):
        cells = CELL.findall(m.group(1))
        if not cells:
            continue
        row = {}
        for title, val in cells:
            k = key(title)
            if k and k not in row:
                row[k] = text(val)
        w = WORKID.search(m.group(1))
        if w:
            row["work_id"], row["y1"], row["y2"] = w.groups()
        if row.get("work_no"):
            out.append(row)
    return out


def parse_detail(page):
    """The one-page note: {fields: {label: value}, scope: [[...]], bills: [{...}]}. Pure."""
    seq = [(k.lower(), text(v)) for k, v in CELLS.findall(page)]
    fields, scope, bills, i = {}, [], [], 0
    while i < len(seq):
        kind, val = seq[i]
        if kind == "th" and val == "Scope":
            hdr = [v for _, v in seq[i:i + 6]]
            i += 6
            while i + 5 < len(seq) and all(k == "td" for k, _ in seq[i:i + 6]) and seq[i][1] != "":
                scope.append(dict(zip([key(h) for h in hdr], [v for _, v in seq[i:i + 6]])))
                i += 6
            continue
        if kind == "th" and val == "Financial year":
            hdr = [key(v) for _, v in seq[i:i + 8]]
            i += 8
            while i + 7 < len(seq) and all(k == "td" for k, _ in seq[i:i + 8]):
                bills.append(dict(zip(hdr, [v for _, v in seq[i:i + 8]])))
                i += 8
            continue
        if kind == "th" and val.startswith("EXP. Upto"):
            hdr = []
            while i < len(seq) and seq[i][0] == "th":
                hdr.append(seq[i][1])
                i += 1
            for h in hdr:
                if i < len(seq) and seq[i][0] == "td":
                    fields[h] = seq[i][1]
                    i += 1
            continue
        if kind == "th" and i + 1 < len(seq) and seq[i + 1][0] == "td" and val:
            fields[val] = seq[i + 1][1]
            i += 2
            continue
        if kind == "th" and val.startswith("Payment Details"):
            fields["Payment Details"] = val.partition(":")[2].strip()
        i += 1
    return {"fields": fields, "scope": scope, "bills": bills}


def _post(ctx, url, data=None, referer=FORM):
    """POST with the session the form page gives; one fresh session if the server answers its short error page."""
    for attempt in range(2):
        if attempt or not ctx.session.cookies.get("JSESSIONID"):
            if ctx.request("GET", FORM, timeout=60) is None:
                return None
        r = ctx.request("POST", url, data=data or {}, headers={"Referer": referer}, timeout=180)
        if r is not None and len(r.content) > 2500:
            return r
    return None


def run(ctx, p):
    if p["kind"] == "list":
        r = _post(ctx, LIST, form(p["dept"], p["year"], p["dist"]))
        if r is None:
            return None
        page = r.text
        ctx.hub.upload_many([(f"raw/list/{p['dept']}/{p['year']}/{p['dist']}.html.gz", gzip.compress(r.content, 6), "application/gzip")])
        rows = parse_list(page)
        for row in rows:
            ctx.record(f"{p['dept']}-{p['year']}-{row.get('work_id') or row['work_no']}",
                       {**row, "dept": p["dept"], "year": p["year"], "dist_code": p["dist"], "source": "beams-capital-works"})
        items = [{"key": f"d-{row['work_id']}", "payload": {"kind": "detail", "work": row["work_id"], "y1": row["y1"], "y2": row["y2"],
                                                            "work_no": row["work_no"]}} for row in rows if row.get("work_id")]
        if items and ctx.seed:
            for i in range(0, len(items), 500):
                ctx.seed(items[i:i + 500])
        return len(rows)
    if p["kind"] == "detail":
        url = f"{DETAIL}?workId={p['work']}&yflag=&year1={p['y1']}&year2={p['y2']}"
        r = _post(ctx, url, referer=LIST)
        if r is None:
            return None
        d = parse_detail(r.text)
        if not d["fields"]:
            ctx.hub.failure("detail", p["work"], "no fields on the work's page")
            return 0
        ctx.record(f"work-{p['work']}", {"work_id": p["work"], "work_no": p.get("work_no"), **d, "source": "beams-work-note"})
        return 1
    raise ValueError(f"unknown kind {p['kind']}")
