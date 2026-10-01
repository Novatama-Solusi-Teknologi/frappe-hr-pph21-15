# Cleansing 0.8.1 — pasangan noncash otomatis lama

Rilis ini menambahkan pembersihan satu kali saat migrate, sesuai permintaan PT PUP karena
belum ada Payroll Entry yang dibuat. Pemeriksaan tetap melihat pemakaian komponen secara
langsung, karena Salary Structure atau Salary Slip bisa ada tanpa Payroll Entry.

## Yang dibersihkan

Hanya Salary Component bernama `PPh21 Utang Noncash [20 karakter kode hex]` dengan
abbreviation dan deskripsi yang cocok dengan identitas komponen buatan app versi lama.
Komponen manual, tiga komponen pajak PPh21, dan master Account/COA tetap dipertahankan.
Baris Accounts milik komponen yang dihapus ikut terhapus sebagai child master tersebut.

Sebelum menghapus pasangan yang belum dipakai, app mengosongkan field **Komponen Pasangan
Noncash** pada mapping PPh21 Settings yang mengarah kepadanya. Baris mapping dan komponen
sumbernya tetap ada. App tidak memilih pengganti, menyalin COA, atau membuat pasangan baru.

Komponen dilewati bila masih dipakai di Salary Detail (Salary Structure/Slip, termasuk
status draft atau cancelled), Additional Salary, komponen sumber mapping, formula/condition,
atau Settings yang sudah dipakai slip submitted. Referensi Link lain tetap diperiksa oleh
mekanisme hapus standar Frappe. Bila referensi lain ditemukan, mapping dipulihkan dan
komponen dipertahankan. Nama/identitas yang berbeda juga dilewati untuk ditinjau manual.

## Langkah update

1. Gunakan source versi **0.8.1** untuk memperbarui repository app yang terhubung ke Frappe Cloud.
2. Jalankan update/deploy site hingga tahap migrate selesai. Tidak perlu uninstall/reinstall.
3. Di daftar **File**, cari `pph21-noncash-cleanup-0.8.1.json` memakai Administrator.
   Laporan bersifat private dan dibuat bila ada komponen yang dihapus atau dilewati.
4. Baca `deleted` untuk daftar yang terhapus, `skipped` untuk alasan komponen dipertahankan,
   dan `cleared_mappings` untuk Settings serta sumber yang perlu dipilihkan pasangan baru.
5. Buka Settings terkait. Pilih Salary Component pasangan yang ingin digunakan, lengkapi
   Accounts per Company pada komponen, kemudian Save. Satu pasangan dapat dipakai oleh
   beberapa sumber/Settings bila tujuan akun utangnya sama.
6. Ikuti [konfigurasi pasangan manual](UPGRADE_0_8.md) sebelum membuat payroll.

Patch tercatat satu kali pada Patch Log; migrate berikutnya tidak mengulang pembersihan.
Jika ada komponen yang dilewati, laporan menjelaskan penyebabnya; app tidak memaksa hapus.
Penghapusan menggunakan mekanisme standar Frappe dengan pemeriksaan link tetap aktif,
bukan penghapusan SQL langsung. Tidak ada Payroll Entry, Salary Slip, atau jurnal baru
yang dibuat oleh proses cleansing.

## Panduan dan validasi

PDF konfigurasi **0.8.0** tetap berlaku untuk alur pasangan manual; dokumen ini menjadi
addendum khusus cleansing. Mesin pajak, tarif, dan jurnal payroll tidak berubah di 0.8.1.

Paket diuji secara lokal dengan layanan/database tiruan. Penghapusan dan migrate pada
site Frappe Cloud belum dijalankan dari lingkungan pengembangan ini. Jumlah komponen yang
benar-benar terhapus baru dapat dipastikan dari laporan setelah update site selesai.
