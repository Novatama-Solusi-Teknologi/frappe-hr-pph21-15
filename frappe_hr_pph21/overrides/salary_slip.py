"""v15 integration. Let HRMS finish prorating amounts before PPh 21.

Submitted Salary Slips and immutable snapshots are the tax ledger. There is
one canonical slip per employee/company/payment month. An Employee Tax
Profile and Employee row locks serialize submit/cancel; a unique key guards races.
"""

from datetime import date
from hashlib import sha256
import json

import frappe
from frappe.utils import cint, flt, getdate
from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip

from frappe_hr_pph21 import __version__
from frappe_hr_pph21.settings import selected_settings
from frappe_hr_pph21.setup import ALLOWANCE, COMPONENTS, REFUND, WITHHOLDING, validate_component, component_role, settings_components, noncash_component_name, component_account
from frappe_hr_pph21.tax.engine import dec, final_period, monthly
from frappe_hr_pph21.tax.rules import RULE_VERSION, check_tax_date, rules_hash


class PPh21SalarySlip(SalarySlip):
    def calculate_net_pay(self, skip_tax_breakup_computation=False):
        active = self.employee and frappe.db.get_value("Employee", self.employee, "pph21_enabled")
        if not active:
            if self.get("pph21_tax_profile"):
                frappe.throw("Slip ini memakai Frappe HR PPh21; aktifkan kembali PPh21 Enabled pada pegawai.")
            if self.employee and self.company and self.posting_date and frappe.db.exists("Salary Slip", {
                "employee": self.employee, "company": self.company, "docstatus": 1,
                "pph21_tax_year": getdate(self.posting_date).year, "pph21_tax_profile": ["is", "set"],
            }):
                frappe.throw("Pegawai sudah memakai Frappe HR PPh21 tahun ini. Jangan menonaktifkan di tengah tahun tanpa migrasi/koreksi riwayat.")
            return super().calculate_net_pay(skip_tax_breakup_computation=skip_tax_breakup_computation)
        self._pph21_calculating = True
        try:
            settings, profile, start, end, employee = self._pph21_context()
            self._pph21_noncash_names = {
                row.salary_component for row in settings.component_mapping
                if row.treatment == "Taxable Noncash" or row.get("noncash_offset_component")
            }
            # Fresh master reads per calculation; submit reloads under row locks.
            self._pph21_noncash_components = {}
            self._pph21_noncash_postings = {}
            self._pph21_settings = settings
            # Previous draft output never becomes a new taxable input.
            for table in ("earnings", "deductions"):
                self.set(table, [row for row in self.get(table) if not component_role(row.salary_component)])
            self._pph21_check_structure()
            super().calculate_net_pay(skip_tax_breakup_computation=True)
            self._pph21_apply(settings, profile, start, end, employee)
        finally:
            self._pph21_calculating = False
            self._pph21_noncash_names = set()
            self._pph21_noncash_components = {}
            self._pph21_noncash_postings = {}
            self._pph21_settings = None

    def get_component_totals(self, component_type, depends_on_payment_days=0):
        if getattr(self, "_pph21_calculating", False):
            for row in self.get(component_type):
                name = row.salary_component
                if component_role(name):
                    continue  # Generated rows are validated separately.
                if name not in self._pph21_noncash_components:
                    self._pph21_noncash_components[name] = frappe.get_doc(
                        "Salary Component", name, for_update=bool(getattr(self, "_pph21_locked", False)))
                component = self._pph21_noncash_components[name]
                if component.get("only_tax_impact") or (component.get("is_flexible_benefit") and
                        component.get("create_separate_payment_entry_against_benefit_claim")):
                    frappe.throw(f"{name}: nonaktifkan Only Tax Impact / pembayaran benefit terpisah agar seluruh payroll masuk jurnal dan pembayaran standar.")
                if name in self._pph21_noncash_names:
                    if component_type != "earnings" or component.type != "Earning" or component.statistical_component:
                        frappe.throw(f"Salary Component {name}: noncash harus Earning dan Statistical Component tidak dicentang.")
                    if not component.do_not_include_in_total:
                        frappe.throw(f"Salary Component {name}: noncash harus Do Not Include in Total pada master.")
                    if name not in self._pph21_noncash_postings:
                        self._pph21_noncash_postings[name] = self._pph21_noncash_posting(component)
                    row.do_not_include_in_total = 1
                elif row.do_not_include_in_total or (component_type == "earnings" and component.do_not_include_in_total):
                    frappe.throw(f"{name}: simpan mapping Settings untuk membuat pasangan Earning noncash. Pasangan potongan noncash dibuat otomatis, jangan ditambahkan manual.")
                # Accounting eligibility is independent of taxability and cash totals.
                # Includes existing masters/structures carrying the old exclusion flag.
                row.do_not_include_in_accounts = 0
        return super().get_component_totals(component_type, depends_on_payment_days=depends_on_payment_days)

    def _pph21_noncash_posting(self, component):
        settings = self._pph21_settings
        mapping = next(row for row in settings.component_mapping if row.salary_component == component.name)
        locked = bool(getattr(self, "_pph21_locked", False))
        name = noncash_component_name(settings.name, component.name)
        if mapping.get("noncash_offset_component") != name:
            frappe.throw(f"{component.name}: simpan PPh21 Settings untuk membuat komponen pasangan noncash.")
        expense = component_account(component, self.company, "Expense", for_update=locked)
        offset = validate_component(name, for_update=locked)
        payable = component_account(offset, self.company, "Liability", for_update=locked)
        return dict(component=component.name, offset_component=name, abbr=offset.salary_component_abbr,
                    expense_account=expense, payable_account=payable)

    def _pph21_add_noncash_offsets(self):
        totals = {}
        for row in self.earnings:
            if row.salary_component in self._pph21_noncash_postings:
                totals[row.salary_component] = totals.get(row.salary_component, dec(0)) + dec(row.amount)
        ledger = []
        for source, amount in totals.items():
            posting = self._pph21_noncash_postings[source]
            if amount:
                self.append("deductions", dict(salary_component=posting["offset_component"],
                    abbr=posting["abbr"], amount=float(amount), default_amount=float(amount),
                    additional_amount=0, depends_on_payment_days=0, is_tax_applicable=0,
                    do_not_include_in_total=1, do_not_include_in_accounts=0,
                    variable_based_on_taxable_salary=0, is_flexible_benefit=0))
            ledger.append({**posting, "amount": str(amount)})
        return ledger

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
        if not self.company or not self.start_date or not self.end_date or not self.posting_date:
            frappe.throw("Lengkapi Company, Start Date, End Date, dan Posting Date (tanggal pembayaran) sebelum menghitung PPh 21.")
        start, end = getdate(self.start_date), getdate(self.end_date)
        paid = getdate(self.posting_date)
        try:
            check_tax_date(paid)
        except ValueError as exc:
            frappe.throw(str(exc))
        if end < start or (end - start).days >= 31:
            frappe.throw("Periode payroll Monthly harus berurutan dan maksimum 31 hari; boleh lintas bulan.")
        if paid < start:
            frappe.throw("Posting Date (tanggal pembayaran) tidak boleh sebelum Start Date payroll.")
        if self.payroll_frequency != "Monthly" or self.salary_slip_based_on_timesheet:
            frappe.throw("Rilis ini hanya mendukung payroll Monthly tanpa Timesheet.")
        if self.currency != "IDR" or frappe.db.get_value("Company", self.company, "default_currency") != "IDR":
            frappe.throw("Salary Slip dan Company harus menggunakan IDR.")
        if dec(self.exchange_rate) != 1:
            frappe.throw("Exchange rate payroll IDR harus 1.")
        employee = frappe.get_doc("Employee", self.employee,
                                  for_update=bool(getattr(self, "_pph21_locked", False)))
        if employee.company != self.company:
            frappe.throw("Perusahaan pegawai berbeda dari Salary Slip.")
        join = getdate(employee.date_of_joining)
        leave = getdate(employee.relieving_date) if employee.relieving_date else None
        if join > end or (leave and leave < start):
            frappe.throw("Periode slip di luar masa kerja pegawai.")
        if paid < join:
            frappe.throw("Tanggal pembayaran tidak boleh sebelum tanggal mulai bekerja.")
        if leave and (paid.year, paid.month) > (leave.year, leave.month):
            frappe.throw("Pembayaran setelah bulan resign belum didukung; tinjau masa pajak terakhir sebelum memproses payroll.")
        if leave and (paid.year, paid.month) == (leave.year, leave.month) and end < leave:
            frappe.throw("Slip masa terakhir harus mencakup sampai tanggal resign. Sesuaikan End Date dan gabungkan seluruh penghasilan terakhir.")
        profile_name = frappe.db.get_value("PPh21 Employee Tax Profile", {
            "employee": self.employee, "company": self.company, "tax_year": paid.year,
        }, "name")
        if not profile_name:
            frappe.throw(f"Buat PPh21 Employee Tax Profile untuk {self.employee}, tahun {paid.year}.")
        profile = frappe.get_doc("PPh21 Employee Tax Profile", profile_name,
                                 for_update=bool(getattr(self, "_pph21_locked", False)))
        settings = selected_settings(profile.pph21_settings, self.company, check_permission=False,
                                     for_update=bool(getattr(self, '_pph21_locked', False)))
        if not profile.permanent_employee or not profile.resident_full_year or profile.facility != "Normal":
            frappe.throw("Profil pajak di luar cakupan rilis: pegawai tetap, WP DN sepanjang tahun, fasilitas Normal.")
        if paid.month <= cint(profile.opening_through_month):
            frappe.throw("Masa ini sudah dicakup saldo awal; tidak boleh dihitung dua kali.")
        return settings, profile, start, end, employee

    def _pph21_check_structure(self):
        if not self.salary_structure:
            frappe.throw("Salary Structure diperlukan untuk payroll PPh21.")
        structure = frappe.get_doc("Salary Structure", self.salary_structure)
        generated_abbrs = [value[1] for value in COMPONENTS.values()]
        mapped = {r.salary_component: r.treatment for r in self._pph21_settings.component_mapping}
        for table in ("earnings", "deductions"):
            for row in list(structure.get(table)) + list(self.get(table)):
                if component_role(row.salary_component):
                    frappe.throw("Hapus komponen otomatis PPh21 dari Salary Structure; app menambahkannya sendiri.")
                if mapped.get(row.salary_component) not in (None, "Ignore") and cint(row.get("statistical_component")):
                    frappe.throw(f"{row.salary_component}: nonaktifkan Statistical Component pada baris Salary Structure/Slip agar nominal noncash masuk bruto pajak.")
                if row.variable_based_on_taxable_salary:
                    frappe.throw("Nonaktifkan komponen pajak standar untuk struktur pegawai PPh21.")
                expression = (row.get("formula") or "") + " " + (row.get("condition") or "")
                if any(abbr in expression for abbr in generated_abbrs) or "pph21_tax_" in expression:
                    frappe.throw("Formula gaji tidak boleh bergantung pada hasil PPh 21 PPh21 (circular dependency).")

    def _pph21_history(self, profile, paid, employee):
        # Stored tax periods remain authoritative for legacy submitted slips.
        # Also fetch any overlapping work period, including across tax years.
        year_start, year_end = date(paid.year, 1, 1), date(paid.year, 12, 31)
        fields = ["name", "start_date", "end_date", "posting_date", "pph21_tax_year", "pph21_tax_month",
                  "pph21_tax_profile", "pph21_tax_gross", "pph21_tax_allowance", "pph21_tax_deductions",
                  "pph21_tax_withholding", "pph21_tax_refund", "pph21_tax_final", "pph21_tax_snapshot"]
        # Identical selection during preview and locked submit. Parameterized SQL
        # expresses the grouped overlap condition without broadening company scope.
        rows = frappe.db.sql(
            "SELECT " + ", ".join(fields) + " FROM `tabSalary Slip` "
            "WHERE employee=%s AND company=%s AND docstatus=1 AND name!=%s "
            "AND (pph21_tax_year=%s OR posting_date BETWEEN %s AND %s "
            "OR (start_date<=%s AND end_date>=%s)) ORDER BY posting_date, name"
            + (" FOR UPDATE" if getattr(self, "_pph21_locked", False) else ""),
            (self.employee, self.company, self.name or "", paid.year, year_start, year_end,
             self.end_date, self.start_date), as_dict=True,
        )
        cutoff = cint(profile.opening_through_month)
        seen, prior_names = set(), []
        gross, deductions, tax = dec(profile.opening_gross), dec(profile.opening_deductions), dec(profile.opening_tax)
        join = getdate(employee.date_of_joining)
        first_payment_month = max(year_start, join).month
        if not cutoff and getdate(self.start_date) <= join <= getdate(self.end_date):
            # A new joiner after the cutoff can receive their first salary next month.
            first_payment_month = paid.month
        for row in rows:
            tracked = bool(row.pph21_tax_profile)
            year = cint(row.pph21_tax_year) if tracked else getdate(row.posting_date).year
            month = cint(row.pph21_tax_month) if tracked else getdate(row.posting_date).month
            if getdate(row.start_date) <= getdate(self.end_date) and getdate(row.end_date) >= getdate(self.start_date):
                frappe.throw(f"Periode kerja tumpang tindih dengan slip submitted {row.name}. Batalkan/amend slip asal terlebih dahulu.")
            if year != paid.year:
                continue
            if month <= cutoff:
                if row.pph21_tax_profile:
                    frappe.throw("Saldo awal tumpang tindih dengan slip PPh21 submitted.")
                continue
            if month >= paid.month:
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
            first_payment_month = min(first_payment_month, month)
            if old_snapshot.get("first_payment_month"):
                first_payment_month = max(first_payment_month, cint(old_snapshot["first_payment_month"]))
            seen.add(month)
            prior_names.append(row.name)
            gross += dec(row.pph21_tax_gross)
            deductions += dec(row.pph21_tax_deductions)
            tax += dec(row.pph21_tax_withholding) - dec(row.pph21_tax_refund)
        expected = set(range(max(first_payment_month, cutoff + 1), paid.month))
        if seen != expected:
            missing = sorted(expected - seen)
            frappe.throw(f"Riwayat payroll belum lengkap untuk bulan {missing}. Isi saldo awal migrasi atau submit slip yang belum ada.")
        return gross, deductions, tax, prior_names, first_payment_month

    def _pph21_apply(self, settings, profile, start, end, employee):
        mapping = {row.salary_component: row.treatment for row in settings.component_mapping}
        base, current_deductions = dec(0), dec(0)
        details = []
        for table in ("earnings", "deductions"):
            for row in self.get(table):
                if component_role(row.salary_component):
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
                        row.do_not_include_in_total and not row.get("do_not_include_in_accounts")
                    ):
                        frappe.throw(f"{row.salary_component}: Noncash harus tidak masuk total tunai tetapi tetap masuk jurnal payroll.")
                    base += amount
                elif treatment == "Annual Deduction":
                    if table != "deductions" or row.do_not_include_in_total:
                        frappe.throw("Annual Deduction harus potongan riil pegawai yang masuk total deduction.")
                    current_deductions += amount
                details.append(dict(component=row.salary_component, table=table,
                                    treatment=treatment, amount=str(amount),
                                    additional_salary=row.get("additional_salary"),
                                    do_not_include_in_total=cint(row.get("do_not_include_in_total")),
                                    do_not_include_in_accounts=cint(row.get("do_not_include_in_accounts")),
                                    noncash_flags_source="Payroll journal" if row.salary_component in self._pph21_noncash_names else None))
        paid = getdate(self.posting_date)
        prior_gross, prior_deductions, prior_tax, prior_names, first_payment_month = self._pph21_history(profile, paid, employee)
        leave = getdate(employee.relieving_date) if employee.relieving_date else None
        is_final = paid.month == 12 or bool(leave and (leave.year, leave.month) == (paid.year, paid.month))
        first = max(date(paid.year, 1, 1), getdate(employee.date_of_joining))
        months = paid.month - first.month + 1
        try:
            if is_final:
                result = final_period(base, prior_gross, prior_deductions + current_deductions,
                                      prior_tax, profile.ptkp_status, months, profile.method, settings.rounding)
            else:
                result = monthly(base, profile.ptkp_status, profile.method, settings.rounding)
        except ValueError as exc:
            frappe.throw(str(exc))
        generated = settings_components(settings)
        tax_accounts = {}
        for base, amount in ((ALLOWANCE, result.allowance), (WITHHOLDING, result.withholding),
                             (REFUND, result.refund)):
            name = generated[base]
            component = validate_component(name, for_update=bool(getattr(self, '_pph21_locked', False)))
            tax_accounts[base] = component_account(component, self.company,
                "Expense" if base == ALLOWANCE else "Liability",
                for_update=bool(getattr(self, '_pph21_locked', False)))
            table = "deductions" if base == WITHHOLDING else "earnings"
            if amount:
                self.append(table, dict(salary_component=name, abbr=component.salary_component_abbr,
                                        amount=float(amount), default_amount=float(amount),
                                        additional_amount=0, depends_on_payment_days=0,
                                        is_tax_applicable=component.is_tax_applicable,
                                        do_not_include_in_total=0, do_not_include_in_accounts=0,
                                        variable_based_on_taxable_salary=0, is_flexible_benefit=0))
        noncash_accounting = self._pph21_add_noncash_offsets()
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
        values = dict(profile=profile.name, settings=settings.name, payment_date=paid, year=paid.year, month=paid.month, final=int(is_final),
                      category=profile.ter_category, method=profile.method, rule=RULE_VERSION,
                      base=result.base_gross, gross=result.taxable_gross, deductions=current_deductions,
                      allowance=result.allowance, withholding=result.withholding, refund=result.refund,
                      rate=result.rate * 100, annual=result.annual_tax)
        for key, value in values.items():
            self.set("pph21_tax_" + key, float(value) if hasattr(value, "as_tuple") else value)
        snapshot = dict(app_version=__version__, rule_version=RULE_VERSION, rule_hash=rules_hash(),
                        rounding=settings.rounding, settings=settings.name, settings_name=settings.settings_name,
                        generated_components=generated, employee=self.employee, company=self.company,
                        year=paid.year, month=paid.month, final=is_final, method=profile.method,
                        tax_period_basis="posting_date", payment_date=str(paid),
                        payroll_start_date=str(start), payroll_end_date=str(end),
                        first_payment_month=first_payment_month,
                        ptkp_status=profile.ptkp_status, category=profile.ter_category,
                        employment={"joining_date": str(getdate(employee.date_of_joining))},
                        relieving_date=str(leave) if leave else None, employment_months=months,
                        opening={field: profile.get(field) for field in (
                            "opening_through_month", "opening_gross", "opening_allowance",
                            "opening_deductions", "opening_tax", "opening_reference")},
                        prior_slips=prior_names, prior_gross=str(prior_gross), prior_tax=str(prior_tax),
                        prior_deductions=str(prior_deductions), components=details,
                        accounts={"allowance": tax_accounts[ALLOWANCE], "tax": tax_accounts[WITHHOLDING],
                                  "refund": tax_accounts[REFUND]},
                        noncash_accounting=noncash_accounting, result=result.as_dict())
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
        # Serialize across profile years too, so changing a payment year cannot
        # submit overlapping work periods under different annual profile locks.
        frappe.db.sql("SELECT name FROM `tabEmployee` WHERE name=%s FOR UPDATE", (self.employee,))
        frappe.db.sql("SELECT name FROM `tabPPh21 Employee Tax Profile` WHERE name=%s FOR UPDATE",
                      (self.pph21_tax_profile,))
        self._pph21_locked = True
