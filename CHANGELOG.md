# Changelog

## 0.4.1 — 2026-09-24

- Label app/workspace menjadi PPh 21; menu default sebagai child HR.
- Migrasi menamai ulang workspace lama dan memperbarui parent menu tanpa membuat duplikat.
- Nama teknis app/Module Def tetap; tidak ada perubahan payroll atau akun.

## 0.4.0 — 2026-09-24

- Beberapa PPh21 Settings bernama dalam satu Company; profil individual dan bulk memilih Settings.
- Setiap Settings baru memiliki komponen allowance/withholding/refund tersendiri sehingga Payroll Entry standar memisahkan akun antar konfigurasi.
- Perbaikan field akun Salary Component Account menjadi `account`, sesuai HRMS v15.
- Snapshot/slip menyimpan Settings yang digunakan. Settings lintas Company/nonaktif ditolak; pilihan profil dan akun yang telah digunakan slip submitted dilindungi.
- Migrasi mempertahankan nama dan komponen Settings lama; profil lama ditautkan hanya bila konfigurasi Company tidak ambigu.
- Panduan konfigurasi, studi kasus, PDF, dan upgrade diperbarui. Tidak ada perubahan rumus atau tarif pajak.

## 0.3.1 — 2026-09-24

- Default kedua checklist Pegawai tetap untuk tujuan PPh 21 dan WP dalam negeri sepanjang tahun pajak menjadi tercentang pada profil baru.
- Nilai profil lama dan validasi cakupan perhitungan tetap dipertahankan. Profil baru melalui bulk sudah menggunakan kedua nilai tersebut.
- Deploy pembaruan dan jalankan migrate agar default DocType tersinkronisasi.

## 0.1.0 — 2026-09-23

Initial staging candidate for Frappe/ERPNext/HRMS v15:

- App identity: Frappe HR PPh21; repository `frappe-hr-pph21`, package `frappe_hr_pph21`.

- PP58 TER A/B/C, progressive annual tax and PTKP master data (2024–2026).
- Full gross-up / gross, annual reconciliation and separate refund.
- Company component/account mapping, annual employee profiles and migration opening balances.
- Server-side Salary Slip extension with audit snapshots and monthly sequencing safeguards.
- Register, reference report, workspace, setup/UAT guides, tests and build configuration.

Requires staging verification before production. DTP and off-cycle payroll are outside this release.
