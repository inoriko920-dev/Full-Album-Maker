# Full Album Maker

Editor album musik untuk **Windows 11 64-bit** dengan timeline, audio, tampilan visual dan spectrum, animasi berbasis musik, dan ekspor MP4 melalui FFmpeg. Source Python/PySide6 serta pengujian otomatis tersedia di repository ini.

## Unduh dan coba aplikasi

**Rilis stabil terbaru yang telah diverifikasi:** lihat [GitHub Releases](https://github.com/inoriko920-dev/Full-Album-Maker/releases). Pilih ZIP dengan nama `Full-Album-Maker-v*-Windows-Portable.zip` dan berkas `SHA256SUMS.txt` pada rilis yang sama.

1. Unduh dan **ekstrak seluruh ZIP** ke folder pilihan pada Windows 11 x64.
2. Jalankan `Full Album Maker.exe` di folder hasil ekstraksi (jangan jalankan langsung dari jendela ZIP).
3. Impor lagu, gambar atau video milik Anda, atur album dan timeline, lalu gunakan pemeriksaan preflight sebelum ekspor MP4.
4. Paket Windows portable memuat runtime dan FFmpeg sendiri; pengguna tidak perlu memasang Python, FFmpeg atau API key untuk alur editor/ekspor offline.
5. Periksa checksum ZIP yang diunduh dengan `Get-FileHash "NAMA_FILE.zip" -Algorithm SHA256` di PowerShell lalu bandingkan dengan `SHA256SUMS.txt`.

Perhatikan ruang kosong disk saat merender album besar. Jangan menghapus/memindahkan file sumber saat aplikasi menggunakannya.

## Status pengujian

- CI: [Windows Portable](https://github.com/inoriko920-dev/Full-Album-Maker/actions/workflows/build-windows-portable.yml).
- Ada pengujian ekspor MP4 nyata dengan 100 lagu WAV sintetis berdurasi gabungan 30 detik, dan stress test 100 lagu dengan durasi total 10 menit; urutan audio dalam hasil render diverifikasi.
- Pengujian dua jam kontinu dengan banyak MP3 asli, variasi driver/GPU, dan seluruh interaksi UI di PC pengguna **belum sepenuhnya tercakup**. Bila menemukan masalah, laporkan lewat [Issues](https://github.com/inoriko920-dev/Full-Album-Maker/issues) dengan versi aplikasi dan langkah reproduksi.

## Pengembangan

Kode aplikasi berada pada `src/full_album_maker/`, pengujian di `tests/`, dan workflow build Windows di `.github/workflows/build-windows-portable.yml`. File dependensi build terpin ada di `build/requirements-windows.lock`.

Untuk menjalankan kode sumber, gunakan lingkungan Python yang sesuai dengan workflow, lalu jalankan tes `python -m pytest -q`. Artefak portable resmi harus dibangun dan diuji melalui Windows CI.

## Catatan pemulihan

Repository awalnya digunakan untuk memulihkan aplikasi dari arsip portable lama, tetapi **sekarang sudah berisi kode sumber aplikasi, pengujian, dan workflow CI aktif**. Arsip cadangan pemulihan lama tetap tersedia di [Releases](https://github.com/inoriko920-dev/Full-Album-Maker/releases), terpisah dari paket rilis stabil.
