"""Tests du robot (sans réseau) : contrôles de plausibilité, déduction des décisions,
lecture de calendriers officiels enregistrés."""
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "robot"))

import calendars as K  # noqa: E402
import update as U  # noqa: E402
from validate import check, check_fx  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


class Fake:
    def __init__(self, path):
        self.content = open(path, "rb").read()
        self.text = self.content.decode("utf-8", "replace")


class TestValidation(unittest.TestCase):
    def test_hors_bornes(self):
        self.assertEqual(check("policy", "US", {"value": 250, "date": "2026-01-01"}, None, None)[0], "reject")

    def test_saut_mis_en_attente_puis_confirme(self):
        prev = {"value": 2.0, "date": "2026-01-01"}
        new = {"value": 7.0, "date": "2026-01-02"}
        self.assertEqual(check("policy", "US", new, prev, None)[0], "pending")
        self.assertEqual(check("policy", "US", new, prev, {"value": 7.0, "date": "2026-01-02"})[0], "accept")

    def test_turquie_saut_autorise(self):
        self.assertEqual(check("policy", "TR", {"value": 45, "date": "2026-01-02"}, {"value": 40, "date": "2026-01-01"}, None)[0], "accept")

    def test_date_qui_recule(self):
        self.assertEqual(check("cpi", "US", {"value": 3, "date": "2026-01"}, {"value": 3, "date": "2026-02"}, None)[0], "reject")

    def test_fx(self):
        self.assertEqual(check_fx("USD", {"value": 1.5, "date": "2026-01-02"}, {"value": 1.1, "date": "2026-01-01"}, None)[0], "pending")
        self.assertEqual(check_fx("USD", {"value": 1.11, "date": "2026-01-02"}, {"value": 1.1, "date": "2026-01-01"}, None)[0], "accept")


class TestDecisions(unittest.TestCase):
    S = [("2026-01-01", 4.0), ("2026-03-18", 4.0), ("2026-03-19", 3.75), ("2026-06-01", 3.75)]

    def test_baisse(self):
        self.assertEqual(U.decision_at(self.S, "2026-03-18"), {"type": "baisse", "bp": -25, "new": 3.75})

    def test_maintien(self):
        self.assertEqual(U.decision_at(self.S, "2026-05-10")["type"], "maintien")

    def test_dernier_changement(self):
        self.assertEqual(U.last_change(self.S), ("2026-03-19", 4.0, 3.75))


class TestCalendriers(unittest.TestCase):
    today = dt.date(2026, 11, 23)

    def run_parser(self, name, mapping):
        K.page = lambda url, **kw: Fake(os.path.join(FIX, mapping[url]))
        return K.fetch(name, list(mapping)[0], self.today)

    def test_fed(self):
        d = self.run_parser("fed", {"https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm": "fed.html"})
        self.assertIn("2026-10-28", d)
        self.assertIn("2026-12-09", d)

    def test_boe(self):
        d = self.run_parser("boe", {"https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates": "boe.html"})
        self.assertIn("2026-11-05", d)
        self.assertIn("2026-12-17", d)

    def test_boj(self):
        d = self.run_parser("boj", {"https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm": "boj.html"})
        self.assertIn("2026-10-30", d)
        self.assertIn("2026-12-18", d)

    def test_rba(self):
        d = self.run_parser("rba", {"https://www.rba.gov.au/schedules-events/calendar/?topics=mone": "rba.html"})
        self.assertIn("2026-11-03", d)

    def test_banxico_pdf(self):
        d = K._banxico_pdf(open(os.path.join(FIX, "banxico_2026.pdf"), "rb").read())
        self.assertEqual(d, ["2026-02-05", "2026-03-26", "2026-05-07", "2026-06-25",
                             "2026-08-06", "2026-09-24", "2026-11-05", "2026-12-17"])


if __name__ == "__main__":
    unittest.main()
