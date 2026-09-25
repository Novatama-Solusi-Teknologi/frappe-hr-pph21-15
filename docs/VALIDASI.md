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


## Hotfix 0.5.1 — flag noncash pada baris slip

Kondisi master kedua checkbox = 1 tetapi baris Salary Structure/Slip = 0 direproduksi
menggunakan metode asli HRMS v15 `update_component_row`. Sebelum perubahan, tes gagal
dengan pesan Noncash yang sama seperti log pengguna. Setelah perubahan, nominal noncash
masuk bruto pajak, dikeluarkan dari total tunai pertama HRMS, dan kedua flag pengecualian
tersimpan = 1 pada baris slip untuk dipakai Payroll Entry.

**105 tes Python dan 8 tes JavaScript lulus**, termasuk enam tes tambahan:
master benar/baris lama, pengecualian sejak total awal dan read lock saat submit,
penolakan Statistical Component pada baris struktur, master salah/baris terlihat benar,
perubahan master sebelum submit, dan Additional Salary noncash pada metode Gross.
Hitung ulang idempotent dan Gross Up tetap diuji. Contract adapter sekarang memakai tujuh
metode asli HRMS v15, termasuk dua metode pembentukan/prorata baris tambahan.
Pyflakes, compile, dan git diff --check lulus.

PDF 0.5.0 tidak diubah; docs/HOTFIX_0_5_1.md menjelaskan perubahan dan langkah pemulihan.
Tidak ada penulisan ke master/struktur atau slip submitted lama. Tidak ada commit/push/deploy.
Pengujian lokal masih menggunakan DB double, bukan Create/Submit Salary Slips dan jurnal
pada site Frappe Cloud PT PUP.


## Rilis 0.5.2 — tampilan kertas kerja

**106 tes Python dan 16 tes JavaScript lulus.** Delapan tes JS baru memeriksa format rupiah
serta persen TER, rekonsiliasi/refund, escape HTML, snapshot lama, JSON rusak, pembeda nilai
kosong dari nol, integrasi ringkasan/dialog Salary Slip, serta fallback sebelum field HTML tersedia.
Satu tes schema tambahan memastikan JSON tetap disimpan/read-only/hidden dan field HTML
ringkasan terpasang. Pyflakes dan git diff --check lulus. Mesin pajak tidak diubah.

Renderer aktual dijalankan pada Chrome headless dengan data ilustrasi, pada lebar 1120 px dan
390 px. Tampilan bulanan serta refund masa terakhir diperiksa lewat screenshot; tidak ada
overflow halaman, tabel komponen pada layar kecil digeser horizontal. Ini adalah preview
HTML lokal, bukan screenshot dari Desk site PT PUP. Dialog extra-large sesuai source Frappe v15.

Panduan baru docs/KERTAS_KERJA.md menjelaskan tampilan, sumber data, dan langkah upgrade.
PDF konfigurasi 0.5.0 tetap disertakan. Tidak ada commit/push/deploy atau perubahan site produksi.


## Rilis 0.6.0 — BPJS dan PPh21 dalam jurnal payroll

Pemeriksaan 25 September 2026: **118 tes Python dan 18 tes JavaScript lulus**.
Pyflakes dan git diff --check lulus. Tarif serta mesin pajak tidak diubah.

Contract test tambahan menjalankan 11 metode asli Payroll Entry HRMS v15 dari source
yang sama dengan pengujian 0.4.0, mencakup pembentukan accrual journal dan Bank Entry.
DB, pemilihan baris slip, Journal Entry persistence, serta layanan Frappe dimock.
Skenario Gross, Gross Up, kontribusi perusahaan nonobjek, dan refund masa terakhir
memastikan debit = kredit, Salary Payable dan pembayaran bank = net pay.
Iuran perusahaan Rp480.000 + potongan pegawai Rp120.000 menghasilkan kredit utang BPJS
Rp600.000. Skenario juga mencakup pencatatan per Employee dan pembagian cost center 60/40.
Tunjangan, pemotongan, dan refund PPh21 diperiksa terhadap akun Settings yang dipilih.

Tes lain mencakup pasangan otomatis idempotent, nilai setelah prorata/Additional Salary,
master lama dengan flag accounting exclusion, noncash nonobjek, akun salah Company/jenis,
mapping belum lengkap, perubahan akun/mapping setelah submitted, larangan pasangan manual,
serta filter akun dan escape HTML tabel jurnal kertas kerja.

PDF v0.6.0 sebanyak 13 halaman telah dirender dan diperiksa secara visual. Renderer kertas
kerja aktual dengan tabel jurnal noncash dijalankan pada Chrome headless lebar 1120 dan
390 px; tidak ada overflow halaman, tabel lebar dapat digeser pada layar kecil.

Belum dilakukan instalasi/migrate, posting Journal Entry nyata, pembayaran bank, atau
verifikasi transaksi/cancellation pada bench lengkap atau site PT PUP. Pengujian lokal
bukan pengganti UAT pada staging. Tidak ada commit/push/deploy. Slip submitted lama tidak
ditulis ulang. Ikuti UPGRADE_0_6.md dan lengkapi akun utang pada mapping sebelum kalkulasi
ulang draft payroll.


## Rilis 0.7.0 - COA hanya di Salary Component

**121 tes Python dan 18 tes JavaScript lulus** pada 25 September 2026. Tes akun sebelumnya
disesuaikan untuk membaca Accounts komponen; Settings Save tidak mengisi atau menimpa COA.
Tes tambahan mencakup Settings/pasangan baru tanpa akun, pemakaian COA master meskipun nilai
Settings lama berbeda, duplicate Company ditolak, dan multiple Company tetap didukung.
Schema/UI tidak memiliki Link Account pada Settings maupun child mapping. Refund memiliki
rekaman akun tersendiri dalam snapshot. Akun submitted tetap dilindungi.

Contract jurnal/Bank Entry asli HRMS v15 tetap lulus untuk BPJS, Gross, Gross Up, refund,
noncash nonobjek, cost center dan Employee-wise accounting. Pyflakes dan diff check lulus.
PDF 0.7.0 (13 halaman) dirender dan diperiksa secara visual. Wheel, sdist dan source ZIP
dibangun untuk rilis ini. Tarif dan rumus pajak tidak berubah.

Belum dilakukan migrate/UI/posting jurnal pada bench lengkap atau Frappe Cloud PT PUP.
Tidak ada commit, push, deploy, perubahan Accounts master site, atau perubahan slip submitted.
Lihat UPGRADE_0_7.md untuk langkah update dan UAT.md untuk verifikasi staging.


## Hotfix 0.7.1 - backfill pasangan noncash

125 tes Python lulus, termasuk empat tes baru: backfill mapping kosong/membuat pasangan,
link ke pasangan yang sudah ada dengan akun tetap utuh, pelestarian link konflik/skip cash,
dan pemanggilan sinkronisasi pada hook after_migrate setelah migrasi Settings.
Migrate ulang tidak menduplikasi komponen dan tidak mengubah Accounts. Pengujian masih
menggunakan DB double, bukan migrate pada site/bench lengkap.

Pyflakes, diff check, build wheel/sdist, dan integritas source ZIP diperiksa. Tidak ada
perubahan JavaScript, tarif/rumus, PDF atau jurnal submitted. PDF konfigurasi 0.7.0 tetap
disertakan. Tidak ada commit/push/deploy ke Frappe Cloud dari lingkungan ini.
