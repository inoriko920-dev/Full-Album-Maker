# STEP06 — Visual per Lagu Baseline & Handoff

Status: **READY_FOR_STEP07_WITH_LIMITATIONS**  
Branch: `ui/step-06-visual`  
Baseline STEP05 branch head: `171a8bac8cee127fca0e513ffc625b9ff8dc25a9`  
Verified implementation SHA before this documentation commit: `2846fff3e89b3c6e1dac518149a9e55ecfa8bbc2`  
Validation run: `37020269776`  
Evidence artifact: `step06-visual-evidence` / artifact `11231789733`  
Artifact digest: `sha256:19d2b79caada1856ecab783b1392b354196775904c4fb4c3d978153c18fe5047`

## 1. Scope actually implemented

STEP06 adds per-song Visual editing to the production Foundation shell while continuing to use the same `ProjectDocument`, `EditorController`, playlist identity, Timeline resolver and Undo/Redo history established by STEP04/STEP05. It does not create a second project model or a second timeline engine.

Implemented and verified:

- Per-song Visual source assignment using existing `SongInstance.visual_asset_id` and `SetSongVisual`.
- Explicit states: Foto, Video, Tanpa Visual and Missing.
- Source clear detaches the song assignment without deleting the media-library asset.
- Relink replaces the source location while preserving the existing `asset_id` and song assignment.
- Deterministic Auto Match uses available image/video assets without AI/random guessing and preserves explicit assignments by default.
- Fit / Fill.
- Non-destructive Crop X/Y/Width/Height.
- Position X/Y and Scale.
- Image Motion: None/Static, Ken Burns, Zoom In, Zoom Out, Pan Left and Pan Right.
- Pan & Zoom toggle.
- Video playback policy: Normal, Loop Video or Freeze End; Loop and Freeze are mutually exclusive and exposed only for Video assignments.
- Per-song transition: Cut, Fade, Slide, Slide Left and Slide Right with bounded duration.
- `Apply to Selected` copies Visual settings atomically to selected songs without copying/replacing their source assignments.
- Production Visual workspace routing with song list/context, large preview, Visual inspector and V1 Visual + A1 Audio alignment timeline.
- Stable selection by `song_id`; filtering does not silently rebind selection by row index.
- Preview/playhead and previous/next song navigation share the STEP05 editor session.
- Decoded Video preview frame reuses the existing asynchronous media preview cache and rejects stale decode results after selection changes.
- Visual timeline displays transition badges derived from the same persisted per-song settings used by the renderer contract.
- Visual settings persist in project state, are Undo/Redo aware and survive `ProjectDocument` round-trip.
- Entering the Visual workspace does not mutate project content.

## 2. Architecture / provenance decisions

The implementation is intentionally additive and preserves recovered contracts.

- Canonical source assignment remains `SongInstance.visual_asset_id`; STEP06 does not invent a competing assignment table.
- Per-song editable Visual metadata is stored under `extensions["song_visual_settings_v1"]`.
- Older recovered `song_visual` layer properties remain the fallback. STEP06 does not rewrite old projects merely because they are opened.
- All persistent mutations run through Editor commands / the existing `EditorController`, so dirty state, revision checks, history and Undo/Redo remain authoritative.
- `RelinkMediaAsset` preserves `asset_id`; it changes locator/name/fingerprint only after the replacement file is verified.
- Eligibility rules for Loop/Freeze are enforced in the STEP06 assignment/UI layer instead of making the legacy normalizer reject older data on load.
- `TimelineResolver` remains the timing source of truth for preview alignment and render-graph compilation.
- `v13_render_graph.py` remains an additive extension of the existing S11 compiler path. It consumes per-song crop/fit/position/scale/motion/video-policy/transition settings and retains the legacy fallback when the STEP06 song-visual path is not active.
- STEP06 does not redesign Template, Spectrum, AI Agent or Render workspaces.

## 3. Automated validation evidence

Run `37020269776` on implementation SHA `2846fff3e89b3c6e1dac518149a9e55ecfa8bbc2` completed the final clean STEP06 gate successfully.

Results:

- Compile source: **PASS**.
- STEP06 focused tests: **14 passed**.
  - 4 per-song settings / render-graph contract tests.
  - 5 assignment / missing / relink / deterministic-auto-match tests.
  - 2 asynchronous Video preview stale-result tests.
  - 3 Visual UI / production-route tests.
- Recovered v1.3 Visual regression: **1 passed, 6 skipped**.
- STEP05 Timeline regression gate: **16 passed**.
- Full recovered regression suite: **328 passed, 88 skipped** in 40.91 seconds.
- Deterministic Visual capture: **PASS**.
- Visual geometry / fixture contract: **PASS**.
- Secret scan: **PASS**.
- Evidence artifact upload: **PASS**.

### CI isolation correction made during STEP06

An intermediate full-suite run exposed a test-environment contamination problem: `tests/test_step06_visual_ui.py` imported `full_album_maker.main` at module-collection time. That production import intentionally installs application-wide compatibility layers, so it polluted unrelated recovered tests in the same pytest process and caused the old renderer regression test to fail/hang.

The product source was not altered to hide the failure. The production-route assertion was moved into a fresh Python subprocess. This still verifies the real production installers and real Visual route, while preventing app-wide monkey patches from leaking into the rest of the recovered regression suite. The final run then returned the full suite to a clean **328 passed / 88 skipped** result.

The final workflow also keeps a five-minute full-suite timeout as an anti-hang guard.

## 4. Deterministic Visual fixture and geometry

The evidence capture uses the real production `FoundationMainWindow`, not a standalone mock screenshot. Its six-song fixture contains:

- 2 Foto assignments.
- 2 Video assignments.
- 1 Tanpa Visual assignment.
- 1 Missing source assignment.
- Primary song: `Senja di Kota Ini`.
- Primary Visual: Foto `visual-foto-1.png`.
- Fit mode: Fill.
- Motion: Ken Burns.
- Transition: Fade, 1.2 seconds.
- A Video Loop example and a Video Freeze End example elsewhere in the fixture.
- One selected song and live `Apply to Selected (1)` inspector state.
- Route mutation guard proving the document content signature is unchanged merely by opening Visual.

Golden-size CI geometry:

| Item | Measured |
| --- | ---: |
| Full capture | 1672 × 941 |
| Context panel | 264 px |
| Right dock | 348 px |
| Timeline dock | 238 px |
| Status bar | 28 px |
| Song rows | 6 |
| Workspace | `visual` |
| Route preserved content | `true` |
| QA font | Noto Sans |

Responsive 1366 × 768 capture also passed. Its context panel remained 264 px, right dock measured 300 px, Timeline remained 238 px high, all six rows remained present, and project content again remained unchanged by route activation.

## 5. Golden reference status

Canonical UI-05 contract:

- UI ID: `UI-05`
- File expected by the gate: `docs/ui-reference/05-visual.png`
- Expected SHA-256: `8b661752b235de74843950945126ab80837dec01953b796fcdcd6ad2ac317ef8`
- Golden viewport: 1672 × 941

Repository status: **LOCAL_PENDING**.

The exact immutable UI-05 PNG is not present in this branch. Therefore STEP06 does **not** claim pixel-overlay PASS or exact pixel parity. The CI still produces a deterministic current screenshot and geometry report. If the immutable canonical PNG is later supplied with the exact expected hash, the existing gate will verify the hash and produce 50% overlay + absolute diff automatically.

## 6. Known limitations — explicit, not hidden

### L1 — Exact UI-05 pixel comparison is still LOCAL_PENDING

Geometry, routing, fixture state and deterministic production capture pass, but exact golden overlay/diff cannot be executed without the immutable `05-visual.png` binary. This is an evidence limitation, not converted into a fake PASS.

### L2 — Video preview is decoded-frame preview, not full embedded video playback

STEP06 can asynchronously decode and display a representative Video frame using the existing preview-cache infrastructure. Stale results are generation/asset guarded. It does not introduce a full timeline-synchronized embedded Video playback engine. The transport/playhead remains the STEP05 editor session.

### L3 — Real FFmpeg execution parity is not claimed by the Linux STEP06 gate

The STEP06 focused renderer test validates generated graph semantics for crop/fit/scale/motion/loop/freeze/transition. The Linux CI intentionally does not install Ubuntu system FFmpeg because doing so activates legacy real-FFmpeg tests designed around the project's pinned Windows build and previously produced environment-dependent false failures.

The recovered v1.3 real-FFmpeg cases therefore remain skipped in this Linux gate. A Windows/pinned-portable FFmpeg smoke for STEP06 should be recorded separately if exact runtime rendering evidence is required before final release. Do not reinterpret graph-contract PASS as a Windows FFmpeg execution PASS.

## 7. Self-review of diff

Compared with STEP05 branch head `171a8bac8cee127fca0e513ffc625b9ff8dc25a9`, implementation SHA `2846fff3e89b3c6e1dac518149a9e55ecfa8bbc2` is **28 commits ahead and 0 behind**.

The diff contains 15 changed paths. It is predominantly additive STEP06 source/test/workflow work. Existing production source changes are intentionally narrow:

- `src/full_album_maker/main.py` — activates the STEP06 production layers after STEP05.
- `src/full_album_maker/v13_render_graph.py` — extends the recovered renderer compiler for verified per-song Visual semantics while retaining legacy fallback behavior.
- `tests/test_editor_v2_v13_song_visuals.py` — small regression-test adjustment only.

New STEP06 modules contain assignment/relink, settings, workspace, production wiring, guarded preview decode, transition timeline completion and deterministic capture logic. No force-push, rescue deletion, unrelated schema rewrite, second editor model, Template redesign, Spectrum redesign, AI redesign or Render-workspace redesign was performed.

## 8. Handoff contract for STEP07

STEP07 may build on this branch only after the user explicitly requests it. The next step must treat the following STEP06 contracts as baseline, not implementation suggestions:

- Keep `SongInstance.visual_asset_id` as canonical per-song Visual assignment.
- Keep `song_visual_settings_v1` compatible and preserve legacy fallback behavior.
- Keep all Visual mutations command-based and Undo/Redo-safe.
- Keep selection identity based on `song_id`, not visible-row position.
- Do not copy source assignments when applying settings to multiple selected songs.
- Preserve Missing records and `asset_id` during relink.
- Preserve the shared STEP05 Timeline resolver/session/playhead; do not create a separate Visual timing engine.
- Preserve stale-result guards for asynchronous Video preview decode.
- Preserve production-route test isolation; importing app-wide installers during global pytest collection is prohibited.
- Keep UI-05 exact golden status as `LOCAL_PENDING` until the immutable reference binary is genuinely available.
- Carry forward STEP05 limitations that remain architecturally unresolved unless STEP07 explicitly owns them.

Before STEP07 implementation, live branch/HEAD must be re-read. Do not rely only on the SHA written in this document if the branch has moved.

## 9. Gate decision

**READY_FOR_STEP07_WITH_LIMITATIONS**

Rationale: required per-song Visual assignment/editing, bulk settings, missing/relink behavior, shared selection/timeline integration, persistence, Undo/Redo, guarded preview decode, renderer graph semantics, production routing and deterministic geometry all pass the final STEP06 CI gate and the full recovered regression suite.

The remaining limitations are explicit evidence/runtime boundaries: exact UI-05 pixel overlay is `LOCAL_PENDING`, decoded Video preview is not full embedded playback, and Linux CI does not claim execution parity with the project's pinned Windows FFmpeg build.

Do **not** start STEP07 from this document alone unless the user explicitly requests STEP07.
