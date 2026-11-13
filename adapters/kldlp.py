"""Kerala PWD "Defect Liability Period" work lists (pwd.kerala.gov.in, IMF website -> Projects): per wing (Roads, NH, Buildings,
Bridges, KRFB, KSTP, RICK) every work still under the contractor's defect liability: work name (often with chainage), DLP start and
end, CONTRACTOR name and phone, PWD division, subdivision and the engineers' phone numbers, as the site publishes them.
No login, no captcha. Queue item {"kind": "all"}: the wing list, then every wing's pages (the pager's links; tokens change per page).
Records: one per row, id "<wing>-<Sl.No>". Pages to the bucket as one .jsonl.gz."""
import gzip
import html
import json
import re
from urllib.parse import urljoin

from adapters.common import clean

SITE = "https://www.pwd.kerala.gov.in/IMF_website/Projects/"
START = SITE + "wings_list.php?id_ml=RU4="
WING = re.compile(r'<a[^>]+href="(work_listing_dlp\.php\?[^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
PAGER = re.compile(r"""<a[^>]+href=["']([^"']*Page=(\d+)[^"']*)["']""", re.I)
TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<(td|th)\b[^>]*>(.*?)</\1>", re.S | re.I)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def text(s):
    return clean(html.unescape(re.sub(r"<[^>]+>", " ", s)))


def parse(page):
    """(header, rows) of the DLP table. Pure."""
    page = COMMENT.sub("", page)
    header, rows = [], []
    for m in TR.finditer(page):
        cells = CELL.findall(m.group(1))
        if not cells:
            continue
        vals = [text(v) for _, v in cells]
        if all(k.lower() == "th" for k, _ in cells):
            header = [re.sub(r"[^a-z0-9]+", "_", v.lower()).strip("_") for v in vals]
        elif header and len(vals) == len(header) and vals[0].isdigit():
            rows.append(dict(zip(header, vals)))
    return header, rows


def run(ctx, p):
    r = ctx.request("GET", START, timeout=90)
    if r is None:
        return None
    wings, n, raw = [], 0, []
    for href, label in WING.findall(r.text):
        lab = text(label)
        if lab and not lab.isdigit() and lab not in [w[1] for w in wings]:     # each wing has a name link and a count link
            wings.append((href, lab))
    for href, lab in wings:
        url, seen, page_no = urljoin(SITE, html.unescape(href)), set(), 1
        while url and page_no not in seen and len(seen) < 500:
            seen.add(page_no)
            r = ctx.request("GET", url, timeout=90)
            if r is None:
                ctx.hub.failure("page", f"{lab} {page_no}", "page did not load")
                break
            raw.append(json.dumps({"wing": lab, "page": page_no, "url": url, "html": r.text}, ensure_ascii=False))
            _, rows = parse(r.text)
            for row in rows:
                sl = row.get("sl_no") or row.get(next(iter(row)))
                ctx.record(f"{re.sub('[^a-z0-9]+', '-', lab.lower())}-{sl}", {**row, "wing": lab, "source": "kerala-pwd-dlp"})
                n += 1
            nxt = sorted((int(no), h) for h, no in PAGER.findall(r.text) if int(no) not in seen)
            nxt = [x for x in nxt if x[0] == page_no + 1]
            url, page_no = (urljoin(SITE, html.unescape(nxt[0][1])), nxt[0][0]) if nxt else (None, page_no)
    ctx.hub.upload_many([("raw/kerala-dlp/pages.jsonl.gz", gzip.compress("\n".join(raw).encode(), 6), "application/gzip")])
    return n
