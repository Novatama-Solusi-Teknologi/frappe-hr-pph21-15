# PPh 21 — ERPNext / Frappe HR v15

Custom app PPh 21 Indonesia untuk PT PUP. Rilis **0.4.2**, kandidat untuk uji staging.

Nama tampilan: **PPh 21**. Menu default: **HR > PPh 21**. Nama repository: `frappe-hr-pph21`.
Nama teknis app, metadata project, dan Python package: `frappe_hr_pph21`; gunakan nama dengan underscore
pada perintah `install-app`, `build --app`, dan `run-tests --app`.

Menggunakan Salary Slip dan Payroll Entry standar; tidak mengubah source ERPNext/HRMS.
Memerlukan **Frappe v15 + ERPNext v15 + HRMS v15**, Python 3.10+, dan perusahaan/payroll IDR.

## Fitur

- Master TER A/B/C PP 58/2023 lengkap: 44/40/41 lapisan, PTKP dan tarif Pasal 17.
- Gross dan gross-up penuh. Gross-up memeriksa tarif atas bruto setelah tunjangan.
- Rekonsiliasi Desember atau bulan resign; PKP dibulatkan ke bawah ke ribuan rupiah.
- Pengembalian lebih potong sebagai komponen tersendiri, bukan tunjangan negatif.
- Profil pajak pegawai per tahun, saldo awal migrasi dari pemberi kerja yang sama.
- Pemetaan komponen tunai, noncash, pengurang tahunan, nonobjek dan potongan lainnya.
- Snapshot kertas kerja pada setiap slip; register dapat diekspor melalui fitur report Frappe.
- Hitung ulang idempotent, proteksi duplikasi masa, dan pembatalan dari bulan terbaru.
- Aktivasi per pegawai dan perusahaan; instalasi tidak mengaktifkan payroll otomatis.

## Perbaikan 0.4.2

Memperbaiki error migrasi `rename_doc() got an unexpected keyword argument 'ignore_permissions'`
saat upgrade workspace. Deploy commit baru sebelum menjalankan ulang migrate; retry dengan
source 0.4.1 akan mengulang error. Petunjuk pemulihan ada di [panduan upgrade](docs/UPGRADE_0_4.md).

## Baru di 0.4.1

Label app/workspace menjadi **PPh 21**, dengan menu default di bawah **HR**. Upgrade
menamai ulang workspace lama sebelum sync agar tidak muncul dua menu. Nama teknis app
dan Module Def tetap untuk kompatibilitas instalasi.

## Baru di 0.4.0

Satu Company dapat memiliki beberapa **PPh21 Settings** bernama, misalnya **PUP - Kantor**
dan **PUP - Produksi**. Pilih Settings pada profil pegawai atau baris bulk. Setiap konfigurasi
baru memiliki komponen pajak tersendiri agar akun beban/utang tidak saling menimpa.
[Upgrade 0.4.0 dan migrasi data lama](docs/UPGRADE_0_4.md).

## Sebelumnya di 0.3.0

Tahun dipilih dari DocType **Fiscal Year**, bukan diketik sebagai angka. Tahun internal
diambil dari periode Januari-Desember. **NIK/NPWP opsional** pada profil dan bulk;
identitas kosong tidak memblokir payroll Normal. [Panduan upgrade 0.3.0](docs/UPGRADE_0_3.md).

## Form dan bulk profile

Form 2-3 kolom, kode komponen pada mapping, filter akun per Company, dan
[Bulk PPh21 Employee Tax Profile](docs/BULK_PROFILE.md) dengan default PTKP dari Employee.
Untuk site yang sudah terpasang, ikuti [panduan upgrade](docs/UPGRADE_0_4.md).

## Memasang ke Frappe Cloud

**Custom app memerlukan Private Bench Group.** Public/shared bench biasa hanya mendukung app
Marketplace yang tersedia. App ini belum diterbitkan di Marketplace.

1. Upload **isi root repository ini** ke repository GitHub milik Anda. Di root harus ada
   `pyproject.toml`, `README.md`, dan folder `frappe_hr_pph21/`—jangan bungkus satu folder tambahan.
2. Di Frappe Cloud, buka **Private Bench Group → Apps → Add App → Add from GitHub**.
3. Beri akses Frappe Cloud GitHub App ke repository, pilih branch `main`.
4. Pastikan bench mempunyai `frappe`, `erpnext`, `hrms`, semuanya branch/major **version-15**.
5. Deploy pembaruan bench ke **site staging**. Buka site → Apps → Install App → `frappe_hr_pph21`.
6. Jalankan [konfigurasi](docs/KONFIGURASI.md), lalu [uji penerimaan](docs/UAT.md).
7. Setelah hasil staging cocok dengan payroll pembanding, pasang versi yang sama di produksi.

Frappe Cloud memasang app dari GitHub, **bukan mengunggah ZIP langsung ke site**. Arsip ZIP
rilis berisi source untuk diunggah ke repository tersebut. Tidak diperlukan Server Script.

Panduan resmi: [Installing an app](https://docs.frappe.io/cloud/installing-an-app) dan
[Private benches](https://docs.frappe.io/cloud/benches).

## Instalasi bench mandiri

```sh
bench get-app --branch main https://github.com/ORGANISASI_ANDA/frappe-hr-pph21.git
bench --site SITE_ANDA install-app frappe_hr_pph21
bench --site SITE_ANDA migrate
bench build --app frappe_hr_pph21
```

Ganti placeholder dengan repository/site Anda. Jangan menjalankan `bench init` di bench produksi.
App memblokir instalasi bila major version tidak cocok atau ada app lain yang override `Salary Slip`.

## Mulai konfigurasi

Buka workspace **HR > PPh 21** sebagai **HR Manager** atau **System Manager**:

1. Buat `PPh21 Settings`: nama konfigurasi, perusahaan, akun beban tunjangan, akun utang pajak, dan pemetaan seluruh komponen.
2. Buat `PPh21 Employee Tax Profile` per pegawai/tahun, pilih Settings dan Fiscal Year, isi PTKP, NIK/NPWP jika tersedia, Gross Up/Gross,
   dan saldo awal bila mulai di tengah tahun.
3. Aktifkan `PPh21 Enabled` pada Employee serta pengaturan perusahaan.
4. Jalankan payroll biasa. App menambahkan komponen pajak ke slip secara otomatis.

**Jangan menambahkan komponen otomatis PPh21 ke Salary Structure atau Additional Salary.**
Detail pemetaan BPJS, contoh setup, jurnal, dan saldo awal ada di [KONFIGURASI.md](docs/KONFIGURASI.md).
Panduan langkah demi langkah dengan kasus taxable/nonobjek, Gross/Gross Up, BPJS, THR,
dan masa terakhir ada di [STUDI_KASUS_PAYROLL.md](docs/STUDI_KASUS_PAYROLL.md).
Versi siap baca/cetak: [Panduan PDF 0.4.1](docs/Panduan_PPh21_Payroll_PT_PUP.pdf).

## Batas rilis 0.4.0

- Pegawai tetap untuk tujuan PPh 21, WP dalam negeri sepanjang tahun, fasilitas Normal. NIK/NPWP opsional; app tetap memakai tarif Normal.
- Tahun yang dibundel: **2024–2026**. Tahun lain diblokir sampai master diperbarui.
- **Satu Salary Slip per pegawai/perusahaan/bulan kalender.** THR/bonus melalui Additional Salary ke slip tersebut.
  Gaji dan THR dalam dua slip terpisah/off-cycle belum didukung. Tidak mengubah transaksi lama otomatis.
- Tidak mencakup DTP, PPh 26, pegawai tidak tetap, pesangon final, gross-up sebagian,
  perubahan kewajiban pajak subjektif, rehire dalam tahun yang sama, dan penggabungan pemberi kerja lain.
- App menghitung pajak dari nominal BPJS yang sudah dihitung payroll. **Bukan kalkulator iuran BPJS**.
- Noncash objek pajak hanya memengaruhi dasar pajak; pembukuan iurannya dilakukan terpisah.
- Tidak mengirim data ke DJP, tidak memvalidasi NIK secara online, dan tidak menghasilkan XML Coretax/bukti potong resmi.
- Metode pembulatan nominal pajak wajib dicocokkan dengan hasil pelaporan yang digunakan PT PUP.
  Pilihan awal `Floor IDR`; tersedia `Half Up IDR`. PKP tetap floor ribuan rupiah.
- Lihat [VALIDASI.md](docs/VALIDASI.md) untuk pengujian yang telah/belum dilakukan.

## Pengembangan dan pengujian

```sh
python3 -m unittest discover -s tests -v
node --test tests/test_form_scripts.cjs
```

Untuk contract test menggunakan metode kalkulasi asli HRMS v15:

```sh
curl -L --fail https://raw.githubusercontent.com/frappe/hrms/2238ff627439b0ca0b02badbebed7ffd00273637/hrms/payroll/doctype/salary_slip/salary_slip.py -o /tmp/pph21-v15-salary-slip.py
HRMS_SALARY_SLIP_SOURCE=/tmp/pph21-v15-salary-slip.py python3 -m unittest discover -s tests -v
```

Tanpa variabel tersebut, contract test ditandai skipped; uji mesin tetap berjalan. CI memakai
commit sumber yang sama. Smoke test pada site testing yang sudah menginstal app:

```sh
bench --site SITE_TESTING run-tests --app frappe_hr_pph21 --module frappe_hr_pph21.tests.test_installation
```

Jangan mengaktifkan `allow_tests` di site produksi. Perubahan aturan pajak harus menjadi rilis
baru dengan versi/hash baru; snapshot slip submitted tidak ditulis ulang saat migrate.

## Sumber aturan

- [PP 58/2023](https://jdih.kemenkeu.go.id/dok/pp-58-tahun-2023), Lampiran A–C.
- [PMK 168/2023](https://jdih.kemenkeu.go.id/dok/pmk-168-tahun-2023), masa terakhir dan pengurangan.
- [Buku DJP PPh 21/26](https://static.pajak.go.id/download/kalkulator/Buku_PPh2126_Release_20240108.pdf).
- [Identitas NIK/NPWP dan tarif normal](https://www.pajak.go.id/en/node/104597).
- [HRMS v15 source](https://github.com/frappe/hrms/tree/version-15).

Lisensi MIT. Tidak ada kredensial, data pegawai, atau koneksi ke site produksi di repository ini.
# frappe-hr-pph21-15
