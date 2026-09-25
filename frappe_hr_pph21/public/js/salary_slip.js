/* Display saved tax calculations; never recalculate tax in the browser. */
(() => {
    const months = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"];
    const escape = value => frappe.utils.escape_html(String(value ?? "—"));
    const present = value => value !== null && value !== undefined && value !== "";
    const number = value => {
        if (!present(value) || !["number", "string"].includes(typeof value) || String(value).trim() === "") return null;
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    };
    const money = value => {
        const n = number(value);
        return n === null ? "—" : "Rp " + new Intl.NumberFormat("id-ID", {maximumFractionDigits: 2}).format(n);
    };
    const percent = value => {
        const n = number(value);
        return n === null ? "—" : new Intl.NumberFormat("id-ID", {maximumFractionDigits: 4}).format(n * 100) + "%";
    };
    const date = value => {
        if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return "—";
        const [y, m, d] = value.split("-").map(Number);
        if (!months[m - 1] || d < 1 || d > new Date(y, m, 0).getDate()) return "—";
        return `${d} ${months[m - 1]} ${y}`;
    };
    const object = value => value && typeof value === "object" && !Array.isArray(value);
    const read = raw => {
        try {
            const data = JSON.parse(raw);
            return object(data) && object(data.result) && Object.keys(data.result).length ? data : null;
        } catch (_) { return null; }
    };
    const css = `<style>
        .pph21-sheet{color:var(--text-color,#243746);font-size:13px;line-height:1.5}
        .pph21-sheet *{box-sizing:border-box}
        .pph21-sheet .pph21-head{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px}
        .pph21-sheet h3{font-size:22px;margin:3px 0 6px;font-weight:650}
        .pph21-sheet h4{font-size:15px;font-weight:650;margin:24px 0 10px}
        .pph21-sheet .pph21-eyebrow{font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--text-muted,#657882)}
        .pph21-sheet .pph21-muted{color:var(--text-muted,#657882);font-size:12px}
        .pph21-sheet .pph21-badge{display:inline-block;border:1px solid var(--border-color,#dce4e8);border-radius:20px;padding:4px 10px;margin:4px 4px 0 0}
        .pph21-sheet .pph21-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
        .pph21-sheet .pph21-meta{padding:12px 0;border-bottom:1px solid var(--border-color,#dce4e8);overflow-wrap:anywhere}
        .pph21-sheet .pph21-meta dt{font-weight:400;font-size:12px;color:var(--text-muted,#657882);margin-bottom:4px}
        .pph21-sheet .pph21-meta dd{margin:0;font-weight:550}
        .pph21-sheet .pph21-card{background:var(--control-bg,#f4f7f9);border:1px solid var(--border-color,#dce4e8);border-radius:8px;padding:14px;min-width:0}
        .pph21-sheet .pph21-card strong{display:block;font-size:20px;margin-top:7px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
        .pph21-sheet .pph21-note{padding:12px 14px;background:var(--control-bg,#f4f7f9);border-left:3px solid #14828a;border-radius:4px;margin:14px 0}
        .pph21-sheet .pph21-scroll{overflow-x:auto}
        .pph21-sheet table{width:100%;border-collapse:collapse;font-size:13px}
        .pph21-sheet th,.pph21-sheet td{padding:10px 12px;border-bottom:1px solid var(--border-color,#dce4e8);vertical-align:top;overflow-wrap:anywhere}
        .pph21-sheet th{background:var(--control-bg,#f4f7f9);font-weight:600;text-align:left}
        .pph21-sheet .pph21-amount{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
        .pph21-sheet .pph21-total{font-weight:650;background:var(--control-bg,#f4f7f9)}
        .pph21-sheet .pph21-components{min-width:560px}
        .pph21-sheet details{margin-top:22px;border-top:1px solid var(--border-color,#dce4e8);padding-top:12px}
        .pph21-sheet summary{cursor:pointer;font-weight:600}
        @media(max-width:600px){.pph21-sheet .pph21-grid{grid-template-columns:1fr}.pph21-sheet h3{font-size:20px}.pph21-sheet .pph21-card strong{font-size:19px}.pph21-sheet th,.pph21-sheet td{padding:9px 8px}}
    </style>`;
    const meta = (label, value) => `<div class="pph21-meta"><dt>${escape(label)}</dt><dd>${escape(present(value) ? value : "—")}</dd></div>`;
    const card = (label, value) => `<div class="pph21-card"><span>${escape(label)}</span><strong>${escape(money(value))}</strong></div>`;
    const row = (label, value, total = false) => `<tr${total ? ' class="pph21-total"' : ""}><td>${escape(label)}</td><td class="pph21-amount">${escape(value)}</td></tr>`;
    const table = rows => `<div class="pph21-scroll"><table><thead><tr><th scope="col">Uraian</th><th scope="col" class="pph21-amount">Nilai</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
    function render(data, {compact = false, dirty = false} = {}) {
        if (!data) return `${css}<div class="pph21-sheet"><div class="pph21-note">Kertas kerja belum tersedia atau tidak dapat dibaca. Untuk draft, simpan dan hitung ulang Salary Slip. Untuk slip submitted, minta administrator memeriksa data kertas kerja tersimpan.</div></div>`;
        const result = data.result;
        const final = data.final === true || data.final === 1 || data.final === "1";
        const period = `${months[Number(data.month) - 1] || "Masa belum tercatat"} ${data.year ?? ""}`;
        const cards = `<div class="pph21-grid">${card("Tunjangan PPh21", result.allowance)}${card("PPh21 dipotong", result.withholding)}${card("PPh21 dikembalikan", result.refund)}</div>`;
        const notice = dirty ? '<div class="pph21-note">Form memiliki perubahan yang belum disimpan. Angka di bawah berasal dari kertas kerja terakhir; simpan dan hitung ulang sebelum memeriksa hasil akhir.</div>' : "";
        const header = `<div class="pph21-head"><div><div class="pph21-eyebrow">Kertas kerja PPh21</div><h3>${escape(period)}</h3><div class="pph21-muted">${escape(data.company)}</div></div><div><span class="pph21-badge">${escape(data.method)}</span><span class="pph21-badge">${final ? "Rekonsiliasi masa terakhir" : "TER bulanan"}</span></div></div>`;
        if (compact) return `${css}<div class="pph21-sheet">${notice}${header}${cards}<p class="pph21-muted" style="margin-top:12px">Buka tombol Kertas Kerja PPh 21 untuk rincian komponen dan perhitungan.</p></div>`;
        const calculation = final ? [
            row("Bruto setahun termasuk tunjangan pajak", money(result.annual_gross)),
            row("Biaya jabatan (pengurang)", money(result.job_expense)),
            row("Iuran/pengurang tahunan yang diperbolehkan", money(result.annual_deductions)),
            row("Penghasilan tidak kena pajak (PTKP)", money(result.ptkp)),
            row("Penghasilan kena pajak (PKP), dibulatkan ke ribuan", money(result.pkp)),
            row("PPh21 setahun", money(result.annual_tax), true),
            row("PPh21 neto masa sebelumnya", money(result.prior_tax)),
            row("PPh21 dipotong masa ini", money(result.withholding), true),
            row("Kelebihan potong dikembalikan", money(result.refund)),
        ] : [
            row("Bruto sebelum tunjangan pajak", money(result.base_gross)),
            row("Tunjangan PPh21", money(result.allowance)),
            row("Bruto yang dikenakan TER", money(result.taxable_gross), true),
            row("Tarif efektif rata-rata (TER)", percent(result.rate)),
            row("PPh21 dipotong setelah pembulatan", money(result.withholding), true),
        ];
        const treatments = {"Taxable Cash":"Objek pajak · tunai", "Taxable Noncash":"Objek pajak · noncash", "Non Taxable":"Nonobjek pajak", "Annual Deduction":"Pengurang tahunan", "Ignore":"Tidak memengaruhi pajak"};
        const components = Array.isArray(data.components) ? data.components.filter(object) : [];
        const componentRows = components.map(c => `<tr><td>${escape(c.component)}${c.additional_salary ? `<div class="pph21-muted">Additional Salary: ${escape(c.additional_salary)}</div>` : ""}</td><td>${escape(c.table === "earnings" ? "Penghasilan" : c.table === "deductions" ? "Potongan" : "—")}</td><td>${escape(treatments[c.treatment] || c.treatment)}</td><td class="pph21-amount">${escape(money(c.amount))}</td></tr>`).join("");
        const opening = object(data.opening) ? data.opening : {};
        const accounts = object(data.accounts) ? data.accounts : {};
        const priors = Array.isArray(data.prior_slips) ? data.prior_slips.map(escape).join(", ") : "";
        const basis = data.tax_period_basis === "posting_date" ? "Masa pajak mengikuti Posting Date sebagai tanggal pembayaran." : "Kertas kerja versi lama: masa pajak mengikuti nilai yang tersimpan saat perhitungan, tanpa mengubah transaksi lama.";
        return `${css}<article class="pph21-sheet">${notice}${header}${cards}
            <dl class="pph21-grid">${meta("Karyawan", data.employee)}${meta("PTKP / kategori TER", `${data.ptkp_status ?? "—"} / ${data.category ?? "—"}`)}${meta("Pengaturan PPh21", data.settings_name || data.settings)}${meta("Tanggal pembayaran", date(data.payment_date))}${meta("Periode kerja", `${date(data.payroll_start_date)} – ${date(data.payroll_end_date)}`)}${meta("Pembulatan pajak", data.rounding)}</dl>
            <p class="pph21-muted">${escape(basis)}</p>
            <h4>${final ? "Rekonsiliasi pajak tahunan" : "Perhitungan masa ini"}</h4>${table(calculation)}
            <div class="pph21-note">${final ? "Masa terakhir menggunakan perhitungan pajak tahunan dikurangi pajak neto masa sebelumnya. Selisih lebih potong ditampilkan sebagai pengembalian." : data.method === "Gross Up" ? "Tunjangan pajak menambah bruto dan sudah diperhitungkan dalam PPh21 masa ini. Nilai tunjangan sama dengan PPh21 yang dipotong." : "Metode Gross: PPh21 dipotong dari penghasilan pegawai."}</div>
            <h4>Komponen penghasilan dan potongan</h4><p class="pph21-muted">Nominal setelah perhitungan payroll/prorata. Komponen pajak otomatis ditampilkan pada ringkasan di atas. Noncash menambah bruto pajak tanpa menambah pembayaran tunai.</p>
            <div class="pph21-scroll"><table class="pph21-components"><thead><tr><th scope="col">Komponen</th><th scope="col">Jenis</th><th scope="col">Perlakuan pajak</th><th scope="col" class="pph21-amount">Nominal</th></tr></thead><tbody>${componentRows || '<tr><td colspan="4">Rincian komponen tidak tersedia pada kertas kerja ini.</td></tr>'}</tbody></table></div>
            <h4>Akumulasi sebelum masa ini</h4><p class="pph21-muted">Sudah termasuk saldo awal dan slip sebelumnya; jangan dijumlahkan lagi dengan saldo awal.</p>${table([row("Bruto pajak sebelumnya", money(data.prior_gross)),row("Pengurang tahunan sebelumnya", money(data.prior_deductions)),row("PPh21 neto sebelumnya", money(data.prior_tax))])}
            <details><summary>Saldo awal, riwayat, dan akun</summary>
            <dl class="pph21-grid">${meta("Saldo awal sampai bulan", number(opening.opening_through_month) === 0 ? "Tidak ada saldo awal" : months[Number(opening.opening_through_month)-1])}${meta("Referensi saldo awal", opening.opening_reference)}${meta("Bulan bekerja untuk rekonsiliasi", data.employment_months)}</dl>
            ${table([row("Saldo awal bruto (termasuk tunjangan)", money(opening.opening_gross)),row("Tunjangan dalam saldo awal bruto", money(opening.opening_allowance)),row("Saldo awal pengurang tahunan", money(opening.opening_deductions)),row("Saldo awal PPh21 dipotong", money(opening.opening_tax))])}
            <h4>Slip sebelumnya</h4><p style="overflow-wrap:anywhere">${priors || "Tidak ada referensi slip sebelumnya pada kertas kerja ini."}</p>
            <dl class="pph21-grid">${meta("Akun beban tunjangan", accounts.allowance)}${meta("Akun utang PPh21", accounts.tax)}${meta("Versi aturan / app", `${data.rule_version ?? "—"} / ${data.app_version ?? "—"}`)}</dl></details>
            <p class="pph21-muted" style="margin-top:18px">Nilai ditampilkan dari kertas kerja yang tersimpan pada Salary Slip. Tanda — berarti data tidak tercatat.</p>
        </article>`;
    }
    frappe.hr_pph21_worksheet = {read, render};
    frappe.ui.form.on("Salary Slip", {
        refresh(frm) {
            frm.set_df_property("pph21_tax_snapshot", "hidden", 1);
            const wrapper = frm.fields_dict.pph21_tax_worksheet?.$wrapper;
            if (!frm.doc.pph21_tax_snapshot) {
                if (wrapper) wrapper.empty();
                return;
            }
            frm.set_df_property("income_tax_calculation_breakup_section", "hidden", 1);
            const options = () => ({dirty: typeof frm.is_dirty === "function" && frm.is_dirty()});
            if (wrapper) wrapper.html(render(read(frm.doc.pph21_tax_snapshot), {...options(), compact: true}));
            frm.add_custom_button(__("Kertas Kerja PPh 21"), () => {
                const dialog = new frappe.ui.Dialog({
                    title: __("Kertas Kerja PPh 21"), size: "extra-large",
                    fields: [{fieldtype: "HTML", fieldname: "worksheet"}],
                });
                dialog.fields_dict.worksheet.$wrapper.html(render(read(frm.doc.pph21_tax_snapshot), options()));
                dialog.show();
            });
        },
    });
})();
