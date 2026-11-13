"""Bihar Rural Works Department quality report (ATR, Action Taken Report): www.rwdbihar.gov.in/report/ATR_Report.aspx.
One row per inspection of a rural road: wing (chief engineer), circle, division, scheme, road name, observation date, ATR number,
inspector (user name), awarded grade (S satisfactory, SRI needs improvement, U unsatisfactory, "Regraded to S"), contractor (name |
PAN | registration number, or name [registration]), ATR compliance, letter number and date. Public page: no login, no captcha.

The page is an ASP.NET form. Each drop-down posts back and refills the next: wing -> circle -> division. The grid shows 20 rows
per page and pages by postback (Page$N), so each page needs the view state of the page before it.
Queue items:
- {"kind": "seed"}: walks wing -> circle -> division and queues one "div" item per division (about 30 circles; the whole road
  report is about 1,200 pages, 24,000 rows), plus one "type" item each for the bridge and the maintenance report.
- {"kind": "div", "wing": "1", "circle": "4", "division": "12", "names": [...]}: selects wing, circle and division, then reads
  every page of the road grid. One record per row; all pages of the division go to the bucket as one gzipped file.
- {"kind": "type", "type": "rdnBridge" | "rdnMaintn"}: the bridge or maintenance report (all wings), every page.
A division whose grid has no rows gives 0 records (not a failure)."""
import gzip
import html
import json
import re

from adapters.common import clean, sha1

URL = "https://www.rwdbihar.gov.in/report/ATR_Report.aspx"
HIDDEN = re.compile(r'<input type="hidden" name="(__[A-Z]+)" id="__[A-Z]+" value="([^"]*)"')
SELECTS = ("ddlWing", "ddlCircle", "ddlDivision", "ddlScheme", "ddlroadatr")
GRID = {"rdnRoad": "gvATRRoadGen", "rdnBridge": "gvATRBridgeGen", "rdnMaintn": "gvATRMaintenance"}
COLS = ["sl_no", "wing", "circle", "division", "scheme", "road_name", "observation_date", "atr_no", "user_name", "awarded_grade",
        "contractor", "atr_compliance", "letter_no", "letter_date"]
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
TD = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
PAN = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")


def options(page, name):
    """[(value, text)] of a drop-down. Pure."""
    m = re.search(r'<select name="%s".*?</select>' % name, page, re.S)
    if not m:
        return []
    return [(v, clean(html.unescape(t))) for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>(.*?)</option>', m.group(0), re.S)]


def selected(page, name):
    m = re.search(r'<select name="%s".*?</select>' % name, page, re.S)
    s = re.search(r'<option selected="selected" value="([^"]*)"', m.group(0)) if m else None
    return s.group(1) if s else "0"


def form(page, qmc):
    f = {k: html.unescape(v) for k, v in HIDDEN.findall(page)}
    for n in SELECTS:
        f[n] = selected(page, n)
    f.update({"QMC": qmc, "txtSrcByRoad": "", "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__LASTFOCUS": ""})
    return f


def split_contractor(text):
    """'M/S X AND CO. | AAHFR8155J | 1150233' -> name, PAN, registration. 'Name (904/09)' / 'Name [ 78/08 2nd Class ]' keep the
    registration in brackets. Pure."""
    parts = [p.strip() for p in text.split("|")]
    name, pan, reg = parts[0], "", ""
    rest = parts[1:]
    for p in rest:
        if PAN.fullmatch(p):
            pan = p
        elif p:
            reg = p
    if not rest:
        m = re.match(r"(.*?)\s*[\[(]\s*([^\])]*?)\s*[\])]\s*$", name)
        if m and re.search(r"\d", m.group(2)):
            name, reg = m.group(1), m.group(2)
        m = PAN.search(name)
        if m:
            pan = m.group(1)
    return name, pan, reg


def parse(page, grid="gvATRRoadGen"):
    """Rows of one grid page: [{sl_no, wing, ..., contractor, contractor_name, contractor_pan, contractor_reg}]. Pure."""
    t = re.search(r'<table[^>]*id="%s".*' % grid, page, re.S)
    if not t:
        return []
    out = []
    for m in TR.finditer(t.group(0)):
        if "<table" in m.group(1) or "Page$" in m.group(1):      # the pager row
            continue
        cells = [clean(html.unescape(re.sub(r"<[^>]+>", " ", c)).replace("&nbsp", " ").replace("\xa0", " ")) for c in TD.findall(m.group(1))]
        if len(cells) < 11 or not re.fullmatch(r"\d+", cells[0]):
            continue
        row = dict(zip(COLS, cells))
        row["contractor_name"], row["contractor_pan"], row["contractor_reg"] = split_contractor(row.get("contractor", ""))
        out.append(row)
    return out


def current_page(page, grid):
    """The page number the pager marks as current (a <span>), 1 when the grid has no pager. Pure."""
    t = re.search(r'<table[^>]*id="%s".*' % grid, page, re.S)
    nums = re.findall(r"<span>(\d+)</span>", t.group(0)) if t else []
    return int(nums[-1]) if nums else 1


def has_page(page, grid, n):
    return f"__doPostBack(&#39;{grid}&#39;,&#39;Page${n}&#39;)" in page


class Form:
    def __init__(self, ctx, qmc="rdnRoad"):
        self.ctx, self.qmc, self.page = ctx, qmc, None

    def get(self):
        r = self.ctx.request("GET", URL, timeout=120)
        self.page = r.text if r is not None else None
        return self.page

    def post(self, target, arg="", **fields):
        f = form(self.page, self.qmc)
        f.update({"__EVENTTARGET": target, "__EVENTARGUMENT": arg, **fields})
        if target in SELECTS:      # a new upper choice resets the lower ones
            for low in SELECTS[SELECTS.index(target) + 1:3]:
                f[low] = "0"
        r = self.ctx.request("POST", URL, data=f, headers={"Referer": URL}, timeout=180)
        self.page = r.text if r is not None else None
        return self.page


def all_pages(ctx, fm, grid, label):
    """Read every page of the grid now shown; returns (rows, raw pages). A missed page fails the item (the hub retries it)."""
    rows, raw = parse(fm.page, grid), [fm.page]
    n = 1
    while has_page(fm.page, grid, n + 1):
        if fm.post(grid, f"Page${n + 1}") is None:
            raise RuntimeError(f"{label}: page {n + 1} did not answer")
        got = current_page(fm.page, grid)
        if got != n + 1:
            raise RuntimeError(f"{label}: asked page {n + 1}, got {got}")
        n += 1
        rows += parse(fm.page, grid)
        raw.append(fm.page)
    return rows, raw


def save(ctx, path, raw):
    body = "\n<!-- page break -->\n".join(raw).encode("utf-8", "replace")
    ctx.hub.upload_many([(path, gzip.compress(body, 6), "application/gzip")])


def put(ctx, rows, extra, tag):
    for r in rows:
        k = sha1(tag, r.get("wing"), r.get("circle"), r.get("division"), r.get("scheme"), r.get("road_name"), r.get("observation_date"),
                 r.get("atr_no"), r.get("user_name"), r.get("awarded_grade"), r.get("contractor"))[:20]
        ctx.record(f"atr-{tag}-{k}", {**r, **extra, "source": "bihar-rwd-atr", "url": URL})


def run(ctx, p):
    kind = p.get("kind")
    if kind == "seed":
        fm = Form(ctx)
        if fm.get() is None:
            return None
        items = [{"key": f"type-{t}", "payload": {"kind": "type", "type": t}} for t in ("rdnBridge", "rdnMaintn")]
        for w, wn in options(fm.page, "ddlWing"):
            if w == "0":
                continue
            if fm.post("ddlWing", ddlWing=w) is None:
                return None
            wing_page = fm.page
            for c, cn in options(wing_page, "ddlCircle"):
                if c == "0":
                    continue
                fm.page = wing_page
                if fm.post("ddlCircle", ddlWing=w, ddlCircle=c) is None:
                    return None
                for d, dn in options(fm.page, "ddlDivision"):
                    if d == "0":
                        continue
                    items.append({"key": f"div-{w}-{c}-{d}", "payload": {"kind": "div", "wing": w, "circle": c, "division": d,
                                                                         "names": [wn, cn, dn]}})
        ctx.seed(items)
        ctx.record("atr-seed", {"divisions": sum(1 for i in items if i["payload"]["kind"] == "div"), "items": [i["key"] for i in items],
                                "source": "bihar-rwd-atr", "url": URL})
        return len(items)
    if kind == "div":
        fm = Form(ctx)
        if fm.get() is None or fm.post("ddlWing", ddlWing=p["wing"]) is None:
            return None
        if fm.post("ddlCircle", ddlWing=p["wing"], ddlCircle=p["circle"]) is None:
            return None
        if fm.post("ddlDivision", ddlWing=p["wing"], ddlCircle=p["circle"], ddlDivision=p["division"]) is None:
            return None
        if selected(fm.page, "ddlDivision") != str(p["division"]):
            raise RuntimeError("division not selected after postback")
        grid = GRID["rdnRoad"]
        rows, raw = all_pages(ctx, fm, grid, f"div {p['division']}")
        save(ctx, f"raw/rwd-atr/road-{p['wing']}-{p['circle']}-{p['division']}.html.gz", raw)
        put(ctx, rows, {"report": "road", "wing_code": p["wing"], "circle_code": p["circle"], "division_code": p["division"],
                        "pages": len(raw)}, "road")
        return len(rows)
    if kind == "type":
        t = p["type"]
        fm = Form(ctx, t)
        if fm.get() is None or fm.post(t) is None:
            return None
        grid = GRID[t]
        rows, raw = all_pages(ctx, fm, grid, t)
        save(ctx, f"raw/rwd-atr/{t}.html.gz", raw)
        put(ctx, rows, {"report": {"rdnBridge": "bridge", "rdnMaintn": "maintenance"}[t], "pages": len(raw)}, t)
        return len(rows)
    raise ValueError(f"unknown kind {kind!r}")


if __name__ == "__main__":      # parse a saved page: python -m adapters.rwdatr page.html
    import sys
    print(json.dumps(parse(open(sys.argv[1], errors="replace").read())[:3], indent=1, ensure_ascii=False))
