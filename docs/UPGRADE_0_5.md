# Upgrade PPh 21 ke 0.5.0 — periode cutoff

Perbaikan mengatasi error “memerlukan satu periode dalam satu bulan kalender” saat
Create Salary Slips dengan periode 26 Agustus–25 September 2026.

## Pengisian tanggal

| Field | Contoh PT PUP | Fungsi |
|---|---|---|
| Payroll Frequency | Monthly | Maksimum 31 hari dalam satu periode kerja |
| Start Date | 26 Agustus 2026 | Awal periode kerja/absensi |
| End Date | 25 September 2026 | Akhir periode kerja/absensi |
| Posting Date | 25 September 2026 | Tanggal pembayaran; sumber tahun/masa pajak |
| Fiscal Year pada Tax Profile | Tahun kalender 2026 | Profil dipilih berdasarkan tahun pembayaran |
| Saldo awal sampai bulan | 8, bila migrasi mulai September | Total masa pembayaran Januari–Agustus |

App tidak mengubah Start/End Date atau menghitung ulang jumlah hari kerja HRMS.
Nominal setelah prorata HRMS menjadi input pajak. Posting Date diteruskan oleh Payroll Entry
ke Salary Slip. Tanggal Bank Payment/Payment Entry terpisah tidak dibaca untuk menggeser masa.
Jika sudah ada riwayat PPh21 Januari–Agustus dalam app, jangan isi saldo awal untuk masa sama.

| Periode kerja | Posting Date | Masa pajak |
|---|---|---|
| 26 Agustus–25 September 2026 | 25 September 2026 | September 2026 |
| 26 Agustus–25 September 2026 | 1 Oktober 2026 | Oktober 2026; perlu riwayat September |
| 26 November–25 Desember 2026 | 25 Desember 2026 | Desember 2026; rekonsiliasi tahunan |
| 26 Desember 2025–25 Januari 2026 | 25 Januari 2026 | Januari 2026; profil tahun 2026 |

Tahun aturan masih 2024–2026. Pembayaran Januari 2027 memerlukan pembaruan master aturan;
jangan mengganti tanggal pembayaran untuk menghindari pembatasan tersebut.

## Urutan upgrade dan ulang proses

1. Push source 0.5.0 ke repository app, deploy di staging Frappe Cloud dan jalankan migrate.
   Tidak perlu uninstall/reinstall. Rilis ini memuat hotfix workspace dan permission sebelumnya.
2. Reload Desk. Field baca-saja **Tanggal Pembayaran (Posting Date)** muncul di bagian PPh 21
   Salary Slip setelah dihitung; kertas kerja merekam tanggal pembayaran serta periode kerja.
3. Pastikan Tax Profile 2026 tersedia dan saldo awal/riwayat sampai Agustus lengkap.
   Isi Posting Date sesuai tanggal pembayaran sebenarnya sebelum Create Salary Slips.
4. Periksa Payroll Entry yang gagal: jika belum ada slip, ulangi Create Salary Slips setelah
   status job gagal selesai. Jika ada draft parsial, periksa/hitung ulang draft tersebut melalui
   alur HRMS; jangan membuat duplikat. Untuk slip submitted, gunakan prosedur cancel/amend
   dari masa terbaru beserta jurnal terkait, bukan menghapus data langsung.
5. Uji masa September, nominal gross-up, prorata, akun Settings, serta jurnal lewat Payroll Entry.
   Deploy ke produksi setelah UAT dan backup sesuai proses Frappe Cloud perusahaan.

## Riwayat dan batasan

- Upgrade tidak mengubah slip submitted lama. Masa/tahun yang tersimpan tetap sumber riwayat,
  meskipun Posting Date legacy berbeda; tinjau dan koreksi terkontrol bila perlu sebelum beralih.
- Satu slip per pegawai/perusahaan/masa pembayaran. Bonus/THR digabung; Payroll Date Additional
  Salary harus berada dalam periode kerja agar diambil HRMS. Off-cycle dua slip belum didukung.
- Slip periode kerja tumpang tindih tetap ditolak meskipun dibayar pada bulan/tahun berbeda.
- Rekonsiliasi mengikuti pembayaran Desember atau bulan resign. Slip resign harus mencakup
  hari terakhir bekerja. Pembayaran setelah bulan resign belum didukung oleh rilis ini.
- Pegawai baru yang join di dalam periode kerja pertamanya boleh menerima pembayaran pertama
  pada bulan berikutnya. Bulan pertama disimpan pada snapshot; periode berikutnya tetap wajib urut.
- Tidak mengubah tarif TER, rumus gross-up, atau pengaturan COA.

Basis Posting Date diterapkan untuk alur pembayaran PT PUP yang dikonfirmasi pengguna.
Penentuan saat terutang tetap mengikuti administrasi perusahaan dan
[PMK 168/2023 Pasal 21](https://jdih.kemenkeu.go.id/dok/pmk-168-tahun-2023/summary):
pembayaran atau terutangnya penghasilan, mana yang lebih dahulu. App tidak mendeteksi
perbedaan tanggal pengakuan utang, pembayaran bank, dan Posting Date secara otomatis.

Pengujian lokal memakai metode aritmetika HRMS v15 dan database double. Instalasi/migrasi,
transaksi bersamaan, serta Create/Submit Salary Slips pada site PT PUP tetap perlu UAT.
