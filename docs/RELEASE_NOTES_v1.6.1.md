# Full Album Maker v1.6.1 — Windows 11 Portable

Tanggal: 9 Oktober 2026

## Apa yang berubah sejak v1.6.0

Rilis pemeliharaan dan keandalan ekspor album, bukan perombakan UI.

- Meningkatkan keamanan antrean render: job yang menunggu tidak hilang ketika riwayat melampaui 200 entri; perubahan antrean hanya menjadi aktif setelah data berhasil tersimpan.
- Menuntaskan alur **Retry Render** dan status BLOCKED saat FFmpeg atau media tidak siap, sehingga job gagal tidak dicoba ulang otomatis tanpa henti.
- Menangani pembatalan FFmpeg ketika proses belum mengirim progres, setelah stdout ditutup, dan selama verifikasi final (FFprobe); render yang dibatalkan tidak diterbitkan sebagai MP4.
- Melindungi file MP4 tujuan dari penimpaan yang tidak diizinkan ketika file muncul sesudah preflight.
- Memperbaiki penempatan lagu pada **Free Timeline** menggunakan penundaan audio yang sesuai pada filter FFmpeg, agar lagu tidak terdengar sebelum timestamp masing-masing.
- Memperketat pemeriksaan media: cover fallback yang aktif wajib tersedia; media track nonaktif tidak ikut memblokir ekspor; direktori yang kebetulan bernama `album.mp4` ditolak meskipun opsi overwrite aktif.
- Memperbaiki pembersihan file staging per attempt dan penanganan nama album dengan karakter `[ ]`.

## Pengujian Windows yang digunakan

- Seluruh pytest dan pengujian render FFmpeg nyata.
- Album **100 sumber audio WAV yang berbeda**, dipercepat menjadi 30 detik, berhasil diekspor ke MP4 H.264/AAC; urutan audio diverifikasi pada sejumlah posisi.
- Album **100 sumber WAV**, total **10 menit** audio dan video, berhasil diekspor ke MP4 nyata; penyimpanan/pembukaan ulang proyek serta urutan audio pada titik awal, tengah, akhir diverifikasi.
- Render kedua menggunakan sumber panjang yang sama dibatalkan secara nyata, lalu dicek bahwa tidak ada MP4 final/parsial yang diterbitkan.
- Pembuatan EXE Windows, ZIP portable, SHA-256, serta uji menjalankan paket hasil ekstraksi secara terisolasi tanpa instalasi Python/FFmpeg global atau API key.

## Cara menjalankan

1. Unduh `Full-Album-Maker-v1.6.1-Windows-Portable.zip` dari GitHub Releases.
2. Verifikasi checksum ZIP terhadap `SHA256SUMS.txt` pada rilis yang sama.
3. Ekstrak seluruh ZIP ke folder biasa di Windows 11 64-bit, bukan menjalankan EXE di dalam aplikasi pembuka ZIP.
4. Jalankan `Full Album Maker.exe` dari hasil ekstraksi. Paket ini telah memuat runtime Python dan FFmpeg sendiri.
5. Impor file media yang valid, atur album/timeline, periksa preflight dan lokasi output, kemudian render MP4.

## Batas pembuktian

- Pengujian otomatis di atas **belum membuktikan** ekspor nyata dua jam penuh, alur impor 100 MP3 produksi, semua codec yang mungkin, maupun interaksi UI pengguna pada setiap konfigurasi komputer.
- Tes yang lulus menunjukkan ketahanan pada kasus yang telah diuji, bukan jaminan bebas semua bug.
- Rilis ini cocok untuk dicoba pengguna di Windows 11. Laporkan masalah yang hanya tampak pada komputer tertentu beserta langkah reproduksi.

## Release gate

Publikasi v1.6.1 harus terjadi **hanya setelah** CI Windows pada commit `main` hasil merge lulus seluruh pytest, render FFmpeg, build PyInstaller, pemeriksaan checksum, smoke EXE dan smoke ZIP hasil ekstraksi. Workflow membuat GitHub Release dari commit `main` jika tag rilis belum ada.
