# Validasi rilis 0.4.0

Tanggal pemeriksaan: 24 September 2026.

## Hasil lokal

- Tambahan 0.4.0: Settings bernama per Company, komponen/akun terisolasi, profile/bulk selection,
  penolakan Company salah/nonaktif/izin ditolak, snapshot Settings, migrasi idempotent,
  komponen otomatis tidak boleh masuk struktur/Additional Salary, dan proteksi akun/profil
  setelah slip submitted (termasuk pajak nol).
- Metode asli HRMS v15 `get_salary_component_account` dan `get_account` diuji untuk
  gabungan dua konfigurasi pada Company/cost center yang sama. Terbukti membaca field
  `Salary Component Account.account` dan memisahkan nominal berdasarkan COA.
  Source Payroll Entry diambil dari branch `version-15` pada 24 September 2026.
  SHA256: `a3d1f609dafecc6ee2352245fb006a5fe219a32378245899b335334483397fcf`.

- Tambahan 0.3.0: sumber Fiscal Year dari tanggal master, penolakan periode/Company salah,
  backfill tanpa menebak, penamaan profil saat insert, identitas opsional, pelestarian NIK
  lama pada bulk, filter register, dan payroll tanpa identitas terverifikasi.


- **81 test Python lulus**: mesin pajak, schema/package, adapter v15, dan controller bulk.
- **8 test JavaScript lulus**: filter akun, reset pilihan Company, default baris, identitas
  saat Employee berubah, lookup async yang terlambat, dan default profil individual.
- Controller bulk diuji dengan database double transaksional: create/update/tidak berubah,
  saldo awal dipertahankan, input invalid, izin Employee/profil, konfirmasi wajib,
  serta rollback seluruh batch ketika baris berikutnya gagal atau profil terkunci.
- Uji gross-up mencakup **2.928 kombinasi** sekitar batas TER dan 400 sampel acak deterministik.
- Contoh PP 58/2023: pegawai K/0, gaji 10 juta/bulan dan pensiun 100 ribu/bulan menghasilkan
  pajak setahun 2.715.000 dan pemotongan Desember 515.000.
- Gross-up Rp10 juta TK/0 menghasilkan tunjangan/potongan Rp230.179 (Floor IDR), TER A 2,25%.
- Uji rekonsiliasi dengan tunjangan sebelumnya, refund resign, join tengah tahun, seluruh lapisan
  progresif termasuk 35%, dan pembulatan PKP.
- Contract tests memuat lima metode kalkulasi asli dari source HRMS branch version-15,
  commit **2238ff627439b0ca0b02badbebed7ffd00273637**. Database dan layanan Frappe dimock.
- Diuji prorata sebelum TER, noncash, iuran pegawai, hitung ulang tanpa duplikasi,
  saldo awal, histori, final/refund, pemblokiran input di luar cakupan, submit/cancel.
- Python compile dan pyflakes lulus; file JavaScript lolos pemeriksaan syntax Node.
- Wheel dan source distribution berhasil dibangun menggunakan flit_core. Paket source
  diperiksa memuat hooks, metadata DocType, workspace, report, JS dan dokumentasi.

## Yang belum diverifikasi di runtime nyata

Belum dijalankan instalasi/migrate, UI Desk, permission enforcement, transaksi database
bersamaan, dan posting Journal Entry pada bench Frappe/ERPNext/HRMS lengkap ataupun site
Frappe Cloud PT PUP. Unit/contract tests menggunakan database dan layanan tiruan, bukan bench lengkap.
Test rollback lokal tidak dianggap sebagai pengganti pengujian transaksi database nyata.

Smoke test `frappe_hr_pph21.tests.test_installation` disertakan untuk dijalankan pada site testing
yang sudah memasang app. [UAT.md](UAT.md) memuat skenario transaksi dan jurnal yang perlu
lulus pada staging sebelum aktivasi produksi.

## Perubahan pada sistem yang sudah ada

Tidak ada koneksi atau perubahan ke ERPNext/Frappe Cloud produksi. App belum diunggah ke
GitHub atau Marketplace. Repository tidak berisi kredensial atau data pegawai nyata.
Instalasi membuat schema/custom fields dan komponen bernama PPh21, tetapi tidak mengaktifkan
pegawai, menetapkan akun perusahaan, membuat Salary Slip, atau memposting jurnal.

## Dokumentasi 0.4.0

Panduan Markdown memuat bulk profile, beberapa kelompok akun, dan upgrade 0.4.0. PDF 11 halaman telah dirender dan
diperiksa secara visual; contoh angka payroll dipertahankan dari panduan sebelumnya.
Tidak ada perubahan pada `tax/engine.py` atau master tarif dalam revisi ini.

## Pemeriksaan tambahan 0.4.1

Tiga tes migrasi workspace lulus: rename idempotent dan parent HR, pelestarian child menu,
penolakan konflik workspace milik modul lain, serta penyembunyian duplikat tanpa menghapus
kontennya. Empat tes package lulus; pyflakes dan git diff --check lulus. Perubahan menu belum
diuji langsung pada Desk Frappe Cloud PT PUP. Tes payroll 0.4.0 di atas tidak diulang karena
perubahan ini hanya label, metadata workspace, serta migrasi navigasi.

## Hotfix 0.4.2

Error dari log site berhasil direproduksi setelah double `frappe.rename_doc` memakai
signature public API Frappe v15 yang ketat, bukan `**kwargs`. Tes gagal dengan
`unexpected keyword argument 'ignore_permissions'` sebelum perbaikan, lalu lulus
setelah parameter tersebut dihapus. Tiga tes migrasi dan empat tes package lulus;
pyflakes dan git diff --check juga lulus. Payroll tidak diubah atau diuji ulang pada hotfix ini.

Signature diverifikasi pada source resmi:
https://github.com/frappe/frappe/blob/version-15/frappe/__init__.py
(`frappe.rename_doc`, berbeda dari fungsi internal di `frappe.model.rename_doc`).
Belum dijalankan ulang migrasi pada Frappe Cloud PT PUP dari lingkungan ini.

## Hotfix 0.4.3 - lookup Employee untuk role khusus

Tes role khusus mereproduksi penolakan `frappe.only_for` sebelum perubahan. Setelah
pembatasan nama role dihapus, lookup mengembalikan Company/nama/PTKP untuk Employee
yang dapat dibaca dan tetap menolak Employee yang aksesnya ditolak. Fungsi tidak
menggunakan ignore_permissions dan tidak mengembalikan NIK/NPWP atau field Employee lain.

31 tes controller bulk/profil, 4 tes package, dan 8 tes JavaScript lulus. Pyflakes dan
git diff --check lulus. Tidak ada perubahan perhitungan pajak. Izin diuji memakai
Frappe double; pengaturan Role Permission/User Permission serta impersonation pada
site PT PUP belum diverifikasi langsung dari lingkungan ini.


## Rilis 0.5.0 — cutoff dan tanggal pembayaran

Pemeriksaan 25 September 2026: **99 tes Python dan 8 tes JavaScript lulus**.
Tes Python mencakup 14 tambahan terkait periode/tanggal pembayaran dan Additional Salary:
periode 26 Agustus–25 September, prorata, bulan bayar Oktober, pergantian tahun, pemilihan
profil, saldo awal, riwayat tersimpan legacy, duplikasi masa, overlap periode kerja,
rekonsiliasi Desember, karyawan baru setelah cutoff, resign, tahun di luar aturan, dan bonus.
Pemilihan SQL riwayat dijalankan juga pada SQLite dengan data lintas Company/Employee dan
status cancelled; ini memeriksa logika seleksi, bukan isolasi transaksi MariaDB/Frappe.
Jalur preview dan submit memakai seleksi yang sama; submit menambah FOR UPDATE serta
penguncian Employee/profil. Penguncian konkuren tetap memerlukan UAT pada database nyata.

Tarif dan rumus di tax/engine.py serta tax/rules.py tidak diubah. Lima metode aritmetika
asli HRMS v15 tetap dipakai pada controller contract tests. HRMS mengambil Posting Date
Payroll Entry ke argumen pembuatan Salary Slip; absensi/prorata mengikuti Start/End Date.
PDF 12 halaman dirender dan diperiksa, termasuk tabel cutoff baru di halaman 12.

Tidak dilakukan migrasi, pembuatan slip, posting jurnal, commit/push atau deploy ke site PT PUP.
Gunakan UAT.md dan UPGRADE_0_5.md untuk verifikasi pada staging.
