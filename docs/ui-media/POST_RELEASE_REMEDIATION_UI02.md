# POST-RELEASE REMEDIATION — UI-02 MEDIA

Status: **PASS untuk remediation UI-02; bukan klaim pixel-perfect final untuk seluruh 9 workspace.**

## Scope

Tahap ini hanya memperbaiki **UI-02 Media / Media Library** setelah UI-01 Beranda selesai dan merged. Workspace UI-03 sampai UI-09 tidak dikerjakan pada tahap ini.

Canonical golden:
- viewport: 1672 × 941
- reference: `02-media.png`
- SHA-256: `117572570f900d7f25e2fd0dc822bd59c4496dcc6f23bfb9af8cb8b9d10aa3a5`

Kontrak fungsi import, async probe/thumbnail, search/filter/sort, multi-select, collections, metadata, missing/relink, reveal, Add to Album, dan timeline preview tetap dipertahankan.

## Baseline visual gap

Fresh baseline pada branch sebelum remediation:
- mean absolute RGB difference: **38.77**
- pixel dengan delta salah satu channel > 25: **36.16%**

## Hasil remediation

Final screenshot candidate dari GitHub Actions run **37426127822**:
- mean absolute RGB difference: **26.95**
- normalized mean absolute difference: **0.1057**
- pixel dengan delta salah satu channel > 25: **32.27%**
- perbaikan mean absolute RGB terhadap baseline: sekitar **30.5%**

Residual terbesar terutama berasal dari fixture yang memakai artwork deterministik, sedangkan golden memakai media foto/video contoh yang spesifik, serta perbedaan native rasterization/icon. Runtime tetap memprioritaskan preview media nyata dari cache/source dan tidak menggunakan crop/screenshot golden sebagai konten aplikasi.

## Perubahan utama

- Navigation rail Media dikunci mendekati geometri golden tanpa mengubah Beranda.
- Context Media dipadatkan: Semua, Audio, Foto, Video, Favorit, Missing dan Folder Proyek.
- 5-column media grid dipertahankan pada golden viewport.
- Card dibuat lebih padat dengan selection overlay, overflow menu, thumbnail/waveform, duration/resolution/FPS badge, nama dan metadata.
- Urutan fixture visual dibuat deterministic agar mixed Audio/Foto/Video menyerupai ritme golden tanpa mengubah sorting runtime.
- Video badge dipadatkan menjadi 4K/1080p/720p agar tidak overlap pada card.
- Inspector Media diperbesar, lokasi ditampilkan sebagai folder, metadata fixture diselaraskan, dan fallback preview video dibuat lebih representatif; cached real preview tetap menang.
- Timeline Media mempertahankan tiga track Video/Audio/Teks, ruler 10-detik, durasi fixture 01:32, dan toolbar Media dipindah ke header route-specific agar tidak ada toolbar ganda.
- Geometry Media route tetap scoped: perubahan tidak menggeser shell Beranda atau workspace berikutnya.

## Functional safety

- Import file/folder tetap background/non-blocking.
- Missing media tetap terlihat dan Relink tetap tersedia.
- Selection Ctrl/Shift dan multi-select tetap menggunakan model lama.
- Collection metadata tetap sidecar dan tidak mengubah project schema.
- Preview cache tetap lazy dan hasil stale tetap ditolak.
- Add to Album tetap memakai handoff command; tidak melakukan mutasi Album di tahap Media.
- Golden PNG tidak dijadikan background UI atau media fixture.

## Verification

Evidence production UI:
- STEP03 completion/evidence run: **37426127822**
- STEP03 validation run: **37426127869**
- Windows portable build run: **37426134877**
- production UI head: `946b909db38066b4e00b867d26a5d34d88b1988e`
- STEP03 completion: **PASS**
- STEP03 focused + full recovered regression: **PASS**
- FFmpeg preview smoke: **PASS**
- Windows portable build/smoke: **PASS**
- final screenshot/evidence: **PASS**

Branch juga menambahkan regression lock untuk:
- Media navigation rail;
- compact context-row heights;
- 5-column layout;
- exact deterministic fixture order;
- context/right-dock/timeline/status geometry.

## Residual gap

Fixture screenshot tidak memalsukan foto/video golden. Karena itu pixel metric total masih dipengaruhi perbedaan konten thumbnail. Pada project nyata, preview cache memakai media pengguna yang sebenarnya. Perbedaan kosmetik kecil dapat dikoreksi pada integration regression setelah semua workspace diremediasi, tanpa membuka kembali kontrak fungsi UI-02.

Tahap sequential berikutnya setelah UI-02 merged adalah **UI-03 Album**.
