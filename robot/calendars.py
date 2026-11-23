"""Lecture des calendriers officiels des banques centrales.

Chaque lecteur renvoie la liste des dates d'ANNONCE des décisions (AAAA-MM-JJ),
passées et futures, telles qu'écrites sur la page officielle. Aucune date n'est
estimée : si la page ne donne rien, la liste est vide et le site affiche
« non publiée »."""
import datetime as dt
import io
import re

from bs4 import BeautifulSoup

from dates import MONTHS, find_dates, month_num
from net import get

YEAR = re.compile(r"\b(20\d\d)\b")


def lines_of(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    txt = re.sub(r"[ \t\xa0​﻿]+", " ", soup.get_text("\n"))
    return [l.strip() for l in txt.split("\n") if l.strip()]


def page(url, **kw):
    return get(url, browser=True, timeout=45, **kw)


def iso(d):
    return d.isoformat()


def mk(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- États-Unis
def fed(url, today):
    L = lines_of(page(url).text)
    out, year = [], None
    rx_day = re.compile(r"^(\d{1,2})(?:\s*-\s*(\d{1,2}))?\*?(?:\s*\((.*)\))?$")
    for i, l in enumerate(L):
        m = re.match(r"^(20\d\d) FOMC Meetings$", l)
        if m:
            year = int(m.group(1))
            continue
        if year is None:
            continue
        mm = re.match(r"^(January|February|March|April|May|June|July|August|September|October|November|December)(?:/(January|February|March|April|May|June|July|August|September|October|November|December))?$", l)
        if mm and i + 1 < len(L):
            d = rx_day.match(L[i + 1])
            if not d:
                continue
            note = (d.group(3) or "").lower()
            if "notation" in note or "unscheduled" in note:
                continue
            last_day = d.group(2) or d.group(1)
            mon = mm.group(2) if (mm.group(2) and d.group(2)) else mm.group(1)
            x = mk(year, MONTHS[mon.lower()], last_day)
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Canada
def boc(url, today):
    out = []
    L = lines_of(page(url).text)  # « Upcoming events » : dates futures
    for i, l in enumerate(L[:-1]):
        if re.match(r"^Interest Rate Announcement", L[i + 1]):
            for _, d in find_dates(l):
                out.append(iso(d))
    # Page du taux directeur : tableau des décisions passées (date | taux | variation)
    L = lines_of(page("https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/").text)
    for i, l in enumerate(L[:-1]):
        ds = find_dates(l)
        if len(ds) == 1 and re.match(r"^[A-Z][a-z]+ \d{1,2}, 20\d\d\*?$", l) and re.match(r"^\d+\.\d\d$", L[i + 1]):
            out.append(iso(ds[0][1]))
    return out


# ---------------------------------------------------------------- Zone euro
def ecb(url, today):
    L = lines_of(page(url).text)
    out = []
    for i, l in enumerate(L[:-1]):
        m = re.match(r"^(\d\d)/(\d\d)/(20\d\d)$", l)
        if m:
            nxt = L[i + 1].lower()
            if "monetary policy meeting" in nxt and "non-monetary" not in nxt and ("day 2" in nxt or "press conference" in nxt):
                x = mk(m.group(3), m.group(2), m.group(1))
                if x:
                    out.append(iso(x))
        if l == "Latest monetary policy press conference":
            for _, d in find_dates(L[i + 1]):
                out.append(iso(d))
    return out


# ---------------------------------------------------------------- Royaume-Uni
def boe(url, today):
    L = lines_of(page(url).text)
    out, year = [], None
    for l in L:
        m = re.match(r"^(20\d\d) (?:confirmed|provisional) dates", l, re.I)
        if m:
            year = int(m.group(1))
            continue
        m = re.match(r"^(?:Monday|Tuesday|Wednesday|Thursday|Friday) (\d{1,2}) ([A-Za-z]+)$", l)
        if m and year:
            mo = month_num(m.group(2))
            x = mk(year, mo, m.group(1)) if mo else None
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Suisse
def snb(url, today):
    out = []
    for u in (url, "https://www.snb.ch/en/the-snb/mandates-goals/monetary-policy/decisions"):
        for l in lines_of(page(u).text):
            m = re.match(r"^Monetary policy assessment of (\d{1,2} [A-Za-z]+ 20\d\d)", l)
            if m:
                for _, d in find_dates(m.group(1)):
                    out.append(iso(d))
    return out


# ---------------------------------------------------------------- Suède
def riksbank(url, today):
    out = []
    for y in (today.year, today.year + 1):
        try:
            L = lines_of(page(f"https://www.riksbank.se/en-gb/press-and-published/calendar/calendar-{y}/").text)
        except Exception:  # noqa: BLE001  (l'année suivante peut ne pas exister encore)
            continue
        for i, l in enumerate(L):
            if not l.startswith("Publication of monetary policy decision") or i < 2:
                continue
            m = re.match(r"^([A-Za-z]{3,9})\.? (20\d\d)$", L[i - 1])
            if m and re.match(r"^\d{1,2}$", L[i - 2]):
                mo = month_num(m.group(1))
                x = mk(m.group(2), mo, L[i - 2]) if mo else None
                if x:
                    out.append(iso(x))
    return out


# ---------------------------------------------------------------- Norvège
def norges(url, today):
    L = lines_of(page(url).text)
    out = []
    for l in L:
        if re.match(r"^\d{1,2} [A-Za-z]{3,9}\.? 20\d\d$", l):
            for _, d in find_dates(l):
                out.append(iso(d))
    return out


# ---------------------------------------------------------------- Tchéquie
def cnb(url, today):
    out = []
    for u in ("https://www.cnb.cz/en/about_cnb/bank-board/",
              f"https://www.cnb.cz/en/cnb-news/news/Dates-of-the-CNB-Boards-meetings-in-{today.year + 1}/"):
        try:
            L = lines_of(page(u).text)
        except Exception:  # noqa: BLE001
            continue
        for i, l in enumerate(L[:-1]):
            if re.match(r"^\d{1,2} [A-Za-z]+ 20\d\d$", l) and re.search(r"meeting on monetary policy", L[i + 1], re.I):
                for _, d in find_dates(l):
                    out.append(iso(d))
    return out


# ---------------------------------------------------------------- Hongrie
def mnb(url, today):
    L = lines_of(page(url).text)
    out, year = [], None
    for l in L:
        m = re.search(r"meetings \((20\d\d)\)", l) or re.match(r"^(20\d\d) H[12]$", l)
        if m:
            year = int(m.group(1))
        for m in re.finditer(r"(\d{1,2}) ([A-Z][a-z]+)(?: (20\d\d))? \(P\)", l):
            y = int(m.group(3)) if m.group(3) else year
            mo = month_num(m.group(2))
            x = mk(y, mo, m.group(1)) if (y and mo) else None
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Japon
def boj(url, today):
    soup = BeautifulSoup(page(url).text, "html.parser")
    out = []
    for tbl in soup.find_all("table"):
        cap = tbl.find("caption")
        m = YEAR.search(cap.get_text(" ") if cap else "")
        if not m:
            continue
        year = int(m.group(1))
        for tr in tbl.find_all("tr"):
            td = tr.find(["td", "th"])
            if not td:
                continue
            t = re.sub(r"\s+", " ", td.get_text(" ")).strip()
            # « Jan. 22 (Thurs.), 23 (Fri.) » ou « Apr. 30 (Thurs.), May 1 (Fri.) »
            parts = re.findall(r"(?:([A-Z][a-z]{2,4})\.?\s+)?(\d{1,2})\s*\(", t)
            if not parts:
                continue
            mon = None
            for p_mon, _ in parts:
                if p_mon:
                    mon = month_num(p_mon)
            first_mon = month_num(parts[0][0]) if parts[0][0] else None
            if not first_mon:
                continue
            last_mon = mon or first_mon
            x = mk(year, last_mon, parts[-1][1])
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Afrique du Sud
def sarb(url, today):
    L = lines_of(page("https://www.resbank.co.za/en/home/what-we-do/monetary-policy/monetary-policy-committee").text)
    out, on = [], False
    for l in L:
        if "UPCOMING ANNOUNCEMENTS" in l.upper():
            on = True
            continue
        if on:
            ds = find_dates(l)
            if ds and re.match(r"^\d{1,2} [A-Za-z]+ 20\d\d$", l):
                out.append(iso(ds[0][1]))
            elif out:
                break
    return out


# ---------------------------------------------------------------- Turquie
def cbrt(url, today):
    soup = BeautifulSoup(page("https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Announcements/Calendar").text, "html.parser")
    out = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        ds = find_dates(tds[0].get_text(" "))  # 1re colonne = décision du comité
        if ds:
            out.append(iso(ds[0][1]))
    return out


# ---------------------------------------------------------------- Inde
def rbi(url, today):
    L = lines_of(page("https://www.rbi.org.in/scripts/annualpolicy.aspx").text)
    out = []
    for l in L:
        m = re.match(r"^([A-Z][a-z]+) ((?:\d{1,2}, )*\d{1,2}) and (\d{1,2}), (20\d\d)$", l)
        if m:
            mo = month_num(m.group(1))
            x = mk(m.group(4), mo, m.group(3)) if mo else None
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Mexique
MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
         "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}


def _banxico_pdf(content):
    """Calendrier annuel Banxico (PDF). Ligne « Mois j1 j2 j3 » : la 1re date est
    l'annonce de décision, sauf si c'est la publication des minutes (2 semaines
    après la décision précédente, ou date marquée d'une note sur les minutes).
    Contrôle : le nombre de dates doit égaler celui annoncé en note (« ocho fechas »)."""
    from pypdf import PdfReader
    txt = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)
    m = re.search(r"Calendario (20\d\d) para los anuncios", txt)
    if not m:
        return []
    year = int(m.group(1))
    words = {"seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12}
    mcount = re.search(r"considera (\w+) fechas", txt)
    expected = words.get(mcount.group(1).lower()) if mcount else None
    notes_minutas = {n for n, body in re.findall(r"(?m)^\s*(\d) (.{0,80})", txt) if "minutas" in body.lower()}
    out, prev = [], None
    for mon, nums in re.findall(r"(?m)^(" + "|".join(k.capitalize() for k in MESES) + r") ([\d ]+)$", txt):
        toks = nums.split()
        if not toks:
            continue
        t = toks[0]
        note = None
        if int(t) > 31:
            t, note = t[:-1], t[-1]
        x = mk(year, MESES[mon.lower()], t)
        if not x:
            continue
        if prev and (x - prev).days == 14:
            continue
        if note and note in notes_minutas and mon.lower() == "enero":
            continue
        out.append(x)
        prev = x
    if expected and len(out) != expected:
        raise ValueError(f"Banxico : {len(out)} dates lues au lieu de {expected} annoncées — calendrier ignoré")
    return [iso(d) for d in out]


def banxico(url, today):
    base = "https://www.banxico.org.mx"
    soup = BeautifulSoup(page(base + "/publicaciones-y-prensa/anuncios-de-las-decisiones-de-politica-monetaria/anuncios-politica-monetaria-t.html").text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        if "calendario de decisiones" in a.get_text(" ").lower():
            link = a["href"]
            if link.startswith("/"):
                link = base + link
            out += _banxico_pdf(page(link).content)
    return out


# ---------------------------------------------------------------- Brésil
def bcb(url, today):
    """API officielle de la BCB : liste des communiqués du Copom (décisions passées).
    Le calendrier des réunions futures n'est pas exposé dans une page lisible par un robot."""
    r = get("https://www.bcb.gov.br/api/servico/sitebcb/copom/comunicados", params={"quantidade": 12})
    return [c["dataReferencia"][:10] for c in r.json().get("conteudo", []) if c.get("dataReferencia")]


# ---------------------------------------------------------------- Corée du Sud
def bok(url, today):
    L = lines_of(page(url).text)
    out, year = [], None
    for l in L:
        if re.match(r"^20\d\d$", l):
            year = int(l)
            continue
        m = re.match(r"^([A-Z][a-z]{2,3})\.\s?(\d{1,2}) \(", l)
        if m and year:
            mo = month_num(m.group(1))
            x = mk(year, mo, m.group(2)) if mo else None
            if x:
                out.append(iso(x))
    return out


# ---------------------------------------------------------------- Indonésie
def bi(url, today):
    L = lines_of(page(url).text)
    out = []
    for l in L:
        if re.match(r"^(?:Mon|Tues|Wednes|Thurs|Fri)day-(?:Mon|Tues|Wednes|Thurs|Fri)day, ", l):
            for _, d in find_dates(l):
                out.append(iso(d))
    return out


# ---------------------------------------------------------------- Australie
def rba(url, today):
    L = lines_of(page(url).text)
    out = []
    for i, l in enumerate(L[:-2]):
        if re.match(r"^\d{1,2} [A-Z][a-z]+ 20\d\d$", l) and re.match(r"^\d{1,2}\.\d\d pm AE[SD]T$", L[i + 1]) \
                and L[i + 2] == "Monetary Policy Decision":
            for _, d in find_dates(l):
                out.append(iso(d))
    return out


PARSERS = {"fed": fed, "boc": boc, "ecb": ecb, "boe": boe, "snb": snb, "riksbank": riksbank,
           "norges": norges, "cnb": cnb, "mnb": mnb, "boj": boj, "sarb": sarb, "cbrt": cbrt,
           "rbi": rbi, "banxico": banxico, "bcb": bcb, "bok": bok, "bi": bi, "rba": rba}


def fetch(parser, url, today):
    fn = PARSERS.get(parser)
    if not fn:
        raise NotImplementedError(f"pas de lecteur « {parser} »")
    lo, hi = today - dt.timedelta(days=500), today + dt.timedelta(days=800)
    dates = sorted({d for d in fn(url, today) if lo.isoformat() <= d <= hi.isoformat()})
    return dates
