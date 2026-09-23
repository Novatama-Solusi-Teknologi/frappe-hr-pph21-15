# Upgrade ke Frappe HR PPh21 0.2.0

## Perubahan

- Form Settings dan profil individual menggunakan 2-3 kolom; saldo awal dapat dilipat.
- Tabel mapping tetap lebar penuh; kode `Salary Component Abbreviation` tampil pada dropdown
  pencarian dan kolom Kode Komponen. Pencarian menerima nama ataupun abbreviation.
- Dropdown akun otomatis mengikuti Company, jenis akun, IDR, akun aktif, dan bukan group.
  Mengganti Company mengosongkan akun yang sebelumnya dipilih. Validasi server tetap berlaku.
- Bagian PPh21 pada Salary Slip menggunakan 3 kolom; JSON kertas kerja di bagian tersendiri.
- Form [Bulk PPh21 Employee Tax Profile](BULK_PROFILE.md) untuk membuat/memperbarui profil.
- Default `custom_ptkp` Employee tersedia pada bulk dan form individual; tidak membuat
  custom field Employee baru jika field tersebut tidak ada.
- Mesin TER/gross-up, tarif, dan metode pembulatan tidak berubah pada rilis ini.

## Frappe Cloud

1. Push source rilis 0.2.0 ke repository/branch app yang terhubung ke Private Bench Group.
2. Deploy pembaruan bench ke site staging yang memiliki Frappe, ERPNext, dan HRMS v15.
3. Pastikan site menjalankan migrate; tidak perlu uninstall/reinstall app.
4. Reload browser setelah deploy. Periksa menu Bulk, layout, kode komponen, dan filter akun.
5. Jalankan skenario [UAT](UAT.md), terutama akses Company dan rollback batch.
6. Setelah staging lulus, deploy versi yang sama ke produksi sesuai proses perusahaan.

Migrate menambahkan schema bulk, layout, dan kode tampilan pada mapping lama. Data profil,
settings akun, saldo awal, snapshot slip submitted, serta angka payroll tidak di-reset.
App tetap bernama teknis `frappe_hr_pph21` dan repository `frappe-hr-pph21`.

## Bench mandiri

Setelah source app pada bench diperbarui:

```sh
bench --site SITE_ANDA migrate
bench build --app frappe_hr_pph21
bench --site SITE_ANDA clear-cache
```

Ganti SITE_ANDA dengan nama site. Ikuti proses backup/deploy perusahaan sebelum produksi.
