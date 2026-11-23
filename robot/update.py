"""Robot quotidien de FX Atlas.

Lit les sources officielles, contrôle chaque valeur, garde la dernière bonne
valeur en cas de doute ou de panne, écrit les fichiers du site dans docs/data/
et un journal lisible. Un pays ou une source en panne ne bloque jamais les autres.

Code de sortie ≠ 0 si trop de données essentielles manquent (le site est quand
même mis à jour avec les dernières bonnes valeurs, et la panne est visible
en rouge dans GitHub Actions)."""
import datetime as dt
import json
import os
import re
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calendars  # noqa: E402
import sources as S  # noqa: E402
from validate import check, check_fx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "docs", "data")
TODAY = dt.date.fromisoformat(os.environ.get("FX_ATLAS_TODAY", dt.date.today().isoformat()))
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

# Seuils au-delà desquels une valeur est signalée comme « ancienne » (jours)
STALE = {"policy": 10, "cpi": 100, "y10": 75, "fx": 5}
MAX_MISSING_SHARE = 0.20  # échec visible si > 20 % des valeurs essentielles manquent

LOG = []


def log(country, source, what, value, status, detail=""):
    LOG.append({"pays": country, "source": source, "donnee": what,
                "valeur": value, "statut": status, "detail": detail})
    print(f"[{status:^11}] {country:4} {what:22} {str(value):>14}  {source}  {detail}")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def days_old(date_str):
    if not date_str:
        return None
    d = date_str if len(date_str) > 7 else date_str + "-28"
    try:
        return (TODAY - dt.date.fromisoformat(d[:10])).days
    except ValueError:
        return None


def iso(d):
    return d.isoformat()


def safe(label, fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:  # noqa: BLE001
        log("--", label, "téléchargement", None, "ERREUR", f"{type(e).__name__}: {str(e)[:200]}")
        traceback.print_exc(limit=1)
        return None


def compress_steps(series):
    """Série quotidienne d'un taux directeur -> points de changement (+ dernier point)."""
    out = []
    for d, v in series:
        if not out or abs(out[-1][1] - v) > 1e-9:
            out.append([d, v])
    if series and out[-1][0] != series[-1][0]:
        out.append([series[-1][0], series[-1][1]])
    return out


def last_change(series):
    """Dernier changement de niveau : (date, ancien, nouveau)."""
    for i in range(len(series) - 1, 0, -1):
        if abs(series[i][1] - series[i - 1][1]) > 1e-9:
            return series[i][0], series[i - 1][1], series[i][1]
    return None


def value_at(series, date_str):
    """Valeur en vigueur à une date (dernière observation ≤ date)."""
    best = None
    for d, v in series:
        if d <= date_str:
            best = v
        else:
            break
    return best


def accept_metric(kind, code, cand, state, extra=None):
    """Applique la validation et la règle « dernière bonne valeur ».
    cand : {"value","date","source","series","url"} ou None (source muette)."""
    key = f"{code}:{kind}"
    prev = state["good"].get(key)
    pend = state["pending"].get(key)
    if cand is None:
        if prev:
            rec = dict(prev, status="pas_a_jour", note="Source indisponible aujourd'hui : dernière valeur validée conservée.")
            log(code, prev.get("source", ""), kind, prev["value"], "GARDÉE", "source muette")
            return rec
        log(code, "", kind, None, "N/D", "aucune source")
        return {"value": None, "status": "nd"}
    decision, why = check(kind, code, cand, prev, pend)
    if decision == "accept":
        state["good"][key] = {k: cand[k] for k in ("value", "date", "source", "series", "url") if k in cand}
        state["pending"].pop(key, None)
        rec = dict(cand)
        age = days_old(cand.get("date"))
        lim = (extra or {}).get("stale", STALE[kind])
        if kind != "policy" and age is not None and age > lim:  # taux directeur : fraîcheur jugée d'après les réunions
            rec["status"] = "ancien"
            rec["note"] = f"Dernière valeur publiée par la source : {cand['date']} (il y a {age} jours)."
            log(code, cand["source"], kind, cand["value"], "ANCIEN", f"date {cand['date']}")
        else:
            rec["status"] = "ok"
            log(code, cand["source"], kind, cand["value"], "OK", f"date {cand['date']} {why}".strip())
        return rec
    if decision == "pending":
        state["pending"][key] = {"value": cand["value"], "date": cand.get("date")}
    if prev:
        rec = dict(prev, status="pas_a_jour",
                   note=f"Nouvelle valeur {cand['value']} ({cand.get('date')}) écartée : {why}. Dernière valeur validée conservée.")
        log(code, cand["source"], kind, cand["value"], "REFUSÉE", why)
        return rec
    log(code, cand["source"], kind, cand["value"], "REFUSÉE", why + " (aucune valeur antérieure)")
    return {"value": None, "status": "nd", "note": f"Valeur reçue écartée : {why}."}


def main():
    cfg = load_json(os.path.join(ROOT, "config", "countries.json"), None)
    C = cfg["countries"]
    codes = [c["code"] for c in C]
    state = load_json(os.path.join(DATA, "state.json"), {"good": {}, "pending": {}, "calendars": {}, "governors": {}})
    for k in ("good", "pending", "calendars", "governors", "history"):
        state.setdefault(k, {})
    # Garde-fou : une valeur gardée avec une date future est forcément une erreur -> oubliée
    for k in [k for k, v in state["good"].items() if isinstance(v, dict) and (v.get("date") or "") > iso(TODAY)]:
        print(f"État : valeur à date future écartée ({k} {state['good'][k].get('date')})")
        state["good"].pop(k)
    start_hist = iso(TODAY - dt.timedelta(days=365 * 3 + 400))

    # ---------- 1. Taux directeurs (BIS) ----------
    bis = safe("BIS WS_CBPOL", S.bis_policy_rates, codes, start_hist)
    bis_rates, bis_url = bis if bis else ({}, None)
    # Sources officielles directes (prioritaires quand elles répondent)
    official = {}
    v = safe("Banque du Canada V39079", S.boc_valet_range, "V39079", start_hist)
    if v:
        official["CA"] = {"series": v[0], "url": v[1], "source": "Banque du Canada", "id": "Valet V39079"}
    v = safe("BCE FM DFR", S.ecb_dfr, start_hist)
    if v and v[0]:
        official["XM"] = {"series": v[0], "url": "https://data.ecb.europa.eu/data/datasets/FM/FM.D.U2.EUR.4F.KR.DFR.LEV",
                          "source": "BCE", "id": "FM.D.U2.EUR.4F.KR.DFR.LEV"}
    v = safe("Banque d'Angleterre IUDBEDR", S.boe_bank_rate, start_hist)
    if v:
        official["GB"] = {"series": v[0], "url": v[1], "source": "Banque d'Angleterre", "id": "IADB IUDBEDR"}
    v = safe("BCB SGS 432", S.bcb_selic, start_hist)
    if v:
        official["BR"] = {"series": v[0], "url": "https://www.bcb.gov.br/controleinflacao/historicotaxasjuros",
                          "source": "Banco Central do Brasil", "id": "SGS 432 (Selic cible)"}
    us_range = safe("Fed de New York (fourchette)", S.nyfed_range)

    # ---------- 2. Inflation (BIS) ----------
    cpi = safe("BIS WS_LONG_CPI", S.bis_cpi_yoy, codes, start_hist[:7])
    cpi_series, cpi_url = cpi if cpi else ({}, None)

    # ---------- 3. Taux de change (BCE) ----------
    ccys = sorted({c["currency"] for c in C} - {"EUR"})
    fx = safe("BCE EXR", S.ecb_fx, ccys, iso(TODAY - dt.timedelta(days=400)))
    fx_series, fx_url = fx if fx else ({}, None)

    # ---------- 4. Taux à 10 ans (OCDE) ----------
    y10 = safe("OCDE DF_FINMARK", S.oecd_10y, {c["oecd"] for c in C if c.get("oecd")},
               (TODAY - dt.timedelta(days=500)).isoformat()[:7])
    y10_series = y10[0] if y10 else {}

    # ---------- 5. Gouverneurs (Wikidata) ----------
    gov = safe("Wikidata", S.wikidata_governors, [],
               [c["wikidata_bank"] for c in C if c.get("wikidata_bank")]) or {}

    out_countries = {}
    hist_out = {}
    for c in C:
        code = c["code"]
        try:
            out_countries[code], hist_out[code] = build_country(
                c, state, bis_rates, bis_url, official, us_range, cpi_series, cpi_url, gov, y10_series)
        except Exception as e:  # noqa: BLE001  — un pays ne fait jamais tomber les autres
            traceback.print_exc()
            log(code, "robot", "pays entier", None, "ERREUR", f"{type(e).__name__}: {e}")
            prev = load_json(os.path.join(DATA, "atlas.json"), {}).get("countries", {}).get(code)
            if prev:
                out_countries[code] = prev
                out_countries[code]["robot_error"] = "Erreur du robot aujourd'hui : données de la veille affichées."

    # ---------- 5. Métriques dérivées croisées ----------
    us = out_countries.get("US", {}).get("metrics", {}).get("policy", {})
    for code, cc in out_countries.items():
        m = cc["metrics"]
        p = m.get("policy", {})
        if us.get("value") is not None and p.get("value") is not None:
            m["carry_usd"] = derived(p["value"] - us["value"], [p, us], "Taux directeur moins taux directeur américain")
        else:
            m["carry_usd"] = {"value": None, "status": "nd"}

    fx_block = build_fx(C, fx_series, fx_url, state, out_countries)

    # ---------- 6. Écriture ----------
    essentials = [(k, m) for k, cc in out_countries.items() for m in ("policy", "cpi")]
    missing = [f"{k}:{m}" for k, m in essentials
               if out_countries[k]["metrics"].get(m, {}).get("status") in ("nd", "pas_a_jour", None)]
    share = len(missing) / max(1, len(essentials))
    changes = diff_changes(load_json(os.path.join(DATA, "atlas.json"), {}), out_countries)
    atlas = {"generated_at": NOW, "as_of": iso(TODAY), "countries": out_countries, "changes": changes,
             "quality": {"missing": missing, "missing_share": round(share, 3)}}
    os.makedirs(DATA, exist_ok=True)
    dump(os.path.join(DATA, "atlas.json"), atlas)
    dump(os.path.join(DATA, "history.json"), {"generated_at": NOW, "countries": hist_out})
    dump(os.path.join(DATA, "fx.json"), fx_block)
    dump(os.path.join(DATA, "log.json"), {"generated_at": NOW, "entries": LOG})
    dump(os.path.join(DATA, "state.json"), state)
    write_summary(share, missing)
    if share > MAX_MISSING_SHARE:
        print(f"\nÉCHEC : {share:.0%} des données essentielles manquent ou ne sont pas à jour : {missing}")
        return 1
    print(f"\nTerminé : {len(missing)} donnée(s) essentielle(s) manquante(s) ou pas à jour.")
    return 0


def diff_changes(prev_atlas, now):
    """Changements depuis le passage précédent : taux directeurs et nouvelles publications d'inflation."""
    out = []
    old = (prev_atlas or {}).get("countries", {})
    if not old:
        return out
    for code, c in now.items():
        o = old.get(code, {}).get("metrics", {})
        p, po = c["metrics"].get("policy", {}), o.get("policy", {})
        if p.get("value") is not None and po.get("value") is not None and abs(p["value"] - po["value"]) > 1e-9:
            bp = round((p["value"] - po["value"]) * 100)
            val = f"{p['value']:.2f}".replace(".", ",")
            out.append(f"{c['name']} : taux directeur {'relevé' if bp > 0 else 'abaissé'} de {abs(bp)} pb, à {val} % (valeur du {p.get('date')}).")
        i, io_ = c["metrics"].get("cpi", {}), o.get("cpi", {})
        if i.get("date") and io_.get("date") and i["date"] > io_["date"] and i.get("value") is not None:
            out.append(f"{c['name']} : inflation de {i['date']} publiée → {str(i['value']).replace('.', ',')} % (avant : {str(io_.get('value')).replace('.', ',')} %).")
    return out


def derived(value, parts, how):
    st = "ok"
    for p in parts:
        if p.get("status") in ("pas_a_jour", "ancien"):
            st = "ancien" if st == "ok" else st
    return {"value": round(value, 3), "status": st, "source": "Calcul FX Atlas", "note": how,
            "date": max((p.get("date") or "") for p in parts) or None}


def build_country(c, state, bis_rates, bis_url, official, us_range, cpi_series, cpi_url, gov, y10_series):
    code = c["code"]
    metrics = {}
    hist = {}

    # --- taux directeur ---
    series, cand = None, None
    o = official.get(code)
    if o:
        o = dict(o, series=[x for x in o["series"] if x[0] <= iso(TODAY)])
    b = bis_rates.get(code)
    if o and o["series"]:
        series = o["series"]
        d, v = series[-1]
        cand = {"value": v, "date": d, "source": o["source"], "series": o["id"], "url": o["url"]}
        if b:
            bv = value_at(b, d)
            if bv is not None and abs(bv - v) > 0.005:
                log(code, "contrôle BIS", "écart officiel/BIS", f"{v} vs {bv}", "ÉCART",
                    "la source officielle de la banque centrale est retenue")
            elif bv is not None:
                log(code, "contrôle BIS", "officiel = BIS", v, "OK", f"au {d}")
    elif b:
        series = b
        d, v = b[-1]
        cand = {"value": v, "date": d, "source": "BIS (Banque des règlements internationaux)",
                "series": f"WS_CBPOL D.{code}", "url": f"https://data.bis.org/topics/CBPOL/BIS%2CWS_CBPOL%2C1.0/D.{code}"}
    if series is None:
        series = [tuple(x) for x in state["history"].get(code, {}).get("policy", [])]
    metrics["policy"] = accept_metric("policy", code, cand, state)
    if code == "US" and us_range and metrics["policy"].get("value") is not None:
        lo_, hi_, d_ = us_range
        if abs((lo_ + hi_) / 2 - metrics["policy"]["value"]) < 0.01:
            metrics["policy"]["range"] = [lo_, hi_]
            metrics["policy"]["rate_note"] = f"Fourchette cible {lo_:.2f}–{hi_:.2f} % (Fed de New York, {d_}) ; valeur affichée = milieu de fourchette (convention BIS)."
        else:
            log(code, "Fed de New York", "fourchette", f"{lo_}-{hi_}", "ÉCART", "milieu différent du taux BIS : fourchette non affichée")
    if c.get("rate_note"):
        metrics["policy"]["rate_note"] = c["rate_note"]
    if series:
        state["history"].setdefault(code, {})["policy"] = compress_steps(series)
        cut = iso(TODAY - dt.timedelta(days=365 * 3 + 31))
        hist["policy"] = [p for p in compress_steps(series) if p[0] >= cut] or compress_steps(series)[-1:]
        # variation sur 12 mois
        if metrics["policy"].get("value") is not None:
            ago = value_at(series, iso(TODAY - dt.timedelta(days=365)))
            if ago is not None:
                metrics["policy_12m"] = derived(metrics["policy"]["value"] - ago, [metrics["policy"]],
                                                "Taux directeur actuel moins taux d'il y a 12 mois")
    metrics.setdefault("policy_12m", {"value": None, "status": "nd"})

    # --- inflation ---
    cs = cpi_series.get(code)
    cand = None
    if cs:
        d, v = cs[-1]
        cand = {"value": round(v, 2), "date": d, "source": "BIS (indices de prix nationaux)",
                "series": f"WS_LONG_CPI M.{code}.771",
                "url": f"https://data.bis.org/topics/CPI/BIS%2CWS_LONG_CPI%2C1.0/M.{code}.771"}
        cut = (TODAY - dt.timedelta(days=365 * 3 + 31)).isoformat()[:7]
        hist["cpi"] = [[d, round(v, 2)] for d, v in cs if d >= cut]
    metrics["cpi"] = accept_metric("cpi", code, cand, state, {"stale": c.get("cpi_stale_days", STALE["cpi"])})

    # --- 10 ans ---
    ys = y10_series.get(c.get("oecd"))
    cand = None
    if ys:
        d, v = ys[-1]
        cand = {"value": v, "date": d, "source": "OCDE (taux à long terme, moyenne mensuelle)",
                "series": f"DF_FINMARK {c['oecd']}.M.IRLT",
                "url": "https://data-explorer.oecd.org/vis?df[ds]=dsDisseminateFinalDMZ&df[id]=DSD_STES%40DF_FINMARK&df[ag]=OECD.SDD.STES"}
    if ys or state["good"].get(f"{code}:y10"):
        metrics["y10"] = accept_metric("y10", code, cand, state)
    else:
        metrics["y10"] = {"value": None, "status": "nd", "note": "Pas de série OCDE pour ce pays."}

    # --- cible + dérivées ---
    t = c.get("target")
    target = {"value": None, "status": "nd", "note": c.get("target_note")}
    if t:
        target = {"value": t.get("value"), "label": t["label"], "url": t["url"], "source": "Site officiel de la banque centrale"}
        txt = safe(f"cible {code}", S.page_text, t["url"])
        prev_t = state["good"].get(f"{code}:target")
        if txt:
            norm = re.sub(r"\s+", " ", txt[0]).replace("\u00a0", " ")
            if t.get("extract"):
                mm = re.search(t["extract"], norm)
                if mm:
                    v = float(mm.group(1).replace(",", "."))
                    if 0 < v < 20:
                        target.update(value=v, label=t["label"].replace("{v}", f"{v:g}".replace(".", ",")), status="ok", checked=iso(TODAY))
                        state["good"][f"{code}:target"] = {"value": v, "label": target["label"], "checked": iso(TODAY)}
                        log(code, t["url"], "cible", v, "OK", "valeur lue sur la page officielle")
                    else:
                        mm = None
                if not mm:
                    if prev_t:
                        target.update(value=prev_t["value"], label=prev_t["label"], status="a_verifier", checked=prev_t["checked"],
                                      note="Valeur non relue aujourd'hui sur la page officielle : dernière valeur lue conservée.")
                    else:
                        target.update(value=None, label="n/d", status="nd")
                    log(code, t["url"], "cible", target.get("value"), "À VÉRIFIER", "valeur introuvable sur la page")
            elif t["check"] in norm or t["check"].replace(" ", "") in norm.replace(" ", ""):
                target.update(status="ok", checked=iso(TODAY))
                state["good"][f"{code}:target_checked"] = iso(TODAY)
                log(code, t["url"], "cible", t["label"], "OK", f"mention « {t['check']} » retrouvée sur la page officielle")
            else:
                target.update(status="a_verifier", checked=state["good"].get(f"{code}:target_checked"),
                              note="La mention attendue n'a pas été retrouvée sur la page officielle : cible à revérifier.")
                log(code, t["url"], "cible", t["label"], "À VÉRIFIER", "mention introuvable")
        else:
            if t.get("extract") and prev_t:
                target.update(value=prev_t["value"], label=prev_t["label"])
            elif t.get("extract"):
                target.update(value=None, label="n/d")
            target.update(status="a_verifier", checked=state["good"].get(f"{code}:target_checked") or (prev_t or {}).get("checked"),
                          note="Page officielle injoignable aujourd'hui.")
            log(code, t["url"], "cible", target.get("value"), "À VÉRIFIER", "page injoignable")
    p, i = metrics["policy"], metrics["cpi"]
    if p.get("value") is not None and i.get("value") is not None:
        metrics["real"] = derived(p["value"] - i["value"], [p, i], "Taux directeur moins inflation sur un an")
    else:
        metrics["real"] = {"value": None, "status": "nd"}
    if target.get("value") is not None and i.get("value") is not None:
        metrics["gap"] = derived(i["value"] - target["value"], [i], "Inflation moins cible de la banque centrale")
    else:
        metrics["gap"] = {"value": None, "status": "nd"}

    # --- gouverneur ---
    governor = pick_governor(code, c, gov.get(c.get("wikidata_bank")), state)

    # --- réunions ---
    meetings = build_meetings(c, state, series)

    # Fraîcheur du taux : la valeur est à jour si aucune réunion n'a eu lieu depuis sa date
    pol = metrics["policy"]
    if pol.get("value") is not None and pol.get("status") in ("ok", "ancien") and pol.get("date"):
        last_m = (meetings.get("last") or {}).get("date")
        age = days_old(pol["date"])
        if last_m and pol["date"] < last_m and (TODAY - dt.date.fromisoformat(last_m)).days >= 2:
            pol["status"] = "ancien"
            pol["note"] = f"La source n'a pas encore publié de valeur postérieure à la réunion du {last_m}."
            log(code, pol.get("source", ""), "policy", pol["value"], "ANCIEN", f"réunion du {last_m} pas encore reflétée")
        elif last_m or meetings.get("status") == "aucun":
            limit = 45 if last_m else 21
            if age is not None and age > limit:
                pol["status"] = "ancien"
                pol["note"] = f"Dernière valeur publiée par la source : {pol['date']}."
            else:
                pol["status"] = "ok"
                pol.pop("note", None)

    return ({"code": code, "name": c["name"], "geo": c["geo"], "cb": c["cb"], "currency": c["currency"],
             "governor": governor, "target": target, "metrics": metrics, "meetings": meetings}, hist)


def _norm(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t)
    return "".join(ch for ch in t if not unicodedata.combining(ch)).lower()


def name_on_page(name, txt):
    """Vrai si tous les mots du nom (3 lettres et plus) apparaissent ensemble (à moins de 40 caractères)."""
    toks = [t for t in re.split(r"[\s\-.,]+", _norm(name)) if len(t) >= 3]
    if not toks:
        return False
    main = max(toks, key=len)
    for m in re.finditer(r"\b" + re.escape(main) + r"\b", txt):
        win = txt[max(0, m.start() - 40): m.end() + 40]
        if all(re.search(r"\b" + re.escape(t) + r"\b", win) for t in toks):
            return True
    return False


def pick_governor(code, c, rows, state):
    """Candidats Wikidata (mandats sans date de fin, du plus récent au plus ancien),
    retenus seulement si le nom figure sur une page officielle de la banque centrale."""
    prev = state["governors"].get(code)
    pages = []
    for u in c.get("governor_check", []):
        u = u.replace("{year}", str(TODAY.year))
        t = safe(f"page dirigeant {code}", S.page_text, u)
        if t:
            pages.append((u, _norm(t[0])))
    if rows:
        # mandats sans date de début = données historiques incomplètes dans Wikidata : écartés
        rows = sorted([r for r in rows if r.get("start")], key=lambda r: r["start"], reverse=True)
        seen = set()
        for r in rows:
            name = r.get("head") or ""
            if name in seen or not name or name.startswith("Q"):
                continue
            seen.add(name)
            hit = next((u for u, txt in pages if name_on_page(name, txt)), None)
            if hit:
                g = {"name": name, "since": r.get("start"), "source": "Wikidata, nom confirmé sur le site de la banque centrale",
                     "url": f"https://www.wikidata.org/wiki/{r['head_qid']}", "check_url": hit, "status": "ok", "checked": iso(TODAY)}
                if prev and prev.get("name") != name:
                    log(code, "Wikidata + site officiel", "dirigeant", name, "CHANGEMENT", f"précédent : {prev.get('name')}")
                else:
                    log(code, "Wikidata + site officiel", "dirigeant", name, "OK", hit)
                state["governors"][code] = g
                return g
        log(code, "Wikidata", "dirigeant", rows[0].get("head") if rows else None, "NON CONFIRMÉ",
            "nom absent des pages officielles vérifiées" if pages else "pages officielles injoignables")
        if prev and not pages:
            return dict(prev, status="pas_a_jour")
        return {"name": None, "status": "nd", "note": "Nom non confirmé par une page officielle de la banque centrale."}
    if prev:
        log(code, "Wikidata", "dirigeant", prev.get("name"), "GARDÉE", "pas de réponse aujourd'hui")
        return dict(prev, status="pas_a_jour")
    log(code, "Wikidata", "dirigeant", None, "N/D")
    return {"name": None, "status": "nd"}


def build_meetings(c, state, series):
    code = c["code"]
    if not c.get("calendar"):
        lc = last_change(series or [])
        return {"status": "aucun", "note": c.get("calendar_note"),
                "last_change": {"date": lc[0], "bp": round((lc[2] - lc[1]) * 100), "new": lc[2]} if lc else None}
    cal = c["calendar"]
    dates, err = None, None
    try:
        dates = calendars.fetch(cal["parser"], cal["url"], TODAY)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {str(e)[:150]}"
    prev = state["calendars"].get(code)
    status = "ok"
    if dates and len(dates) >= 2:
        merged = sorted(set(dates) | {d for d in (prev or {}).get("dates", []) if d < iso(TODAY)})
        state["calendars"][code] = {"dates": merged, "checked": iso(TODAY)}
        log(code, cal["url"], "calendrier", f"{len(dates)} dates", "OK")
    else:
        status = "pas_a_jour"
        log(code, cal["url"], "calendrier", None, "GARDÉ" if prev else "N/D", err or "aucune date lue")
    known = (state["calendars"].get(code) or {}).get("dates", [])
    today = iso(TODAY)
    past = [d for d in known if d < today]
    fut = [d for d in known if d >= today]
    m = {"source": cal["url"], "status": status if known else "nd",
         "checked": (state["calendars"].get(code) or {}).get("checked"),
         "last": None, "next": {"date": fut[0]} if fut else {"date": None, "note": "non publiée"},
         "upcoming": fut[:4]}
    if past:
        last = past[-1]
        m["last"] = {"date": last, "decision": decision_at(series, last)}
    if c.get("calendar_note"):
        m["note"] = c["calendar_note"]
    lc = last_change(series or [])
    if lc:
        m["last_change"] = {"date": lc[0], "bp": round((lc[2] - lc[1]) * 100), "new": lc[2]}
    return m


def decision_at(series, meeting):
    """Décision prise à une réunion, déduite de la série officielle du taux :
    un changement dans les 0 à 10 jours suivant la réunion (délai d'entrée en vigueur)."""
    if not series:
        return {"type": "inconnue"}
    md = dt.date.fromisoformat(meeting)
    before = value_at(series, iso(md - dt.timedelta(days=1)))
    after_date = iso(md + dt.timedelta(days=10))
    after = value_at(series, min(after_date, series[-1][0]))
    if series[-1][0] < meeting:
        return {"type": "inconnue", "note": "série pas encore à jour après la réunion"}
    if before is None or after is None:
        return {"type": "inconnue"}
    diff = round((after - before) * 100)
    if diff > 0:
        return {"type": "hausse", "bp": diff, "new": after}
    if diff < 0:
        return {"type": "baisse", "bp": diff, "new": after}
    return {"type": "maintien", "bp": 0, "new": after}


def build_fx(C, fx_series, fx_url, state, countries):
    """Taux de référence BCE (devise pour 1 EUR). Historique 400 jours pour les performances."""
    rates = {}
    ccys = sorted({c["currency"] for c in C} - {"EUR"})
    for ccy in ccys:
        s = fx_series.get(ccy)
        key = f"FX:{ccy}"
        prev = state["good"].get(key)
        pend = state["pending"].get(key)
        if s:
            d, v = s[-1]
            dec, why = check_fx(ccy, {"value": v, "date": d}, prev, pend)
            if dec == "accept":
                state["good"][key] = {"value": v, "date": d}
                state["pending"].pop(key, None)
                age = days_old(d)
                st = "ok" if age is not None and age <= STALE["fx"] else "ancien"
                rates[ccy] = {"value": v, "date": d, "status": st}
                log("FX", "BCE", f"EUR/{ccy}", v, "OK" if st == "ok" else "ANCIEN", f"date {d} {why}".strip())
                continue
            if dec == "pending":
                state["pending"][key] = {"value": v, "date": d}
            log("FX", "BCE", f"EUR/{ccy}", v, "REFUSÉE", why)
        if prev:
            rates[ccy] = dict(prev, status="pas_a_jour")
            log("FX", "BCE", f"EUR/{ccy}", prev["value"], "GARDÉE")
        else:
            rates[ccy] = {"value": None, "status": "nd"}
    # Historique commun (dates où toutes les devises ont une valeur ou presque)
    hist = {}
    for ccy in ccys:
        for d, v in fx_series.get(ccy, []):
            hist.setdefault(d, {})[ccy] = v
    dates = sorted(hist)
    history = {"dates": dates, "rates": {ccy: [hist[d].get(ccy) for d in dates] for ccy in ccys}}
    if not dates:
        old = load_json(os.path.join(DATA, "fx.json"), {})
        history = old.get("history", history)
    # Performance de chaque devise face au dollar depuis le 1er janvier -> métrique du globe
    for code, cc in countries.items():
        ccy = cc["currency"]
        perf = fx_perf_vs_usd(ccy, history, "ytd")
        cc["metrics"]["fx_ytd"] = ({"value": round(perf[0] * 100, 2), "date": perf[1], "status": "ok",
                                    "source": "BCE (taux de référence), calcul FX Atlas",
                                    "note": "Variation de la devise face au dollar depuis le dernier fixing de l'année précédente"}
                                   if perf else {"value": None, "status": "nd",
                                                 "note": "Devise de référence" if ccy == "USD" else None})
    return {"generated_at": NOW, "base": "EUR", "source": "Banque centrale européenne — taux de change de référence (vers 16 h, heure de Francfort)",
            "source_url": "https://data.ecb.europa.eu/data/datasets/EXR", "series": "EXR D.{devise}.EUR.SP00.A",
            "rates": rates, "history": history}


def fx_perf_vs_usd(ccy, history, window):
    if ccy == "USD":
        return None
    dates = history["dates"]
    if not dates:
        return None
    R = history["rates"]

    def usd_per(ccy_, i):
        usd = R.get("USD", [None] * len(dates))[i]
        if ccy_ == "EUR":
            return usd  # 1 EUR = usd USD
        x = R.get(ccy_, [None] * len(dates))[i]
        return (usd / x) if (usd and x) else None
    i_now = len(dates) - 1
    while i_now >= 0 and usd_per(ccy, i_now) is None:
        i_now -= 1
    if i_now < 0:
        return None
    if window == "ytd":
        y = dates[i_now][:4]
        cands = [i for i, d in enumerate(dates) if d[:4] < y]
        if not cands:
            return None
        i_ref = cands[-1]
    else:
        return None
    a, b = usd_per(ccy, i_now), usd_per(ccy, i_ref)
    if not a or not b:
        return None
    return a / b - 1, dates[i_now]


def dump(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def write_summary(share, missing):
    lines = ["## Journal du robot FX Atlas", "",
             f"Données essentielles manquantes ou pas à jour : **{len(missing)}** ({share:.0%})", "",
             "| Pays | Donnée | Valeur | Statut | Source | Détail |", "|---|---|---|---|---|---|"]
    for e in LOG:
        lines.append(f"| {e['pays']} | {e['donnee']} | {e['valeur'] if e['valeur'] is not None else 'n/d'} | "
                     f"{e['statut']} | {str(e['source'])[:60]} | {str(e['detail'])[:90]} |")
    text = "\n".join(lines)
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    with open(os.path.join(DATA, "journal.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
