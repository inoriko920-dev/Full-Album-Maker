# POST-RELEASE REMEDIATION — UI-01 BERANDA

Status: **PASS untuk remediation pass UI-01; bukan klaim pixel-perfect final untuk seluruh 9 workspace.**

## Scope

Tahap ini hanya memperbaiki **UI-01 Beranda / Project Hub** setelah canonical golden references berhasil dipulihkan dan diverifikasi. Workspace UI-02 sampai UI-09 tidak dikerjakan pada tahap ini.

Golden source:
- viewport: 1672 × 941
- reference: `01-beranda.png`
- SHA-256: `039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

## Baseline visual gap

Post-release audit sebelum remediation:
- mean absolute RGB difference: **25.17**
- pixel dengan delta salah satu channel > 25: **21.45%**

## Hasil remediation

Screenshot final dari GitHub Actions run **37422891352** dibandingkan dengan golden exact 1672 × 941:
- mean absolute RGB difference: **18.11**
- normalized mean absolute difference: **0.0710**
- pixel dengan delta salah satu channel > 25: **20.61%**

Dibanding baseline 25.17, mean absolute RGB turun sekitar **28%**. Gap terbesar yang tersisa tetap berasal dari perbedaan artwork contoh, rasterisasi/font/icon, dan native chrome. Runtime tidak memakai crop golden atau screenshot golden sebagai konten aplikasi.

## Perubahan utama

- Lebar navigation rail Beranda disesuaikan tanpa mengubah lebar rail workspace editor lain.
- Ritme vertikal tombol navigasi diselaraskan lebih dekat ke golden.
- Hero Beranda disetel ulang: margin, ukuran heading, button geometry, serta komposisi ilustrasi.
- Alpha warna ilustrasi diperbaiki agar warna biru transparan dirender benar, bukan berubah menjadi warna yang salah.
- Recent-project card menggunakan menu overlay, duration badge, fallback artwork deterministik non-fotografis, dan akan memprioritaskan thumbnail proyek nyata melalui `thumbnail_ref` bila tersedia.
- Autosave banner, header recent, serta Mulai Cepat dirapikan spacing-nya.
- Inspector Beranda diubah menjadi dua grup nyata: **Status Portable** dan **Pengaturan Cepat**.
- Status portable memakai indikator lingkaran + label yang sesuai reference.
- Excess chrome pada bagian atas inspector ketika expanded dihilangkan agar tab Properti/AI kembali ke posisi visual yang benar.
- Screenshot evidence sekarang merekam geometri Beranda tambahan untuk regression berikutnya.

## Functional safety

Perubahan ini tidak mengubah kontrak create/open/recovery/recent/default settings. AI tetap opsional dan tidak memblokir editing manual. Tidak ada golden screenshot yang dijadikan background UI.

## Verification

GitHub Actions run: **37422891352**
Head SHA: `cdadac60c0cf9ca71ad8a554b5b19517c880962a`

Hasil:
- STEP01 foundation regression: **PASS**
- STEP02 focused tests: **PASS**
- full recovered regression suite: **PASS**
- STEP02 geometry/edge-state gate: **PASS**
- secret scan: **PASS**
- screenshot/evidence artifact upload: **PASS**

## Residual gap

Empat recent-project cards pada golden memakai artwork fotografis spesifik. Fixture memakai fallback artwork deterministik agar ritme visual dapat diuji tanpa menyalin media golden. Jika project nyata memiliki thumbnail yang valid, card sekarang memprioritaskan media project tersebut melalui `thumbnail_ref`.

Tahap berikutnya setelah UI-01 ditutup adalah **UI-02 Media**, tetap sequential.
