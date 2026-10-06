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

Screenshot final dari GitHub Actions run **37421706368** dibandingkan dengan golden exact 1672 × 941:
- mean absolute RGB difference: **24.61**
- pixel dengan delta salah satu channel > 25: **21.26%**

Jika area foto thumbnail contoh pada empat recent-project card dikeluarkan dari pengukuran:
- baseline mean absolute RGB: **15.85**
- final mean absolute RGB: **15.43**
- baseline pixel delta >25: **15.20%**
- final pixel delta >25: **14.96%**

Metric total tetap dipengaruhi kuat oleh isi thumbnail golden yang bersifat contoh. Runtime tidak memalsukan/crop screenshot golden sebagai thumbnail proyek.

## Perubahan utama

- Lebar navigation rail Beranda disesuaikan tanpa mengubah lebar rail workspace editor lain.
- Ritme vertikal tombol navigasi diselaraskan lebih dekat ke golden.
- Hero Beranda disetel ulang: margin, ukuran heading, button geometry, serta komposisi ilustrasi.
- Alpha warna ilustrasi diperbaiki agar warna biru transparan dirender benar, bukan berubah menjadi warna yang salah.
- Recent-project card menggunakan menu overlay di area cover dan duration badge seperti golden.
- Autosave banner, header recent, serta Mulai Cepat dirapikan spacing-nya.
- Inspector Beranda diubah menjadi dua grup nyata: **Status Portable** dan **Pengaturan Cepat**.
- Status portable memakai indikator lingkaran + label yang sesuai reference.
- Excess chrome pada bagian atas inspector ketika expanded dihilangkan agar tab Properti/AI kembali ke posisi visual yang benar.
- Screenshot evidence sekarang merekam geometri Beranda tambahan untuk regression berikutnya.

## Functional safety

Perubahan ini tidak mengubah kontrak create/open/recovery/recent/default settings. AI tetap opsional dan tidak memblokir editing manual. Tidak ada golden screenshot yang dijadikan background UI.

## Verification

GitHub Actions run: **37421706368**
Head SHA: `bf96b1558ca54d1761daf5352c987362918939c5`

Hasil:
- STEP01 foundation regression: **15 passed**
- STEP02 focused tests: **25 passed**
- full recovered regression suite: **470 passed, 89 skipped**
- STEP02 geometry/edge-state gate: **PASS**
- secret scan: **PASS**
- screenshot/evidence artifact upload: **PASS**

## Residual gap

Empat recent-project cards pada golden memakai artwork fotografis spesifik. Fixture runtime menggunakan fallback netral karena tidak boleh mengarang media pengguna atau menggunakan crop golden sebagai konten aplikasi. Jika project nyata memiliki cover/thumbnail, card harus memakai media project tersebut melalui data runtime.

Tahap berikutnya setelah UI-01 ditutup adalah **UI-02 Media**, tetap sequential.
