"""Lecture des sources officielles. Chaque fonction renvoie des séries brutes
(liste de (date ISO, valeur)) triées par date. Aucune valeur n'est inventée :
une ligne illisible est ignorée, une source muette lève une exception."""
import csv
import io
import json

from net import get

BIS = "https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}"
ECB = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv"
VALET = "https://www.bankofcanada.ca/valet/observations/{series}/json"
WIKIDATA = "https://query.wikidata.org/sparql"


def _num(s):
    s = (s or "").strip()
    if s in ("", ".", "NaN", "NA"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_sdmx_csv(text, key_col):
    """CSV SDMX (BIS ou BCE) -> {clé: [(date, valeur), ...]}"""
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        k = row.get(key_col)
        v = _num(row.get("OBS_VALUE"))
        d = (row.get("TIME_PERIOD") or "").strip()
        if not k or v is None or not d:
            continue
        out.setdefault(k, []).append((d, v))
    for k in out:
        out[k].sort()
    return out


def bis_policy_rates(codes, start):
    url = BIS.format(flow="WS_CBPOL", key="D." + "+".join(codes))
    r = get(url, params={"startPeriod": start, "format": "csv"})
    return parse_sdmx_csv(r.text, "REF_AREA"), r.url


def bis_cpi_yoy(codes, start):
    # UNIT_MEASURE 771 = variation sur un an (%)
    url = BIS.format(flow="WS_LONG_CPI", key="M." + "+".join(codes) + ".771")
    r = get(url, params={"startPeriod": start, "format": "csv"})
    return parse_sdmx_csv(r.text, "REF_AREA"), r.url


def ecb_fx(ccys, start):
    url = ECB.format(flow="EXR", key="D." + "+".join(ccys) + ".EUR.SP00.A")
    r = get(url, params={"startPeriod": start, "format": "csvdata"})
    return parse_sdmx_csv(r.text, "CURRENCY"), r.url


def ecb_dfr(start):
    url = ECB.format(flow="FM", key="D.U2.EUR.4F.KR.DFR.LEV")
    r = get(url, params={"startPeriod": start, "format": "csvdata"})
    d = parse_sdmx_csv(r.text, "PROVIDER_FM_ID")
    return (next(iter(d.values())) if d else []), r.url


def parse_fred_csv(text):
    rows = list(csv.reader(io.StringIO(text)))
    out = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        v = _num(row[1])
        if v is not None:
            out.append((row[0].strip(), v))
    out.sort()
    return out


def fred(series, start):
    r = get(FRED, params={"id": series, "cosd": start})
    if not r.text.lstrip().lower().startswith(("observation_date", "date")):
        raise ValueError(f"FRED {series}: réponse inattendue")
    return parse_fred_csv(r.text), r.url


def boc_valet(series, n=10):
    r = get(VALET.format(series=series), params={"recent": n})
    data = r.json()
    out = []
    for o in data.get("observations", []):
        v = _num((o.get(series) or {}).get("v"))
        if v is not None:
            out.append((o["d"], v))
    out.sort()
    return out, r.url


def boc_valet_range(series, start):
    r = get(VALET.format(series=series), params={"start_date": start})
    data = r.json()
    out = []
    for o in data.get("observations", []):
        v = _num((o.get(series) or {}).get("v"))
        if v is not None:
            out.append((o["d"], v))
    out.sort()
    if not out:
        raise ValueError("Valet : aucune observation")
    return out, f"https://www.bankofcanada.ca/valet/observations/{series}/json"


GOVERNOR_QUERY = """
SELECT ?country ?bank ?bankLabel ?head ?headLabel ?start WHERE {
  VALUES ?country { %s }
  ?bank wdt:P31 wd:Q66344 ; wdt:P17 ?country .
  { ?bank wdt:P2388 ?pos . ?head p:P39 ?st . ?st ps:P39 ?pos . }
  UNION { ?bank p:P488 ?st . ?st ps:P488 ?head . }
  UNION { ?bank p:P1037 ?st . ?st ps:P1037 ?head . }
  FILTER NOT EXISTS { ?st pq:P582 ?end }
  OPTIONAL { ?st pq:P580 ?start }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}"""

GOVERNOR_QUERY_ORG = """
SELECT ?bank ?bankLabel ?head ?headLabel ?start WHERE {
  VALUES ?bank { %s }
  { ?bank wdt:P2388 ?pos . ?head p:P39 ?st . ?st ps:P39 ?pos . }
  UNION { ?bank p:P488 ?st . ?st ps:P488 ?head . }
  UNION { ?bank p:P1037 ?st . ?st ps:P1037 ?head . }
  FILTER NOT EXISTS { ?st pq:P582 ?end }
  OPTIONAL { ?st pq:P580 ?start }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "fr,en". }
}"""


def _sparql(q):
    r = get(WIKIDATA, params={"query": q, "format": "json"},
            headers={"Accept": "application/sparql-results+json"}, timeout=60)
    return r.json()["results"]["bindings"]


def _qid(b, k):
    v = b.get(k, {}).get("value", "")
    return v.rsplit("/", 1)[-1] if v else None


def wikidata_governors(country_qids, org_qids):
    """Renvoie {qid pays ou organisation: [ {bank, head, start}, ...]}"""
    out = {}
    if country_qids:
        q = GOVERNOR_QUERY % " ".join("wd:" + c for c in country_qids)
        for b in _sparql(q):
            out.setdefault(_qid(b, "country"), []).append({
                "bank": b.get("bankLabel", {}).get("value"),
                "bank_qid": _qid(b, "bank"),
                "head": b.get("headLabel", {}).get("value"),
                "head_qid": _qid(b, "head"),
                "start": (b.get("start", {}).get("value") or "")[:10] or None})
    if org_qids:
        q = GOVERNOR_QUERY_ORG % " ".join("wd:" + c for c in org_qids)
        for b in _sparql(q):
            out.setdefault(_qid(b, "bank"), []).append({
                "bank": b.get("bankLabel", {}).get("value"),
                "bank_qid": _qid(b, "bank"),
                "head": b.get("headLabel", {}).get("value"),
                "head_qid": _qid(b, "head"),
                "start": (b.get("start", {}).get("value") or "")[:10] or None})
    return out


def page_text(url, browser=True):
    """Texte brut d'une page web officielle (pour calendriers et cibles)."""
    from bs4 import BeautifulSoup
    r = get(url, browser=browser)
    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        return json.dumps(r.json(), ensure_ascii=False), r.text
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return soup.get_text("\n"), r.text
