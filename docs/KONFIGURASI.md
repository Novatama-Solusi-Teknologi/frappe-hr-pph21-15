# Konfigurasi PT PUP - rilis 0.3.0

Form master memakai 2-3 kolom; tabel mapping tetap selebar form.
Profil massal dapat dibuat melalui [Bulk PPh21 Employee Tax Profile](BULK_PROFILE.md).

## 1. Komponen dan akun

Instalasi membuat tiga Salary Component berikut, tanpa account atau nilai payroll:

| Komponen | Tipe | Taxable | Account setelah Settings disimpan |
|---|---|---|---|
| PPh21 Tunjangan Pajak | Earning | Ya | Beban Tunjangan PPh 21 |
| PPh21 Potongan Pajak | Deduction | Tidak relevan | Utang PPh 21 |
| PPh21 Pengembalian Pajak | Earning | Tidak | Utang PPh 21 |

Semua tidak bergantung pada payment days, tidak statistical, dan tidak memakai formula.
Komponen ditambahkan otomatis setelah HRMS menghitung gaji aktual. **Jangan memasukkannya ke
Salary Structure/Additional Salary.** Pengaturan ini diperiksa kembali pada setiap kalkulasi.

Di PPh21 Settings pilih akun Expense dan Liability non-group, aktif, IDR, milik perusahaan
tersebut. Menyimpan Settings memetakan akun pada Salary Component untuk perusahaan ini.
Dropdown akun otomatis dibatasi Company yang dipilih, root type, IDR, aktif, dan non-group.
Jika Company diganti, pilihan akun lama dikosongkan.
Tidak ada Company, Chart of Accounts atau Journal Entry yang dibuat otomatis oleh instalasi.

Pengaturan pembulatan awal Floor IDR (ke bawah rupiah penuh). Pilih Half Up IDR bila itu
kebijakan payroll yang telah dicocokkan dengan pelaporan. Setelah ada slip submitted,
perubahan pembulatan diblokir. Pembulatan PKP ke ribuan rupiah tetap wajib di engine.

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

Buat satu PPh21 Employee Tax Profile per Employee/tahun. Pilih Link **Fiscal Year** dari master ERPNext;
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

Payroll Period sebaiknya Januari–Desember. Pakai Payroll Frequency Monthly dan Salary Slip
berdasarkan bulan kalender. Periode boleh dimulai tanggal join atau berakhir tanggal resign.
Masa pajak ditentukan dari bulan Start/End Date slip, bukan bulan tombol submit ditekan.
Pastikan periode mencerminkan saat terutang pajak pada administrasi perusahaan.

Tambahkan THR/bonus melalui Additional Salary sebelum slip bulan tersebut disubmit. Bila ada
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
