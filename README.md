# road-works: per-work records of road works

A family of the s1d-labs scrape pool. It collects the open works-monitoring pages of state and national road agencies: one record
per work, with the road, the costs, the progress and, where the site gives it, the contractor. The records feed road.s1d.me.

| Project | Source | Records (2026-11-14 test) | Contractor |
|---|---|---|---|
| road-works-mh-beams | Maharashtra BEAMS, PWD capital works report: work list per district and year, then one note per work | about 900 rows per district and year; one note per work | yes (work note) |
| road-works-mp-lppp | MP PWD LPPP dashboard (SOAP grids) | 13,823 completed works, 3,251 live works | yes |
| road-works-mp-rams | MPRDC RAMS ArcGIS query layers (works history, roads, inventory, bridges, tolls) | about 36,000 features | works history |
| road-works-mp-ipms | MP IPMS ArcGIS works layers | 60 features | no |
| road-works-bihar-rwd | Bihar RWD road list | 2,603 rows for Araria alone; 39 districts | no |
| road-works-ka-ngsk | Karnataka RDPR NGSK work-wise progress | 4,001 PRED works in 2025-26; 7 agencies x 15 years | no |
| road-works-kl-dlp | Kerala PWD works under defect liability | 2,678 | yes, with phone |
| road-works-paimana | MoSPI PAIMANA, central road projects of Rs 150 crore and more, per month | 974 projects (2026-09) | no |
| road-works-national | NHAI project lists (1,762), NHIDCL status (409, with contractors), Infracon tender lists (about 6,900), TN highways details-of-works PDFs, TNRSP, Kerala iROADS tiles | | NHIDCL |

- All projects run on GitHub runners through the hub's Indian proxies (`proxy="IN"`). No login, captcha, OTP or token is passed.
- Where a site's certificate chain fails (rams.mp.gov.in, the LPPP server, nhidcl.com, infracon.nic.in) the request is sent without
  certificate checks and the records say `tls_unverified`.
- Raw answers go to the bucket under `raw/` (gzip); records keep every field.

Setup: change `family.py`, then Actions -> setup. Tests: `python -m pytest tests`. One item without the hub:
`python crawl.py --local beams '{"kind": "list", "dept": "H", "year": "2025-2026", "dist": 61}'`.
