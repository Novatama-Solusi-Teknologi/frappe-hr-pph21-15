# Upgrade 0.6.0 — BPJS dan PPh21 di jurnal payroll

> Arsip rilis 0.6.0. Untuk versi terbaru, gunakan [UPGRADE_0_7.md](UPGRADE_0_7.md): COA hanya di Salary Component.

Rilis ini menggantikan pembukuan noncash terpisah pada 0.5.x. Seluruh komponen moneter
slip PPh21 masuk jurnal Payroll Entry. Mesin tarif dan rumus pajak tidak berubah.

## Konfigurasi per komponen noncash perusahaan

| Tempat | Pengaturan |
|---|---|
| Salary Component | Type Earning; Do Not Include in Total = 1; Statistical Component = 0 |
| Salary Component → Accounts | Akun beban (Expense), IDR, aktif, non-group, Company sesuai |
| Salary Component | Do Not Include in Accounting Entries = 0; app juga menormalkan baris dari konfigurasi lama |
| PPh21 Settings → Mapping | Taxable Noncash untuk objek; Non Taxable untuk nonobjek yang memenuhi syarat |
| Detail baris mapping | Isi Akun Utang Noncash / BPJS, akun Liability milik Company yang sama |
| Save Settings | App membuat Pasangan Utang Otomatis dengan akun tersebut |

Akun Expense dan Liability divalidasi. Akun utang wajib dipilih pengguna; app tidak menebak COA.
Buka detail baris mapping untuk melihat field baru. JHT/JP bagian perusahaan yang memenuhi
pengecualian tetap dapat memakai Non Taxable dengan Do Not Include in Total = 1 dan akun utang.

Pasangan otomatis berbentuk Deduction, Do Not Include in Total = 1, Accounting Entries = 0.
Nominalnya sama dengan jumlah seluruh baris komponen noncash pada slip setelah prorata,
termasuk Additional Salary. Pasangan tidak mengurangi THP dan tidak mengurangi bruto/PKP.
**Jangan memasukkan pasangan otomatis ke Salary Structure/Additional Salary**, atau menambah
potongan manual lain untuk mengimbangi BPJS perusahaan. Potongan BPJS bagian karyawan tetap terpisah.

## Contoh jurnal (nominal ilustrasi)

Gaji Rp10.000.000, BPJS perusahaan Rp480.000, potongan BPJS karyawan Rp120.000.
Untuk menunjukkan alur BPJS, tabel ini belum memasukkan baris PPh21.

| Akun | Debit | Kredit |
|---|---:|---:|
| Beban gaji | 10.000.000 | — |
| Beban BPJS perusahaan | 480.000 | — |
| Utang BPJS (480.000 + 120.000) | — | 600.000 |
| Utang gaji karyawan sebelum PPh21 | — | 9.880.000 |
| Total | 10.480.000 | 10.480.000 |

PPh21 masuk jurnal yang sama:

| Transaksi | Debit | Kredit / dampak |
|---|---|---|
| Gross Up | Beban tunjangan PPh21 | Utang PPh21; tunjangan dan potongan sama |
| Gross | Tidak ada beban tunjangan | Utang PPh21; utang gaji/THP berkurang sebesar pajak |
| Refund masa terakhir | Utang PPh21 | Utang gaji/THP bertambah sebesar pengembalian |

Akun PPh21 mengikuti PPh21 Settings pada profil. Akun noncash debit mengikuti master
Salary Component per Company; kredit mengikuti mapping Settings. Untuk akun beban noncash
berbeda dalam satu Company, gunakan komponen sumber berbeda dengan Accounts yang sesuai.
Pembagian cost center dan mode pencatatan per Employee mengikuti HRMS.

## Pembayaran

Bank Entry pembayaran gaji hanya membayar net gaji kepada pegawai. Pasangan noncash saling
menetralkan pada perhitungan pembayaran, sehingga BPJS perusahaan tidak ikut ditransfer ke pegawai.
Saat menyetor BPJS/PPh21, catat pembayaran utang melalui transaksi pembayaran ERPNext:
**Debit Utang BPJS/PPh21, Kredit Bank**. Ini pelunasan kewajiban yang sudah dibentuk payroll,
bukan pembukuan ulang beban. App tidak mengirim uang atau menyetor pajak/BPJS otomatis.

## Urutan upgrade

1. Deploy source 0.6.0, migrate, build assets, hard reload Desk.
2. Periksa master BPJS perusahaan: noncash, non-statistical, akun Expense yang benar.
3. Buka setiap Settings yang digunakan, isi akun utang pada setiap mapping noncash, Save.
   Pasangan utang dibuat otomatis. Settings lama tanpa akun noncash akan ditolak saat payroll
   sampai konfigurasi dilengkapi, agar nominal tidak masuk Utang Gaji secara keliru.
4. Periksa dan hitung ulang draft. Jangan membuat duplikat Salary Slip.
5. Submit melalui Payroll Entry. Periksa jurnal accrual, utang BPJS/PPh21, net gaji, cost center,
   serta Bank Entry. Uji Gross/Gross Up, refund, dan payroll per Employee pada staging.

Tidak ada penulisan ulang slip/jurnal submitted lama. Bila ingin mengoreksi payroll lama,
gunakan cancel/amend sesuai urutan masa dan batalkan jurnal/pembayaran terkait melalui alur
ERPNext. Jangan membukukan ulang beban yang sudah pernah diakui lewat proses sebelumnya.

Akun/atribut pasangan otomatis dan sumber noncash yang sudah dipakai submitted dikunci.
Penggantian mapping akun noncash setelah dipakai membutuhkan Settings baru atau koreksi slip.
Parameter moneter lainnya tetap mengikuti aturan penguncian app sebelumnya.

Snapshot dan Kertas Kerja PPh21 menampilkan pasangan jurnal noncash. Tes lokal memakai kode
aritmetika jurnal dan Bank Entry asli HRMS v15 dengan query/layanan tiruan; hasil tetap perlu
UAT pada database dan site Frappe Cloud PT PUP.
