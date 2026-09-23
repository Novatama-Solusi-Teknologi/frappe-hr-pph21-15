# Uji penerimaan pada Frappe Cloud staging

Gunakan salinan site/konfigurasi dengan data pegawai uji. Jangan mengirim email payroll
kepada pegawai sungguhan saat UAT. Pengujian berikut belum dijalankan pada site PT PUP.

## Instalasi

1. Pastikan Frappe/ERPNext/HRMS major 15 dan tidak ada override Salary Slip lain.
2. Install app, migrate, buka workspace Frappe HR PPh21 sebagai HR Manager.
3. Periksa tiga Salary Component, dua form master, custom fields Employee/Salary Slip,
   register, dan referensi TER. Pastikan tidak ada pegawai/perusahaan otomatis aktif.
4. Jalankan migrate sekali lagi: komponen tidak duplikat, account tetap tersimpan.
5. Jika testing di bench sendiri, jalankan smoke test yang tercantum di README.

## Hitung dan pembayaran

| Skenario | Hasil yang harus diperiksa |
|---|---|
| TK/0, Januari, taxable cash 10 juta, Gross Up, Floor IDR | Tunjangan=potongan 230.179, bruto 10.230.179, net 10 juta |
| Simpan/hitung ulang slip yang sama 3 kali | Nominal sama; tidak ada baris pajak ganda |
| Gaji 10 juta + JHT pegawai 200 ribu | Bruto TER tetap 10 juta sebelum tunjangan; net 9,8 juta |
| Tambah BPJS perusahaan objek pajak 400 ribu, noncash | Bruto dasar naik 400 ribu; cash net tetap 10 juta sebelum potongan lainnya |
| Prorata gaji ke 7 juta | Bruto sebelum tunjangan 7 juta; tunjangan tidak diprorata lagi |
| Gaji + THR masing-masing 10 juta, Gross | Bruto gabungan 20 juta, TER A 9%, pajak 1,8 juta |
| K/0 Gross, 12 × 10 juta, pensiun 100 ribu/bulan | PPh setahun 2.715.000; Jan–Nov 200.000/bulan; Desember 515.000 |
| TK/0 gross-up 10 juta Januari, resign Februari | Final tax nol pada contoh tanpa income lain; refund seluruh potongan Januari |
| Mulai kerja Juli, 6 × 10 juta, TK/0 Gross, tanpa iuran | Bruto 60 juta, biaya jabatan 3 juta, PKP 3 juta, tax setahun 150 ribu |
| Saldo awal sampai Agustus, payroll September–Desember | Total sama dengan penghitungan payroll Januari–Desember pembanding |

Submit melalui **Payroll Entry**, bukan hanya tombol Salary Slip. Periksa:

- Debit beban tunjangan, kredit utang pajak, net payroll payable dan bank payment.
- Refund mendebit akun utang pajak dan menambah payroll payable.
- Komponen noncash tidak menambah payroll payable dan tidak mencatat BPJS dua kali.
- Tampilan default print slip, currency, pembulatan dan report CSV.
- Bonus/Additional Salary, prorata LWP, dan deduction riil sesuai struktur PT PUP.

## Proteksi dan koreksi

- Pegawai tanpa profile, komponen belum dipetakan, atau DTP harus gagal dengan pesan jelas.
- Slip kedua dalam satu bulan, periode dua bulan, dan tahun di luar 2024–2026 harus ditolak.
- Submit bulan setelah riwayat berlubang harus ditolak.
- Submit dua slip masa sama bersamaan: hanya satu boleh berhasil (uji transaksi database nyata).
- Setelah Februari submitted, cancel Januari harus ditolak. Cancel Februari lalu Januari boleh,
  dengan mengikuti pembatalan Payroll Entry/Journal Entry native.
- Amend slip canceled: kunci unik masa lama harus bebas; hasil ulang sesuai input terbaru.
- Ubah profil/saldo awal yang sudah dipakai: ditolak sampai slip terkait dibatalkan.
- User Employee tidak boleh melihat profil/register pegawai lain. Uji Company User Permission.
- Pegawai yang tidak diaktifkan tetap memakai payroll standar.

Catat versi minor Frappe/ERPNext/HRMS, input, hasil payroll pembanding, jurnal, dan sign-off
penanggung jawab payroll. Cocokkan juga format/pembulatan dengan pelaporan pajak yang digunakan.
