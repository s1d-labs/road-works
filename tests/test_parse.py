"""Parsers on saved pages (2026-11-14). Run: python -m pytest tests"""
from pathlib import Path

from adapters import beams, kldlp, lppp, ngsk, rwdbihar
from adapters.files import table_rows

PAGES = Path(__file__).parent / "pages"


def page(name):
    return (PAGES / name).read_text(errors="replace")


def test_beams_list():
    rows = beams.parse_list(page("beams_list.html"))
    assert len(rows) == 3
    r = rows[0]
    assert r["work_id"].isdigit() and r["work_no"] and r["district"] == "THANE"
    assert {"name_of_the_work", "road_category", "chainage_from", "chainage_to", "pw_division"} <= set(r)


def test_beams_detail():
    d = beams.parse_detail(page("beams_detail.html"))
    assert d["fields"]["Main Agency Name"] == "M/s G H Khandelwal"
    assert d["fields"]["Administrative Approval No."] == "SH-3612/CR-1823/ PLN-3"
    assert d["bills"][1]["name_of_agency"] == "M/s G H Khandelwal" and d["bills"][1]["gross_amount_rs"] == "3199072"


def test_bihar_rwd():
    rows = rwdbihar.parse(page("bihar_rwd.html"))
    assert [r["row"] for r in rows] == [0, 1, 2]
    assert rows[0]["road"] == "Mushari pul to Gawaspur via Sadarpur School" and rows[1]["status"] == "Retender"


def test_lppp():
    rows = lppp.parse(page("lppp_completed.xml"))
    assert len(rows) == 3 and rows[0].get("ContractorName") and rows[0].get("WorkName")


def test_kerala_dlp():
    _, rows = kldlp.parse(page("kerala_dlp.html"))
    assert len(rows) == 50 and rows[0]["name_of_contractor"] and rows[0]["dlp_end_date"]


def test_ngsk():
    rows = ngsk.parse(page("ngsk.html"))
    assert len(rows) == 3 and rows[0]["work_id"].startswith("34A/") and rows[0]["district"] == "BAGALKOTE"


def test_table_rows():
    html = "<table><tr><td>S.No</td><td>Project Name</td></tr><tr><td>1</td><td>NH-48 km 10 to 20</td></tr></table>"
    assert table_rows(html) == [{"s_no": "1", "project_name": "NH-48 km 10 to 20"}]
