# Upgrade 0.7.0 - COA hanya di Salary Component

PPh21 Settings dan detail mapping tidak lagi mempunyai pilihan Account. Semua COA dibaca
dari tabel **Accounts** pada masing-masing Salary Component, sesuai Company payroll.
Menyimpan Settings tidak menulis, menyalin ulang, atau menimpa Accounts.

## Konfigurasi

1. Buat/buka PPh21 Settings, isi nama, Company, pembulatan dan mapping pajak. Save.
2. Bagian Komponen Otomatis menampilkan tautan komponen tunjangan, potongan dan pengembalian.
   Buka setiap Salary Component untuk mengisi Accounts.
3. Untuk noncash, Save membuat pasangan utang otomatis. Buka tautan **Pasangan Utang Otomatis**
   pada detail mapping dan isi Accounts pada komponen pasangan itu.

| Komponen | Accounts per Company | Posisi jurnal |
|---|---|---|
| Tunjangan PPh21 otomatis | Beban Tunjangan PPh21 (Expense) | Debit |
| Potongan PPh21 otomatis | Utang PPh21 (Liability) | Kredit |
| Pengembalian PPh21 otomatis | Utang PPh21 (Liability), biasanya sama dengan potongan | Debit |
| BPJS perusahaan sumber | Beban BPJS (Expense) | Debit |
| Pasangan utang noncash otomatis | Utang BPJS (Liability) | Kredit |
| Potongan BPJS bagian karyawan | Utang BPJS pada komponen potongan biasa | Kredit |

Akun PPh21 dan noncash harus aktif, IDR, bukan group, dan milik Company terkait.
Tepat satu baris Accounts per Company pada setiap komponen. Beberapa Company boleh memakai
satu komponen dengan satu akun masing-masing. Dua akun untuk Company yang sama bukan pasangan
debit/kredit; Payroll Entry bawaan hanya mengambil satu akun untuk komponen dan Company.
Akun gaji serta komponen biasa lainnya tetap mengikuti Accounts bawaan HRMS.

Settings boleh disimpan sebelum Accounts lengkap, agar komponen dan tautannya tersedia.
Kalkulasi payroll akan ditolak dengan nama komponen jika akun belum lengkap/salah/duplikat.
Isi ketiga komponen PPh21 meskipun masa berjalan belum mempunyai tunjangan atau refund.
Tidak perlu mengisi ulang akun yang sudah benar dari versi sebelumnya.

## Noncash tetap masuk jurnal payroll

Sumber BPJS perusahaan: Earning, Do Not Include in Total = 1,
Do Not Include in Accounting Entries = 0, Statistical Component = 0.
Pasangan otomatis: Deduction, Do Not Include in Total = 1, Accounting Entries = 0.
Nominal pasangan sama dengan total aktual sumber setelah prorata dan Additional Salary.
Pasangan tidak mengubah THP atau menjadi pengurang pajak. Jangan masukkan komponen otomatis
ke Salary Structure/Additional Salary dan jangan membuat potongan pengimbang kedua.
Potongan BPJS bagian karyawan tetap terpisah dari pasangan kontribusi perusahaan.

Contoh sebelum PPh21: gaji Rp10.000.000, BPJS perusahaan Rp480.000, bagian pegawai Rp120.000.

| Akun | Debit | Kredit |
|---|---:|---:|
| Beban gaji | 10.000.000 | - |
| Beban BPJS | 480.000 | - |
| Utang BPJS | - | 600.000 |
| Utang gaji | - | 9.880.000 |
| Total | 10.480.000 | 10.480.000 |

Gross Up menambahkan debit tunjangan dan kredit utang PPh21; Gross memotong utang gaji untuk
kredit utang PPh21. Refund mendebit akun komponen pengembalian dan menambah utang gaji.
Bank Entry gaji membayar net gaji saja. Pembayaran BPJS/pajak kemudian mendebit utang dan
mengkredit Bank: pelunasan utang, bukan pembukuan ulang beban atau jurnal beban terpisah.
App tidak melakukan transfer bank/setoran otomatis.

## Upgrade dari versi sebelumnya

1. Deploy 0.7.0, migrate/build assets, lalu hard reload Desk.
2. Accounts master yang sudah dipetakan versi sebelumnya dipertahankan. Kolom akun lama
   Settings tidak lagi tampil atau dibaca; app tidak menghapus data payroll/history.
3. Save setiap Settings untuk membuat pasangan noncash jika belum ada, lalu lengkapi Accounts
   di Salary Component. Pasangan lama 0.6.0 mempertahankan nama dan akunnya.
4. Periksa dan hitung ulang draft Salary Slip. Jangan membuat slip duplikat.
5. Uji Submit melalui Payroll Entry pada staging: jurnal seimbang, BPJS/PPh21 menuju COA
   yang benar, dan Bank Entry sama dengan net pay. Ikuti UAT.md.

Tidak ada koreksi otomatis terhadap slip/jurnal submitted. Koreksi menggunakan cancel/amend
beserta jurnal/pembayaran terkait dan urutan masa. Akun komponen PPh21/pasangan/sumber noncash
yang sudah dipakai submitted tetap dikunci. Untuk kelompok COA lain, gunakan Settings baru
beserta komponen sumber yang sesuai. Mesin tarif, rumus, dan masa pajak tidak berubah.
