# Upgrade Frappe HR PPh21 ke 0.3.0

## Perubahan

- Profil individual, header/baris Bulk, dan filter PPh21 Register menggunakan Link ke
  **Fiscal Year**. Angka tahun internal tetap tersimpan sebagai hasil tanggal master
  untuk kompatibilitas identitas profil, histori, dan engine.
- Fiscal Year harus aktif, periode 1 Januari sampai 31 Desember pada tahun sama, berada
  pada 2024-2026, dan berlaku untuk Company pegawai jika master membatasi Company.
- NIK/NPWP tidak wajib. Jika diisi, format 15/16 digit tetap diperiksa.
- Catatan verifikasi identitas bukan syarat menyimpan profil atau menghitung payroll.
  Identitas kosong tidak ditandai terverifikasi. Skema perhitungan tetap Normal.
- Bulk kosong mempertahankan NIK/NPWP profil lama; perubahan identitas mereset catatan
  verifikasi. Proteksi perubahan profil yang dipakai slip submitted tetap berlaku.

## Deploy dan migrate

1. Pastikan master Fiscal Year yang benar sudah tersedia pada ERPNext. App tidak membuatnya.
2. Push source 0.3.0 ke branch app, deploy ke staging Frappe Cloud, lalu pastikan migrate selesai.
3. Reload browser. Periksa pilihan Fiscal Year, NIK opsional, dan skenario di UAT.md.
4. Deploy versi yang sama ke produksi setelah staging lulus. Tidak perlu uninstall/reinstall.

Migrate hanya menambahkan link ke record lama jika tepat satu master aktif sesuai tahun
kalender dan Company. Bila tidak ditemukan/ambigu, link dibiarkan kosong; angka tahun lama,
nama profil, saldo awal, dan snapshot Salary Slip tidak ditulis ulang. Pilih Fiscal Year
yang tepat sebelum menyimpan perubahan baru pada record yang belum tertaut.

Perintah setelah source bench mandiri diperbarui:

```sh
bench --site SITE_ANDA migrate
bench build --app frappe_hr_pph21
bench --site SITE_ANDA clear-cache
```
