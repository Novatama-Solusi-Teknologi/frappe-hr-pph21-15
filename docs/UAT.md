# Uji penerimaan pada Frappe Cloud staging

Gunakan salinan site/konfigurasi dengan data pegawai uji. Jangan mengirim email payroll
kepada pegawai sungguhan saat UAT. Pengujian berikut belum dijalankan pada site PT PUP.

## Instalasi

1. Pastikan Frappe/ERPNext/HRMS major 15 dan tidak ada override Salary Slip lain.
2. Install app, migrate, buka workspace Frappe HR PPh21 sebagai HR Manager.
3. Periksa tiga Salary Component, tiga form utama (Settings, profil, Bulk), custom fields Employee/Salary Slip,
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
- Slip kedua dalam satu masa pembayaran, periode lebih dari 31 hari, dan tahun pembayaran di luar 2024–2026 harus ditolak.
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

## Form dan Bulk - rilis 0.2.0

- Periksa layout 2-3 kolom di Settings/profil/detail baris dan bagian pajak Salary Slip,
  tabel lebar penuh, serta keterbacaan di desktop dan layar sempit.
- Cari Salary Component dengan nama dan abbreviation; keduanya tampil pada dropdown.
  Mapping lama setelah migrate menampilkan Kode Komponen yang benar.
- Pilih Company A: hanya akun A sesuai root type, IDR, aktif, non-group tersedia.
  Ganti Company B: akun lama kosong; pencarian hanya akun B. Coba kirim akun A melalui
  API pada settings Company B: validasi harus tetap menolak.
- Buat batch 3 karyawan. Company otomatis, custom_ptkp valid terisi; custom_ptkp kosong
  atau tidak dikenali meminta input manual. Ubah default: baris lama tidak tertimpa.
- Save draft tidak membuat profil. Submit tanpa konfirmasi ditolak. Setelah konfirmasi,
  Submit membuat profil dan tautan hasil dengan default Normal/saldo awal nol.
- Ulangi melalui batch baru: nilai identik menghasilkan Tidak berubah; tidak ada duplikasi.
- Perbarui profil yang belum digunakan: lima input berubah, saldo awal/catatan tetap.
- Baris terakhir mengubah profil terkunci: submit gagal; seluruh perubahan baris sebelumnya
  harus di-rollback pada database nyata. Draft dapat diperbaiki dan diajukan ulang.
- Uji dua batch bersamaan untuk Employee/tahun sama dan batch bersamaan dengan submit slip.
  Tidak boleh ada profil ganda atau perubahan melewati proteksi payroll.
- Uji akses Company User Permission: user yang tidak dapat membaca salah satu Employee
  tidak boleh membuka batch berisi NIK pegawai tersebut atau mengisi default pegawai itu.
- Batch submitted tidak dapat dibatalkan seolah-olah efek profil sudah dihapus.
- PPh21 Enabled, Salary Slip, serta jurnal tidak dibuat/diaktifkan otomatis oleh bulk.

## Fiscal Year dan identitas opsional - rilis 0.3.0

- Pada profil, bulk (default/baris), dan PPh21 Register, tahun dipilih melalui Link Fiscal Year.
- Uji master bernama `Periode Payroll PUP` dengan tanggal 2026-01-01 s.d. 2026-12-31:
  profil harus bernama Employee-2026 dan register mencari tahun 2026, bukan menafsir nama master.
- Tolak Fiscal Year disabled, lintas tahun/tahun pendek, di luar 2024-2026, atau tidak berlaku
  untuk Company pegawai. Hak baca Fiscal Year tetap berlaku.
- Migrate: link profil/bulk lama terisi hanya untuk pasangan master yang tunggal dan cocok.
  Master tidak ada/ambigu tidak menyebabkan angka tahun, saldo awal, atau snapshot berubah.
- Profil individual dan bulk dapat disimpan/submitted dengan NIK/NPWP kosong.
  Payroll TK/0 gross-up 10 juta tetap menghasilkan pajak/tunjangan 230.179.
- Identitas yang diisi tidak valid (misalnya 12 digit) ditolak; nol di awal tidak hilang.
- Bulk dengan identitas kosong tidak menghapus NIK/NPWP lama. Identitas baru tidak otomatis
  dianggap tervalidasi; checkbox verifikasi bukan syarat payroll.

## Tambahan UAT 0.4.0

1. Upgrade site staging berisi Settings lama, profil, draft, dan slip submitted. Jalankan
   migrate dua kali; nama/komponen Settings lama, snapshot, saldo awal dan nominal tetap.
   Company tidak lagi unik di database. Profil lama terhubung ke Settings lama.
2. Simpan Settings lama dan verifikasi field Account pada Salary Component Account.
   Mapping akun berbeda yang sudah digunakan slip submitted harus ditolak, bukan ditimpa.
3. Buat PUP - Kantor dan PUP - Produksi dalam Company yang sama, dengan dua pasangan akun.
   Pastikan komponen/abbreviation berbeda dan pengaturan satu tidak menimpa yang lain.
4. Pilih konfigurasi berbeda untuk dua pegawai. Coba Settings Company lain, nonaktif, dan
   di luar User Permissions; pilihan salah harus ditolak di UI dan server.
5. Buat dua slip Gross Up Rp10 juta TK/0 pada payroll sama. Periksa pajak Rp230.179
   masing-masing, serta posting debit beban/kredit utang yang terpisah sesuai konfigurasi.
6. Uji Gross, refund masa terakhir, hitung ulang draft, pembatalan/amendment, dan YTD.
7. Bulk: Settings eksplisit per baris, kosong mempertahankan profil lama, konfigurasi
   tunggal otomatis untuk profil baru, beberapa pilihan mewajibkan pemilihan. Uji rollback.
8. Setelah submit, perubahan Settings profil serta akun/pembulatan Settings ditolak.
   Edit akun langsung pada komponen yang dipakai juga ditolak. Settings lain tetap dapat diedit.
9. Uji submit payroll bersamaan dengan edit akun/Settings pada koneksi berbeda;
   tidak boleh ada snapshot dan akun jurnal yang berbeda akibat race.


## Cutoff dan masa pembayaran - 0.5.0

- Periode 26 Agustus–25 September 2026, Posting Date 25 September: masa 9/tahun 2026;
  saldo awal sampai Agustus. Uji hari kerja/pembayaran asli, LWP dan Gross/Gross Up.
- Periode yang sama, dibayar 1 Oktober: masa 10, harus ada riwayat sampai September.
- Periode 26 Desember 2025–25 Januari 2026: profil 2026, masa 1, bukan final Desember.
- Periode 26 November–25 Desember: final Desember. Cocokkan total pembayaran setahun.
- Tambah bonus Payroll Date 30 Agustus: masuk slip 26 Agustus–25 September; setelah
  slip submitted penambahan ditolak. Bonus 26 September masuk periode berikutnya.
- Karyawan join 28 Agustus, periode pertama 26 Agustus–25 September: masa pertama
  September; Oktober harus membaca riwayat September tanpa meminta slip Agustus.
- Dua periode kerja berbeda tetapi Posting Date pada bulan sama: submit kedua ditolak.
- Periode kerja tumpang tindih dengan slip submitted: ditolak walau tahun pembayaran berbeda.
- Uji bersamaan pada dua tahun profil untuk pegawai sama; penguncian Employee harus
  mencegah dua slip periode tumpang tindih lolos bersamaan.
- Slip submitted lama dengan Posting Date berbeda bulan dari masa tersimpan: tidak
  direlabel otomatis. Tinjau riwayat sebelum menerapkan basis baru pada pegawai tersebut.
- Resign di luar cutoff namun dalam bulan pembayaran: perlu slip final mencakup hari resign;
  pembayaran bulan sesudah resign ditolak sebagai di luar cakupan.
