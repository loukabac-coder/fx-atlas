"""Extraction de dates dans du texte anglais (calendriers officiels)."""
import datetime as dt
import re

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
for k, v in list(MONTHS.items()):
    MONTHS[k[:3]] = v
MONTHS["sept"] = 9
MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"

# 28 January 2026 / 27-28 January 2026 / 3 e 4 ... (on prend le dernier jour d'une plage)
RE_DMY = re.compile(r"\b(\d{1,2})(?:\s*(?:-|–|—|and|&)\s*(\d{1,2}))?\s+" + MON + r",?\s+(\d{4})\b", re.I)
# January 28, 2026 / January 27-28, 2026
RE_MDY = re.compile(r"\b" + MON + r"\s+(\d{1,2})(?:\s*(?:-|–|—)\s*(?:" + MON + r"\s+)?(\d{1,2}))?,?\s+(\d{4})\b", re.I)
RE_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")


def _mk(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d))
    except ValueError:
        return None


def find_dates(text, last_day_of_range=True):
    """Toutes les dates trouvées dans un texte, avec leur position."""
    out = []
    for m in RE_DMY.finditer(text):
        d1, d2, mon, y = m.groups()
        day = d2 if (d2 and last_day_of_range) else d1
        x = _mk(y, MONTHS[mon.lower().rstrip('.')[:4] if mon.lower().startswith('sept') else mon.lower()[:3]], day)
        if x:
            out.append((m.start(), x))
    for m in RE_MDY.finditer(text):
        mon, d1, mon2, d2, y = m.groups()
        mm = MONTHS[mon.lower()[:3]]
        if d2 and last_day_of_range:
            if mon2:
                mm = MONTHS[mon2.lower()[:3]]
            day = d2
        else:
            day = d1
        x = _mk(y, mm, day)
        if x:
            out.append((m.start(), x))
    for m in RE_ISO.finditer(text):
        x = _mk(*m.groups())
        if x:
            out.append((m.start(), x))
    out.sort()
    return out


def month_num(s):
    s = s.lower().strip().rstrip(".")
    return MONTHS.get(s) or MONTHS.get(s[:3])
