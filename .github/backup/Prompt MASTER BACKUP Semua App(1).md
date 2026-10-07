KAMU ADALAH MASTER BACKUP INTEGRATOR UNTUK SELURUH APLIKASI/REPO YANG SAYA BUAT.

TUJUAN UTAMA:\
Buat 1 file final:

MASTER-BACKUP-SEMUA-APP-[TANGGAL].zip

Ini BUKAN backup untuk satu aplikasi saja.

Backup ini harus mencakup SEMUA aplikasi, repo, source code, riwayat Git, build penting, dokumentasi recovery, dan informasi yang diperlukan agar jika akun GitHub saya terkena suspend/hilang lagi, saya dapat membuat akun/repo baru dan memulihkan proyek dengan semudah mungkin.

1. JANGAN membuat fitur baru.
2. JANGAN redesign aplikasi.
3. JANGAN mengubah source code kecuali benar-benar diperlukan untuk membuat mekanisme backup/recovery.
4. Fokus hanya pada BACKUP, INVENTARISASI, VERIFIKASI, dan RECOVERY.
5. Jangan menganggap ZIP source biasa sebagai backup penuh.
6. Jangan hanya menyimpan aplikasi hasil build.
7. Untuk setiap proyek, sebisa mungkin harus tersedia:
   - source code;
   - riwayat Git;
   - branch;
   - tag;
   - commit;
   - workflow GitHub Actions;
   - konfigurasi build;
   - dependency manifest;
   - dokumentasi;
   - prompt/perencanaan penting yang memang tersimpan di repo;
   - build portable terakhir yang sudah teruji jika tersedia.
8. Jangan masukkan password, API key, token GitHub, token Gemini, secret Actions, credential, atau data rahasia ke backup.
9. Secret cukup dicatat sebagai:\
   SECRET_REQUIRED_BUT_NOT_BACKED_UP\
   beserta nama secret yang nantinya perlu diisi kembali.
10. Jangan mengandalkan GitHub tetap tersedia setelah backup dibuat.
11. File final harus bisa saya simpan sendiri di SSD/HDD/cloud lain.

Periksa seluruh repo GitHub saya yang dapat diakses.

Jangan hanya melihat repo yang sedang dibahas di chat.

Buat daftar SEMUA aplikasi/proyek yang saya miliki.

Contoh proyek yang mungkin termasuk, tetapi JANGAN membatasi hanya pada daftar ini:

- Mini Cut / MiniCut
- Full Album Video Maker
- AI Music Downloader
- YouTube Bulk Downloader
- ChatGPT Queue Runner
- Download Aja
- Edit Aja / P5 Edit Aja
- Update P5 Edit Aja
- Subtitle Profesional
- Window Splitter
- Hermes Agent / Hermes Agent Core
- IDM-like Downloader
- Chrome extension terkait downloader
- aplikasi/plugin Premiere yang pernah saya buat
- project lain yang ditemukan di akun GitHub saya.

Jika ditemukan repo lain, MASUKKAN JUGA.

Buat tabel/inventaris:

NAMA PROYEK\
REPO\
DEFAULT BRANCH\
COMMIT TERBARU\
BRANCH\
TAG\
STATUS SOURCE\
STATUS BUILD\
STATUS DOKUMENTASI\
STATUS BACKUP\
CATATAN

Di dalam MASTER ZIP buat struktur seperti:

MASTER-BACKUP-SEMUA-APP/\
│\
├── 00_README_PERTAMA.txt\
├── 00_MASTER_MANIFEST.txt\
├── 00_MASTER_MANIFEST.csv\
├── 00_SHA256SUMS.txt\
├── 00_BACKUP_INFO.txt\
├── RESTORE_ALL.ps1\
├── VERIFY_ALL_BACKUP.ps1\
│\
├── APP_001_NAMA_APP/\
├── APP_002_NAMA_APP/\
├── APP_003_NAMA_APP/\
└── ...

UNTUK SETIAP APLIKASI, usahakan struktur:

APP_xxx_NAMA/\
│\
├── README_RESTORE.txt\
├── STATUS_BACKUP.txt\
├── REPOSITORY_INFO.txt\
├── MAIN_COMMIT.txt\
├── BRANCHES.txt\
├── TAGS.txt\
├── COMMIT_HISTORY.txt\
├── REQUIRED_SECRETS.txt\
├── SHA256SUMS.txt\
│\
├── GIT/\
│   └── NAMA-APP-COMPLETE-GIT-HISTORY.bundle\
│\
├── SOURCE/\
│   └── NAMA-APP-SOURCE-MAIN.zip\
│\
├── BUILD/\
│   └── build portable/stabil terakhir jika tersedia\
│\
├── DOCS/\
│   └── dokumentasi penting\
│\
└── RECOVERY/\
├── RESTORE_TO_NEW_GITHUB.ps1\
├── VERIFY_BACKUP.ps1\
└── PETUNJUK_PEMULIHAN.txt

Untuk repo Git yang masih dapat diakses, buat Git Bundle sebisa mungkin menggunakan konsep:

git bundle create ... --all

Tujuannya agar riwayat Git tidak hilang.

Bundle harus diverifikasi.

Lakukan pengecekan setara dengan:

git bundle verify

Pastikan bundle bukan file kosong/rusak.

Catat ref yang terdapat di dalam bundle.

SOURCE-MAIN.zip dan Git Bundle adalah DUA HAL BERBEDA.

Saya ingin keduanya.

SOURCE-MAIN.zip:\
mudah dibuka manusia.

GIT BUNDLE:\
untuk pemulihan riwayat Git.

Jika sebuah proyek memiliki hasil build portable/stabil yang sudah pernah berhasil dan masih tersedia, backup hasil build tersebut.

Contoh:

NamaApp-Windows-Portable.zip

Tetapi jangan membangun ulang seluruh aplikasi tanpa alasan apabila build terpercaya sudah tersedia.

Jika build tidak tersedia, tulis:

BUILD_NOT_AVAILABLE

Jangan berpura-pura build tersedia.

Jangan memenuhi backup dengan:

venv\
**pycache**\
node_modules\
cache build sementara\
file temp

kecuali memang merupakan komponen runtime distribusi aplikasi yang wajib.

WAJIB simpan file yang menentukan dependency, misalnya:

requirements.txt\
pyproject.toml\
package.json\
package-lock.json\
Cargo.toml\
lock file\
spec PyInstaller\
workflow build\
script build\
dan file konfigurasi terkait.

Tujuannya:

backup tidak membengkak tanpa alasan,\
tetapi aplikasi tetap bisa dibangun kembali.

Setiap aplikasi harus mempunyai PETUNJUK_PEMULIHAN yang ditulis untuk orang awam.

Tuliskan langkah dari kondisi:

"GitHub lama sudah tidak bisa diakses."

Sampai kondisi:

"Repo baru sudah aktif kembali."

Contoh alur:

1. Ekstrak MASTER BACKUP.
2. Masuk folder aplikasi.
3. Verifikasi checksum.
4. Verifikasi Git Bundle.
5. Buat repo kosong pada akun GitHub baru.
6. Restore source/history dari Git Bundle.
7. Atur remote baru.
8. Push branch/tag.
9. Pasang kembali secret yang diperlukan.
10. Jalankan workflow build.
11. Cocokkan commit/checksum.

Sediakan script PowerShell Windows jika memungkinkan.

Saya menggunakan Windows 11.

Buat juga:

RESTORE_ALL.ps1

Script ini tidak boleh sembarangan langsung mengirim semuanya ke GitHub tanpa kontrol.

Script harus membantu saya memilih aplikasi yang akan direstore.

Idealnya:

[1] MiniCut\
[2] Full Album Video Maker\
[3] AI Music Downloader\
...

Pilih nomor aplikasi.

Lalu script memberikan/proses langkah restore untuk aplikasi tersebut.

00_MASTER_MANIFEST.txt harus menjadi peta seluruh backup.

Untuk setiap aplikasi tulis:

APP NAME\
ORIGINAL REPO\
BACKUP DATE\
MAIN COMMIT\
GIT BUNDLE\
SOURCE SNAPSHOT\
BUILD\
DOCS\
RECOVERY SCRIPT\
BACKUP STATUS\
CHECKSUM STATUS

Gunakan status seperti:

BACKUP_COMPLETE\
BACKUP_PARTIAL\
SOURCE_ONLY\
BUILD_NOT_AVAILABLE\
REPO_NOT_ACCESSIBLE\
NEEDS_MANUAL_INPUT

Jangan menyembunyikan kekurangan.

Semua file penting harus mempunyai SHA-256.

Buat:

00_SHA256SUMS.txt

dan checksum per aplikasi.

Buat:

VERIFY_ALL_BACKUP.ps1

yang bisa saya jalankan di Windows untuk memastikan file belum rusak.

JANGAN langsung bilang backup selesai.

Sebelum selesai:

1. Tes ZIP final bisa dibuka.
2. Tes struktur folder.
3. Tes checksum.
4. Tes Git Bundle.
5. Pastikan source snapshot tidak kosong.
6. Pastikan MAIN_COMMIT tercatat.
7. Pastikan branch/ref tercatat.
8. Pastikan script recovery tersedia.
9. Pastikan tidak ada API key/token/password ikut tersimpan.
10. Cocokkan jumlah proyek di manifest dengan jumlah folder aplikasi.

Jika sebuah Git Bundle gagal diverifikasi, backup proyek tersebut BELUM BOLEH diberi status BACKUP_COMPLETE.

Ikuti aturan ini dengan ketat:

Jika suatu proyek disebut sebagai WAJIB dibackup tetapi repo/source/ZIP yang dibutuhkan tidak tersedia atau tidak dapat diakses:

JANGAN mengarang source.\
JANGAN membuat source pengganti.\
JANGAN menyebut backup proyek itu selesai.

Laporkan secara jelas:

INPUT_MISSING:\
[nama proyek/file/repo]

Jika input itu wajib untuk keseluruhan tugas, hentikan proses sesuai aturan input wajib.

Saya hanya ingin SATU paket utama:

MASTER-BACKUP-SEMUA-APP-[TANGGAL].zip

Jangan memberikan puluhan file utama secara terpisah.

Di dalamnya boleh terdapat banyak folder dan ZIP per aplikasi.

Setelah selesai, laporkan secara ringkas:

TOTAL PROYEK:\
BACKUP COMPLETE:\
BACKUP PARTIAL:\
TIDAK DAPAT DIAKSES:\
UKURAN MASTER ZIP:\
SHA-256 MASTER ZIP:\
COMMIT TERBARU PENTING:\
VALIDASI:\
STATUS AKHIR:

Dan berikan saya file MASTER ZIP untuk saya simpan sendiri.

PENTING:\
Tujuan utama backup ini adalah agar kejadian akun GitHub suspend tidak membuat pekerjaan saya hilang lagi.

Saya ingin apabila suatu saat saya membuka ChatGPT baru, mengunggah MASTER ZIP ini, lalu berkata:

"PULIHKAN PROYEK [NAMA APP] KE GITHUB BARU"

AI dapat memahami struktur backup dan melakukan recovery tanpa perlu menebak-nebak.

KERJAKAN SAMPAI MASTER BACKUP BENAR-BENAR TERBUAT DAN TERVERIFIKASI.
