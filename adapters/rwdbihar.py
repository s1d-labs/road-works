"""Bihar Rural Works Department (rwdbihar.gov.in): the road list on the home page (ASP.NET form: year, district, block, scheme).
No login, no captcha. Queue item {"district": 33, "district_name": "Arwal"}: one postback with year, block and scheme = all gives
every road of the district: year, district, block, road name, scheme (PMGSY, MMGSY, RRSMP, ...), status (complete, ongoing,
AA, retender, rescinded ...). One record per row (id: hash of the row), the answer page to the bucket as it came.
The home page's view state is about 0.7 MB; the district answer is up to 6 MB."""
import gzip
import html
import re

from adapters.common import clean, sha1

URL = "https://rwdbihar.gov.in/Default.aspx"
HIDDEN = re.compile(r'<input type="hidden" name="(__[A-Z]+)" id="__[A-Z]+" value="([^"]*)"')
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
VIEW = re.compile(r"RpReport_lnkView_(\d+)")
COLS = ["year", "district", "block", "road", "scheme", "status"]


def parse(page):
    """Rows of the road list (items and alternating items of the repeater): [{year, district, block, road, scheme, status, row}].
    Pure."""
    out = []
    for m in TR.finditer(page):
        v = VIEW.search(m.group(1))
        if not v:
            continue
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", c))) for c in TD.findall(m.group(1))]
        out.append({**dict(zip(COLS, cells[:6])), "row": int(v.group(1))})
    return out


def run(ctx, p):
    r = ctx.request("GET", URL, timeout=180)
    if r is None:
        return None
    form = {k: html.unescape(v) for k, v in HIDDEN.findall(r.text)}
    form.update({"__EVENTTARGET": "", "__EVENTARGUMENT": "", "ctl00$ContentPlaceHolder1$drpYear": "0",
                 "ctl00$ContentPlaceHolder1$ddlDistrict": str(p["district"]), "ctl00$ContentPlaceHolder1$ddlBlock": "0",
                 "ctl00$ContentPlaceHolder1$ddlScheme": "0", "ctl00$ContentPlaceHolder1$btnSubmit": "Submit"})
    r = ctx.request("POST", URL, data=form, headers={"Referer": URL}, timeout=300)
    if r is None:
        return None
    ctx.hub.upload_many([(f"raw/rwd-list/{p['district']}.html.gz", gzip.compress(r.content, 6), "application/gzip")])
    rows = parse(r.text)
    for row in rows:
        k = sha1(p["district"], row.get("year"), row.get("block"), row.get("road"), row.get("scheme"), row["row"])[:16]
        ctx.record(f"rwd-{p['district']}-{k}", {**row, "district_code": p["district"], "source": "bihar-rwd-road-list"})
    return len(rows)
