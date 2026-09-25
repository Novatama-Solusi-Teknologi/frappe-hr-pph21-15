# Hotfix 0.7.1 - sinkronisasi pasangan noncash saat upgrade

## Penyebab

Kalkulasi payroll 0.7.0 menolak mapping yang field noncash_offset_component-nya belum
mengarah ke nama pasangan yang diharapkan. Pada Settings lama dari sebelum fitur pasangan,
kolom baru masih kosong. Migrasi 0.7.0 belum mengisi tautan ini; pembentukan pasangan hanya
berjalan saat Settings disimpan. Error terjadi sebelum pemeriksaan Accounts pasangan.
Log saja belum memastikan apakah master pasangan sudah ada atau apakah Accounts-nya lengkap.

## Perbaikan

Setelah schema dan link Settings disinkronkan, migrate mengisi link mapping noncash yang
kosong dan membuat komponen pasangannya bila belum ada. Berlaku untuk Taxable Noncash dan
Earning noncash Non Taxable/Ignore. Idempotent: tidak menduplikasi pasangan pada migrate ulang.

Akun master, konfigurasi komponen yang sudah ada, dan slip/jurnal submitted tidak diubah.
Link yang sudah terisi dengan nama lain dipertahankan untuk ditinjau; tidak ditimpa diam-diam.
Tidak ada pilihan akun di Settings dan tidak ada penentuan COA berdasarkan kemiripan nama.
Jika pasangan baru dibuat, Accounts kosong sampai diisi pengguna pada Salary Component.

## Langkah pemulihan

1. Update source ke 0.7.1, jalankan migrate dan reload Desk.
2. Buka PPh21 Settings yang dipilih pada profil pegawai. Pada baris BPJS/noncash,
   buka detail baris dan tautan Pasangan Utang Otomatis.
3. Pada Salary Component pasangan, isi Accounts: Company payroll dan akun Utang BPJS
   (Liability, aktif, IDR, non-group). Satu baris per Company. Jika sudah benar, biarkan.
   Komponen sumber tunjangan memakai Accounts beban BPJS (Expense).
4. Ulangi Create Salary Slips dari Payroll Entry terkait. Periksa apakah sudah ada draft
   dari percobaan sebelumnya dan hindari duplikasi. Periksa jurnal pada staging saat Submit.

Untuk pemulihan tanpa update dari 0.7.0, simpan ulang Settings terlebih dahulu agar validate
membuat tautan dan on_update membuat pasangan. Jika form belum berubah sehingga Save tidak
terpicu, ubah Catatan dengan keterangan penyiapan pasangan noncash, lalu Save. Lengkapi
Accounts pasangan sebelum mengulangi payroll.

Panduan PDF 0.7.0 tetap berlaku: hotfix ini memperbaiki upgrade, bukan perubahan form/COA.
