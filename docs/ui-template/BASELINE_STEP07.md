# STEP07 — Template Studio Baseline & Handoff

Status: **READY_WITH_LIMITATIONS**  
Branch: `ui/step-07-template`  
Baseline STEP06 head: `0a120c23c909e81c3e0f7342e89a1713393e8ffd`  
Verified implementation SHA before this documentation commit: `37df34326efd6a71d96bd2081263a3a12eb08745`  
Final validation run for implementation SHA: `37128774612`  
Evidence artifact: `step07-template-evidence` / artifact `11276356061`  
Artifact digest: `sha256:7e00ffb17fbd3a08aa780a1a9e2bfadb9973c92b52ebf5550190a833f4b108b2`

## 1. Scope yang benar-benar diselesaikan

STEP07 menambahkan Template Studio ke production Foundation shell tanpa membuat project model, timeline engine, Visual state, atau Undo/Redo path kedua. Template diperlakukan sebagai parameter semantik yang divalidasi, dapat dipreview secara non-destructive, lalu diterapkan melalui contract project/editor yang sudah ada.

S07-01 sampai S07-30 telah dikerjakan secara serial dan ditutup dengan evidence berikut:

- Handoff STEP06 dan baseline repo diverifikasi sebelum implementasi.
- Capability template recovered diaudit dan dipertahankan sebagai sumber behavior bila masih relevan.
- Built-in template registry tetap menggunakan recovered engine IDs; layer presentasi tidak mengganti ID internal hanya demi nama UI.
- Custom template memakai format/version tervalidasi, stable unique `custom:<uuid>` ID, atomic persistence, corruption isolation, dan portable payload sanitization.
- Favorite disimpan terpisah dari payload template dan survive reload.
- Search, origin Built-in/Custom/Favorit, category, ratio, dan sort bekerja pada metadata secara deterministic.
- Template card mendukung stable selection, heart/favorite, Preview, dan Gunakan tanpa heart memicu apply.
- Preview draft disposable dan non-destructive: tidak mengubah source project, tidak menaikkan revision, dan tidak membuat Undo entry.
- Inspector memetakan Title Layout, Cover Position, Background style, Spacing, Typography/fallback, dan Overlay opacity ke semantic draft/apply state.
- Scope Lagu Ini, Pilihan, dan Semua Lagu diprevalidasi dan diterapkan sebagai satu transaction per apply; selected scope memakai stable `song_id`, bukan visible-row index.
- Apply tidak mengubah playlist order.
- Undo mengembalikan exact prior content signature; Redo mengembalikan applied state.
- Applied template menjadi normal editable project state, bukan state UI sementara.
- Save/reopen `ProjectDocument` mempertahankan hasil apply.
- Buat Template/Duplikat menghasilkan Custom portable dengan unique ID dan tanpa machine absolute path, song ID, API key, atau output path reusable.
- Simpan Custom menggunakan temp + fsync + replace. Failure pada atomic replace tidak merusak file lama; retry normal terbukti berhasil.
- Reset hanya membuang draft/preview state dan tidak memutasi project.
- Thumbnail generation/cache berjalan async, punya cache key berbasis template/payload/ratio, stale/failure guard, placeholder fallback, dan tidak merender kartu offscreen saat window belum tampil.
- Missing resource dan missing font degrade dengan aman; template tidak menjatuhkan project/apply path.
- Template workspace terintegrasi dengan shared shell, shared project, shared STEP05 Timeline, dan STEP06 Visual contracts.
- Deterministic production capture tersedia pada 1672×941 dan 1366×768.
- Tidak ada implementasi Spectrum workspace, AI Agent workspace, atau Render workspace STEP08+ pada branch ini.

## 2. Template schema / storage contract

Custom template tetap memakai recovered/custom-template owner dan tidak memerlukan schema project baru.

- Format: `full-album-maker-custom-template`
- Version: `1`
- ID prefix: `custom:` + UUID
- File suffix: `.famtpl.json`
- Store default: app data `templates/custom` melalui existing `data_dir()` contract.
- Write contract: serialize validated payload → write temp file → flush + `fsync` → atomic `os.replace` → best-effort temp cleanup.
- Corruption contract: satu file custom rusak dilaporkan sebagai error item dan tidak memblok template custom lain.
- Import collision: tidak overwrite template lokal diam-diam; import menjadi copy dengan ID baru.
- Built-in templates tetap immutable dari perspektif Template Studio; edit/duplicate menghasilkan Custom.

Portable layer types yang diizinkan saat baseline ini: `background`, `text`, `spectrum`, `song_title`, `song_cover`, `vinyl`, `playlist_visual`, `progress`, dan `song_time`. Keberadaan `spectrum` sebagai portable layer type bukan izin untuk mengimplementasikan STEP08 Spectrum workspace di STEP07.

## 3. Preview dan apply contract

### Preview

Preview dibuat dari salinan/disposable project state. Production capture membuktikan membuka route Template dan menekan Preview mempertahankan content signature source project. Focused test juga membuktikan controller source tetap `can_undo == False` sesudah preview.

Preview tidak boleh:

- mark project dirty,
- membuat autosave side effect,
- menaikkan revision source,
- menambah Undo history,
- mengganti selection dengan row index,
- menyimpan machine-specific path ke reusable template.

### Apply

Apply melewati existing editor/controller command path. Scope di-resolve sebelum mutation:

- **Lagu Ini** → current stable `song_id`.
- **Pilihan** → stable selected IDs dalam playlist order.
- **Semua Lagu** → seluruh eligible songs tanpa reorder.

Satu apply menjadi satu Undo transaction. Focused acceptance test membuktikan current/selected/all scope, Undo, Redo, exact prior-state restoration, save/reopen persistence, serta kemampuan mengedit state secara normal sesudah apply.

## 4. Custom / favorite / restart evidence

Focused STEP07 tests membuktikan:

- Custom duplicate mendapat unique ID.
- Built-in asset-backed template yang diduplikasi menjadi portable Custom tidak membawa machine-specific asset path.
- Custom store round-trip berhasil dari store instance baru.
- Favorite round-trip berhasil dari store instance baru.
- Corrupt custom file diisolasi dari template valid.
- Original project resource boleh hilang setelah portable Custom dibuat; Custom yang tersimpan tetap dapat dimuat dan dipakai sesuai sanitized payload.
- Atomic-save failure mempertahankan file lama dan membersihkan temporary file; retry selanjutnya berhasil.

## 5. Thumbnail/cache contract

STEP07 menambahkan cache thumbnail async khusus Template Studio tanpa mengubah project state.

Contract yang telah diuji:

- request non-blocking terhadap UI,
- cache key membedakan template/payload hash-version/ratio,
- repeated identical failure tidak memicu render loop tanpa batas,
- renderer yang menyelesaikan sangat cepat tidak deadlock,
- custom payload change menghasilkan key baru/regenerate,
- stale result tidak mengganti kartu yang sudah pindah state,
- failure menampilkan fallback; template tetap usable,
- hidden/not-yet-shown workspace tidak memulai FFmpeg thumbnail work yang tidak diperlukan.

Deterministic golden capture sengaja memakai `FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER=1`, sehingga screenshot menggunakan painted/local fallback yang stabil. Runtime async behavior dibuktikan oleh focused thumbnail tests terpisah.

## 6. Final automated validation evidence

GitHub Actions run `37128774612` menguji implementation SHA `37df34326efd6a71d96bd2081263a3a12eb08745` dan selesai **success**.

Hasil final:

- Source compile: **PASS**.
- STEP07 focused Template + acceptance tests: **24 passed**.
- Recovered template regression collection: **23 skipped** pada Linux gate ini; tidak diklaim sebagai PASS.
- STEP06 Visual regression gate: **14 passed**.
- Full recovered regression suite: **352 passed, 88 skipped** dalam 40.10 detik.
- Deterministic STEP07 capture 1672×941: **PASS**.
- Responsive capture 1366×768: **PASS**.
- Template geometry/fixture contract: **PASS**.
- Secret scan: **PASS**.
- Evidence artifact upload: **PASS**.

Evidence artifact final:

- Name: `step07-template-evidence`
- Artifact ID: `11276356061`
- Size: `304927` bytes
- Digest: `sha256:7e00ffb17fbd3a08aa780a1a9e2bfadb9973c92b52ebf5550190a833f4b108b2`

## 7. Deterministic golden fixture dan geometry

Production capture memakai real `FoundationMainWindow` setelah production STEP01..07 installers aktif, bukan mock standalone.

Golden fixture:

- Workspace: `template`
- Viewport: `1672 × 941`
- Scale: `1.0`
- QA font: `Noto Sans`
- Origin filter: Built-in
- Category: Semua
- Ratio: `16:9`
- Sort: Terbaru
- Selected template: `Senja di Kota Ini` / recovered ID `spotify_clean`
- Template cards in registry: 10
- Timeline project songs: 4
- Selected songs held by shared Visual selection state: 2
- Title Layout: left / Judul di Kiri
- Cover Position: full / Penuh Layar
- Background: `photo_dark_overlay`
- Spacing: normal
- Overlay opacity: `0.60`
- Scope: current / Lagu Ini
- Built-in `Save Custom`: disabled
- Preview state: belum diterapkan ke source project
- Thumbnail in deterministic capture: fallback
- Project content unchanged by route + Preview: `true`

Measured geometry 1672×941:

| Item | Measured |
| --- | ---: |
| Context panel | 264 px |
| Right dock | 348 px |
| Timeline dock | 158 px |
| Status bar | 28 px |
| Cards | 10 |
| Songs | 4 |

Measured responsive geometry 1366×768:

| Item | Measured |
| --- | ---: |
| Context panel | 264 px |
| Right dock | 300 px |
| Timeline dock | 158 px |
| Status bar | 28 px |
| Cards | 10 |
| Songs | 4 |

Kedua capture membuktikan Template workspace aktif, context/inspector/timeline visible, dan Preview tidak mengubah source project content signature.

## 8. Golden UI-06 status

Canonical UI-06 contract:

- UI ID: `UI-06`
- Expected file: `docs/ui-reference/06-template.png`
- Expected SHA-256: `cd2dcd55dcfcf16b947737e459129178a71f76b52b625e398c0fc2f1e87f5895`
- Golden viewport: `1672 × 941`

Repository status: **LOCAL_PENDING**.

Exact immutable `06-template.png` tidak ada di branch ini. Karena itu STEP07 **tidak** mengklaim exact pixel parity, 50% overlay PASS, absolute diff PASS, atau landmark tolerance <=2 px terhadap binary kanonik.

CI sudah menyiapkan mekanisme yang benar: bila binary UI-06 dengan hash yang tepat tersedia, gate akan memverifikasi SHA-256 lalu membuat `template-overlay-50.png` dan `template-diff.png`. Sampai binary itu benar-benar tersedia, status exact golden harus tetap `LOCAL_PENDING`.

Actual deterministic screenshots dan JSON geometry tetap tersedia di evidence artifact final.

## 9. Acceptance criteria AC07-01 sampai AC07-42

Functional acceptance dinilai **PASS** untuk AC07-01 sampai AC07-39 dan AC07-41 berdasarkan focused tests, full regression, production capture, persistence checks, atomic failure/retry, missing resource/font coverage, dan self-review diff.

AC07-40 hanya **PARTIAL / LOCAL_PENDING**: actual golden screenshot tersedia, tetapi overlay/diff terhadap immutable canonical UI-06 belum dapat dibuat karena binary reference tidak tersimpan di repo.

AC07-42 **PASS WITH LIMITATION**: evidence dan handoff lengkap, dengan limitation UI-06 dinyatakan eksplisit dan tidak disamarkan sebagai PASS.

## 10. Self-review diff terhadap STEP06

Dibanding baseline STEP06 `0a120c23c909e81c3e0f7342e89a1713393e8ffd`, implementation SHA `37df34326efd6a71d96bd2081263a3a12eb08745` adalah **26 commits ahead, 0 behind**.

Sebelum commit dokumentasi ini, diff implementation berisi 12 path:

- `.github/workflows/step07-template-validation.yml` — workflow focused/regression/capture/evidence.
- `src/full_album_maker/main.py` — perubahan lama yang sangat sempit untuk mengaktifkan production STEP07 installer.
- `src/full_album_maker/template_capture_step07.py` — deterministic production capture.
- `src/full_album_maker/template_feature_step07.py` — production Template feature integration.
- `src/full_album_maker/template_portability_step07.py` — portable/sanitized duplicate/create helpers.
- `src/full_album_maker/template_studio_step07.py` — descriptors, filters, draft, scope/apply semantics, favorite state.
- `src/full_album_maker/template_thumbnail_cache_step07.py` — async thumbnail/cache layer.
- `src/full_album_maker/template_workspace_step07.py` — Template workspace/context/gallery/inspector/timeline UI.
- `tests/test_step07_template_acceptance.py` — portability/resource/history/heart/atomic failure-retry acceptance.
- `tests/test_step07_template_model.py` — model/store/filter/preview/apply/persistence tests.
- `tests/test_step07_template_thumbnail_cache.py` — async/cache/failure tests.
- `tests/test_step07_template_ui.py` — UI/production-route tests.

Tidak ada file Spectrum workspace, AI Agent workspace, atau Render workspace yang diubah. Tidak ada second project model, second timeline engine, force-push, rescue evidence deletion, atau project schema migration backward-incompatible.

## 11. Known limitations — eksplisit

### L1 — Exact UI-06 pixel overlay masih LOCAL_PENDING

Ini limitation utama yang membuat gate menjadi `READY_WITH_LIMITATIONS`, bukan `READY_FOR_STEP_08` tanpa catatan. Production capture dan geometry deterministic sudah PASS, tetapi exact reference binary tidak tersedia untuk overlay/diff.

### L2 — Recovered S07/S08 template tests legacy tidak dieksekusi pada Linux gate ini

Dua recovered regression modules ter-collect sebagai **23 skipped**. Status ini dipertahankan sebagai skip dan tidak diubah menjadi PASS palsu. Functional STEP07 coverage untuk behavior yang dibutuhkan disediakan oleh 24 focused tests baru, sedangkan full recovered suite tetap bersih dengan 352 PASS / 88 skipped.

### L3 — Font exact golden dapat berbeda dari reference

Deterministic CI memakai pinned Noto Sans. Plan memang mengizinkan safe fallback bila exact Playfair Display-like font tidak tersedia, dengan syarat geometry tetap dijaga dan variance didokumentasikan. Exact typography pixel parity tetap bagian dari L1 sampai immutable UI-06 binary tersedia.

## 12. Handoff STEP07 → STEP08

Project / repo: `inoriko920-dev/Full-Album-Maker`  
Branch: `ui/step-07-template`  
STEP06 baseline: `0a120c23c909e81c3e0f7342e89a1713393e8ffd`  
Verified STEP07 implementation SHA: `37df34326efd6a71d96bd2081263a3a12eb08745`  
STEP07 status: **READY_WITH_LIMITATIONS**

Handoff contract:

- Template schema/version: Custom `full-album-maker-custom-template`, version `1`, `custom:<uuid>`.
- Built-in store: immutable presentation over recovered engine IDs.
- Custom store: atomic, versioned, corruption-isolated, portable-safe.
- Favorite persistence: separate persistent preference store; reload PASS.
- Search/filter/category/ratio/sort: PASS and metadata-driven.
- Preview draft: non-destructive; source revision/content/history unchanged.
- Inspector mappings: Title Layout, Cover Position, Background, Spacing, Typography fallback, Overlay opacity wired to semantic draft/apply state.
- Lagu Ini: atomic PASS.
- Pilihan: stable-ID atomic PASS.
- Semua Lagu: atomic PASS, no reorder.
- Create Template: sanitized portable Custom PASS.
- Duplicate: unique Custom ID PASS.
- Save Custom: round-trip PASS; atomic failure/retry PASS.
- Reset: draft-only PASS.
- Thumbnail/cache: async/cache/failure/stale/fast-render guards PASS.
- Project/Timeline/Visual integration: shared state/contracts preserved; STEP06 regression PASS.
- Undo/Redo/Persistence: PASS; save/reopen applied project state PASS.
- Golden actual screenshot: PASS and uploaded as artifact.
- Exact overlay/diff: **LOCAL_PENDING** until immutable UI-06 binary with expected hash is supplied.
- Secret scan: PASS.

STEP08 constraints:

1. Spectrum may become part of a template payload only through an explicit spectrum layer/action contract; do not bypass template persistence or apply through widget-state copying.
2. Preserve `ProjectDocument`, `EditorController`, shared STEP05 Timeline resolver/session, STEP06 Visual contracts, and STEP07 Template apply transaction model.
3. Preserve non-destructive template Preview and deterministic production capture behavior.
4. Do not reinterpret UI-06 golden status as PASS until the exact binary has been verified by hash and overlay/diff actually generated.
5. Do not change Custom template format/version casually; any incompatible schema change requires explicit migration/review.
6. Do not store song IDs, API keys, output paths, or machine absolute paths inside reusable Template payloads.
7. Do not start STEP08 from this handoff unless the user explicitly requests STEP08.

First safe task for STEP08, after explicit user authorization: re-read live branch/HEAD, verify this handoff and final CI state, then audit recovered Spectrum capability before implementing any Spectrum UI/model changes.

## 13. Final gate decision

**READY_WITH_LIMITATIONS**

Rationale: Template model/store, Built-in/Custom/Favorit behavior, metadata filtering, non-destructive Preview, semantic inspector mappings, three atomic apply scopes, Undo/Redo, Custom create/duplicate/save/restart, portable sanitization, missing-resource/font behavior, async thumbnail/cache, project save/reopen, shared Timeline/Visual integration, production routing, deterministic geometry, secret scan, and full recovered regression suite all have passing evidence on the verified STEP07 implementation SHA.

The remaining blocker to an unconditional visual-parity claim is evidence-only: the immutable canonical UI-06 PNG is absent, so exact overlay/diff remains `LOCAL_PENDING`. This does not block Spectrum work architecturally, but it must remain visible as a limitation.

**Do not start STEP08 unless the user explicitly requests it.**
