"""Parsers on saved pages (2026-11-14). Run: python -m pytest tests"""
from pathlib import Path

from adapters import beams, kldlp, lppp, ngsk, rwdatr, rwdbihar
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


def test_beams_work_id():
    assert beams.work_id("DEC/12/146/03083") == "121214603083"
    assert beams.work_id("MAR/10/441/10432") == "100344110432"
    assert beams.work_id("bad") is None


def test_bihar_atr():
    last = page("bihar_atr_last.html")
    rows = rwdatr.parse(last)
    assert len(rows) == 6 and rwdatr.current_page(last, "gvATRRoadGen") == 1192
    assert not rwdatr.has_page(last, "gvATRRoadGen", 1193)
    r = rows[-1]
    assert r["awarded_grade"] == "U" and r["atr_no"] == "7408" and r["letter_no"] == "710" and r["division"] == "Virpur"
    p2 = page("bihar_atr_p2.html")
    assert rwdatr.current_page(p2, "gvATRRoadGen") == 2 and rwdatr.has_page(p2, "gvATRRoadGen", 3)
    assert len(rwdatr.parse(p2)) == 20 and rwdatr.selected(p2, "ddlDivision") == "2"
    m = rwdatr.parse(page("bihar_atr_maint.html"), "gvATRMaintenance")
    assert len(m) == 17 and m[0]["contractor_name"] == "Brahmdeo Yadav" and m[0]["contractor_reg"] == "904/09"
    assert rwdatr.split_contractor("M/S RAMJEE SINGH AND CO. | AAHFR8155J | 1150233") == ("M/S RAMJEE SINGH AND CO.", "AAHFR8155J", "1150233")


def test_page_keys():
    from adapters import datagovin, iroads
    js = "var headers = { 'shared-public-key': '0123456789abcdef0123456789abcdef', 'TenantId': 'kstp'}"
    assert iroads.page_key(js) == ("0123456789abcdef0123456789abcdef", "kstp")
    assert iroads.page_key("no key here") == (None, None)
    assert datagovin.page_key(['x', 'VUE_APP_ENVIRONMENT_TYPE:"prod",VUE_APP_APIKEY:"00aa11bb22cc33dd44ee55ff6677"']) == "00aa11bb22cc33dd44ee55ff6677"
    assert datagovin.ROAD.search("State-wise length of National Highways") and not datagovin.ROAD.search("Rainfall in Kerala")
