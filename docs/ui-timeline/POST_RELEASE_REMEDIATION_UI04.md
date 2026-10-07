# UI-04 Timeline — Post-Release Remediation

**Status:** PASS candidate for merge  
**Date:** 7 October 2026  
**Stable baseline:** `v1.6.0` / `d0a6982b032738278d94d8b68343e1062cbc20fa`  
**Remediation branch:** `ui/ui04-timeline-remediation-v160`  
**Scope:** presentation/UI parity only for the Timeline workspace. Beat/Spectrum Engine V2 and Timeline model/command semantics remain authoritative and are not rebuilt.

## 1. Visual source of truth

The immutable UI-04 reference is the Timeline image embedded in:

`ASTRA_MASTER_PLAN_UI_FULL_ALBUM_MAKER_PIXEL_MATCH_9_REFERENSI.docx`

Reference contract:

- Workspace: UI-04 Timeline
- Viewport: **1672 × 941 px**
- Reference SHA-256: `d559b1d380f03bbb68ab832d3174b32e9d63d64fe7c1c4af98d11e5e7d3839c3`
- Product state: Free Timeline precision edit, multi-track dominant Timeline, active clip inspector, four markers, one intentional gap and one crossfade.

The reference controls visual hierarchy and geometry. Existing verified model/command behavior controls functional semantics.

## 2. Problems found on v1.6.0 baseline

The original STEP05 Timeline implementation remained functional, but the post-release visual audit identified several structural mismatches:

1. Timeline context panel was approximately 264 px at the golden viewport, substantially narrower than the reference.
2. The Foundation timeline host and STEP05 precision panel both exposed Timeline controls, creating a visually duplicated header/toolbar.
3. The precision canvas lane header was too narrow (145 px) and its ruler too shallow (25 px).
4. The old deterministic fixture represented a ~90 second edit state rather than the 4:28 reference state.
5. The preview remained a dark generic canvas instead of a reference-like sunset/city composition.
6. Inspector presentation contained an extra explicit Apply control not present in the reference.
7. Golden fixture selection/state did not match the visible “Senja di Kota Ini” first-song edit context.

## 3. Remediation architecture

A route-scoped presentation layer was added at:

`src/full_album_maker/timeline_remediation.py`

It is installed after UI-03 Album remediation in `src/full_album_maker/main.py`.

This ordering is intentional:

- UI-03 continues to own Album-specific shell geometry.
- UI-04 owns only the `timeline` route.
- Non-Timeline routes delegate to the previous presentation layer.
- No second timeline engine, document model, renderer, Beat analyzer, or command system is introduced.

## 4. Visual changes

### Golden viewport shell

For Timeline at 1672×941:

- Navigation: existing shared navigation remains unchanged.
- Context panel: **329 px**
- Right inspector: **348 px**
- Timeline host: **345 px**
- Status bar: **28 px**
- Timeline precision panel is mounted directly in the Timeline host instead of being nested below the old generic Timeline body.

For compact 1366×768:

- Context panel: **236 px**
- Right inspector: **286 px**
- Timeline host: **345 px**

### Timeline precision canvas

The presentation constants are now:

- lane-header width: **286 px**
- ruler height: **43 px**
- lane row height: **32 px**

This gives the multi-track area the same dominant visual hierarchy as the golden reference.

### Context / inspector

- Added project heading: **“Proyek: Senja di Kota Ini”** in the golden fixture.
- Track / Marker / Daftar Klip remain functional.
- Inspector keeps the verified Timeline selection/edit signals.
- The redundant visual Apply button is hidden; edits continue through existing signal/command boundaries.
- Inspector subtitle uses the source filename, e.g. **“Senja di Kota Ini.mp3”**.

### Timeline toolbar

The old generic Timeline host toolbar is hidden only on the Timeline route. The precision toolbar is the single visible toolbar.

Visible golden-oriented controls remain:

- Packed / Free
- Split
- Ripple
- Snap
- Marker
- zoom / playhead / Fit controls

The pre-existing Delete Gap operation remains in the functional implementation but is not shown in the UI-04 golden presentation because it is absent from the immutable reference.

## 5. Deterministic acceptance fixture

`src/full_album_maker/timeline_capture.py` now uses an independent deterministic fixture aligned with the reference state.

Acceptance state:

- project: **Senja di Kota Ini**
- playlist mode: **Free**
- songs: **3**
- total duration: **00:04:28.000**
- playhead: **00:01:24.000**
- selected inspector: **Lagu Utama**
- selected source: **Senja di Kota Ini.mp3**
- markers: **4** — Intro, Reff, Bridge, Outro
- gaps: **1**
- crossfades: **1**
- audio resolver errors: **0**
- changing to the Timeline route does **not** mutate document content.

The preview artwork is generated independently for test evidence. No golden-reference pixels are embedded or copied into production/test code.

## 6. Regression protection

New test:

`tests/test_ui04_timeline_remediation.py`

The production layer stack is tested in a subprocess so global monkey-patch installation cannot contaminate unrelated pytest collection.

The regression protects:

- UI-04 golden-route geometry;
- direct precision-panel ownership;
- single Timeline presentation surface;
- project heading and inspector state;
- non-mutating route changes;
- preservation of UI-03 Album shell ownership.

## 7. CI evidence

Final STEP05 validation run before this documentation commit:

- Run: `37641621302`
- Head: `cd157290e47d76720eed033b4f62722a089cc54e`
- Result: **SUCCESS**
- Focused STEP05 + UI-04 tests: PASS
- STEP04 regression gate: PASS
- Full recovered suite: **851 passed, 106 skipped**
- Deterministic golden/empty/1366 captures: PASS
- Geometry and fixture contract: PASS
- Immutable golden verification step: PASS / local golden may remain externally sourced
- Secret scan: PASS
- Evidence artifact: `step05-timeline-evidence`
- Artifact ID: `11491664107`
- Artifact digest: `sha256:93bfdf14f9a05a8a3d681561c5b2e6fd2ff97cb41c6c33c518072a6f1cc9eb3f`

## 8. Visual comparison

Baseline v1.6.0 vs immutable Timeline golden:

- mean absolute RGB error: **41.3168**
- normalized mean error: **0.16203**
- max-channel delta >25: **41.59%**
- max-channel delta >50: **34.82%**

UI-04 remediated capture vs immutable Timeline golden:

- mean absolute RGB error: **32.2954**
- normalized mean error: **0.12665**
- max-channel delta >25: **36.03%**
- max-channel delta >50: **25.39%**

The average image error and large-error region both improve materially. Pixel distance is not the sole acceptance criterion because the deterministic preview artwork is independently generated and font/image rasterization differs from the reference; shell geometry, information hierarchy, functional contract, route isolation, and regression evidence are mandatory alongside visual metrics.

## 9. Non-goals / frozen behavior

UI-04 does **not**:

- replace or modify Beat/Spectrum Engine V2;
- create a new audio analyzer;
- create a second Timeline model or renderer;
- change FFmpeg ownership;
- redesign other workspaces;
- bypass command/Undo/dirty-state architecture;
- embed the immutable golden screenshot into the application.

## 10. Gate decision

**UI-04 Timeline remediation: PASS candidate.**

Merge is allowed only after:

1. the documentation-head STEP05 validation is green;
2. PR-level `Build Windows Portable` is green;
3. UI-03 Album regression remains green;
4. the PR is mergeable against current `main`.

After merge, verify the post-merge Windows portable workflow before declaring UI-04 fully closed.

## 11. Next sequential surface

After UI-04 is merged and the post-merge Windows gate passes, the next post-release visual remediation surface is:

**UI-05 — Visual**

Do not start UI-05 as part of this UI-04 branch.
