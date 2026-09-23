"""Deterministic PPh 21 for permanent resident employees, normal facility.

Rounding is explicit (Floor IDR or Half Up IDR). This is a payroll setting,
not an assertion that every tax filing interface uses the same rounding.
No annualisation for a change in subjective tax liability is supported.
"""

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_UP

from .rules import JOB_EXPENSE_MONTHLY_CAP, JOB_EXPENSE_RATE, PROGRESSIVE, PTKP, TER

ZERO = Decimal(0)
ONE = Decimal(1)
ROUNDING = {"Floor IDR": ROUND_FLOOR, "Half Up IDR": ROUND_HALF_UP}


def dec(value):
    try:
        result = Decimal(str(value if value is not None else 0))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Nilai nominal tidak valid.") from exc
    if not result.is_finite():
        raise ValueError("Nilai nominal harus finite.")
    return result


def nonnegative(value, label):
    result = dec(value)
    if result < 0:
        raise ValueError(f"{label} tidak boleh negatif.")
    return result


def round_tax(value, rounding="Floor IDR"):
    if rounding not in ROUNDING:
        raise ValueError("Metode pembulatan tidak dikenal.")
    return dec(value).quantize(ONE, rounding=ROUNDING[rounding])


def profile_values(status):
    if status not in PTKP:
        raise ValueError("Status PTKP tidak didukung.")
    return PTKP[status]


def ter_rate(gross, category):
    gross = nonnegative(gross, "Bruto")
    if category not in TER:
        raise ValueError("Kategori TER tidak valid.")
    for upper, rate in TER[category]:
        if upper is None or gross <= upper:
            return rate
    raise AssertionError("TER table must end with an unbounded band")


def progressive_tax(pkp):
    taxable = max(ZERO, dec(pkp))
    taxable = (taxable / 1000).to_integral_value(rounding=ROUND_FLOOR) * 1000
    previous, tax = ZERO, ZERO
    for upper, rate in PROGRESSIVE:
        part = taxable - previous if upper is None else min(taxable, upper) - previous
        tax += max(ZERO, part) * rate
        if upper is None or taxable <= upper:
            break
        previous = upper
    return tax


@dataclass(frozen=True)
class Result:
    base_gross: Decimal
    allowance: Decimal
    taxable_gross: Decimal
    withholding: Decimal
    refund: Decimal
    rate: Decimal = ZERO
    annual_gross: Decimal = ZERO
    job_expense: Decimal = ZERO
    annual_deductions: Decimal = ZERO
    ptkp: Decimal = ZERO
    pkp: Decimal = ZERO
    annual_tax: Decimal = ZERO
    prior_tax: Decimal = ZERO
    iterations: int = 0

    def as_dict(self):
        return {key: str(value) if isinstance(value, Decimal) else value
                for key, value in asdict(self).items()}


def monthly(base_gross, status, method="Gross Up", rounding="Floor IDR"):
    base = nonnegative(base_gross, "Bruto")
    category, _ = profile_values(status)
    if method not in ("Gross", "Gross Up"):
        raise ValueError("Metode pajak tidak didukung.")
    allowance = ZERO
    if method == "Gross Up":
        # Candidates around each analytic root also cover whole-IDR rounding.
        # Enumerating in rate order and returning the lowest valid amount picks
        # the least fixed point where TER discontinuities admit several roots.
        candidates = []
        for _, rate in TER[category]:
            root = round_tax(base * rate / (ONE - rate), rounding)
            for candidate in (root - 1, root, root + 1):
                if candidate < 0:
                    continue
                actual = ter_rate(base + candidate, category)
                if actual == rate and round_tax((base + candidate) * actual, rounding) == candidate:
                    candidates.append(candidate)
        if not candidates:
            raise ValueError("Tidak ditemukan gross-up TER yang konsisten setelah pembulatan.")
        allowance = min(candidates)
    gross = base + allowance
    rate = ter_rate(gross, category)
    tax = round_tax(gross * rate, rounding)
    return Result(base, allowance, gross, tax, ZERO, rate=rate)


def annual_liability(gross, annual_deductions, status, employment_months, rounding="Floor IDR"):
    gross = nonnegative(gross, "Bruto setahun")
    deductions = nonnegative(annual_deductions, "Pengurang setahun")
    _, ptkp = profile_values(status)
    if not isinstance(employment_months, int) or not 1 <= employment_months <= 12:
        raise ValueError("Bulan bekerja harus 1–12.")
    job = min(gross * JOB_EXPENSE_RATE, employment_months * JOB_EXPENSE_MONTHLY_CAP)
    pkp = (max(ZERO, gross - job - deductions - ptkp) / 1000).to_integral_value(
        rounding=ROUND_FLOOR) * 1000
    return job, ptkp, pkp, round_tax(progressive_tax(pkp), rounding)


def final_period(base_gross, prior_gross, annual_deductions, prior_tax, status,
                 employment_months, method="Gross Up", rounding="Floor IDR"):
    base = nonnegative(base_gross, "Bruto masa terakhir")
    past = nonnegative(prior_gross, "Bruto masa sebelumnya, termasuk tunjangan pajak")
    paid = nonnegative(prior_tax, "PPh masa sebelumnya")
    deductions = nonnegative(annual_deductions, "Pengurang setahun")
    if method not in ("Gross", "Gross Up"):
        raise ValueError("Metode pajak tidak didukung.")
    allowance, iterations = ZERO, 0
    if method == "Gross Up":
        # Monotone iteration from zero gives the least nonnegative fixed point.
        # PKP is floored to 1,000 on EVERY evaluation, not only after solving.
        for iterations in range(1, 257):
            *_, liability = annual_liability(base + past + allowance, deductions,
                                             status, employment_months, rounding)
            candidate = max(ZERO, liability - paid)
            if candidate == allowance:
                break
            if candidate < allowance:
                raise ValueError("Gross-up tahunan tidak monoton; periksa input.")
            allowance = candidate
        else:
            raise ValueError("Gross-up tahunan gagal konvergen; slip tidak boleh diposting.")
    gross = base + past + allowance
    job, ptkp, pkp, liability = annual_liability(gross, deductions, status, employment_months, rounding)
    balance = liability - paid
    return Result(base, allowance, base + allowance, max(ZERO, balance), max(ZERO, -balance),
                  annual_gross=gross, job_expense=job, annual_deductions=deductions,
                  ptkp=ptkp, pkp=pkp, annual_tax=liability, prior_tax=paid, iterations=iterations)
