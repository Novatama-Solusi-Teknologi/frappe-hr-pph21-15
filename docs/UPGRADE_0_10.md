# Upgrade 0.10.0 — akun pasangan tanpa Salary Component pasangan

## Konfigurasi

Salary Component kontribusi perusahaan tetap satu, misalnya **Tunjangan BPJS JKK**.
Gunakan Type Earning, Do Not Include in Total = 1, Statistical Component = 0, dan
Do Not Include in Accounting Entries = 0. Formula/prorata kontribusi tetap mengikuti
Salary Structure. App tidak menghitung tarif iuran BPJS baru.

Pada tabel **Accounts**, isi satu baris per Company dengan dua kolom:

| Company | Account (akun beban) | Akun Utang Noncash (akun pasangan) |
|---|---|---|
| PT. Prima Unggul Persada | 5210.001 - Biaya Gaji Karyawan HO - PPUP | 2241.001 - Hutang BPJS - PPUP |

Nama akun biaya mengikuti contoh screenshot; pilih akun yang sesuai payroll kelompok
pegawai. Account wajib Expense, Akun Utang Noncash wajib Liability. Keduanya aktif,
non-group, IDR, dan milik Company pada baris yang sama. Bila kolom baru belum terlihat
pada grid, buka detail baris Accounts. Pilihan akun utang terfilter Company baris tersebut.
Company berbeda dapat memiliki baris lain. Dua baris untuk Company sama harus diperbaiki
manual menjadi satu baris; migrasi tidak menghapus atau menggabungkannya diam-diam.

Di Settings, cukup petakan sumber sebagai **Taxable Noncash**, atau **Non Taxable/Ignore**
bila sesuai klasifikasi. Field Komponen Pasangan Noncash tidak lagi ditampilkan atau
wajib diisi. Tidak ada akun yang dipilih pada Settings. Beberapa sumber dan Settings
boleh memakai akun utang sama; masing-masing sumber menyimpan akun pada Accounts-nya.
Jika satu sumber dalam Company sama memerlukan akun berbeda antar-kelompok, gunakan
komponen sumber berbeda atau pemisahan cost center sesuai kebutuhan pencatatan.

Potongan BPJS bagian pegawai tetap komponen Deduction tunai biasa, karena mengurangi
THP. Ini berbeda dari kontribusi perusahaan yang tidak membutuhkan pasangan komponen lagi.
Tiga komponen hasil pajak tetap mengikuti pilihan manual pada rilis 0.9.0.

## Slip, jurnal, dan pembayaran

App menyimpan nominal serta akun beban/utang dalam snapshot slip. Tidak ada baris
Deduction pasangan baru. Saat Payroll Entry membuat accrual Journal Entry, app
menambahkan debit beban dan kredit utang berdasarkan snapshot ke jurnal tersebut.
Nominal noncash tidak menambah utang gaji bersih atau pembayaran Bank Entry.

| Contoh sebelum PPh21 | Debit | Kredit |
|---|---:|---:|
| Beban gaji | 10.000.000 | - |
| Beban BPJS perusahaan | 480.000 | - |
| Utang BPJS (perusahaan 480 ribu + pegawai 120 ribu) | - | 600.000 |
| Utang gaji | - | 9.880.000 |

Cost center, dimensi Payroll Entry, pembentukan referensi Journal Entry, submit, dan
alur pembatalan tetap memakai HRMS. Tidak ada pembukuan/jurnal terpisah. PPh21 tetap
masuk jurnal yang sama. App menambah override Payroll Entry; pemasangan ditolak jika
app lain sudah mengoverride controller ini sampai integrasinya diselesaikan.

## Upgrade dan migrasi

1. Deploy source **0.10.0**, migrate/build assets, lalu reload Desk.
2. Patch menambahkan Akun Utang Noncash pada child Accounts. Sebelum cleansing 0.8.1
   yang belum berjalan, patch mencoba menyalin akun dari pasangan lama yang masih
   tercantum pada mapping. Ini juga mendukung upgrade yang melewati versi sebelumnya.
3. Akun disalin hanya bila sumber/Company memiliki satu akun utang yang valid dan kolom
   tujuan masih kosong. Jika beberapa Settings berbeda akun, Account source duplikat,
   akun tidak valid, atau kolom tujuan sudah berbeda, data dipertahankan dan dicatat.
4. Cari File private **pph21-noncash-accounts-0.10.0.json** sebagai Administrator bila
   ada akun yang disalin/dilewati. `copied` memuat akun tersalin; `skipped` memuat alasan.
   Jika pasangan sudah di-cleansing sebelum upgrade, tidak ada lagi sumber akun untuk
   disalin; isi Akun Utang Noncash manual pada komponen sumber.
5. Lengkapi akun yang kosong atau bermasalah, Save Settings, lalu hitung ulang draft.
   App menghapus keluaran pasangan lama dari draft berdasarkan mapping/snapshot.
6. Periksa slip, kertas kerja, jurnal serta pembayaran pada staging. Tidak perlu
   uninstall/reinstall. Jangan membuat ulang transaksi yang sudah submitted.

Slip submitted lama tidak ditulis ulang. Snapshot lama tanpa mode direct tetap memakai
baris sumber/pasangan yang sudah ada; snapshot baru memakai akun langsung. Payroll Entry
bisa menangani campuran keduanya. Pasangan lama yang masih direferensikan histori tetap
tersimpan. Patch 0.8.1 yang belum berjalan tetap hanya menghapus pasangan otomatis bebas
referensi; 0.10.0 tidak menambah penghapusan master pasangan manual.

Akun beban dan utang yang sudah terisi dikunci setelah sumber dipakai slip submitted.
Mengisi kolom utang baru yang sebelumnya kosong tetap diperbolehkan untuk upgrade.
Perubahan master setelah slip dibuat tidak mengalihkan akun yang tersimpan pada snapshot.

## Batas verifikasi

Tes lokal menggunakan metode asli HRMS v15 untuk accrual, cost center, employee-wise
payable dan Bank Entry, dengan database/persistensi layanan tiruan. Uji mencakup data
baru/lama campuran, pembayaran withheld, retry jurnal, akun snapshot, serta konflik
migrasi. Instalasi, transaksi bersamaan, pembatalan Journal Entry dan posting nyata
pada bench/site Frappe Cloud tetap perlu diuji; belum dijalankan dari lingkungan ini.
Tarif/rumus PPh21 tidak diubah.
