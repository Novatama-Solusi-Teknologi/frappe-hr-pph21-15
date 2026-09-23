import random
import unittest
from decimal import Decimal

from frappe_hr_pph21.tax.engine import (
    annual_liability, final_period, monthly, progressive_tax, round_tax, ter_rate,
)
from frappe_hr_pph21.tax.rules import PTKP, TER, check_tax_date, rules_hash


class TaxEngineTest(unittest.TestCase):
    def test_pp58_official_example(self):
        # PP58 explanatory notes: K/0, salary 10m, pension 100k/month.
        self.assertEqual(monthly(10000000, "K/0", "Gross").withholding, 200000)
        result = final_period(10000000, 110000000, 1200000, 2200000, "K/0", 12, "Gross")
        self.assertEqual(result.annual_gross, 120000000)
        self.assertEqual(result.job_expense, 6000000)
        self.assertEqual(result.pkp, 54300000)
        self.assertEqual(result.annual_tax, 2715000)
        self.assertEqual(result.withholding, 515000)

    def test_grossup_crosses_band(self):
        result = monthly(10000000, "TK/0")
        self.assertEqual(result.allowance, 230179)
        self.assertEqual(result.rate, Decimal('.0225'))
        self.assertEqual(result.taxable_gross, 10230179)
        self.assertEqual(result.allowance, result.withholding)

    def test_b_and_c_independent_examples(self):
        self.assertEqual(monthly(10000000, "K/1", "Gross").withholding, 150000)
        self.assertEqual(monthly(12000000, "K/3", "Gross").withholding, 240000)
        self.assertEqual(monthly(15000000, "K/3", "Gross").withholding, 750000)
        self.assertEqual(monthly(70000000, "K/2", "Gross").withholding, 14700000)

    def test_all_table_boundaries(self):
        self.assertEqual({k: len(v) for k, v in TER.items()}, {"A": 44, "B": 40, "C": 41})
        for category, bands in TER.items():
            previous = Decimal(0)
            for idx, (upper, rate) in enumerate(bands):
                if upper is None:
                    self.assertEqual(ter_rate(previous + 1, category), rate)
                    continue
                self.assertGreater(upper, previous)
                self.assertEqual(ter_rate(upper, category), rate)
                self.assertEqual(ter_rate(upper + Decimal('.01'), category), bands[idx + 1][1])
                previous = upper

    def test_ptkp_categories_and_values(self):
        expected = {"TK/0": ("A", 54000000), "TK/1": ("A", 58500000),
                    "TK/2": ("B", 63000000), "TK/3": ("B", 67500000),
                    "K/0": ("A", 58500000), "K/1": ("B", 63000000),
                    "K/2": ("B", 67500000), "K/3": ("C", 72000000)}
        self.assertEqual(PTKP, expected)

    def test_progressive_marginal_rates(self):
        for base, expected in [(0, 0), (60000000, 3000000), (250000000, 31500000),
                               (500000000, 94000000), (5000000000, 1444000000),
                               (5000001000, 1444000350)]:
            self.assertEqual(progressive_tax(base), expected)
        self.assertEqual(progressive_tax(60000999), 3000000)
        self.assertEqual(progressive_tax(60001000), 3000150)

    def test_monthly_grossup_invariants_near_every_threshold(self):
        samples = 0
        for category, status in (("A", "TK/0"), ("B", "K/1"), ("C", "K/3")):
            for upper, rate in TER[category]:
                if upper is None:
                    continue
                # Both gross boundaries and the corresponding net boundary.
                for center in (upper, upper * (1-rate)):
                    for offset in (-2, -1, 0, 1, 2, Decimal('.25')):
                        for rounding in ("Floor IDR", "Half Up IDR"):
                            base = center + offset
                            result = monthly(base, status, rounding=rounding)
                            self.assertEqual(result.withholding, result.allowance)
                            self.assertEqual(result.taxable_gross - result.withholding, base)
                            self.assertEqual(result.withholding, round_tax(result.taxable_gross * result.rate, rounding))
                            samples += 1
        self.assertEqual(samples, 2928)

    def test_zero_and_exempt_income(self):
        for category, status in (("A", "TK/0"), ("B", "K/1"), ("C", "K/3")):
            for gross in (0, TER[category][0][0]):
                result = monthly(gross, status)
                self.assertEqual(result.allowance, 0)
                self.assertEqual(result.withholding, 0)

    def test_randomized_monthly_fixed_points(self):
        rng = random.Random(20260923)
        for _ in range(400):
            base = Decimal(rng.randrange(0, 300000000000)) / 100
            status = rng.choice(list(PTKP))
            result = monthly(base, status)
            self.assertEqual(result.allowance, result.withholding)

    def test_annual_grossup_includes_previous_allowances(self):
        jan = monthly(10000000, "TK/0")
        result = final_period(10000000, jan.taxable_gross * 11, 0, jan.withholding * 11, "TK/0", 12)
        self.assertEqual(result.allowance, result.withholding)
        self.assertEqual(result.annual_tax, jan.withholding * 11 + result.withholding)
        self.assertEqual(result.annual_gross, 120000000 + jan.allowance * 11 + result.allowance)
        self.assertEqual(result.pkp % 1000, 0)

    def test_resignation_refund_not_negative_allowance(self):
        jan = monthly(10000000, "TK/0")
        result = final_period(10000000, jan.taxable_gross, 0, jan.withholding, "TK/0", 2)
        self.assertEqual(result.annual_tax, 0)
        self.assertEqual(result.allowance, 0)
        self.assertEqual(result.withholding, 0)
        self.assertEqual(result.refund, jan.withholding)

    def test_join_midyear_no_annualisation(self):
        job, ptkp, pkp, tax = annual_liability(60000000, 0, "TK/0", 6)
        self.assertEqual((job, ptkp, pkp, tax), (3000000, 54000000, 3000000, 150000))

    def test_job_expense_low_income_and_cap(self):
        self.assertEqual(annual_liability(5000000, 0, "TK/0", 1)[0], 250000)
        self.assertEqual(annual_liability(100000000, 0, "TK/0", 3)[0], 1500000)

    def test_thr_combined_monthly_base(self):
        combined = monthly(20000000, "TK/0", "Gross")
        self.assertEqual(combined.withholding, 1800000)
        self.assertNotEqual(combined.withholding, monthly(10000000, "TK/0", "Gross").withholding * 2)

    def test_annual_high_income_and_rounding(self):
        for status in PTKP:
            for base in (5000000, 9000000, 50000000, 500000000, 3000000000):
                previous = monthly(base, status)
                result = final_period(base, previous.taxable_gross * 11, 1200000,
                                      previous.withholding * 11, status, 12)
                self.assertEqual(result.annual_tax, previous.withholding * 11 + result.withholding - result.refund)
                self.assertEqual(result.allowance, result.withholding)
                self.assertLess(result.iterations, 256)

    def test_invalid_inputs_fail_closed(self):
        for value in (-1, 'NaN', 'Infinity', 'not money'):
            with self.assertRaises(ValueError):
                monthly(value, "TK/0")
        with self.assertRaises(ValueError):
            monthly(1000, "K/I/0")
        with self.assertRaises(ValueError):
            monthly(1000, "TK/0", method="Net")
        with self.assertRaises(ValueError):
            round_tax(1000, "Unspecified")
        for months in (0, 13, 1.5):
            with self.assertRaises(ValueError):
                annual_liability(1000, 0, "TK/0", months)
        for day in ("2023-12-31", "2027-01-01"):
            with self.assertRaises(ValueError):
                check_tax_date(day)
        self.assertEqual(check_tax_date("2026-12-31").year, 2026)
        self.assertEqual(len(rules_hash()), 64)


if __name__ == "__main__":
    unittest.main()
