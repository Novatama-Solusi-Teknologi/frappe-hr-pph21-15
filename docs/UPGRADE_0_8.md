# Upgrade 0.8.0 - pilih komponen pasangan noncash yang sudah ada

> **Tambahan 0.8.1:** pasangan otomatis lama yang belum dipakai kini dibersihkan satu kali saat migrate.
> Link mapping terkait dikosongkan. Lihat [cleansing 0.8.1](CLEANSING_0_8_1.md);
> keterangan pelestarian seluruh pasangan di bawah menjelaskan perilaku rilis 0.8.0.

> **Rilis 0.9.0:** tiga komponen pajak juga dipilih dari master yang sudah ada;
> app tidak membuat Salary Component lagi. Lihat [upgrade 0.9.0](UPGRADE_0_9.md).

## Perubahan

PPh21 Settings > Pemetaan Komponen > detail baris sekarang menyediakan field editable
**Komponen Pasangan Noncash**. Pilih Salary Component yang sudah ada. App tidak membuat
master pasangan baru pada Save, install, atau migrate. Tiga komponen pajak (tunjangan,
potongan, refund PPh21) tetap disiapkan app per Settings seperti sebelumnya.

Semua COA tetap berasal dari tabel Accounts pada Salary Component sesuai Company.
Pasangan lama tidak dihapus, diganti nama, dinonaktifkan, atau digabung otomatis. Link yang
sudah ada dipertahankan agar histori tetap dapat ditelusuri.

## Menyiapkan pasangan

Gunakan komponen yang memang khusus untuk jurnal kontribusi perusahaan. Bila belum ada
komponen yang sesuai, buat sendiri satu Salary Component dengan nama yang mudah dikenali,
misalnya **Utang BPJS Kesehatan Perusahaan**. Satu komponen dapat digunakan ulang oleh
beberapa Settings; akun berbeda dalam Company yang sama memerlukan komponen berbeda.

| Pengaturan Salary Component pasangan | Nilai |
|---|---|
| Type | Deduction |
| Abbreviation | Isi kode unik, misalnya UBKPER |
| Do Not Include in Total | Dicentang (1), sehingga tidak mengurangi THP |
| Do Not Include in Accounting Entries | Tidak dicentang (0), agar masuk jurnal |
| Depends on Payment Days | Tidak dicentang; nilai sumber sudah diprorata |
| Statistical Component / Is Tax Applicable | Tidak dicentang |
| Variable Based on Taxable Salary / Flexible Benefit / Only Tax Impact | Tidak dicentang |
| Amount Based on Formula | Tidak dicentang |
| Amount / Formula / Condition | Amount nol, Formula dan Condition kosong |
| Disabled | Tidak dicentang |
| Accounts | Akun Liability aktif, non-group, IDR, milik Company payroll |

Tepat satu akun per Company; beberapa Company boleh punya baris masing-masing.
Akun beban tetap pada komponen sumber Earning noncash. Komponen sumber memakai
Do Not Include in Total = 1, Accounting Entries = 0, Statistical Component = 0.

**Jangan menggunakan potongan BPJS bagian karyawan sebagai pasangan.** Potongan karyawan
mengurangi THP (Do Not Include in Total = 0), sedangkan pasangan perusahaan hanya membentuk
jurnal. Keduanya boleh memakai akun utang yang sama, tetapi komponen dan fungsinya berbeda.
Master pasangan tidak diubah diam-diam oleh app; pengguna melengkapi field dan akun di atas.

## Memilih pada Settings

1. Buka Settings yang sesuai Company dan kelompok pegawai.
2. Pada setiap baris Earning noncash, buka detail dan pilih Komponen Pasangan Noncash.
3. Pilihan dibutuhkan untuk Taxable Noncash dan Non Taxable/Ignore yang Earning noncash.
   Baris tunai tidak memakai pasangan.
4. Save. App memeriksa tipe/flag/akun pasangan; tidak menambah master pasangan baru.
5. Hitung ulang draft slip dan periksa jurnal Payroll Entry serta Bank Entry pada staging.

Pasangan pilihan tidak dimasukkan ke Salary Structure, Additional Salary, atau mapping
sebagai komponen sumber. App mengisi baris dan nominalnya dari hasil sumber noncash.
Satu pasangan boleh dipilih beberapa sumber. Nilai setelah prorata/Additional Salary
dijumlahkan menjadi satu baris Deduction pasangan per slip. Snapshot merinci setiap sumber.

## Contoh satu pasangan untuk beberapa sumber

| Sumber | Nilai aktual | Pasangan pilihan |
|---|---:|---|
| Tunjangan BPJS Kesehatan | 400.000 | Utang BPJS Perusahaan |
| Kontribusi perusahaan lain dengan akun utang sama | 80.000 | Utang BPJS Perusahaan |
| Total baris pasangan pada slip | 480.000 | Utang BPJS Perusahaan |

Beban didebit ke Accounts masing-masing sumber, kredit Rp480.000 ke Accounts pasangan.
Pasangan tidak menambah potongan THP dan tidak menjadi pengurang pajak. Potongan BPJS
pegawai, bila ada, tetap diproses sebagai potongan tunai terpisah. Gross/Gross Up/refund
PPh21 tetap masuk jurnal yang sama seperti versi sebelumnya.

## Upgrade dan data lama

Deploy source 0.8.0, migrate/build assets, lalu reload Desk. Tidak perlu uninstall/reinstall.
Proses backfill pasangan otomatis 0.7.1 dihentikan. Mapping kosong sekarang harus dipilih
pengguna; migrate tidak menebak pasangan ataupun COA.

Mapping lama ke PPh21 Utang Noncash [kode] tetap dapat dipakai bila master/Accounts valid.
Pada Settings yang belum dipakai slip submitted, Anda dapat memilih pasangan bersama untuk
mengurangi kebutuhan komponen baru. Hitung ulang draft setelah mengganti pilihan.
Settings yang sudah dipakai submitted mengunci perubahan pasangan/penghapusan mapping;
gunakan konfigurasi baru sesuai alur profil atau koreksi transaksi melalui cancel/amend.
Akun dan atribut pasangan yang sudah dipakai submitted juga tetap dikunci.

Komponen lama masih terlihat pada daftar. Jangan menghapus komponen yang direferensikan
Settings/slip/jurnal. Pembersihan atau penonaktifan komponen lama memerlukan pemeriksaan
pemakaian pada site; tidak dilakukan otomatis oleh rilis ini.

Tidak ada perubahan tarif, rumus pajak, atau masa pembayaran. Panduan PDF 0.8.0 memuat
alur terbaru. Tes lokal menggunakan layanan/DB tiruan; UAT di bench lengkap tetap diperlukan.
