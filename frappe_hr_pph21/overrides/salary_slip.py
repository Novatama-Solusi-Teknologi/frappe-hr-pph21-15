"""v15 integration. Let HRMS finish prorating amounts before PPh 21.

Submitted Salary Slips and immutable snapshots are the tax ledger. There is
one canonical slip per employee/company/calendar month. An Employee Tax
Profile row lock serializes submit/cancel, and a unique key guards races.
"""

import calendar
from datetime import date
from hashlib import sha256
import json

import frappe
from frappe.utils import cint, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from frappe_hr_pph21 import __version__
from frappe_hr_pph21.setup import ALLOWANCE, COMPONENTS, REFUND, WITHHOLDING, validate_component
from frappe_hr_pph21.tax.engine import dec, final_period, monthly
from frappe_hr_pph21.tax.rules import RULE_VERSION, check_tax_date, rules_hash


class PPh21SalarySlip(SalarySlip):
    def calculate_net_pay(self, skip_tax_breakup_computation=False):
        active = self.employee and frappe.db.get_value("Employee", self.employee, "pph21_enabled")
        if not active:
            if self.get("pph21_tax_profile"):
                frappe.throw("Slip ini memakai Frappe HR PPh21; aktifkan kembali PPh21 Enabled pada pegawai.")
            if self.employee and self.company and self.start_date and frappe.db.exists("Salary Slip", {
                "employee": self.employee, "company": self.company, "docstatus": 1,
                "pph21_tax_year": getdate(self.start_date).year, "pph21_tax_profile": ["is", "set"],
            }):
                frappe.throw("Pegawai sudah memakai Frappe HR PPh21 tahun ini. Jangan menonaktifkan di tengah tahun tanpa migrasi/koreksi riwayat.")
            return super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)
        self._pph21_calculating = True
        try:
            settings, profile, start, end, employee = self._pph21_context()
            # Previous draft output never becomes a new taxable input.
            for table in ("earnings", "deductions"):
                self.set(table, [row for row in self.get(table) if row.salary_component not in COMPONENTS])
            self._pph21_check_structure()
            super().calculate_net_pay(skip_tax_breakup_computation=True)
            self._pph21_apply(settings, profile, start, end, employee)
        finally:
            self._pph21_calculating = False

    def add_tax_components(self):
        if getattr(self, "_pph21_calculating", False):
            # HRMS may otherwise auto-discover unrelated tax components from
            # the global Salary Component master even if structure has none.
            self._component_based_variable_tax = {}
            return
        return super().add_tax_components()

    def compute_income_tax_breakup(self):
        if getattr(self, "_pph21_calculating", False) or self.get("pph21_tax_profile"):
            return  # Custom panel/report replaces projected annual tax fields.
        return super().compute_income_tax_breakup()

    def _pph21_context(self):
        if not self.company or not self.start_date or not self.end_date:
            frappe.throw("Lengkapi Company, Start Date, dan End Date sebelum menghitung PPh 21.")
        settings_name = frappe.db.get_value("PPh21 Settings", {"company": self.company}, "name")
        if not settings_name:
            frappe.throw("Buat PPh21 Settings untuk perusahaan ini.")
        settings = frappe.get_doc("PPh21 Settings", settings_name)
        if not settings.enabled:
            frappe.throw("Aktifkan PPh21 Settings untuk pegawai yang menggunakan Frappe HR PPh21.")
        start, end = getdate(self.start_date), getdate(self.end_date)
        try:
            check_tax_date(start)
        except ValueError as exc:
            frappe.throw(str(exc))
        if (start.year, start.month) != (end.year, end.month) or end < start:
            frappe.throw("Frappe HR PPh21 memerlukan satu periode dalam satu bulan kalender.")
        if self.payroll_frequency != "Monthly" or self.salary_slip_based_on_timesheet:
            frappe.throw("Rilis ini hanya mendukung payroll Monthly tanpa Timesheet.")
        if self.currency != "IDR" or frappe.db.get_value("Company", self.company, "default_currency") != "IDR":
            frappe.throw("Salary Slip dan Company harus menggunakan IDR.")
        if dec(self.exchange_rate) != 1:
            frappe.throw("Exchange rate payroll IDR harus 1.")
        employee = frappe.get_doc("Employee", self.employee)
        if employee.company != self.company:
            frappe.throw("Perusahaan pegawai berbeda dari Salary Slip.")
        join = getdate(employee.date_of_joining)
        leave = getdate(employee.relieving_date) if employee.relieving_date else None
        period_start = max(start.replace(day=1), join)
        period_end = end.replace(day=calendar.monthrange(end.year, end.month)[1])
        if leave:
            period_end = min(period_end, leave)
        if join > end or (leave and leave < start):
            frappe.throw("Periode slip di luar masa kerja pegawai.")
        if start not in (start.replace(day=1), period_start) or end not in (
            end.replace(day=calendar.monthrange(end.year, end.month)[1]), period_end
        ):
            frappe.throw("Gunakan satu slip untuk seluruh bulan kalender (atau sampai tanggal resign).")
        profile_name = frappe.db.get_value("PPh21 Employee Tax Profile", {
            "employee": self.employee, "company": self.company, "tax_year": start.year,
        }, "name")
        if not profile_name:
            frappe.throw(f"Buat PPh21 Employee Tax Profile untuk {self.employee}, tahun {start.year}.")
        profile = frappe.get_doc("PPh21 Employee Tax Profile", profile_name,
                                 for_update=bool(getattr(self, "_pph21_locked", False)))
        if not profile.permanent_employee or not profile.resident_full_year or profile.facility != "Normal":
            frappe.throw("Profil pajak di luar cakupan rilis: pegawai tetap, WP DN sepanjang tahun, fasilitas Normal.")
        if not profile.get("tax_identity_validated"):
            frappe.throw("Profil belum memiliki identitas pajak tervalidasi untuk tarif normal.")
        if start.month <= cint(profile.opening_through_month):
            frappe.throw("Masa ini sudah dicakup saldo awal; tidak boleh dihitung dua kali.")
        return settings, profile, start, end, employee

    def _pph21_check_structure(self):
        if not self.salary_structure:
            frappe.throw("Salary Structure diperlukan untuk payroll PPh21.")
        structure = frappe.get_doc("Salary Structure", self.salary_structure)
        generated_abbrs = [value[1] for value in COMPONENTS.values()]
        for table in ("earnings", "deductions"):
            for row in list(structure.get(table)) + list(self.get(table)):
                if row.salary_component in COMPONENTS:
                    frappe.throw("Hapus komponen otomatis PPh21 dari Salary Structure; app menambahkannya sendiri.")
                if row.variable_based_on_taxable_salary:
                    frappe.throw("Nonaktifkan komponen pajak standar untuk struktur pegawai PPh21.")
                expression = (row.get("formula") or "") + " " + (row.get("condition") or "")
                if any(abbr in expression for abbr in generated_abbrs) or "pph21_tax_" in expression:
                    frappe.throw("Formula gaji tidak boleh bergantung pada hasil PPh 21 PPh21 (circular dependency).")

    def _pph21_history(self, profile, start, employee):
        filters = {
            "employee": self.employee, "company": self.company, "docstatus": 1,
            "start_date": ["between", [date(start.year, 1, 1), date(start.year, 12, 31)]],
            "name": ["!=", self.name or ""],
        }
        fields = ["name", "start_date", "end_date", "pph21_tax_profile", "pph21_tax_gross",
                  "pph21_tax_allowance", "pph21_tax_deductions", "pph21_tax_withholding",
                  "pph21_tax_refund", "pph21_tax_final", "pph21_tax_snapshot"]
        if getattr(self, "_pph21_locked", False):
            # Current read, not an old REPEATABLE READ snapshot created during
            # validate. Columns are constants, never supplied by a caller.
            rows = frappe.db.sql(
                "SELECT " + ", ".join(fields) + " FROM `tabSalary Slip` "
                "WHERE employee=%s AND company=%s AND docstatus=1 "
                "AND start_date BETWEEN %s AND %s AND name!=%s ORDER BY start_date FOR UPDATE",
                (self.employee, self.company, date(start.year, 1, 1), date(start.year, 12, 31), self.name or ""),
                as_dict=True,
            )
        else:
            rows = frappe.get_all("Salary Slip", filters=filters, fields=fields, order_by="start_date asc")
        cutoff = cint(profile.opening_through_month)
        seen, prior_names = set(), []
        gross, deductions, tax = dec(profile.opening_gross), dec(profile.opening_deductions), dec(profile.opening_tax)
        for row in rows:
            month = getdate(row.start_date).month
            if month <= cutoff:
                if row.pph21_tax_profile:
                    frappe.throw("Saldo awal tumpang tindih dengan slip PPh21 submitted.")
                continue
            if month >= start.month:
                frappe.throw(f"Slip {row.name} sudah submitted pada masa yang sama/lebih baru. Batalkan berurutan dari masa terbaru.")
            if row.pph21_tax_profile != profile.name or month in seen:
                frappe.throw(f"Riwayat masa {month} tidak valid/duplikat. Lengkapi saldo awal atau koreksi slip {row.name}.")
            if row.pph21_tax_final:
                frappe.throw("Sudah ada masa pajak terakhir. Rehire dalam tahun yang sama belum didukung.")
            if not row.pph21_tax_snapshot:
                frappe.throw(f"Kertas kerja slip {row.name} tidak tersedia.")
            old_snapshot = json.loads(row.pph21_tax_snapshot)
            if old_snapshot.get("employment") != {
                "joining_date": str(getdate(employee.date_of_joining)),
                # Future relieving dates may legitimately be entered after earlier payrolls.
            }:
                frappe.throw("Tanggal mulai bekerja berubah setelah payroll. Koreksi riwayat sebelum menghitung ulang.")
            seen.add(month)
            prior_names.append(row.name)
            gross += dec(row.pph21_tax_gross)
            deductions += dec(row.pph21_tax_deductions)
            tax += dec(row.pph21_tax_withholding) - dec(row.pph21_tax_refund)
        first = max(date(start.year, 1, 1), getdate(employee.date_of_joining)).month
        expected = set(range(max(first, cutoff + 1), start.month))
        if seen != expected:
            missing = sorted(expected - seen)
            frappe.throw(f"Riwayat payroll belum lengkap untuk bulan {missing}. Isi saldo awal migrasi atau submit slip yang belum ada.")
        return gross, deductions, tax, prior_names

    def _pph21_apply(self, settings, profile, start, end, employee):
        mapping = {row.salary_component: row.treatment for row in settings.component_mapping}
        base, current_deductions = dec(0), dec(0)
        details = []
        for table in ("earnings", "deductions"):
            for row in self.get(table):
                if row.salary_component in COMPONENTS:
                    frappe.throw("Additional Salary tidak boleh memakai komponen otomatis PPh21.")
                treatment = mapping.get(row.salary_component)
                if not treatment:
                    frappe.throw(f"Petakan komponen {row.salary_component} pada PPh21 Settings.")
                if row.variable_based_on_taxable_salary:
                    frappe.throw("Komponen pajak standar tidak boleh digabung dengan PPh21 Potongan Pajak.")
                amount = dec(row.amount)
                if amount < 0:
                    frappe.throw("Komponen negatif memerlukan koreksi payroll asal; tidak didukung dalam kalkulasi PPh21.")
                if treatment in ("Taxable Cash", "Taxable Noncash"):
                    if table != "earnings":
                        frappe.throw("Komponen bruto pajak harus berupa Earning.")
                    if treatment == "Taxable Cash" and row.do_not_include_in_total:
                        frappe.throw(f"{row.salary_component}: Taxable Cash harus masuk total earnings.")
                    if treatment == "Taxable Noncash" and not (
                        row.do_not_include_in_total and row.get("do_not_include_in_accounts")
                    ):
                        frappe.throw(f"{row.salary_component}: Noncash harus Do Not Include in Total dan Do Not Include in Accounting Entries. Pembukuan BPJS dilakukan terpisah.")
                    base += amount
                elif treatment == "Annual Deduction":
                    if table != "deductions" or row.do_not_include_in_total:
                        frappe.throw("Annual Deduction harus potongan riil pegawai yang masuk total deduction.")
                    current_deductions += amount
                details.append(dict(component=row.salary_component, table=table,
                                    treatment=treatment, amount=str(amount),
                                    additional_salary=row.get("additional_salary")))
        prior_gross, prior_deductions, prior_tax, prior_names = self._pph21_history(profile, start, employee)
        leave = getdate(employee.relieving_date) if employee.relieving_date else None
        is_final = start.month == 12 or bool(leave and (leave.year, leave.month) == (start.year, start.month))
        first = max(date(start.year, 1, 1), getdate(employee.date_of_joining))
        months = start.month - first.month + 1
        try:
            if is_final:
                result = final_period(base, prior_gross, prior_deductions + current_deductions,
                                      prior_tax, profile.ptkp_status, months, profile.method, settings.rounding)
            else:
                result = monthly(base, profile.ptkp_status, profile.method, settings.rounding)
        except ValueError as exc:
            frappe.throw(str(exc))
        for name, amount in ((ALLOWANCE, result.allowance), (WITHHOLDING, result.withholding),
                             (REFUND, result.refund)):
            component = validate_component(name)
            expected_account = settings.expense_account if name == ALLOWANCE else settings.tax_payable_account
            if not any(row.company == self.company and row.default_account == expected_account
                       for row in component.accounts):
                frappe.throw(f"Simpan ulang PPh21 Settings untuk memetakan akun {name}.")
            table = "deductions" if name == WITHHOLDING else "earnings"
            if amount:
                self.append(table, dict(salary_component=name, abbr=component.salary_component_abbr,
                                        amount=float(amount), default_amount=float(amount),
                                        additional_amount=0, depends_on_payment_days=0,
                                        is_tax_applicable=component.is_tax_applicable,
                                        do_not_include_in_total=0, do_not_include_in_accounts=0,
                                        variable_based_on_taxable_salary=0, is_flexible_benefit=0))
        self.set_precision_for_component_amounts()
        # Already-prorated rows: do not prorate the final amounts a second time.
        self.gross_pay = self.get_component_totals("earnings")
        self.base_gross_pay = flt(self.gross_pay, self.precision("base_gross_pay"))
        self.set_net_pay()
        # Stock fields describe projected annual tax. Clear stale values when
        # amending an old slip; the PPh21 panel is the authoritative calculation.
        for field in ("ctc", "non_taxable_earnings", "total_earnings", "income_from_other_sources",
                      "standard_tax_exemption_amount", "tax_exemption_declaration",
                      "deductions_before_tax_calculation", "annual_taxable_amount",
                      "income_tax_deducted_till_date", "current_month_income_tax",
                      "future_income_tax_deductions", "total_income_tax"):
            self.set(field, 0)
        values = dict(profile=profile.name, year=start.year, month=start.month, final=int(is_final),
                      category=profile.ter_category, method=profile.method, rule=RULE_VERSION,
                      base=result.base_gross, gross=result.taxable_gross, deductions=current_deductions,
                      allowance=result.allowance, withholding=result.withholding, refund=result.refund,
                      rate=result.rate * 100, annual=result.annual_tax)
        for key, value in values.items():
            self.set("pph21_tax_" + key, float(value) if hasattr(value, "as_tuple") else value)
        snapshot = dict(app_version=__version__, rule_version=RULE_VERSION, rule_hash=rules_hash(),
                        rounding=settings.rounding, employee=self.employee, company=self.company,
                        year=start.year, month=start.month, final=is_final, method=profile.method,
                        ptkp_status=profile.ptkp_status, category=profile.ter_category,
                        employment={"joining_date": str(getdate(employee.date_of_joining))},
                        relieving_date=str(leave) if leave else None, employment_months=months,
                        opening={field: profile.get(field) for field in (
                            "opening_through_month", "opening_gross", "opening_allowance",
                            "opening_deductions", "opening_tax", "opening_reference")},
                        prior_slips=prior_names, prior_gross=str(prior_gross), prior_tax=str(prior_tax),
                        prior_deductions=str(prior_deductions), components=details,
                        accounts={"allowance": settings.expense_account, "tax": settings.tax_payable_account},
                        result=result.as_dict())
        self.pph21_tax_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str, indent=2)

    def before_submit(self):
        parent = getattr(super(), "before_submit", None)
        if parent:
            parent()
        if self.get("pph21_tax_profile"):
            self._pph21_lock_profile()
            # Recompute under a database row lock: draft snapshots are not trusted.
            self.calculate_net_pay()
            self.compute_year_to_date()
            self.compute_month_to_date()
            self.compute_component_wise_year_to_date()
            key = f"{self.company}|{self.employee}|{self.pph21_tax_year}|{self.pph21_tax_month}"
            self.pph21_tax_key = sha256(key.encode()).hexdigest()

    def before_cancel(self):
        parent = getattr(super(), "before_cancel", None)
        if parent:
            parent()
        if not self.get("pph21_tax_profile"):
            return
        self._pph21_lock_profile()
        newer = frappe.db.sql(
            "SELECT name FROM `tabSalary Slip` WHERE employee=%s AND company=%s "
            "AND docstatus=1 AND name!=%s AND pph21_tax_year=%s AND pph21_tax_month>%s FOR UPDATE",
            (self.employee, self.company, self.name, self.pph21_tax_year, self.pph21_tax_month),
        )
        if newer:
            frappe.throw("Batalkan slip PPh21 dari masa terbaru dahulu; slip berikutnya bergantung pada riwayat ini.")
        self.pph21_tax_key = None  # Release unique active-month key atomically with cancellation.

    def _pph21_lock_profile(self):
        frappe.db.sql("SELECT name FROM `tabPPh21 Employee Tax Profile` WHERE name=%s FOR UPDATE",
                      (self.pph21_tax_profile,))
        self._pph21_locked = True
