"""Outil de développement : télécharge les réponses brutes de toutes les sources
et les enregistre dans probe_out/ pour écrire et tester les lecteurs.
Ne sert pas au site."""
import datetime as dt
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from net import get  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "probe_out")
os.makedirs(OUT, exist_ok=True)
cfg = json.load(open(os.path.join(ROOT, "config", "countries.json"), encoding="utf-8"))
C = cfg["countries"]
codes = [c["code"] for c in C]
start = (dt.date.today() - dt.timedelta(days=30)).isoformat()

urls = {}
urls["bis_cbpol"] = f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{'+'.join(codes)}?startPeriod={start}&format=csv"
urls["bis_cpi"] = f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LONG_CPI/1.0/M.{'+'.join(codes)}.771?startPeriod=2026-01&format=csv"
ccys = sorted({c["currency"] for c in C} - {"EUR"})
urls["ecb_fx"] = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{'+'.join(ccys)}.EUR.SP00.A?startPeriod={start}&format=csvdata"
urls["ecb_dfr"] = f"https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?startPeriod={start}&format=csvdata"
urls["valet"] = "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=5"
for s in ["DFEDTARU", "DFEDTARL"] + [c["fred_10y"] for c in C if c.get("fred_10y")] + \
         ["IRLTLT01BRM156N", "IRLTLT01TRM156N", "IRLTLT01CNM156N", "IRLTLT01IDM156N", "IRLTLT01INM156N"]:
    urls["fred_" + s] = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}&cosd=2025-01-01"
for c in C:
    if c.get("calendar"):
        urls[f"cal_{c['code']}"] = c["calendar"]["url"]
    if c.get("target"):
        urls[f"target_{c['code']}"] = c["target"]["url"]
extra = json.load(open(os.path.join(os.path.dirname(__file__), "probe_extra.json"), encoding="utf-8"))
urls.update(extra)

summary = {}
for name, url in urls.items():
    try:
        r = get(url, browser=True, tries=2, timeout=40)
        body = r.content
        ext = "json" if "json" in r.headers.get("content-type", "") else ("csv" if "csv" in r.headers.get("content-type", "") or url.endswith("csv") or "format=csv" in url else "html")
        fn = f"{name}.{ext}"
        open(os.path.join(OUT, fn), "wb").write(body)
        summary[name] = {"url": url, "ok": True, "status": r.status_code, "bytes": len(body),
                         "final_url": r.url, "file": fn, "sha": hashlib.sha1(body).hexdigest()[:8]}
    except Exception as e:  # noqa: BLE001
        summary[name] = {"url": url, "ok": False, "error": str(e)[:300]}
    print(name, summary[name].get("ok"), summary[name].get("bytes") or summary[name].get("error"))

# Wikidata (gouverneurs)
try:
    from sources import wikidata_governors
    g = wikidata_governors([c["wikidata_country"] for c in C if c.get("wikidata_country")],
                           [c["wikidata_org"] for c in C if c.get("wikidata_org")])
    json.dump(g, open(os.path.join(OUT, "wikidata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    summary["wikidata"] = {"ok": True}
except Exception as e:  # noqa: BLE001
    summary["wikidata"] = {"ok": False, "error": str(e)[:300]}

json.dump(summary, open(os.path.join(OUT, "_summary.json"), "w"), indent=1)
