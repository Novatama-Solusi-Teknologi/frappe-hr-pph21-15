# Validasi rilis 0.2.0

Tanggal pemeriksaan: 23 September 2026.

## Hasil lokal

- **57 test Python lulus**: mesin pajak, schema/package, adapter v15, dan controller bulk.
- **6 test JavaScript lulus**: filter akun, reset pilihan Company, default baris, identitas
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

## Dokumentasi 0.2.0

Panduan Markdown memuat bulk profile dan upgrade. PDF 11 halaman telah dirender dan
diperiksa secara visual; contoh angka payroll dipertahankan dari panduan sebelumnya.
Tidak ada perubahan pada `tax/engine.py` atau master tarif dalam revisi ini.
