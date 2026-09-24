# Upgrade ke 0.4.0 - beberapa Settings dalam satu Company

Deploy source melalui repository app di Frappe Cloud, jalankan migrate, lalu reload browser.
Tidak perlu uninstall/reinstall. Perubahan schema menghapus batas unik Company pada Settings.

## Perilaku migrasi

- Settings lama tetap memakai ID/nama record Company dan tiga komponen PPh21 lama.
  Nama tampilannya menjadi `<Company> - Standar` jika belum ada.
- Profil individual dan baris bulk lama tanpa Settings ditautkan bila Company hanya memiliki satu konfigurasi.
  Jika tidak ada atau ambigu, pilih Settings secara eksplisit; app tidak mengambil hasil pertama secara acak.
- Fiscal Year, identitas, saldo awal, nama profil, Salary Slip submitted, dan snapshot historis tidak ditulis ulang.
- Settings baru memakai ID `PPH21-SET-00001` dan seterusnya, dengan nama tampilan bebas seperti
  **PUP - Kantor** atau **PUP - Produksi**. Tiga komponen payroll dibuat untuk setiap Settings baru.

## Langkah setelah migrate

1. Buka Settings lama. Periksa akun beban dan utang, lalu **Save** untuk memastikan mapping
   pada field `Salary Component Account.account` yang dipakai HRMS v15.
   Rilis lama memakai field `default_account` yang tidak dibaca Payroll Entry standar.
   Akun yang sudah berisi nilai berbeda dan digunakan slip submitted tidak ditimpa otomatis.
2. Buat Settings baru untuk kelompok akun lain. Isi nama, Company, akun beban/utang,
   pembulatan, dan seluruh mapping komponen; aktifkan Settings sesuai kebutuhan.
3. Pada Employee Tax Profile pilih **PPh21 Settings** milik Company pegawai.
   Bila hanya satu Settings aktif dan dapat diakses, pilihan kosong terisi otomatis saat Save.
   Bila beberapa, pilih sendiri. Bulk menyediakan pilihan per baris, sehingga satu batch dapat
   mencakup beberapa konfigurasi dan Company.
4. Bulk dengan Settings kosong mempertahankan pilihan profil lama. Untuk profil baru,
   Settings wajib dapat ditentukan sebelum batch berhasil Submit.
5. Hitung ulang draft sebelum submit. Periksa Settings, komponen, akun dalam snapshot,
   Net Pay, dan Journal Entry untuk dua pegawai dengan Settings berbeda pada payroll yang sama.

## Proteksi histori

Settings pada profil yang sudah digunakan slip submitted tidak dapat diganti. Batalkan/koreksi
slip terkait sesuai urutan histori jika memang perlu mengubah profil. Jika cukup berlaku mulai
tahun berikutnya, pilih Settings baru pada profil tahun berikutnya.

Akun dan pembulatan Settings yang sudah dipakai slip submitted dikunci. Nama tampilan dapat
diperbarui. Perubahan akun/atribut komponen otomatis yang sudah digunakan juga ditolak.
Company Settings yang telah tersimpan tidak dapat diganti; buat konfigurasi baru.

Jangan menambahkan komponen otomatis ke Salary Structure/Additional Salary. ERPNext tidak
perlu diubah dan tidak ada override Payroll Entry; pemisahan akun memakai mekanisme standar
HRMS berdasarkan komponen dan Company. PPh21 Register lama tetap dapat dibaca; snapshot lama
mempertahankan isi aslinya dan tidak diberi Settings baru secara retrospektif.

Uji staging diperlukan untuk migrasi database nyata, izin Company, dan jurnal sebelum produksi.

## Pembaruan tampilan 0.4.1

Deploy dan migrate seperti biasa, lalu reload Desk. Menu berubah menjadi **HR > PPh 21**.
Workspace lama dinamai ulang sebelum sync agar tidak muncul duplikat. Nama teknis app tetap
`frappe_hr_pph21` dan Module Def internal tetap `Frappe HR PPh21`. Data payroll tidak berubah.
Jika nama PPh 21 sudah dipakai workspace milik modul lain, migrasi berhenti dengan pesan
konflik agar workspace tersebut tidak ditimpa.
