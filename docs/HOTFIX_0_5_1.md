# Hotfix 0.5.1 — checkbox Taxable Noncash

## Mengapa master sudah dicentang tetapi masih error?

Pada HRMS v15, saat menambahkan komponen dari Salary Structure, method
`update_component_row` menyalin flag dari **baris Salary Detail pada struktur**.
Baris struktur dan draft slip dapat masih memuat nilai lama setelah master Salary Component
berubah. App sampai versi 0.5.0 hanya memeriksa flag pada baris slip.

Kondisi master benar tetapi baris struktur masih 0 berhasil mereproduksi error yang sama
seperti log pengguna. Traceback sendiri tidak mencantumkan nilai kedua checkbox; nilai
aktual pada site belum diperiksa langsung.

Referensi source HRMS:
[Salary Slip v15](https://github.com/frappe/hrms/blob/version-15/hrms/payroll/doctype/salary_slip/salary_slip.py)
(method `add_structure_component`, `update_component_row`, `get_component_totals`) dan
[Payroll Entry v15](https://github.com/frappe/hrms/blob/version-15/hrms/payroll/doctype/payroll_entry/payroll_entry.py)
(method `get_salary_components`).

## Perilaku baru

- Khusus komponen yang dipetakan **Taxable Noncash**, app membaca master Salary Component
  secara fresh pada setiap kalkulasi. Pada submit, master dibaca dengan row lock.
- Master harus bertipe Earning, Statistical Component = 0, dan kedua opsi pengecualian = 1.
- Setelah lolos validasi master, kedua flag pada baris Salary Slip diselaraskan sebelum
  HRMS menghitung Gross Pay/Net Pay. Berlaku juga untuk baris Additional Salary noncash.
- Nominal tetap masuk bruto PPh21, tetapi tidak masuk total tunai. Flag pengecualian jurnal
  disimpan pada baris Salary Detail yang dipakai Payroll Entry saat membuat jurnal.
- Snapshot mencatat flag efektif dan sumbernya. Rumus, nominal/prorata komponen, mapping,
  akun, master Salary Component, dan Salary Structure tidak diubah oleh sinkronisasi ini.
- Statistical Component pada baris struktur noncash harus tetap 0; jika 1, app menolak
  dengan pesan khusus karena HRMS akan membuang baris itu dari Salary Slip.
- Tidak ada penulisan ulang slip submitted lama. Pegawai tanpa PPh21 Enabled mengikuti HRMS biasa.

## Langkah pada PT PUP

1. Buka master **Salary Component → Tunjangan BPJS Kesehatan**, lalu pastikan dan Save:

   | Pengaturan | Nilai |
   |---|---|
   | Type | Earning |
   | Do Not Include in Total | Dicentang |
   | Do Not Include in Accounting Entries | Dicentang |
   | Statistical Component | Tidak dicentang |
   | Mapping pada PPh21 Settings | Taxable Noncash |

2. Periksa juga komponen JKK/JKM yang dipetakan Taxable Noncash. Pada baris Salary Structure,
   Statistical Component harus tidak dicentang agar nominal terbentuk pada slip.
3. Deploy source 0.5.1 melalui repository app/Frappe Cloud, jalankan migrate, lalu reload Desk.
   Versi ini memuat perbaikan cutoff 0.5.0. Tidak perlu uninstall/reinstall.
4. Setelah job gagal selesai, periksa apakah sudah ada draft Salary Slip. Jika belum ada,
   ulangi Create Salary Slips. Jika ada draft, hitung ulang melalui alur HRMS dan hindari duplikasi.
5. Periksa bruto pajak, Net Pay serta jurnal di staging. Komponen noncash menambah bruto pajak,
   tanpa membayar nominal BPJS perusahaan kepada pegawai; pembukuan BPJS dilakukan terpisah.

Jika masih ditolak, pesan baru menunjukkan checkbox mana yang belum aktif **di master**.
Save master terlebih dahulu; mencentang baris Salary Structure/Slip saja tidak cukup pada 0.5.1.
PDF 0.5.0 tetap berlaku untuk konfigurasi umum; dokumen ini merupakan tambahan hotfix.

Tes regresi menggunakan source metode asli HRMS v15 dan database double. Belum dilakukan
Create/Submit Salary Slips atau pengecekan jurnal langsung di Frappe Cloud PT PUP.
