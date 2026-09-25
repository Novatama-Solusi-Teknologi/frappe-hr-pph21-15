"""Rebuild the Indonesian user guide (requires reportlab; not a runtime app dependency)."""
from pathlib import Path
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

NAVY = colors.HexColor('#16354b')
TEAL = colors.HexColor('#007e87')
INK = colors.HexColor('#253c4c')
PALE = colors.HexColor('#eaf4f5')
LIGHT = colors.HexColor('#f3f6f8')
styles = {
 'title': ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=25,leading=29,textColor=NAVY,spaceAfter=13),
 'label': ParagraphStyle('label',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=TEAL,spaceAfter=9),
 'h': ParagraphStyle('h',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=NAVY,spaceBefore=15,spaceAfter=7),
 'p': ParagraphStyle('p',fontName='Helvetica',fontSize=10,leading=15,textColor=INK,spaceAfter=9),
 'small': ParagraphStyle('small',fontName='Helvetica',fontSize=8.5,leading=12,textColor=INK,spaceAfter=7),
 'cell': ParagraphStyle('cell',fontName='Helvetica',fontSize=9,leading=13,textColor=INK),
 'th': ParagraphStyle('th',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=colors.white),
}
story=[]
def p(text,style='p'): return Paragraph(text,styles[style])
def add(text,style='p'): story.append(p(text,style))
def heading(text): add(text,'h')
def page(label,title,subtitle):
 if story: story.append(PageBreak())
 add(label,'label');add(title,'title');add(subtitle)
def table(headers,rows,widths,padding=9):
 data=[[p(h,'th') for h in headers]]+[[p(str(v),'cell') for v in r] for r in rows]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
  ('ROWBACKGROUNDS',(0,1),(-1,-1),[LIGHT,colors.white]),('LEFTPADDING',(0,0),(-1,-1),9),
  ('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding),
  ('LINEBELOW',(0,0),(-1,0),1,TEAL)]))
 story.extend([t,Spacer(1,9)])
def callout(title,body):
 t=Table([[p(title,'h')],[p(body)]],colWidths=[499])
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('LEFTPADDING',(0,0),(-1,-1),12),
 ('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,0),5),('BOTTOMPADDING',(0,-1),(-1,-1),8)]))
 story.extend([KeepTogether(t),Spacer(1,8)])
def step(num,title,body):
 story.append(KeepTogether([p(f'{num}. {title}','h'),p(body)]))

page('PANDUAN PRAKTIS / RILIS 0.5.0','Setting PPh21 payroll<br/>dan studi kasus','ERPNext / Frappe HR v15 - untuk HR, payroll, dan finance PT PUP.')
callout('Baru: payroll cutoff, pajak menurut pembayaran','Periode kerja boleh lintas bulan. Isi Posting Date dengan tanggal pembayaran: periode 26 Agustus-25 September dibayar 25 September masuk masa September. Contoh dan langkah pemulihan ada di halaman 12.')
table(['1. Konfigurasi','2. Profil pegawai','3. Hasil payroll'],[
 ['Nama Settings, Company, akun dan mapping komponen.','Pilih Settings dan Fiscal Year. Individual atau bulk.','Periksa pajak, Net Pay, komponen, serta jurnal.']], [166,167,166])
heading('Empat skenario utama')
table(['Komposisi pembayaran','Pajak beban pegawai','Pajak ditunjang perusahaan'],[
 ['Semua penghasilan taxable','Kasus A - Gross','Kasus C - Gross Up'],
 ['Ada pembayaran nonobjek','Kasus B - Gross','Kasus D - Gross Up']], [191,154,154])
add('<b>Gross:</b> pajak mengurangi uang diterima. <b>Gross Up:</b> perusahaan memberi tunjangan sebesar pajak yang dipotong; tunjangan ikut menjadi objek pajak.')
heading('Isi panduan')
table(['Bagian','Hal.','Bagian','Hal.'],[
 ['Settings dan mapping','02','Membaca gross-up','07'],['Profil individual','03','BPJS, noncash, THR','08'],
 ['Bulk profile','04','Desember dan resign','09'],['Dua kelompok akun','05','Saldo awal dan kontrol','10'],
 ['Empat kasus utama','06','Upgrade dan referensi','11'],['Periode cutoff dan pembayaran','12','', '']], [195,40,224,40],padding=6)

page('01 / SETTINGS DAN MAPPING','Konfigurasi bernama, akun terpisah','Menu: PPh21 Settings > New. Satu Company boleh memiliki beberapa Settings.')
step(1,'Isi Nama Pengaturan dan Company','Contoh PUP - Kantor. ID dibuat otomatis, misalnya PPH21-SET-00001. Pilih akun Expense untuk beban tunjangan dan Liability untuk utang PPh21. Akun harus aktif, IDR, non-group, dan milik Company tersebut.')
step(2,'Petakan seluruh komponen slip','Dropdown menampilkan nama, kode abbreviation, dan tipe. Mapping di bawah adalah sumber klasifikasi pajak app; checkbox Is Tax Applicable saja belum cukup.')
table(['Contoh komponen','Treatment','Dampak'],[
 ['Gaji, tunjangan tunai, THR, bonus','Taxable Cash','Menambah bruto pajak dan tunai.'],
 ['Reimbursement at cost yang memenuhi syarat','Non Taxable','Tunai bertambah; bruto pajak tidak.'],
 ['JKK/JKM/BPJS Kesehatan perusahaan objek pajak','Taxable Noncash','Bruto bertambah tanpa tunai.'],
 ['JHT/JP pegawai yang memenuhi syarat','Annual Deduction','Potongan tunai; pengurang fiskal masa terakhir.'],
 ['BPJS Kesehatan pegawai / kasbon','Ignore','Potongan tunai, bukan pengurang fiskal.']], [185,116,198])
callout('Komponen otomatis khusus setiap Settings','Save membuat komponen tunjangan, potongan, dan pengembalian dengan akhiran ID Settings. Jangan memasukkannya ke Salary Structure atau Additional Salary. Settings lama mempertahankan komponen tanpa akhiran.')
add('<b>Taxable Noncash:</b> Earning, Do Not Include in Total = 1, Do Not Include in Accounting Entries = 1, Statistical Component = 0. Pembukuan iuran noncash dilakukan terpisah. JHT/JP perusahaan yang memenuhi pengecualian tidak dipetakan sebagai Taxable Noncash. [2, 4]','small')

page('02 / PROFIL INDIVIDUAL','Hubungkan pegawai ke Settings','Menu: PPh21 Employee Tax Profile > New. Satu profil per pegawai dan tahun pajak.')
step(1,'Pilih Employee dan PPh21 Settings','Company/nama mengikuti Employee. Pilih Settings aktif untuk perusahaan tersebut. Jika hanya satu pilihan aktif yang dapat diakses, pilihan kosong diisi saat Save; jika beberapa, pilih sendiri.')
step(2,'Pilih Fiscal Year dan PTKP','Fiscal Year berasal dari master ERPNext. Tahun diambil dari tanggal periode, bukan nama record. PTKP mengikuti custom_ptkp jika tersedia dan dikenali; nilai kosong/tidak dikenal perlu dipilih manual.')
step(3,'Pilih metode; NIK/NPWP opsional','Pilih Gross atau Gross Up. NIK/NPWP boleh kosong; jika diisi, format 15/16 digit diperiksa. Verifikasi identitas hanya catatan manual dan tidak menghambat payroll bila belum dicentang.')
step(4,'Periksa default dan saldo awal','Pegawai tetap untuk tujuan PPh21 dan WP dalam negeri sepanjang tahun otomatis tercentang pada profil baru. Fasilitas Normal. Lengkapi saldo awal jika migrasi, lalu aktifkan PPh21 Enabled pada Employee.')
step(5,'Jalankan payroll standar','Gunakan struktur Monthly dan Assignment. Posting Date menentukan masa pembayaran. THR/bonus melalui Additional Salary dalam periode kerja slip. Periksa masa pajak, Settings, tunjangan, potongan, dan Net Pay sebelum Submit.')
callout('Fiscal Year yang didukung','Periode aktif 1 Januari-31 Desember dalam tahun yang sama, pada 2024-2026, berlaku untuk Company pegawai. Contoh record bernama Periode Payroll PUP dengan tanggal tahun 2026 menghasilkan tahun pajak 2026.')
add('Settings pada profil yang sudah dipakai slip submitted tidak dapat diganti langsung. Koreksi mengikuti pembatalan slip berurutan; untuk tahun berikutnya pilih Settings pada profil tahun berikutnya.','small')

page('03 / BULK PROFILE','Banyak karyawan, pilihan per baris','HR &gt; PPh 21 &gt; Bulk PPh21 Employee Tax Profile > New.')
table(['Input','Cara pengisian'],[
 ['Karyawan','Company dan nama otomatis mengikuti Employee.'],
 ['Fiscal Year','Mengikuti Fiscal Year Default untuk baris baru; dapat dipilih per baris.'],
 ['PPh21 Settings','Pilih konfigurasi aktif milik Company karyawan.'],
 ['PTKP','Dari custom_ptkp jika dikenali; boleh dikoreksi.'],
 ['Metode PPh21','Gross / Gross Up mengikuti default untuk baris baru.'],
 ['NIK / NPWP','Opsional pada detail baris. Kosong mempertahankan identitas profil lama.']], [130,369])
step(1,'Isi default, lalu maksimum 200 baris','Pilih Fiscal Year Default dan Metode Default. Setiap baris dapat memakai Settings berbeda; satu batch juga boleh berisi beberapa Company sesuai izin akses.')
step(2,'Save draft, periksa, lalu konfirmasi dan Submit','Save belum mengubah profil. Konfirmasi batch menyatakan pegawai tetap, WP dalam negeri sepanjang tahun, fasilitas Normal. Submit menerapkan seluruh baris; satu kegagalan membatalkan seluruh perubahan profil.')
step(3,'Periksa hasil tiap baris','Hasil: Dibuat / Diperbarui / Tidak berubah, dengan tautan Profil Pajak. Aktivasi Employee dan saldo awal tidak diisi otomatis oleh bulk.')
callout('Jika Settings pada baris dikosongkan','Profil lama: konfigurasi sebelumnya dipertahankan. Profil baru: app memilih otomatis hanya bila tepat satu Settings aktif dapat diakses; jika beberapa atau tidak ada, Submit ditolak sampai pilihan jelas.')
add('Profil baru: saldo awal nol, fasilitas Normal, pegawai tetap dan WP dalam negeri aktif setelah konfirmasi batch. Profil lama mempertahankan saldo awal/statusnya. Batch submitted tidak dapat dibatalkan untuk menghapus efek profil.','small')

page('04 / DUA KELOMPOK AKUN','Satu Company, dua konfigurasi','Contoh seluruh karyawan di PT PUP; nama COA berikut hanya ilustrasi.')
table(['Pengaturan','PUP - Kantor','PUP - Produksi'],[
 ['Company','PT PUP','PT PUP'],['Employee contoh','EMP-KANTOR','EMP-PRODUKSI'],
 ['Akun beban tunjangan','Beban PPh21 Kantor','Beban PPh21 Produksi'],
 ['Akun utang pajak','Utang PPh21 Kantor','Utang PPh21 Produksi'],
 ['Pilihan Tax Profile','Settings Kantor','Settings Produksi']], [135,182,182])
heading('Pajak sama, tujuan akun berbeda')
add('Asumsi kedua pegawai: TK/0, taxable cash Rp10.000.000, Gross Up, masa biasa, Floor IDR, tanpa penghasilan atau potongan lain. Masing-masing menghasilkan tunjangan dan potongan Rp230.179.')
table(['Baris pajak dalam jurnal','Debit (Rp)','Kredit (Rp)'],[
 ['Beban PPh21 Kantor','230.179','-'],['Utang PPh21 Kantor','-','230.179'],
 ['Beban PPh21 Produksi','230.179','-'],['Utang PPh21 Produksi','-','230.179']], [299,100,100])
add('Tabel hanya menampilkan bagian pajak; jurnal payroll penuh juga memuat gaji dan akun payroll payable. Dengan cost center yang sama sekalipun, akun tetap terpisah karena komponen khusus setiap Settings.','small')
callout('Gross dan pengembalian pajak','Metode Gross tidak memberi tunjangan, tetapi potongan tetap menuju akun utang Settings pegawai. Pengembalian pada masa terakhir memakai akun utang konfigurasi yang sama.')
add('Setelah slip submitted memakai Settings, akun dan pembulatannya dikunci. Nama tampilan masih dapat diperbarui. Untuk kelompok akun lain, buat Settings baru; jangan mengganti akun komponen yang sudah dipakai.','small')

page('05 / PERBANDINGAN UTAMA','Empat kasus, satu pandangan','Semua angka dalam rupiah. Label A-D konsisten pada kedua tabel.')
callout('Asumsi kasus A-D','Pegawai tetap, TK/0 - TER A, fasilitas Normal, masa biasa (bukan Desember/resign), Floor IDR. Tanpa BPJS, kasbon, atau penghasilan lain.')
heading('Input dan metode')
table(['Kasus','Tunai taxable','Nonobjek','Metode'],[
 ['A - Semua taxable','10.000.000','0','Gross'],['B - Ada nonobjek','8.000.000','2.000.000','Gross'],
 ['C - Semua taxable','10.000.000','0','Gross Up'],['D - Ada nonobjek','8.000.000','2.000.000','Gross Up']], [174,110,110,105])
heading('Hasil otomatis app')
table(['ID','Bruto TER','TER','Tunjangan','PPh21','Uang diterima'],[
 ['A','10.000.000','2%','0','200.000','9.800.000'],['B','8.000.000','1,5%','0','120.000','9.880.000'],
 ['C','10.230.179','2,25%','230.179','230.179','10.000.000'],['D','8.121.827','1,5%','121.827','121.827','10.000.000']], [30,103,55,100,100,111])
add('Tunai taxable adalah penghasilan sebelum tunjangan pajak. Nonobjek diasumsikan reimbursement perjalanan dinas sesuai biaya aktual yang memenuhi syarat, bukan sebagian gaji yang dipilih untuk dibebaskan.','small')
heading('Cara menyiapkan contoh')
add('A/C: Gaji Pokok Rp8 juta + Tunjangan Jabatan Rp2 juta, keduanya Taxable Cash. B/D: Gaji Pokok Rp8 juta Taxable Cash + reimbursement Rp2 juta Non Taxable. Pilih metode sesuai tabel pada profil pegawai.')
add('Lapisan TER mengacu PP 58/2023 [1]. Gross Up tetap menampilkan potongan pajak pada slip. Pilihan akun tidak mengubah angka bila input, mapping, metode dan pembulatan sama.','small')

page('06 / MEMBACA HASIL','Mengapa gross-up Rp230.179?','Kasus C: penghasilan tunai sebelum tunjangan pajak Rp10.000.000.')
table(['Bruto awal','Tambah tunjangan','Bruto final'],[
 ['Rp10.000.000<br/>TER awal 2%','Rp230.179<br/>ikut objek pajak','Rp10.230.179<br/>TER final 2,25%']], [166,167,166])
heading('Ilustrasi Salary Slip')
table(['Baris pada slip','Nominal (Rp)'],[
 ['Gaji Pokok','8.000.000'],['Tunjangan Jabatan','2.000.000'],['PPh21 Tunjangan Pajak [ID Settings]','230.179'],
 ['Total earning tunai','10.230.179'],['PPh21 Potongan Pajak [ID Settings]','(230.179)'],['Uang ditransfer','10.000.000']], [349,150])
callout('Tunjangan konsisten dengan pajak final','Floor IDR: Rp10.230.179 x 2,25% = Rp230.179 setelah pembulatan. Tunjangan menambah dasar pajak, sehingga Rp200.000 belum cukup. App menghitungnya otomatis.')
heading('Bila sebagian pembayaran nonobjek')
add('Kasus B/D memakai reimbursement dinas sepenuhnya untuk tugas perusahaan, sesuai pengeluaran sebenarnya dengan bukti. Kelebihan uang perjalanan lumpsum dapat menjadi penghasilan. Rujukan FAQ DJP PMK 66/2023 nomor 7 [3].')
add('Kasus D: Rp8.000.000 + Rp2.000.000 + Rp121.827 - Rp121.827 = Rp10.000.000 diterima. Reimbursement tidak masuk bruto TER.')
add('Pisahkan komponen berdasarkan sifat transaksi. Jika reimbursement sudah dibayar melalui Expense Claim, jangan dibayar atau dibukukan ulang melalui payroll.','small')

page('07 / VARIASI PAYROLL','BPJS, noncash, dan THR','Asumsi TK/0, masa biasa, fasilitas Normal, Floor IDR. Angka dalam rupiah.')
heading('A. Potongan pegawai - gaji taxable Rp10 juta')
table(['Potongan','Nominal','Mapping'],[
 ['JHT + JP yang memenuhi syarat','300.000','Annual Deduction'],['BPJS Kesehatan pegawai','100.000','Ignore'],['Kasbon','500.000','Ignore']], [249,100,150])
table(['Metode','Tunjangan','PPh21','Uang diterima'],[
 ['Gross','0','200.000','8.900.000'],['Gross Up','230.179','230.179','9.100.000']], [124,125,125,125])
add('Potongan lain Rp900.000. JHT/JP tidak mengurangi bruto TER bulanan; pengurang fiskal digunakan pada masa terakhir. Gross-up pajak tidak menanggung kasbon atau iuran pegawai. [2]','small')
heading('B. Gaji Rp10 juta + noncash taxable Rp400 ribu')
table(['Metode','Bruto awal','Tunjangan / PPh21','Uang diterima'],[
 ['Gross','10.400.000','0 / 260.000','9.740.000'],['Gross Up','10.400.000','266.666 / 266.666','10.000.000']], [95,120,164,120])
add('Bruto awal sebelum tunjangan pajak. Noncash menambah bruto pajak tanpa dibayar tunai. Tidak ada potongan iuran pegawai pada contoh B.','small')
heading('C. Gaji Rp10 juta + THR Rp10 juta')
table(['Metode','Bruto TER','Tunjangan','PPh21','Uang diterima'],[
 ['Gross','20.000.000','0','1.800.000','18.200.000'],['Gross Up','21.978.021','1.978.021','1.978.021','20.000.000']], [80,110,100,100,109])
add('TER kedua contoh C: 9%. THR lewat Additional Salary ke satu slip bulan yang sama. Angka BPJS adalah asumsi nominal, bukan formula tarif/batas upah iuran.','small')

page('08 / MASA TERAKHIR','Desember dan bulan resign','Masa terakhir memakai rekonsiliasi tahunan, bukan mengulang TER masa biasa. [2]')
add('App menghitung penghasilan aktual, biaya jabatan, pengurang yang diperbolehkan, PTKP, dan tarif progresif. Pajak masa terakhir adalah selisih pajak tahunan dengan pemotongan sebelumnya.')
heading('Desember - K/0, metode Gross')
add('Bekerja Januari-Desember. Gaji Rp10 juta/bulan dan iuran pensiun pegawai yang memenuhi syarat Rp100 ribu/bulan; tanpa komponen lain.')
table(['Rekonsiliasi','Nominal (Rp)'],[
 ['Bruto setahun','120.000.000'],['Biaya jabatan','(6.000.000)'],['Iuran pensiun setahun','(1.200.000)'],
 ['PTKP K/0','(58.500.000)'],['PKP','54.300.000'],['PPh21 setahun','2.715.000'],
 ['Pajak Januari-November: 11 x 200.000','(2.200.000)'],['PPh21 Desember','515.000'],['Uang diterima Desember','9.385.000']], [349,150])
add('Uang diterima = Rp10 juta - Rp100 ribu - Rp515 ribu. Biaya jabatan/PTKP dihitung engine; jangan membuatnya sebagai Salary Component deduction.','small')
heading('Resign Februari - TK/0, Gross Up')
add('Gaji Rp10 juta pada Januari dan Februari, lalu resign Februari. WP dalam negeri sepanjang tahun; tanpa penghasilan lain pada pemberi kerja ini. Januari sudah dipotong Rp230.179 dengan tunjangan yang sama.')
callout('Hasil Februari','Pajak tahunan Rp0; tunjangan baru Rp0; refund Rp230.179; uang diterima Rp10.230.179. Tunjangan Januari tidak ditarik kembali. Isi Relieving Date sebelum slip terakhir.')

page('09 / SALDO AWAL DAN KONTROL','Periksa hasil sebelum produksi','Contoh PT PUP mulai memakai app pada September 2026.')
table(['Field profil','Isi saldo awal'],[
 ['Saldo awal sampai bulan','8 - mencakup Januari-Agustus.'],
 ['Bruto termasuk tunjangan pajak','Total bruto Januari-Agustus, termasuk taxable noncash dan tunjangan pajak.'],
 ['Tunjangan pajak dalam bruto','Bagian tunjangan dari bruto di atas; jangan ditambahkan dua kali.'],
 ['Pengurang yang diperbolehkan','Total JHT/JP/pensiun dan zakat yang memenuhi syarat; bukan biaya jabatan/PTKP.'],
 ['PPh21 telah dipotong','Total pemotongan Januari-Agustus.'],
 ['Referensi kertas kerja','Referensi rekap payroll yang sudah diperiksa.']], [230,269])
add('Saldo awal hanya untuk pemberi kerja yang sama. Masa sesudah cutoff harus berurutan. Profil dikunci setelah digunakan pada slip submitted.','small')
step(1,'Periksa draft dan snapshot','Cocokkan Settings, mapping, bruto, tunjangan, potongan, Net Pay, dan akun pada Kertas Kerja PPh21. Hitung ulang draft setelah perubahan konfigurasi yang diperbolehkan.')
step(2,'Periksa jurnal untuk dua Settings','Pada satu Payroll Entry, pastikan beban dan utang masing-masing kelompok masuk COA yang benar. Uji Gross, Gross Up, Desember, dan refund resign. Cocokkan dengan payroll pembanding.')
callout('Pajak nol tetap perlu riwayat','Gaji Rp5 juta, TK/0, Gross pada masa biasa menghasilkan TER 0%. Tetap gunakan Taxable Cash dan PPh21 Enabled; penghasilan masuk rekonsiliasi tahunan.')
add('Instalasi/migrate, UI Desk, izin Company, transaksi bersamaan, dan posting jurnal belum diuji pada site PT PUP. Tes lokal tidak menggantikan UAT pada bench lengkap.','small')

page('10 / UPGRADE DAN REFERENSI','Upgrade ke rilis 0.5.0','Menu: HR &gt; PPh 21. Nama teknis app: frappe_hr_pph21.')
step(1,'Deploy source dan migrate','Push source ke repository app, deploy ke staging Frappe Cloud, jalankan migrate, lalu reload browser. Workspace lama berganti nama menjadi PPh 21 di bawah HR. Tidak perlu uninstall/reinstall.')
step(2,'Periksa Settings lama, lalu Save','Nama tampilan menjadi Company - Standar; ID dan komponen lama dipertahankan. Save memastikan mapping pada field Account yang dibaca HRMS v15. Mapping lama berbeda yang sudah digunakan slip submitted tidak ditimpa otomatis.')
step(3,'Buat konfigurasi baru dan pilih di profil','Tambahkan Settings untuk kelompok akun lain. Profil lama ditautkan otomatis bila tepat satu Settings cocok dengan Company. Jika ambigu, pilih sendiri. Snapshot dan nominal slip lama tidak ditulis ulang.')
table(['Didukung','Belum didukung'],[
 ['Pegawai tetap, WP dalam negeri sepanjang tahun, fasilitas Normal. NIK opsional.','DTP, pegawai tidak tetap, PPh26, perubahan kewajiban pajak subjektif.'],
 ['Fiscal Year Januari-Desember 2024-2026; Gross dan gross-up penuh.','Periode fiskal lintas tahun, gross-up sebagian, dua slip/off-cycle per bulan.']], [250,249])
add('App tidak mengirim laporan DJP, memvalidasi NIK online, atau membuat bukti potong resmi. Perhitungan tarif dan contoh tidak diubah oleh fitur beberapa Settings.','small')
heading('Referensi yang dapat diklik')
refs=[
 ('PP 58 Tahun 2023 - lapisan TER','https://jdih.kemenkeu.go.id/dok/pp-58-tahun-2023'),
 ('PMK 168 Tahun 2023 - pemotongan dan rekonsiliasi','https://pajak.go.id/id/peraturan/petunjuk-pelaksanaan-pemotongan-pajak-atas-penghasilan-sehubungan-dengan-pekerjaan-jasa-1'),
 ('FAQ DJP PMK 66/2023 nomor 7 - reimbursement','https://stats.pajak.go.id/sites/default/files/2023-12/FAQ%20Terkait%20PMK-66%20Tahun%202023.pdf'),
 ('Materi DJP bukti potong A1 - iuran','https://pajak.go.id/sites/default/files/2025-12/Pembuatan%20Bukti%20Pemotongan%20PPh%20Pasal%2021-Tahunan%20A1%20%20%281%29.pdf')]
for i,(label,url) in enumerate(refs,1): add(f'<link href="{url}" color="#007e87">[{i}] {label}</link>','small')
add('Panduan source: docs/UPGRADE_0_5.md, UPGRADE_0_4.md, KONFIGURASI.md, BULK_PROFILE.md, STUDI_KASUS_PAYROLL.md, UAT.md, dan VALIDASI.md.','small')


page('11 / PERIODE CUTOFF','Periode kerja dan masa pajak','Mulai 0.5.0: Start/End Date untuk HRMS; Posting Date untuk masa pembayaran.')
table(['Field Payroll Entry','Contoh PT PUP','Hasil'],[
 ['Start Date','26 Agustus 2026','Awal absensi/prorata.'],
 ['End Date','25 September 2026','Akhir absensi/prorata.'],
 ['Posting Date','25 September 2026','Masa September 2026.'],
 ['Tax Profile / saldo awal','Fiscal Year 2026 / sampai bulan 8','Saldo awal Jan-Agustus bila migrasi.']], [139,158,202])
add('Posting Date harus tanggal pembayaran yang benar. Tanggal klik Submit dan tanggal Bank Payment terpisah tidak menggeser masa pajak otomatis. Jika Jan-Agustus sudah ada sebagai slip PPh21, jangan isi saldo awal untuk masa yang sama.','small')
table(['Periode kerja','Dibayar (Posting Date)','Masa pajak'],[
 ['26 Agu-25 Sep 2026','1 Oktober 2026','Oktober; riwayat sampai September diperlukan.'],
 ['26 Nov-25 Des 2026','25 Desember 2026','Desember; rekonsiliasi tahunan.'],
 ['26 Des 2025-25 Jan 2026','25 Januari 2026','Januari; profil 2026.']], [166,151,182])
heading('Mengulang Create Salary Slips yang gagal')
add('Deploy source 0.5.0, jalankan migrate, lalu reload Desk. Periksa Posting Date, profil dan riwayat/saldo awal. Jika belum ada slip, ulangi Create Salary Slips. Jika ada draft parsial, periksa dan hitung ulang draft melalui alur HRMS agar tidak membuat duplikat.','small')
add('Periksa Tanggal Pembayaran (Posting Date), Tahun Pajak dan Masa Pajak pada bagian PPh 21 Salary Slip. Snapshot menyimpan tanggal pembayaran dan periode kerja. Uji nominal serta jurnal pada staging sebelum produksi.','small')
heading('Batas dan riwayat')
add('Satu slip per pegawai/Company/masa pembayaran, maksimum 31 hari kalender dalam periode. Slip submitted lama tidak direlabel. Payroll Date bonus harus masuk Start/End Date slip. Resign harus dicakup slip final dan dibayar dalam bulan resign; pembayaran bulan sesudahnya belum didukung. Tahun pembayaran 2027 masih di luar master aturan.','small')
add('Basis pembayaran dipakai untuk alur PT PUP yang dikonfirmasi. Saat terutang menurut PMK 168/2023 Pasal 21 tetap mengikuti pembayaran atau terutangnya penghasilan, mana lebih dahulu; app tidak mendeteksi tanggal pengakuan utang terpisah. [2]','small')


def decorate(canvas,doc):
 canvas.saveState();canvas.setFillColor(NAVY);canvas.setFont('Helvetica-Bold',8)
 canvas.drawString(48,807,'PT PUP / PPH 21');canvas.drawRightString(547,807,'PANDUAN PAYROLL / V15')
 canvas.setStrokeColor(TEAL);canvas.line(48,795,547,795)
 canvas.setFont('Helvetica',8);canvas.setFillColor(INK)
 canvas.drawString(48,32,'PPh 21 0.5.0 | 25 September 2026')
 canvas.drawRightString(547,32,f'{doc.page:02d} / 12');canvas.restoreState()

if __name__ == '__main__':
 out=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/'docs/Panduan_PPh21_Payroll_PT_PUP.pdf'
 out.parent.mkdir(parents=True,exist_ok=True)
 doc=SimpleDocTemplate(str(out),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=65,bottomMargin=53,
                       title='Panduan PPh21 Payroll PT PUP - v0.5.0',author='PT PUP',pageCompression=1)
 doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
 print(out)
