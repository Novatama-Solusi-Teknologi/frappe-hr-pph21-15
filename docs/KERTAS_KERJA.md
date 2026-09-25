# Kertas Kerja PPh21 — tampilan 0.5.2

## Cara membuka

1. Buka Salary Slip yang sudah memiliki hasil perhitungan PPh21.
2. Bagian **Kertas Kerja PPh21** berisi ringkasan tunjangan, pajak dipotong, dan pengembalian.
3. Klik tombol **Kertas Kerja PPh 21** untuk rincian dalam dialog lebar.

| Bagian | Isi |
|---|---|
| Ringkasan | Masa/tahun pajak, metode, tunjangan, potongan, pengembalian |
| Identitas | Karyawan, Company, PTKP/TER, Settings, tanggal pembayaran, periode kerja |
| Masa biasa | Bruto awal, tunjangan, bruto TER, tarif TER, pajak setelah pembulatan |
| Masa terakhir | Bruto setahun, biaya jabatan, pengurang, PTKP, PKP, pajak setahun dan selisih masa ini |
| Komponen | Penghasilan/potongan, klasifikasi pajak, nominal setelah prorata, referensi Additional Salary |
| Akumulasi | Bruto, pengurang, pajak neto sebelum masa ini; sudah termasuk saldo awal |
| Detail tambahan | Buka Saldo awal, riwayat, dan akun untuk melihat saldo awal, slip sebelumnya, akun dan versi |

Nominal menggunakan format rupiah Indonesia, misalnya Rp 10.666.666 dan TER 2,5%.
Pada layar kecil, ringkasan tersusun satu kolom dan tabel komponen bisa digeser horizontal.

## Sumber angka

Tampilan membaca snapshot yang sudah tersimpan, tidak menghitung ulang pajak di browser.
Data JSON tetap disimpan untuk audit; field JSON disembunyikan pada form. Nilai nol tetap
ditampilkan sebagai Rp 0. Tanda — berarti nilai tidak tercatat, bukan nol.

Kertas kerja lama tetap dapat dibaca. Jika belum merekam tanggal pembayaran/periode kerja,
tanggal ditampilkan — tanpa mengambil data dari master sekarang atau menggeser masa lama.
Jika form memiliki perubahan belum disimpan, dialog menampilkan pemberitahuan bahwa angka
masih berasal dari kertas kerja terakhir. Simpan/hitung ulang draft sebelum verifikasi akhir.
Kertas kerja rusak/tidak tersedia menampilkan pesan penanganan, bukan JSON atau error JavaScript.

## Upgrade

Deploy source 0.5.2 dan jalankan migrate agar field HTML ringkasan ditambahkan dan field JSON
lama disembunyikan. Pastikan build assets/deploy Frappe Cloud selesai, lalu hard reload browser
agar script Salary Slip terbaru dimuat. Tidak perlu uninstall app atau menghitung ulang slip
submitted lama hanya untuk melihat tampilan baru. Perhitungan pajak dan nominal tidak berubah.

Panduan PDF 0.5.0 tetap berlaku untuk konfigurasi payroll; dokumen ini melengkapi perubahan UI.
Uji pada staging: buka slip masa biasa, Desember/resign, refund, serta slip lama sebelum produksi.
