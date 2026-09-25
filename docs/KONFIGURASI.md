# Konfigurasi PT PUP - rilis 0.4.0

Form master memakai 2-3 kolom; tabel mapping tetap selebar form.
Profil massal dapat dibuat melalui [Bulk PPh21 Employee Tax Profile](BULK_PROFILE.md).

## 1. Komponen dan akun

Setiap **PPh21 Settings** baru membuat tiga komponen otomatis khusus konfigurasi itu.
Nama komponennya memakai akhiran ID Settings, misalnya `[PPH21-SET-00001]`.
Instalasi juga mempertahankan tiga komponen tanpa akhiran untuk Settings lama:


| Komponen | Tipe | Taxable | Account setelah Settings disimpan |
|---|---|---|---|
| PPh21 Tunjangan Pajak | Earning | Ya | Beban Tunjangan PPh 21 |
| PPh21 Potongan Pajak | Deduction | Tidak relevan | Utang PPh 21 |
| PPh21 Pengembalian Pajak | Earning | Tidak | Utang PPh 21 |

Semua tidak bergantung pada payment days, tidak statistical, dan tidak memakai formula.
Komponen ditambahkan otomatis setelah HRMS menghitung gaji aktual. **Jangan memasukkannya ke
Salary Structure/Additional Salary.** Pengaturan ini diperiksa kembali pada setiap kalkulasi.

Di PPh21 Settings pilih akun Expense dan Liability non-group, aktif, IDR, milik perusahaan
tersebut. Isi **Nama Pengaturan** agar mudah dikenali. Satu Company boleh memiliki beberapa
Settings; menyimpan Settings memetakan akun ke komponen khususnya, bukan menimpa konfigurasi lain.
Contoh:

| Nama Settings | Company | Beban tunjangan | Utang PPh21 | Profil pegawai |
|---|---|---|---|---|
| PUP - Kantor | PT PUP | Beban PPh21 Kantor | Utang PPh21 Kantor | Kelompok kantor |
| PUP - Produksi | PT PUP | Beban PPh21 Produksi | Utang PPh21 Produksi | Kelompok produksi |

Nama akun di atas ilustrasi; pilih akun COA yang benar-benar ada. Kedua Settings tetap
memerlukan mapping semua komponen yang muncul pada slip kelompoknya.
Dropdown akun otomatis dibatasi Company yang dipilih, root type, IDR, aktif, dan non-group.
Pada form baru, mengganti Company mengosongkan pilihan akun lama. Company tidak dapat diganti setelah Settings disimpan.
Tidak ada Company, Chart of Accounts atau Journal Entry yang dibuat otomatis oleh instalasi.

Pengaturan pembulatan awal Floor IDR (ke bawah rupiah penuh). Pilih Half Up IDR bila itu
kebijakan payroll yang telah dicocokkan dengan pelaporan. Setelah ada slip submitted,
perubahan akun/pembulatan Settings yang digunakan diblokir. Pembulatan PKP ke ribuan rupiah tetap wajib di engine.

## 2. Pemetaan komponen

Dropdown Salary Component menampilkan nama, kode abbreviation, dan tipe komponen.
Kode juga tampil pada kolom Kode Komponen; pencarian bisa memakai nama atau kode.

Seluruh komponen yang muncul pada slip pegawai PPh21 wajib dipetakan secara eksplisit.
Checkbox Is Tax Applicable bawaan tidak menjadi sumber keputusan pajak app; mapping ini
adalah sumbernya. Selaraskan checkbox bawaan untuk menghindari kebingungan pengguna.

| Contoh | Treatment | Catatan |
|---|---|---|
| Gaji pokok, tunjangan, lembur | Taxable Cash | Penghasilan tunai objek pajak |
| THR, bonus | Taxable Cash | Additional Salary pada bulan yang sama |
| JKK/JKM/BPJS Kesehatan pemberi kerja | Taxable Noncash | Masuk bruto pajak, tidak dibayar tunai |
| Natura kena pajak | Taxable Noncash | Hanya yang objek pajak setelah pengecualian |
| JHT/JP pegawai yang memenuhi syarat | Annual Deduction | Pengurang tahunan; tetap potongan THP bulanan |
| Zakat wajib yang memenuhi syarat melalui pemberi kerja | Annual Deduction | Periksa penerima dan bukti pembayaran |
| Reimbursement/nonobjek yang memenuhi syarat | Non Taxable | Bukan blanket exemption untuk seluruh reimbursement |
| BPJS Kesehatan pegawai, kasbon, potongan lain | Ignore | Tetap mengurangi THP; bukan pengurang fiskal tahunan |

Biaya jabatan dan PTKP **tidak perlu dibuat sebagai komponen deduction**; engine
menghitungnya pada masa terakhir. JHT/JP perusahaan yang memenuhi pengecualian tidak masuk
bruto pajak; jangan memetakannya sebagai Taxable Noncash.

Untuk Noncash gunakan Salary Component **Earning** dengan:

- `Do Not Include in Total = 1`
- `Do Not Include in Accounting Entries = 1`
- `Statistical Component = 0`

HRMS v15 tidak menyimpan Statistical Component sebagai baris Salary Slip; karena itu tidak
bisa menjadi sumber audit nominal noncash di app ini. Iuran noncash dibukukan melalui proses
BPJS perusahaan yang terpisah agar biaya/utang BPJS tidak tercatat ganda. Jika versi minor HRMS
Anda belum mempunyai Do Not Include in Accounting Entries, upgrade v15 lebih dahulu atau
adaptasi integrasi noncash; app tidak akan mengabaikan komponen tersebut secara diam-diam.

Formula BPJS yang ada tetap dikelola Salary Structure. App tidak menentukan batas upah,
persentase iuran, atau klasifikasi risiko JKK. Jangan membuat formula komponen dasar bergantung
pada PPH21_TAX_ALLOW/PPH21_TAX atau field pph21_tax_* karena menyebabkan ketergantungan melingkar.

## 3. Profil pegawai

Buat satu PPh21 Employee Tax Profile per Employee/tahun. Pilih **PPh21 Settings** yang aktif
untuk Company pegawai. Saat pilihan kosong, app mengisi otomatis hanya bila ada satu Settings
aktif yang dapat diakses; jika beberapa, pilih sendiri. Pilihan dikunci setelah profil dipakai slip submitted.
 Pilih Link **Fiscal Year** dari master ERPNext;
angka tahun dihitung dari tanggal periode, bukan nama record. Periode harus Januari-Desember, aktif,
berlaku untuk Company pegawai, dan berada dalam tahun 2024-2026. Company mengikuti Employee. PTKP default dari `Employee.custom_ptkp` jika ada dan dikenali,
namun tetap dapat dikoreksi. Nilai kosong/tidak dikenali perlu dipilih manual.
Pilih status PTKP berdasarkan keadaan yang berlaku untuk tahun pajak itu, dengan bukti HR.
Kategori TER otomatis: A = TK/0,TK/1,K/0; B = TK/2,TK/3,K/1,K/2; C = K/3.

NIK/NPWP **opsional**. Jika diisi, app memeriksa format 15/16 digit.
Checkbox verifikasi identitas hanya catatan manual; kosong/tidak terverifikasi tidak memblokir
penyimpanan profil atau payroll. App tidak menghubungi DJP dan tidak otomatis menandai identitas
sebagai terverifikasi. Perhitungan tetap memakai skema Normal yang didukung app.

Mulai v0.3.1, **Pegawai tetap untuk tujuan PPh 21** dan **WP dalam negeri sepanjang tahun pajak**
otomatis tercentang pada profil baru. Nilai profil yang sudah tersimpan tidak diubah.
Periksa kesesuaiannya dengan kondisi pegawai; validasi cakupan perhitungan tetap berlaku.
Pegawai mulai Juli atau
resign April tetap dapat termasuk WP dalam negeri sepanjang tahun; ini berbeda dari baru
menjadi/berhenti sebagai subjek pajak dalam negeri. Kasus kedua tidak dicakup rilis ini.
Pilih fasilitas Normal; DTP diblokir karena memerlukan mekanisme pembayaran dan pelaporan berbeda.

Tanggal mulai/resign berasal dari Employee. Isi relieving date **sebelum** membuat slip akhir.
Perubahan status pajak/profile setelah digunakan pada slip submitted diblokir; koreksi dengan
pembatalan/amendment berurutan dan pembetulan pelaporan bila diperlukan.

## 4. Migrasi pertengahan tahun

Contoh mulai memakai app September 2026:

- Opening through month = 8.
- Opening gross = bruto Januari–Agustus **termasuk tunjangan pajak** dan komponen noncash objek pajak.
- Opening allowance = tunjangan pajak Januari–Agustus (bagian dari opening gross, bukan penambahan kedua).
- Opening deductions = JHT/JP/iuran pensiun/zakat yang diperbolehkan Januari–Agustus.
- Opening tax = PPh 21 yang sudah dipotong Januari–Agustus, dalam rupiah penuh.
- Opening reference = nomor/path kertas kerja yang sudah diperiksa payroll.

Jangan masukkan biaya jabatan atau PTKP sebagai opening deductions. Jangan masukkan
penghasilan dari pemberi kerja lain. Setiap bulan setelah cutoff harus mempunyai satu slip PPh21
submitted berurutan; sistem menolak histori yang berlubang. Untuk bulan bekerja dengan gaji
nihil, buat slip nihil agar riwayat lengkap.

Jika ada slip lama non-PPh21 sebelum cutoff dalam ERPNext, saldo awal tetap diisi dari kertas
kerja dan slip tersebut tidak dijumlah ulang. Saldo awal tidak boleh tumpang tindih dengan
slip PPh21 submitted. Masa terakhir/resign tidak boleh dimasukkan sebagai saldo awal.

## 5. Payroll bulanan dan THR

Pakai Payroll Frequency Monthly. Periode kerja boleh lintas bulan dengan panjang maksimum
31 hari, misalnya 26 Agustus–25 September 2026. Start/End Date tetap untuk absensi/prorata HRMS.
**Posting Date adalah tanggal pembayaran yang dipakai app untuk tahun dan masa pajak.**
Contoh Posting Date 25 September 2026 masuk September, memakai Tax Profile Fiscal Year 2026.
Tanggal klik Submit maupun tanggal Bank Payment terpisah tidak mengubah masa pajak otomatis.
Pastikan Posting Date sesuai administrasi pembayaran/masa terutang perusahaan. Payroll Period
HRMS tetap dikonfigurasi sesuai kebutuhan HRMS; Fiscal Year profil pajak harus Januari–Desember.

Saldo awal sampai Agustus berarti masa pembayaran Januari–Agustus. Riwayat mulai September
harus berurutan. Karyawan baru yang mulai bekerja dalam periode kerja pertama boleh menerima
gaji pertama pada bulan berikutnya tanpa slip nihil pada bulan join; bulan pembayaran pertama
disimpan dalam kertas kerja. Bila pegawai sudah bekerja sebelum periode pertama yang diinput,
riwayat sebelumnya tetap diperlukan atau harus dicakup saldo awal.

Untuk resign, slip terakhir harus mencakup sampai tanggal berhenti dan dibayar dalam bulan
resign. Pembayaran setelah bulan resign masih di luar cakupan. Jangan memaksakan tanggal palsu;
tinjau proses payroll final. Lihat [contoh cutoff dan upgrade](UPGRADE_0_5.md).

Tambahkan THR/bonus melalui Additional Salary sebelum slip masa tersebut disubmit.
Payroll Date Additional Salary harus masuk Start/End Date slip agar dipungut HRMS. Bila ada
pembayaran THR lebih dulu, proses pembayaran/advance mengikuti akuntansi perusahaan, tetapi
kertas kerja pajak bulan tetap satu slip gabungan. App ini belum mengelola pajak dua slip/off-cycle.

Hapus komponen income tax lama dari struktur pegawai yang memakai PPh21. Jangan menggunakan
Variable Based On Taxable Salary untuk komponen pajak PPh21. Pegawai tanpa PPh21 Enabled
mempertahankan kalkulasi native; pegawai PPh21 membutuhkan Settings yang aktif.

## 6. Masa terakhir dan pengembalian

Engine menjumlah riwayat aktual, menghitung biaya jabatan 5% (maksimum 500.000 × bulan bekerja),
pengurang yang diperbolehkan, PTKP, PKP floor ribuan, dan tarif progresif Pasal 17.
Untuk Gross Up, tunjangan masa terakhir diselesaikan dengan menghitung ulang PKP pada setiap
iterasi sampai tunjangan = tambahan pajak. Tidak memakai TER pada masa terakhir.

Jika lebih potong, tunjangan masa terakhir nol dan selisih dibayar sebagai PPh21 Pengembalian
PPh 21. **Tidak ada clawback otomatis atas tunjangan sebelumnya.** Refund bukan penghasilan
kena pajak baru. Dengan desain ini THP masa terakhir bisa meningkat karena pengembalian.

## 7. Jurnal ilustratif

Untuk bruto tunai 10 juta TK/0 dengan gross-up Floor IDR:

| Account | Debit | Kredit |
|---|---:|---:|
| Beban gaji | 10.000.000 | |
| Beban tunjangan PPh 21 | 230.179 | |
| Utang PPh 21 | | 230.179 |
| Utang gaji | | 10.000.000 |

Jika ada refund 100.000: debit Utang PPh 21, kredit Utang Gaji 100.000 melalui komponen
pengembalian. Penyetoran pajak/debit saldo pajak dan kompensasi pelaporan tetap ditangani
proses akuntansi dan pajak perusahaan. Uji jurnal Payroll Entry pada staging sebelum produksi.

## 8. Koreksi dan audit

Kertas kerja JSON menyimpan versi/hash aturan, metode pembulatan, mapping/nominal, saldo awal,
referensi slip sebelumnya, akun, dan hasil. Buka tombol Kertas Kerja PPh 21 pada Salary Slip.
PPh21 Register hanya menampilkan slip submitted dan mengikuti permission Salary Slip.
PPh21 TER Reference menampilkan seluruh master tarif.

Untuk koreksi bulan lampau, batalkan dari bulan terbaru ke bulan yang perlu diperbaiki,
amend, lalu proses ulang secara kronologis. Jangan mengedit database langsung. Migrate tidak
mengubah snapshot submitted, saldo awal atau payroll yang telah diposting.

Pemetaan dan akun perusahaan dapat memengaruhi slip draft berikutnya. Hindari mengubah
account Salary Component saat Payroll Entry belum selesai diposting; selesaikan jurnal dahulu.


## Checkbox noncash setelah perubahan Salary Component

Mulai 0.5.1, app menyelaraskan kedua flag pengecualian dari master Salary Component yang
sudah disimpan ke baris slip Taxable Noncash sebelum menghitung total gaji. Ini menangani
flag lama pada Salary Structure/draft. Statistical Component harus tetap tidak dicentang,
termasuk pada baris struktur. [Langkah penanganan error](HOTFIX_0_5_1.md).


## Membaca kertas kerja

Mulai 0.5.2, tombol **Kertas Kerja PPh 21** pada Salary Slip menampilkan tabel yang dapat
langsung dibaca. Ringkasan nominal tampil pada form; JSON audit disembunyikan.
Lihat [panduan kertas kerja](KERTAS_KERJA.md) untuk rincian bagian dan slip versi lama.
