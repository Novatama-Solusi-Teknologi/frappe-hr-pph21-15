# Bulk PPh21 Employee Tax Profile

Panduan **Frappe HR PPh21 0.4.0**, untuk ERPNext/Frappe HR v15.
Form dapat dibuka melalui workspace **HR > PPh 21** atau pencarian Desk.

## Tujuan dan tata letak

Satu form memuat maksimum **200 baris profil**. Bagian default di atas menggunakan tiga
kolom; tabel karyawan menggunakan lebar penuh. Form profil individual dan Settings memakai
2-3 kolom. Tampilan pada layar kecil mengikuti layout responsif Frappe.

Empat data utama dan satu identitas opsional tersedia per baris:

| Field | Cara pengisian |
|---|---|
| Karyawan | Pilih Employee. Nama dan Company diambil otomatis dari data Employee. |
| Fiscal Year | Pilih dari DocType Fiscal Year; mengikuti Fiscal Year Default untuk baris baru. Angka tahun internal dihitung otomatis dari tanggal periode. |
| NIK / NPWP | Opsional. Jika diisi harus 15/16 digit. Kosong pada bulk mempertahankan identitas profil lama. |
| PTKP | Default dari `Employee.custom_ptkp` jika ada dan dikenali; tetap dapat dikoreksi. |
| Metode PPh21 | Mengikuti Metode Default saat baris ditambahkan: Gross Up atau Gross. |

Fiscal Year dipilih dari master yang sudah ada, bukan angka tahun bebas atau tebakan dari
nama record. Pilih periode aktif 1 Januari-31 Desember yang berlaku untuk Company pegawai;
tahun didukung 2024-2026. Default metode
adalah Gross Up. Perubahan default hanya berlaku pada baris baru/kosong, tidak menimpa baris
lama. Kode Employee dan nama pegawai mengikuti tampilan Link standar ERPNext.

PTKP yang didukung: TK/0, TK/1, TK/2, TK/3, K/0, K/1, K/2, K/3. Variasi huruf kecil,
spasi, atau tanpa slash seperti `tk0` dinormalisasi. Jika custom field tidak ada/kosong,
atau nilainya tidak dikenali (misalnya K/I/3), PTKP harus dipilih manual; app tidak menebak TK/0.
Default PTKP yang sama juga berlaku saat memilih Employee pada profil individual.

Company bersifat read-only dan diperiksa kembali di server; bukan input manual.
Satu batch dapat berisi lebih dari satu Company, sepanjang pengguna memiliki akses baca
ke seluruh Employee dan akses membuat/mengubah profil yang bersangkutan.

## Langkah kerja

1. Buka **Bulk PPh21 Employee Tax Profile > New**.
2. Tentukan **Fiscal Year Default** dan **Metode Default**.
3. Tambahkan baris pada **Profil Karyawan**, pilih Employee, lalu lengkapi lima field di atas.
   Buka detail baris untuk melihat Company/nama karyawan.
4. Klik **Save**. Ini hanya menyimpan draft batch; profil individual belum diubah.
5. Periksa semua baris, lalu centang **Saya mengonfirmasi seluruh baris memenuhi persyaratan standar**.
   Konfirmasi ini sekali per batch, bukan pengisian field pajak tambahan per pegawai.
6. Klik **Submit**. App membuat/memperbarui profil individual dalam satu transaksi.
7. Buka detail baris untuk melihat **Hasil** dan tautan **Profil Pajak**.
8. Periksa saldo awal jika migrasi serta aktivasi **PPh21 Enabled** pada Employee sebelum payroll.

Persyaratan standar yang dikonfirmasi: pegawai tetap untuk tujuan PPh21, WP dalam negeri
sepanjang tahun, dan fasilitas Normal. NIK/NPWP boleh kosong.
Konfirmasi pengguna bukan validasi identitas online ke DJP. Jika tidak sesuai, jangan
masukkan pegawai tersebut ke batch standar ini.

## Default profil baru dan perlakuan profil lama

| Field di luar lima input | Profil baru | Profil yang sudah ada |
|---|---|---|
| Company / Nama Pegawai | Dari Employee | Dari Employee; proteksi payroll tetap berlaku |
| Kategori TER | Otomatis dari PTKP | Dihitung kembali dari PTKP |
| WP dalam negeri / pegawai tetap | Aktif setelah konfirmasi batch | Dipertahankan |
| Verifikasi identitas | Tidak ditandai otomatis | Dipertahankan; direset jika identitas diubah |
| Fasilitas Pajak | Normal | Dipertahankan |
| Bulan dan nominal saldo awal | 0 | **Dipertahankan**, tidak di-reset |
| Referensi saldo awal / catatan | Default kosong | **Dipertahankan** |
| PPh21 Enabled pada Employee | Tidak diubah | Tidak diubah |

Jika profil baru membutuhkan saldo awal, lengkapi melalui profil individual sebelum membuat
slip. Bulk ini tidak membuat Salary Slip, tidak memposting jurnal, dan tidak mengaktifkan
payroll perusahaan/pegawai secara otomatis.

## Hasil proses dan proteksi

| Hasil | Arti |
|---|---|
| Dibuat | Profil Employee/tahun tersebut belum ada dan berhasil dibuat. |
| Diperbarui | Lima input berubah pada profil yang masih boleh dikoreksi. |
| Tidak berubah | Profil sudah ada dengan nilai sama; tidak dibuat duplikat dan tidak disimpan ulang. |

Duplikasi Employee+tahun dalam satu batch ditolak. Employee yang sama dengan tahun berbeda
diperbolehkan jika tanggal kerja sesuai. Tahun, identitas, PTKP, dan metode diperiksa di server.

Jika satu baris gagal, **seluruh perubahan profil dalam batch di-rollback**, termasuk profil
baru pada baris sebelumnya. Batch tetap belum submitted. Perbaiki data lalu ulangi Submit.
Profil yang sudah digunakan oleh Salary Slip submitted tidak boleh diubah melalui bulk;
baris identik yang tidak mengubah profil tetap diterima sebagai Tidak berubah.

Batch submitted merupakan rekaman penerapan dan tidak dapat dibatalkan untuk menghapus efeknya.
Koreksi menggunakan batch baru atau profil individual, mengikuti proteksi histori payroll.
Hak akses profil/Employee tidak dilewati; membaca batch juga mensyaratkan akses ke semua
Employee yang tercantum. Uji Company User Permission pada site staging.

## Contoh tiga baris

| Karyawan contoh | Company otomatis | Fiscal Year | NIK/NPWP | custom_ptkp | Metode |
|---|---|---:|---|---|---|
| EMP-001 | PT PUP | FY 2026 (master) | Boleh kosong | TK/0 | Gross |
| EMP-002 | PT PUP | FY 2026 (master) | Boleh kosong | K/1 | Gross Up |
| EMP-003 | PT PUP | FY 2026 (master) | Boleh kosong | Kosong: pilih manual | Gross Up |

Contoh di atas tidak memuat identitas nyata. Saldo awal dan PPh21 Enabled tetap diperiksa
setelah profil berhasil dibuat.

## Migrasi dari rilis sebelumnya

Migrate menautkan record lama jika tepat satu Fiscal Year aktif sesuai periode dan Company.
Jika tidak ada atau ambigu, link dibiarkan kosong; angka tahun lama tetap tersimpan untuk
kompatibilitas histori. Pilih master yang benar sebelum mengedit kembali record tersebut.
Tidak ada Fiscal Year baru yang dibuat otomatis. Profil baru tetap menggunakan tahun hasil
master, walaupun angka internal dikirim berbeda melalui API.

Pada profil baru, NIK/NPWP kosong disimpan kosong dan status verifikasi tetap nonaktif.
Pada profil lama, NIK/NPWP kosong dalam bulk berarti tidak mengubah identitas. Untuk
menghapus identitas secara sengaja, gunakan profil individual sesuai proteksi histori.

## Pilihan PPh21 Settings per baris (0.4.0)

Pilih **PPh21 Settings** untuk masing-masing karyawan. Dropdown hanya menampilkan konfigurasi
aktif milik Company karyawan. Satu batch dapat berisi beberapa kelompok akun.

- Profil baru: jika Settings kosong dan hanya satu pilihan aktif yang dapat diakses, app
  mengisinya saat membuat profil. Jika beberapa atau tidak ada, Submit ditolak sampai dipilih.
- Profil lama: Settings kosong pada baris bulk mempertahankan konfigurasi sebelumnya.
- Settings dari perusahaan berbeda, nonaktif, atau tidak dapat diakses ditolak.
- Mengganti Employee membersihkan pilihan Settings sebelumnya.
- Profil yang sudah digunakan slip submitted tidak dapat dipindahkan ke Settings lain.
- NIK/NPWP tetap opsional dan tersedia saat membuka detail baris; kolom grid menampilkan
  Settings agar kelompok akun mudah dibandingkan.
