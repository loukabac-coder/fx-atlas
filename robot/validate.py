"""Contrôles de plausibilité. Une valeur douteuse n'écrase jamais une bonne valeur :
elle est mise « en attente » et n'est acceptée que si la source la confirme
au passage suivant du robot (deux lectures identiques de suite)."""

BOUNDS = {
    "policy": (-1.0, 60.0),
    "cpi": (-5.0, 120.0),
    "y10": (-1.5, 40.0),
}
# Variation maximale « normale » entre deux lectures (points de %)
JUMP = {"policy": 2.0, "cpi": 6.0, "y10": 1.5}
JUMP_OVERRIDE = {("policy", "TR"): 10.0, ("cpi", "TR"): 25.0, ("y10", "TR"): 6.0}


def check(kind, code, new, prev, pending):
    """Renvoie (décision, raison). décision ∈ {"accept", "reject", "pending"}.
    new / prev / pending : dict {"value", "date"} ou None."""
    if new is None or new.get("value") is None:
        return "reject", "aucune valeur reçue"
    v = new["value"]
    lo, hi = BOUNDS[kind]
    if not (lo <= v <= hi):
        return "reject", f"hors bornes [{lo} ; {hi}]"
    if prev and prev.get("value") is not None:
        if new.get("date") and prev.get("date") and new["date"] < prev["date"]:
            return "reject", f"date plus ancienne que la valeur gardée ({prev['date']})"
        lim = JUMP_OVERRIDE.get((kind, code), JUMP[kind])
        if abs(v - prev["value"]) > lim:
            if pending and pending.get("value") == v and pending.get("date") == new.get("date"):
                return "accept", f"saut de {v - prev['value']:+.2f} pt confirmé par une 2e lecture"
            return "pending", f"saut de {v - prev['value']:+.2f} pt (> {lim}) : à confirmer au prochain passage"
    return "accept", ""


def check_fx(ccy, new, prev, pending):
    """Taux de change (unités de devise pour 1 EUR)."""
    if new is None or not new.get("value") or new["value"] <= 0:
        return "reject", "aucune valeur reçue"
    if prev and prev.get("value"):
        if new.get("date") and prev.get("date") and new["date"] < prev["date"]:
            return "reject", "date plus ancienne que la valeur gardée"
        lim = 0.15 if ccy in ("TRY",) else 0.10
        chg = new["value"] / prev["value"] - 1
        if abs(chg) > lim:
            if pending and pending.get("value") == new["value"] and pending.get("date") == new.get("date"):
                return "accept", f"variation {chg:+.1%} confirmée"
            return "pending", f"variation {chg:+.1%} > {lim:.0%} : à confirmer"
    return "accept", ""
