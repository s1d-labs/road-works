"""Small public files and pages, fetched once and stored as they came, with a record per row where the file is a table.

Queue item {"name": "...", "url": "...", "mode": ...}:
  json-data   NHAI's project lists (nhai.gov.in/assets/json/*.json): {"data": [...]}, one record per project (id: UPC or row).
  html-table  a page whose <table> rows are the data (Infracon consultancy tender lists): one record per row with the header names.
  find-xlsx   a page that links the file (NHIDCL "current status"): the newest .xlsx link on it is stored; every sheet row is a record.
  raw         store only (PDF budget volumes, JSON with embedded tables, map tiles); a PDF also gets its text layer stored as .txt.
  post-json   a JSON POST (Karnataka Mahiti Kanaja KRDCL projects): "body" is sent as JSON; list rows become records.
Files go to raw/files/<name>.<ext>[.gz]."""
import gzip
import html
import io
import json
import re
from urllib.parse import urljoin

from adapters.common import clean, pdf_text, sha1

TR = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S | re.I)
CELL = re.compile(r"<(td|th)\b[^>]*>(.*?)</\1>", re.S | re.I)
XLSX = re.compile(r'href="([^"]+\.xlsx)"', re.I)


def text(s):
    return clean(html.unescape(re.sub(r"<[^>]+>", " ", s)))


def table_rows(page):
    """[{header: cell}] of every table row that has as many cells as the latest header row. Pure."""
    header, out = [], []
    for m in TR.finditer(re.sub(r"<!--.*?-->", "", page, flags=re.S)):
        cells = CELL.findall(m.group(1))
        if not cells:
            continue
        vals = [text(v) for _, v in cells]
        links = re.findall(r'href="([^"]+)"', m.group(1))
        if all(k.lower() == "th" for k, _ in cells) or re.match(r"(s\.?\s*no|sl\.?\s*no|sr\.?\s*no)\b", vals[0], re.I):
            header = [re.sub(r"[^a-z0-9]+", "_", v.lower()).strip("_") or f"c{i}" for i, v in enumerate(vals)]
        elif header and len(vals) == len(header):
            row = dict(zip(header, vals))
            if links:
                row["links"] = links
            out.append(row)
    return out


def xlsx_rows(data):
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = [[("" if v is None else str(v)) for v in r] for r in ws.iter_rows(values_only=True)]
        hi = max(range(min(len(rows), 10)), key=lambda i: sum(1 for v in rows[i] if v.strip()), default=0)
        header = [re.sub(r"[^a-z0-9]+", "_", h.lower()).strip("_") or f"c{i}" for i, h in enumerate(rows[hi] if rows else [])]
        for i, r in enumerate(rows[hi + 1:], start=hi + 2):
            if any(v.strip() for v in r):
                yield ws.title, i, dict(zip(header, r))


def store(ctx, name, r, ext):
    data = r.content
    path = f"raw/files/{name}.{ext}" + ("" if ext in ("pdf", "xlsx", "gz") else ".gz")
    files = [(path, data if ext in ("pdf", "xlsx", "gz") else gzip.compress(data, 6), "application/octet-stream")]
    if ext == "pdf":
        t, pages = pdf_text(data)
        if t.strip():
            files.append((f"raw/files/{name}.pdf.txt", t.encode(), "text/plain"))
    ctx.hub.upload_many(files)
    return path


def run(ctx, p):
    name, url, mode = p["name"], p["url"], p["mode"]
    kw = {"timeout": 300, "verify": p.get("verify", True)}     # verify False only where the certificate fails (owner OK 2026-11-11)
    tls = {"tls_unverified": True} if kw["verify"] is False else {}
    if p.get("warm"):                                   # some sites set a cookie on the home page first (Infracon)
        ctx.request("GET", p["warm"], **kw)
    if mode == "post-json":
        r = ctx.request("POST", url, json=p["body"], headers={"Referer": p.get("referer", url)}, **kw)
    else:
        r = ctx.request("GET", url, headers={"Referer": p.get("referer", url)}, **kw)
    if r is None:
        return None
    if mode == "find-xlsx":
        links = XLSX.findall(r.text)
        if not links:
            ctx.hub.failure("no-file", url, "no .xlsx link on the page")
            return 0
        furl = urljoin(url, html.unescape(links[0]))
        f = ctx.request("GET", furl, **kw)
        if f is None:
            return None
        stamp = re.sub(r"[^0-9-]", "", furl.rsplit("_", 1)[-1])[:10] or sha1(furl)[:8]
        path = store(ctx, f"{name}-{stamp}", f, "xlsx")
        n = 0
        for sheet, i, row in xlsx_rows(f.content):
            ctx.record(f"{name}-{stamp}-{sheet}-{i}", {**row, "sheet": sheet, "row": i, "file": path, "url": furl, "source": name, **tls})
            n += 1
        return n
    ext = p.get("ext") or ("pdf" if r.content[:5] == b"%PDF-" else "json" if mode in ("json-data", "post-json") else "html")
    path = store(ctx, name, r, ext)
    if mode == "raw":
        ctx.record(f"{name}-file", {"url": url, "file": path, "bytes": len(r.content), "source": name, **tls})
        return 1
    if mode in ("json-data", "post-json"):
        d = r.json()
        if isinstance(d, str):
            try:
                d = json.loads(d)
            except ValueError:
                pass
        rows = d.get("data") if isinstance(d, dict) and isinstance(d.get("data"), list) else d
        if isinstance(rows, dict):
            rows = next((v for v in rows.values() if isinstance(v, list)), [rows])
        if not isinstance(rows, list):
            rows = [{"value": rows}]
        for i, row in enumerate(rows):
            row = row if isinstance(row, dict) else {"value": row}
            ctx.record(f"{name}-{i:05d}", {**row, "row": i, "file": path, "source": name, **tls})
        return len(rows)
    if mode == "html-table":
        rows = table_rows(r.text)
        for i, row in enumerate(rows):
            ctx.record(f"{name}-{i:05d}", {**row, "row": i, "file": path, "source": name, **tls})
        return len(rows)
    raise ValueError(f"unknown mode {mode}")
