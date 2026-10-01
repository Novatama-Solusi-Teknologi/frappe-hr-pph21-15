# Upgrade 0.9.0 — komponen pajak pilihan pengguna

## Perubahan

App tidak lagi membuat Salary Component saat install, Save Settings, atau migrate.
Bagian **Pilihan Komponen PPh21** menyediakan tiga Link yang dapat diedit:

| Pilihan | Contoh nama bebas | Type | Is Tax Applicable | Accounts per Company |
|---|---|---|---|---|
| Komponen Tunjangan PPh21 | Tunjangan PPh21 | Earning | 1 | Expense: Beban Tunjangan PPh21 |
| Komponen Potongan PPh21 | PPh21 | Deduction | 0 | Liability: Utang PPh21 |
| Komponen Pengembalian PPh21 | Refund PPh21 | Earning | 0 | Liability: Utang PPh21 |

Nama di atas hanya contoh. Gunakan master yang sudah ada bila sesuai; pengguna dapat
membuat master sendiri bila belum ada. Ketiganya wajib dipilih dan harus berbeda.
Satu master dapat dipakai banyak Settings untuk **peran yang sama**, termasuk Settings
milik Company berbeda bila Accounts per Company lengkap. Nama master tampil pada slip;
app tidak menambahkan akhiran ID Settings. Perhitungan TER/gross-up tidak berubah.

Untuk ketiganya: Abbreviation wajib; Amount nol; Formula/Condition kosong. Tidak dicentang:
Depends on Payment Days, Statistical Component, Variable Based on Taxable Salary,
Do Not Include in Total, Do Not Include in Accounting Entries, Flexible Benefit,
Only Tax Impact, Amount Based on Formula, Disabled. Tidak ada perubahan master/COA otomatis.

## Penggunaan banyak Settings dan Salary Structure

| Settings | Salary Structure pegawai | Tunjangan | Potongan | Pengembalian |
|---|---|---|---|---|
| PUP - Kantor | Gaji Kantor | Tunjangan PPh21 | PPh21 | Refund PPh21 |
| PUP - Produksi | Gaji Produksi | Tunjangan PPh21 | PPh21 | Refund PPh21 |

Profil pegawai memilih Settings. Setelah HRMS menghitung gaji dari Salary Structure,
app mengisi hasil pajak pada slip dengan komponen pilihan tersebut. **Cukup pilih pada
Settings; jangan menambahkan komponen hasil pajak ke baris Salary Structure, Additional
Salary, atau tabel mapping sumber taxable/pengurang.** Ini mencegah pajak dihitung dua kali.
Formula sumber gaji tidak boleh merujuk abbreviation hasil pajak karena nilainya baru
tersedia setelah perhitungan gaji selesai.

Satu komponen memakai tepat satu akun per Company. Jika dua kelompok dalam Company sama
memerlukan COA berbeda, pilih komponen berbeda untuk peran terkait. Contoh: tunjangan
Kantor/Produksi berbeda akun beban, tetapi potongan dan refund tetap memakai komponen
bersama dengan akun utang yang sama. Tidak perlu menduplikasi seluruh set.

## Upgrade

1. Update source app ke 0.9.0 lalu migrate/build assets dan reload Desk.
2. Siapkan tiga master beserta flag dan Accounts seperti tabel di atas.
3. Buka setiap Settings yang belum dipakai slip submitted; pilih master bersama dan Save.
4. Pilih pasangan noncash pada detail mapping bila ada sumber noncash. Pasangan BPJS tidak
   boleh memakai komponen Potongan PPh21 karena perlakuan total gajinya berbeda.
5. Hitung ulang draft slip. Periksa nama komponen, kertas kerja, net pay, jurnal dan Bank Entry.

Pilihan komponen lama tetap dipertahankan agar tidak memutus link. Tidak ada rename,
penggabungan, atau penghapusan otomatis tiga komponen pajak lama dalam upgrade ini.
Untuk mengurangi daftar master, setelah seluruh Settings dialihkan, komponen lama yang
bebas referensi dapat dihapus melalui fungsi standar Salary Component. Jangan menghapus
komponen yang masih dipakai struktur, Additional Salary atau slip.

Settings yang sudah dipakai slip submitted mengunci perubahan pilihan pajak/pembulatan;
master yang sudah dipakai submitted mengunci akun/atribut perhitungannya. Penguncian
Settings didasarkan pemakaian Settings itu sendiri, sehingga pemakaian master bersama
pada Settings lain tidak mengunci pembulatan Settings yang belum dipakai.

Patch cleansing noncash 0.8.1 tetap disertakan dan berjalan satu kali jika belum pernah
berjalan. Patch ini menghapus pasangan noncash otomatis yang bebas referensi dan mengosongkan
mapping terkait, tetapi tidak menghapus komponen pajak. Baca [addendum cleansing](CLEANSING_0_8_1.md).

## Verifikasi

Pengujian lokal mencakup master bersama, nama bebas, validasi tipe/flag/akun, larangan
peran/sumber/pasangan tumpang tindih, penguncian submitted, penggantian komponen draft,
pencegahan duplikasi, Gross/Gross Up/refund serta jurnal payroll dan pembayaran.
Database/layanan Frappe menggunakan test double; migrate dan posting nyata pada Frappe Cloud
belum diverifikasi dari lingkungan ini. Panduan PDF 0.9.0 memuat konfigurasi yang sama.
