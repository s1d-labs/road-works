"""What this family scrapes: per-work records of road works that state and national agencies publish on open monitoring pages,
so a road on road.s1d.me can show its works, contractor, cost and progress. Task crawl: one adapter per site (adapters/);
task arcgis: public ArcGIS layers with object ids (copy of road-maps' arcgis.py).

  road-works-mh-beams    Maharashtra PWD capital works (BEAMS, Finance Dept): every work per district and budget year, with road
                         category (SH / MDR number), chainage, costs, expenditure, division; then each work's note with the
                         contractor and every RA bill (queued by the list items, one item per work id).
  road-works-mp-lppp     Madhya Pradesh PWD LPPP dashboard: completed works with contractor, live works with agency.
  road-works-mp-rams     MPRDC road asset system (ArcGIS): works history with chainage and contractor, road list, ongoing works,
                         state highways, MDRs, road inventory, bridges, black spots, toll plazas.
  road-works-mp-ipms     MP IPMS works layers (ArcGIS): roads, buildings, bridges with AA / TS numbers.
  road-works-bihar-rwd   Bihar RWD road list per district: road, block, scheme, status.
  road-works-ka-ngsk     Karnataka RDPR works per agency, year and district: work name with km, AA, amount, payment, status.
  road-works-kl-dlp      Kerala PWD works under defect liability: work, contractor and phone, division, DLP dates.
  road-works-paimana     MoSPI PAIMANA monthly status of central road projects of Rs 150 crore and more.
  road-works-national    NHAI project lists, NHIDCL project status with contractors, Infracon consultancy tender lists, Tamil Nadu
                         highways budget "details of works" PDFs, TNRSP contracts, Kerala iROADS road-section map tiles.

Indian government servers: workers go through the hub's Indian proxies (proxy="IN"). No login, captcha or OTP is passed anywhere.
Not collected (walls, 2026-11-14): MH PMIS (login + captcha), UP PWD Srishti / geofence (login; a static API key in the page JS:
owner's call), MP Lok Path RIMS (token, OTP), Odisha works dashboard (login, signed API), Punjab PWIMS (login + captcha), KSHIP PMS
(401), Kerala iROADS DLP API (a fixed key printed in the page: owner's call), NHAI toll system (down), IHMCL (Cloudflare check),
PM GatiShakti (login), MoRTH PMIS (403), data.gov.in files (login; the API with the published sample key: owner's call).
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
FAMILY = json.loads((HERE / "scrape.json").read_text())["family"]

BEAMS_DIST = {54: "AHILYANAGAR", 62: "AKOLA", 61: "AMRAVATI", 33: "BEED", 47: "BHANDARA", 63: "BULDHANA", 48: "CHANDRAPUR",
              31: "CHHATRAPATI SAMBHAJINAGAR", 35: "DHARASHIV", 52: "DHULE", 49: "GADCHIROLI", 44: "GONDIA", 38: "HINGOLI",
              53: "JALGAON", 36: "JALNA", 26: "KOLHAPUR", 37: "LATUR", 71: "MUMBAI", 46: "NAGPUR", 34: "NANDED", 55: "NANDURBAR",
              51: "NASHIK", 16: "PALGHAR", 32: "PARBHANI", 22: "PUNE", 13: "RAIGAD", 14: "RATNAGIRI", 24: "SANGLI", 23: "SATARA",
              15: "SINDHUDURG", 25: "SOLAPUR", 12: "THANE", 45: "WARDHA", 65: "WASHIM", 64: "YAVATMAL"}   # the form's list, 2026-11-14
BEAMS_YEARS = ["2026-2027", "2025-2026", "2024-2025", "2023-2024", "2022-2023"]
BEAMS_DONE_YEARS = ["2025-2026", "2024-2025", "2023-2024", "2022-2023", "2021-2022"]     # the completed works report's years
BIHAR = {7: "Araria", 33: "Arwal", 35: "Aurangabad", 23: "Banka", 20: "Begusarai", 22: "Bhagalpur", 29: "Bhojpur", 30: "Buxar",
         13: "Darbhanga", 2: "EastChamparan", 36: "Gaya", 15: "Gopalganj", 38: "Jamui", 34: "Jehanabad", 31: "Kaimur", 10: "Katihar",
         21: "Khagaria", 8: "Kishanganj", 25: "Lakhisarai", 11: "Madhepura", 5: "Madhubani", 24: "Munger", 14: "Muzaffarpur",
         27: "Nalanda", 37: "Nawada", 39: "Others", 28: "Patna", 9: "Purnea", 32: "Rohtas", 12: "Saharsa", 19: "Samastipur",
         17: "Saran", 26: "Sheikhpura", 3: "Sheohar", 4: "Sitamarhi", 16: "Siwan", 6: "Supaul", 18: "Vaishali", 1: "WestChamparan"}
NGSK_YEARS = {11: "2012-13", 9: "2013-14", 10: "2014-15", 6: "2015-16", 7: "2016-17", 8: "2017-18", 3: "2018-19", 4: "2019-20",
              5: "2020-21", 1: "2021-22", 2: "2022-23", 12: "2023-24", 13: "2024-25", 14: "2025-26", 15: "2026-27"}
NGSK_AGENCIES = {1: "KRRDA", 4: "PRED", 8: "RWS", 9: "TP", 10: "HD", 11: "NK", 12: "KTIL"}
PAIMANA_MONTHS = [f"{y}-{m:02d}" for y in (2025, 2026) for m in range(1, 13) if "2025-07" <= f"{y}-{m:02d}" <= "2026-09"]

NHAI = "https://nhai.gov.in/assets/json"
TNF = "https://www.financedept.tn.gov.in/en/my-documents/2020/07"
TN_PDF = [("tn-dow-highways-2025-26", f"{TNF}/Publication_No_59-1.pdf"), ("tn-dow-highways-2024-25", f"{TNF}/Publication_No_59.pdf"),
          ("tn-dow-highways-2023-24", f"{TNF}/Demand-No_59_DETAILS-OF-WORKS-FOR-HIGHWAYS.pdf")] + \
         [(f"tn-dow-highways-{y}-{y % 100 + 1:02d}", f"{TNF}/{y}-{y + 1}_p59.pdf") for y in range(2017, 2023)]
RMMS = "https://pwdrmms.kerala.gov.in/citizen"
KL_TILES = [(x, y) for x in range(1449, 1465) for y in range(950, 978)]     # zoom 11 over Kerala (sea tiles are empty)


def _file(name, url, mode, **kw):
    return {"key": name, "payload": {"name": name, "url": url, "mode": mode, **kw}}


# nhai.gov.in answers only the hub proxies 91.124.42.x: the national project borrows only those (proxy_only)
NATIONAL = (
    [_file(f"nhai-{n}", f"{NHAI}/get_{n}_projects.json", "json-data") for n in ("ui", "om", "dpr_in_progress", "target_in_cfy", "to_be_awarded")]
    + [_file("nhidcl-status", "https://nhidcl.com/en/current-status", "find-xlsx", verify=False)]
    + [_file(f"infracon-{n}", f"https://infracon.nic.in/projects.asp?nid={n}", "html-table", warm="https://infracon.nic.in/", verify=False)
       for n in range(1, 6)]
    + [_file(n, u, "raw", ext="pdf") for n, u in TN_PDF]
    + [_file("tnrsp-site-data", "https://www.tnrsp.tn.gov.in/data.temp.json", "raw", ext="json")]
    + [_file(f"kl-iroads-11-{x}-{y}", f"{RMMS}/kstp-network-sections/11/{x}/{y}.mvt", "raw", ext="mvt", referer=f"{RMMS}/portal/")
       for x, y in KL_TILES]
)

RAMS = "https://rams.mp.gov.in/arcgis/rest/services/mprams"
RAMS_LAYERS = ["WORKSHISTORY", "MPRDC_WORKSHIST", "MPRDC_WORKS_ONGOING_UPCOMING", "SearchAllRoad", "StateHighway", "MajorDistrictRoad",
               "ADVANCEROADINVENTORY", "BRIDGE", "BlackSpot", "TollPlaza"]   # query layers without object ids: adapters/rams.py
IPMS = "https://gis.autodcr.com/server/rest/services/IPMS_GISLAYERS_LIVE/FeatureServer"


def _proj(name, title, adapter, items, unit, record, workers=2, delay_ms=1000, target="", task="crawl", proxy_only=None):
    return {"proxy_only": proxy_only, "name": f"{FAMILY}-{name}", "title": title, "task": task, "target": target, "env": {"ADAPTER": adapter} if adapter else {},
            "proxy": "IN", "max_workers": workers, "delay_ms": delay_ms, "unit_label": unit, "record_label": record, "items": items}


PROJECTS = [
    _proj("mh-beams", "Maharashtra PWD capital works (BEAMS): every work with road category, chainage, cost, expenditure, contractor and RA bills",
          "beams", [{"key": f"l-{d}-{y}-{c}", "payload": {"kind": "list", "dept": d, "year": y, "dist": c, "dist_name": n}}
                    for d in ("H", "T") for y in BEAMS_YEARS for c, n in BEAMS_DIST.items()]
                   + [{"key": f"c-{y}-{t}-{c}", "payload": {"kind": "completed", "dept": "H", "year": y, "worktype": t, "dist": c, "dist_name": n}}
                      for y in BEAMS_DONE_YEARS for t in ("ROAD", "BRIDGE") for c, n in BEAMS_DIST.items()],
          "district list or work note", "work row or work note", workers=3, delay_ms=700, target="beams.mahakosh.gov.in"),
    _proj("mp-lppp", "Madhya Pradesh PWD LPPP dashboard: completed works with contractor, live works with agency",
          "lppp", [{"key": "completed-pwdbr", "payload": {"method": "GetCompletedWorks_PWDBR"}},
                   {"key": "completed-pwdbhawan", "payload": {"method": "GetCompletedWorks_PWDBHAWAN"}},
                   {"key": "mis-1-2-3", "payload": {"method": "GetMISReportData", "org": "1,2,3"}}],
          "grid", "work", workers=1, delay_ms=3000, target="52.172.154.79"),
    _proj("mp-rams", "MPRDC road asset system (ArcGIS): works history with chainage and contractor, roads, bridges, black spots, tolls",
          "rams", [{"key": l.lower(), "payload": {"layer": l.lower(), "url": f"{RAMS}/{l}/MapServer/0"}} for l in RAMS_LAYERS],
          "layer", "feature", workers=1, delay_ms=1500, target="rams.mp.gov.in"),
    _proj("mp-ipms", "Madhya Pradesh IPMS works layers (ArcGIS): roads, buildings, bridges with AA and TS numbers",
          "", [{"key": f"count-ipms{n}", "payload": {"url": f"{IPMS}/{n}", "name": f"ipms{n}", "size": 1000}} for n in (0, 1, 2)],
          "page of features", "page", workers=1, delay_ms=1500, target="gis.autodcr.com", task="arcgis"),
    _proj("bihar-rwd", "Bihar Rural Works Department road list: road, block, scheme, status per district",
          "rwdbihar", [{"key": f"d-{c}", "payload": {"district": c, "district_name": n}} for c, n in BIHAR.items()],
          "district", "road", workers=1, delay_ms=3000, target="rwdbihar.gov.in"),
    _proj("ka-ngsk", "Karnataka RDPR works (NGSK): work-wise progress per agency, year and district",
          "ngsk", [{"key": f"a{a}-y{y}", "payload": {"year": y, "year_name": yn, "agency": a, "agency_name": an}}
                   for a, an in NGSK_AGENCIES.items() for y, yn in NGSK_YEARS.items()],
          "agency and year", "work", workers=2, delay_ms=1000, target="ngsk.karnataka.gov.in"),
    _proj("kl-dlp", "Kerala PWD works under defect liability: contractor, phone, division, DLP dates",
          "kldlp", [{"key": "all", "payload": {"kind": "all"}}], "wing list", "work", workers=1, delay_ms=1500, target="www.pwd.kerala.gov.in"),
    _proj("paimana", "MoSPI PAIMANA: monthly status of central road projects of Rs 150 crore and more (cost, expenditure, progress, dates)",
          "paimana", [{"key": f"m-{m}", "payload": {"month": m, "sector": 107}} for m in PAIMANA_MONTHS],
          "month", "project-month", workers=1, delay_ms=2000, target="paimana-proj.mospi.gov.in"),
    _proj("national", "NHAI project lists, NHIDCL project status with contractors, Infracon tender lists, TN highways works PDFs, Kerala iROADS tiles",
          "files", NATIONAL, "file", "row or file", workers=2, delay_ms=1000, target="nhai.gov.in", proxy_only=["91.124.42."]),
]

BEAMS_FORM = "https://beams.mahakosh.gov.in/Beams5/BudgetMVC/MISRPT/PWDWorkReports/pwd_capitalWorkRpt.jsp"
PROBES = [{"name": f"{FAMILY}:beams.mahakosh.gov.in", "url": BEAMS_FORM, "expect": "selFinYear"},
          {"name": f"{FAMILY}:ngsk.karnataka.gov.in", "url": "https://ngsk.karnataka.gov.in/Reports/WorkWiseProgressReport", "expect": "FinancialYearId"}]
PROJECTS[0]["probe"] = PROBES[0]["name"]
PROJECTS[5]["probe"] = PROBES[1]["name"]
assert PROJECTS[0]["name"].endswith("mh-beams") and PROJECTS[5]["name"].endswith("ka-ngsk")
