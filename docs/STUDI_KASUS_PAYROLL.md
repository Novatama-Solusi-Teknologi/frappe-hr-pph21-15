# Panduan PPh21 payroll: konfigurasi dan studi kasus

Untuk PT PUP — ERPNext/Frappe HR v15, app **Frappe HR PPh21 0.3.0**.
Disusun 23 September 2026. Semua contoh angka dihitung menggunakan mesin app.
Panduan ini mengasumsikan app sudah terpasang; pengujian transaksi nyata tetap dilakukan
di staging sebagaimana [UAT](UAT.md). Rilis 0.3.0 menggunakan master Fiscal Year dan NIK/NPWP opsional; rumus pajak tetap sama.

## Pembaruan form dan bulk profile di 0.3.0

- Form Settings/profil individual memakai 2-3 kolom; tabel tetap lebar penuh.
- Mapping menampilkan nama dan kode Salary Component Abbreviation; pencarian menerima keduanya.
- Pilihan akun mengikuti Company, jenis akun, IDR, aktif, dan non-group.
- Gunakan [Bulk PPh21 Employee Tax Profile](BULK_PROFILE.md) untuk mengisi banyak karyawan
  dalam satu form: Employee, Fiscal Year, NIK/NPWP opsional, PTKP, metode. Company otomatis; PTKP
  default dari `custom_ptkp` jika tersedia. Save menyimpan draft; Submit menerapkan seluruh batch.
- Konfirmasi persyaratan standar sekali per batch. Profil baru memakai Normal dan saldo awal nol;
  profil lama mempertahankan saldo awal. PPh21 Enabled pada Employee tidak diubah otomatis.
- Panduan deploy pembaruan: [UPGRADE_0_3.md](UPGRADE_0_3.md).

## 1. Bedakan objek pajak dan penanggung pajak

Ada dua keputusan yang terpisah:

| Keputusan | Tempat pengaturan | Pilihan |
|---|---|---|
| Komponen mana yang masuk perhitungan pajak? | PPh21 Settings → Pemetaan Komponen | Taxable Cash, Taxable Noncash, Annual Deduction, Non Taxable, Ignore |
| Siapa yang menanggung PPh21 pegawai? | PPh21 Employee Tax Profile → Metode PPh 21 | Gross atau Gross Up |

**Gross**: PPh21 menjadi potongan yang mengurangi uang diterima pegawai.
**Gross Up**: perusahaan menambahkan tunjangan pajak sebesar PPh21 yang dipotong;
tunjangan itu sendiri masuk dasar pajak. Slip tetap menampilkan potongan pajak.

Jadi pegawai dengan semua penghasilan taxable dapat memakai Gross maupun Gross Up.
Pegawai yang menerima campuran penghasilan taxable dan pembayaran nonobjek juga dapat
memakai salah satunya. Metode ditentukan per pegawai/tahun; mapping berlaku per perusahaan.

"Sebagian taxable" harus mempunyai dasar klasifikasi yang benar. Gaji biasa tidak boleh
dibuat hanya 80% taxable atas pilihan perusahaan. Pisahkan komponen sesuai sifat transaksi.
Jika maksudnya perusahaan menanggung 50% pajak atau hanya meng-gross-up gaji pokok,
**gross-up sebagian belum didukung versi 0.3.0**.

## 2. Konfigurasi awal

### A. Salary Component

Buat/gunakan komponen yang dibutuhkan, kemudian petakan pada **PPh21 Settings**:

| Contoh nama komponen | Type | Treatment di app | Dampak |
|---|---|---|---|
| Gaji Pokok | Earning | Taxable Cash | Menambah pembayaran tunai dan bruto pajak |
| Tunjangan Jabatan / Makan Tunai / Transport Tunai | Earning | Taxable Cash | Menambah pembayaran tunai dan bruto pajak |
| THR / Bonus / Lembur | Earning | Taxable Cash | Digabung dengan penghasilan bulan itu |
| Reimbursement Perjalanan Dinas At Cost | Earning | Non Taxable | Pembayaran tunai tanpa menambah bruto pajak, apabila memenuhi syarat |
| JKK / JKM / BPJS Kesehatan Perusahaan yang objek pajak | Earning | Taxable Noncash | Menambah bruto pajak tanpa pembayaran tunai |
| JHT Pegawai / JP Pegawai yang memenuhi syarat | Deduction | Annual Deduction | Mengurangi uang diterima; pengurang fiskal pada rekonsiliasi tahunan |
| BPJS Kesehatan Pegawai | Deduction | Ignore | Mengurangi uang diterima, tanpa mengurangi bruto TER |
| Cicilan Kasbon | Deduction | Ignore | Mengurangi uang diterima, bukan pengurang fiskal |

Pengaturan app membaca **mapping**, bukan hanya checkbox bawaan `Is Tax Applicable`.
Selaraskan checkbox dengan klasifikasi agar mudah dipahami admin. Petakan semua komponen
biasa yang muncul pada slip, termasuk deductions. `Ignore` berarti diabaikan untuk pajak,
bukan dihapus dari perhitungan pembayaran payroll.

Untuk `Taxable Noncash`, gunakan Earning dengan:

- `Do Not Include in Total = 1`.
- `Do Not Include in Accounting Entries = 1`.
- `Statistical Component = 0`.

Nominal iuran perusahaan tetap dihitung melalui formula payroll perusahaan. Pembukuan biaya
dan utang BPJS dilakukan terpisah dari baris noncash ini. JHT/JP perusahaan yang memenuhi
pengecualian tidak dipetakan sebagai `Taxable Noncash`.

Rujukan perlakuan iuran: [materi DJP pengisian bukti potong A1](https://pajak.go.id/sites/default/files/2025-12/Pembuatan%20Bukti%20Pemotongan%20PPh%20Pasal%2021-Tahunan%20A1%20%20%281%29.pdf).

### B. PPh21 Settings

1. Masuk sebagai **HR Manager** atau **System Manager**. Cari `PPh21 Settings` melalui pencarian Desk.
2. Buat pengaturan untuk Company PT PUP, lalu aktifkan pengaturannya.
3. Pilih akun **Beban Tunjangan PPh 21**: akun Expense aktif, bukan group, IDR, milik PT PUP.
4. Pilih akun **Utang PPh 21 / Pengembalian**: akun Liability dengan ketentuan yang sama.
5. Pilih pembulatan **Floor IDR** untuk mereplikasi contoh panduan ini. Cocokkan dengan
   hasil pelaporan sebelum produksi; pembulatan dikunci setelah ada slip submitted.
6. Isi **Pemetaan Komponen** sesuai tabel, kemudian Save.

Instalasi telah membuat tiga komponen otomatis:

- `PPh21 Tunjangan Pajak`.
- `PPh21 Potongan Pajak`.
- `PPh21 Pengembalian Pajak`.

**Jangan tambahkan ketiganya ke Salary Structure atau Additional Salary.** App mengisinya
sendiri. Jangan memasang komponen income tax lama/native bersamaan untuk pegawai ini.

### C. Profil pegawai

1. Cari `PPh21 Employee Tax Profile`, buat satu profil per Employee/tahun.
2. Isi Employee, pilih **Fiscal Year** dari master ERPNext, dan pilih Status PTKP.
   Angka tahun otomatis berasal dari periode Januari-Desember pada master.
3. NIK/NPWP boleh kosong; jika diisi harus 15/16 digit. Checkbox verifikasi identitas
   hanya catatan manual, bukan syarat penyimpanan/payroll dan bukan validasi online DJP.
4. Pilih **Metode PPh 21 = Gross** atau **Gross Up**. Default app adalah Gross Up;
   ubah secara eksplisit bila pajak menjadi beban pegawai.
5. Konfirmasikan pegawai tetap untuk tujuan PPh21 dan WP dalam negeri sepanjang tahun
   hanya jika sesuai. Pilih **Fasilitas Pajak = Normal**.
6. Isi saldo awal jika migrasi payroll pertengahan tahun; lihat bagian 7.
7. Save, lalu aktifkan **PPh21 Enabled** pada Employee.

Kategori TER diisi otomatis dari PTKP: A untuk TK/0, TK/1, K/0; B untuk TK/2, TK/3,
K/1, K/2; C untuk K/3. Referensi: [PP 58/2023](https://jdih.kemenkeu.go.id/dok/pp-58-tahun-2023).

### D. Struktur dan proses payroll

Buat **Salary Structure** Monthly berisi komponen gaji/potongan biasa, kemudian buat
**Salary Structure Assignment** untuk pegawai. Pegawai Gross dan Gross Up boleh memakai
struktur yang sama jika komposisi gajinya sama; metode berasal dari profil masing-masing.

Gunakan satu slip per pegawai/masa pembayaran. Start/End Date boleh lintas bulan
(maksimum 31 hari); tahun/masa pajak mengikuti Posting Date sebagai tanggal pembayaran.
Contoh 26 Agustus–25 September, dibayar 25 September: masa September.
Lihat [contoh cutoff](UPGRADE_0_5.md).
Tambahkan penghasilan tidak rutin melalui **Additional Salary** sebelum membuat/menghitung
ulang slip bulan tersebut. Jalankan **Payroll Entry → Salary Slip**, periksa draft,
lalu submit setelah nominal sesuai. Riwayat slip harus berurutan.

## 3. Empat kasus utama

Asumsi: pegawai tetap, status **TK/0 → TER A**, fasilitas Normal, masa pajak biasa
(bukan Desember/bulan resign), pembulatan Floor IDR. Tidak ada BPJS, kasbon, atau
penghasilan lain dalam empat contoh ini. Semua nominal dalam rupiah.

| Kasus | Penghasilan tunai taxable sebelum tunjangan pajak | Pembayaran nonobjek | Metode | Tunjangan pajak otomatis | Bruto dasar TER | TER | PPh21 dipotong | Uang ditransfer |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| A. Semua penghasilan taxable, pajak beban pegawai | 10.000.000 | 0 | Gross | 0 | 10.000.000 | 2% | 200.000 | 9.800.000 |
| B. Ada pembayaran nonobjek, pajak beban pegawai | 8.000.000 | 2.000.000 | Gross | 0 | 8.000.000 | 1,5% | 120.000 | 9.880.000 |
| C. Semua penghasilan taxable, pajak gross-up | 10.000.000 | 0 | Gross Up | 230.179 | 10.230.179 | 2,25% | 230.179 | 10.000.000 |
| D. Ada pembayaran nonobjek, pajak gross-up | 8.000.000 | 2.000.000 | Gross Up | 121.827 | 8.121.827 | 1,5% | 121.827 | 10.000.000 |

Angka merupakan perhitungan mesin app dengan lapisan TER dari PP 58/2023.

### Kasus A — seluruh penghasilan taxable dan dipotong dari pegawai

Isi struktur: Gaji Pokok Rp8.000.000 + Tunjangan Jabatan Rp2.000.000, keduanya
`Taxable Cash`. Pada profil pilih `Gross`.

App menambahkan `PPh21 Potongan Pajak` Rp200.000. Uang ditransfer:
Rp8.000.000 + Rp2.000.000 − Rp200.000 = **Rp9.800.000**.

### Kasus B — sebagian pembayaran bukan objek pajak

Isi Gaji Pokok Rp8.000.000 sebagai `Taxable Cash`. Tambahkan Rp2.000.000 sebagai
`Reimbursement Perjalanan Dinas At Cost` dengan mapping `Non Taxable`. Pilih `Gross`.

Contoh reimbursement mengasumsikan perjalanan sepenuhnya untuk tugas perusahaan,
senilai pengeluaran sebenarnya, didukung bukti, dan bukan tambahan imbalan pegawai.
DJP membedakannya dari kelebihan uang perjalanan lumpsum yang menjadi penghasilan.
Lihat [FAQ DJP PMK 66/2023, nomor 7](https://stats.pajak.go.id/sites/default/files/2023-12/FAQ%20Terkait%20PMK-66%20Tahun%202023.pdf).

Pajak hanya memakai dasar Rp8.000.000. Uang ditransfer Rp9.880.000, termasuk penggantian
biaya Rp2.000.000. Ini **bukan gaji Rp10 juta yang dibebaskan 20% secara arbitrer**.

Jika reimbursement sudah dibayar melalui Expense Claim, jangan dibayar ulang melalui payroll.
Pastikan proses pencatatan klaim dan payroll tidak menggandakan biaya/utang.

### Kasus C — seluruh penghasilan taxable dengan gross-up

Gunakan komposisi Kasus A, tetapi pilih `Gross Up` pada profil pegawai contoh yang lain.
Tidak perlu membuat formula tunjangan pajak sendiri.

```text
Gaji + tunjangan jabatan           10.000.000
PPh21 Tunjangan Pajak                 230.179
Total earning tunai               10.230.179
PPh21 Potongan Pajak                 230.179
Uang ditransfer                    10.000.000
```

Tunjangan Rp200.000 tidak cukup: tunjangan menjadi objek pajak juga. App mencari jumlah
yang konsisten dengan TER atas bruto setelah tunjangan. Pada kasus ini tarif berubah
dari 2% menjadi 2,25%. Setelah pembulatan, pajak sama dengan tunjangan Rp230.179.

### Kasus D — campuran taxable/nonobjek dengan gross-up

Gunakan komposisi Kasus B dan pilih `Gross Up`. Bruto pajak Rp8.121.827 menghasilkan
pajak Rp121.827. Reimbursement Rp2.000.000 tetap di luar dasar pajak.
Uang ditransfer: Rp8.000.000 + Rp2.000.000 + Rp121.827 − Rp121.827 = **Rp10.000.000**.

## 4. Kasus potongan BPJS dan kasbon

Misalkan penghasilan tunai taxable Rp10.000.000, dengan potongan berikut. Nilai iuran
di sini diasumsikan sebagai nominal payroll yang telah dihitung, bukan contoh tarif/batas upah BPJS.

| Potongan pegawai | Nominal | Mapping |
|---|---:|---|
| JHT yang memenuhi syarat | 200.000 | Annual Deduction |
| JP yang memenuhi syarat | 100.000 | Annual Deduction |
| BPJS Kesehatan | 100.000 | Ignore |
| Kasbon | 500.000 | Ignore |
| Total | 900.000 | |

| Metode | Bruto dasar TER | Tunjangan pajak | PPh21 | Potongan lain | Uang ditransfer |
|---|---:|---:|---:|---:|---:|
| Gross | 10.000.000 | 0 | 200.000 | 900.000 | 8.900.000 |
| Gross Up | 10.230.179 | 230.179 | 230.179 | 900.000 | 9.100.000 |

JHT/JP pegawai tidak mengurangi dasar TER bulanan; pengurang fiskalnya digunakan pada
rekonsiliasi masa terakhir. Potongan payroll tetap mengurangi pembayaran pada bulan berjalan.
Karena itu gross-up pajak tidak berarti perusahaan menanggung BPJS pegawai atau kasbon.
Dasar penghitungan: [PMK 168/2023](https://pajak.go.id/id/peraturan/petunjuk-pelaksanaan-pemotongan-pajak-atas-penghasilan-sehubungan-dengan-pekerjaan-jasa-1).

## 5. Kasus tambahan

### A. Ada penghasilan taxable noncash

Misalkan gaji tunai Rp10.000.000 dan iuran perusahaan objek pajak Rp400.000.
Nilai Rp400.000 hanya ilustrasi total nominal noncash, bukan formula iuran.
Petakan gaji `Taxable Cash` dan iuran `Taxable Noncash` dengan flag pada bagian 2.

| Metode | Bruto sebelum tunjangan pajak | Tunjangan pajak | PPh21 | Uang ditransfer |
|---|---:|---:|---:|---:|
| Gross | 10.400.000 | 0 | 260.000 | 9.740.000 |
| Gross Up | 10.400.000 | 266.666 | 266.666 | 10.000.000 |

Pegawai tidak menerima Rp400.000 secara tunai, tetapi nilainya menambah bruto pajak.
Contoh ini belum memasukkan potongan iuran pegawai.

### B. Gaji dan THR pada bulan yang sama

Gaji taxable Rp10.000.000 + THR taxable Rp10.000.000, tanpa penghasilan/potongan lainnya.
Buat Additional Salary THR untuk bulan tersebut dan gabungkan ke satu Salary Slip.

| Metode | Bruto dasar TER | TER | Tunjangan pajak | PPh21 | Uang ditransfer |
|---|---:|---:|---:|---:|---:|
| Gross | 20.000.000 | 9% | 0 | 1.800.000 | 18.200.000 |
| Gross Up | 21.978.021 | 9% | 1.978.021 | 1.978.021 | 20.000.000 |

App belum mendukung dua slip/off-cycle untuk pegawai yang sama pada bulan yang sama.

### C. Gaji taxable tetapi pajak bulan berjalan nol

Gaji Rp5.000.000, TK/0, metode Gross menghasilkan TER 0% dan PPh21 Rp0 pada masa biasa.
Tetap petakan gaji sebagai `Taxable Cash`. Pajak nol tidak mengubah gaji menjadi nonobjek;
penghasilan tetap masuk riwayat rekonsiliasi tahunan. Jangan mematikan PPh21 Enabled.

## 6. Desember, resign, dan pengembalian

Masa terakhir dihitung kembali secara tahunan menggunakan penghasilan aktual, biaya jabatan,
pengurang yang diperbolehkan, PTKP, dan tarif progresif, dikurangi PPh21 sebelumnya.
Masa terakhir adalah Desember atau bulan berhenti bekerja. Selisih lebih potong dikembalikan.
Lihat [PMK 168/2023](https://pajak.go.id/id/peraturan/petunjuk-pelaksanaan-pemotongan-pajak-atas-penghasilan-sehubungan-dengan-pekerjaan-jasa-1).

Contoh terpisah: **K/0**, Gross, bekerja Januari–Desember, gaji Rp10.000.000/bulan,
iuran pensiun pegawai yang memenuhi syarat Rp100.000/bulan, tanpa komponen lain.

| Perhitungan app | Nominal |
|---|---:|
| Bruto setahun | 120.000.000 |
| Biaya jabatan | (6.000.000) |
| Iuran pensiun setahun | (1.200.000) |
| PTKP K/0 | (58.500.000) |
| PKP | 54.300.000 |
| PPh21 setahun | 2.715.000 |
| Sudah dipotong Januari–November: 11 × 200.000 | (2.200.000) |
| PPh21 Desember | 515.000 |
| Uang ditransfer Desember: 10.000.000 − 100.000 − 515.000 | 9.385.000 |

Jangan membuat biaya jabatan atau PTKP sebagai Salary Component deduction.

Contoh resign: pegawai TK/0, Gross Up, gaji Rp10.000.000 pada Januari dan Februari,
resign Februari, WP dalam negeri sepanjang tahun, tanpa penghasilan lain pada pemberi kerja ini.
Januari: tunjangan dan pajak Rp230.179. Pada Februari, hasil final app adalah pajak tahunan
nol, tunjangan baru nol, dan `PPh21 Pengembalian Pajak` Rp230.179. Pembayaran Februari
menjadi Rp10.230.179. App tidak menarik kembali tunjangan pajak Januari.
Isi **Relieving Date** pada Employee sebelum membuat slip terakhir.

Untuk Gross Up pada masa terakhir, app menyelesaikan tunjangan berdasarkan selisih pajak
tahunan, bukan mengulang TER bulan biasa. Jangan menyalin nominal tunjangan November
ke Desember secara manual.

## 7. Mulai menggunakan app di tengah tahun

Jika payroll PT PUP mulai memakai app pada September 2026, isi profil setiap pegawai:

| Field saldo awal | Isi |
|---|---|
| Saldo awal sampai bulan | 8 |
| Bruto objek pajak termasuk tunjangan pajak | Total Januari–Agustus, termasuk taxable noncash dan tunjangan pajak |
| Tunjangan pajak (sudah termasuk bruto) | Bagian tunjangan dalam bruto di atas; jangan ditambahkan dua kali |
| Iuran pensiun/JHT/JP dan zakat yang diperbolehkan | Total pengurang yang memenuhi syarat, tanpa biaya jabatan/PTKP |
| PPh21 telah dipotong | Total pemotongan Januari–Agustus |
| Referensi kertas kerja saldo awal | Referensi rekap yang telah diperiksa |

Saldo awal hanya untuk pemberi kerja yang sama. Jangan mengosongkannya jika ada payroll
sebelum implementasi. Bulan sesudah cutoff harus diproses berurutan. Profil dikunci setelah
dipakai pada slip submitted; perubahan metode di tengah tahun bukan toggle bebas.

## 8. Pemeriksaan hasil dan batas penggunaan

Sebelum submit payroll pertama, cocokkan draft empat pegawai contoh dengan tabel bagian 3.
Periksa baris gaji, bruto pajak, tunjangan, potongan, dan Net Pay. Buka **Kertas Kerja PPh 21**
pada Salary Slip. Setelah submit, periksa **PPh21 Register** dan jurnal Payroll Entry.
Lakukan pengujian masa terakhir juga; panduan uji lengkap ada di [UAT.md](UAT.md).

Rilis 0.3.0 mendukung tahun 2024–2026, pegawai tetap untuk tujuan PPh21, WP dalam negeri
sepanjang tahun dan fasilitas Normal. NIK/NPWP opsional. Fasilitas DTP,
gross-up sebagian, pegawai tidak tetap, PPh26, serta perubahan kewajiban pajak subjektif
memerlukan penanganan lain. Kelayakan fasilitas pajak perusahaan harus ditentukan sebelum
memilih Normal. App ini tidak mengirim laporan atau membuat bukti potong resmi DJP.

Hasil angka di panduan telah diperiksa melalui engine lokal. Instalasi, tampilan, dan
jurnal pada site Frappe Cloud PT PUP belum diverifikasi langsung. Detail pengujian tersedia
di [VALIDASI.md](VALIDASI.md).

## Tambahan 0.4.0 - dua kelompok akun dalam satu Company

| Employee contoh | PPh21 Settings | Metode | Beban tunjangan | Utang pajak |
|---|---|---|---|---|
| EMP-KANTOR | PUP - Kantor | Gross Up | Beban PPh21 Kantor | Utang PPh21 Kantor |
| EMP-PRODUKSI | PUP - Produksi | Gross Up | Beban PPh21 Produksi | Utang PPh21 Produksi |

Company keduanya PT PUP. Dengan input sama (TK/0, penghasilan taxable Rp10 juta,
masa biasa, Floor IDR), masing-masing menghasilkan tunjangan dan potongan Rp230.179.
Besaran pajak sama, tetapi Salary Component dan akun hasil payroll berbeda mengikuti Settings
pilihan di profil. Pada Payroll Entry yang sama, periksa debit tunjangan kantor Rp230.179,
debit tunjangan produksi Rp230.179, serta kredit ke masing-masing utang PPh21 Rp230.179.
Contoh mengasumsikan tidak ada penghasilan/potongan lain dan belum masa rekonsiliasi.

Jika metode Gross, tidak ada baris tunjangan; potongan tetap menuju akun utang Settings
pegawai tersebut. Pengembalian pada masa terakhir juga memakai akun utang Settings itu.
