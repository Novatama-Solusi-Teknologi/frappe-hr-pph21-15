"""Versioned PP 58/2023 master data. Upper limits are inclusive, in IDR.

Source: PP 58/2023, Appendix A-C (44, 40 and 41 rows respectively).
https://jdih.kemenkeu.go.id/api/download/e47c3fc4-a912-4bf1-bcad-335fee3f71f8/2023pp058.pdf
"""

from datetime import date
from decimal import Decimal
from hashlib import sha256
import json

RULE_VERSION = "PP58-2023_PMK168-2023_v1"
SUPPORTED_YEARS = (2024, 2025, 2026)

# All numbers below are thousands of rupiah, converted exactly to full IDR.
_A = [5400, 5650, 5950, 6300, 6750, 7500, 8550, 9650, 10050, 10350,
      10700, 11050, 11600, 12500, 13750, 15100, 16950, 19750, 24150,
      26450, 28000, 30050, 32400, 35400, 39100, 43850, 47800, 51400,
      56300, 62200, 68600, 77500, 89000, 103000, 125000, 157000,
      206000, 337000, 454000, 550000, 695000, 910000, 1400000, None]
_B = [6200, 6500, 6850, 7300, 9200, 10750, 11250, 11600, 12600,
      13600, 14950, 16400, 18450, 21850, 26000, 27700, 29350,
      31450, 33950, 37100, 41100, 45800, 49500, 53800, 58500,
      64000, 71000, 80000, 93000, 109000, 129000, 163000, 211000,
      374000, 459000, 555000, 704000, 957000, 1405000, None]
_C = [6600, 6950, 7350, 7800, 8850, 9800, 10950, 11200, 12050,
      12950, 14150, 15550, 17050, 19500, 22700, 26600, 28100,
      30100, 32600, 35400, 38900, 43000, 47400, 51200, 55800,
      60400, 66700, 74500, 83200, 95600, 110000, 134000, 169000,
      221000, 390000, 463000, 561000, 709000, 965000, 1419000, None]


def _bands(limits, initial_rates):
    rates = initial_rates + list(range(4, 35))
    assert len(limits) == len(rates)
    return tuple((None if limit is None else Decimal(limit * 1000),
                  Decimal(str(rate)) / 100) for limit, rate in zip(limits, rates))


TER = {
    "A": _bands(_A, [0, .25, .5, .75, 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 3, 3.5]),
    "B": _bands(_B, [0, .25, .5, .75, 1, 1.5, 2, 2.5, 3]),
    "C": _bands(_C, [0, .25, .5, .75, 1, 1.25, 1.5, 1.75, 2, 3]),
}
PTKP = {
    "TK/0": ("A", Decimal(54000000)), "TK/1": ("A", Decimal(58500000)),
    "TK/2": ("B", Decimal(63000000)), "TK/3": ("B", Decimal(67500000)),
    "K/0": ("A", Decimal(58500000)), "K/1": ("B", Decimal(63000000)),
    "K/2": ("B", Decimal(67500000)), "K/3": ("C", Decimal(72000000)),
}
PROGRESSIVE = ((Decimal(60000000), Decimal('.05')),
               (Decimal(250000000), Decimal('.15')),
               (Decimal(500000000), Decimal('.25')),
               (Decimal(5000000000), Decimal('.30')),
               (None, Decimal('.35')))
JOB_EXPENSE_RATE = Decimal('.05')
JOB_EXPENSE_MONTHLY_CAP = Decimal(500000)


def rules_hash():
    payload = {"ter": TER, "ptkp": PTKP, "progressive": PROGRESSIVE,
               "job_rate": JOB_EXPENSE_RATE, "job_cap": JOB_EXPENSE_MONTHLY_CAP,
               "version": RULE_VERSION, "years": SUPPORTED_YEARS}
    return sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest()


def check_tax_date(value):
    day = date.fromisoformat(str(value)[:10])
    if day.year not in SUPPORTED_YEARS:
        raise ValueError("Master pajak app ini hanya mencakup tahun 2024–2026. Perbarui app untuk tahun lain.")
    return day
