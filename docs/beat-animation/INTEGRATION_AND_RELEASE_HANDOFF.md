# Full-Album-Maker — Beat/Spectrum Engine V2
## Integration & Release Handoff

**Date:** 7 October 2026 (WIB)  
**Repository:** `inoriko920-dev/Full-Album-Maker`  
**Engine development branch:** `feature/beat-animation-engine-v2`  
**Document role:** Integration/release handoff after STEP00–15. This is **not STEP16**.

## 1. Executive Status

The Audio Reactive / Beat / Spectrum Engine V2 development roadmap is complete through STEP15. The engine is not being redesigned or restarted. The remaining work is controlled integration with the current `main`, regression verification, Windows portable validation, and final release publication.

### Completed
- MASTER PLAN is frozen.
- STEP00–STEP15 planning/implementation path is complete.
- STEP15 Release Candidate RC1 returned **GO**.
- RC1 source: `ccbd8f3a9d2b5b98942e0bfd939c464c7cb4db5a`.
- RC1 full regression evidence: **955 tests passed**.
- RC1 Windows portable artifact passed runtime/export smoke.
- Final development documentation head before integration handoff: `681525f0b748dd9afc5ed2fdcddcf9e6a817f3f4`.

### Current production-main state
- Current `main`: `0e8e8a107415cd00e5dd458a166356854013f080`.
- This commit contains post-release UI-03 Album remediation that did not exist at the original Beat Engine V2 baseline.
- Beat Engine branch and `main` currently diverge from common baseline `584c94774e6197ecf60ecedb3bffd5a8797e7737`.
- Integration must preserve both the Beat Engine V2 implementation and UI-03 remediation.

## 2. Scope Boundary

This handoff does **not** authorize a new feature roadmap. Do not create STEP16 merely to continue the same Beat Engine project.

Integration scope is limited to:
1. Synchronize `feature/beat-animation-engine-v2` with current `main`.
2. Resolve only genuine conflicts introduced by divergence.
3. Preserve all Beat Engine STEP04–15 runtime behavior.
4. Preserve current-main UI remediation and existing non-Beat behavior.
5. Re-run regression and Windows portable release-candidate gates on the synchronized source.
6. Open a controlled PR to `main` only after the synchronized branch is green.
7. Merge and publish stable v1.6.0 only after the final gates pass.

## 3. Source of Truth Reading Order for Another AI/Session

Before changing integration code, read in this order:
1. `docs/beat-animation/SOURCE_OF_TRUTH.md`
2. `docs/beat-animation/MASTER_PLAN_BEAT_ANIMATION_ENGINE_FULL_ALBUM_MAKER_V1.docx`
3. STEP00 through STEP15 DOCX files in numeric order.
4. `docs/beat-animation/STEP15_FINAL_RELEASE_CANDIDATE_GO_REPORT_FULL_ALBUM_MAKER_2026-10-07.md`
5. This `INTEGRATION_AND_RELEASE_HANDOFF` document.
6. Current main post-release UI documentation, especially `docs/ui-album/POST_RELEASE_REMEDIATION_UI03.md`.
7. Relevant workflow definitions before changing CI/release logic.

Do not infer the project from filenames alone and do not repeat completed planning.

## 4. Important Architecture Decisions That Must Not Be Broken

- The stable Full-Album-Maker application remains the host application; Beat Engine V2 is an additive engine/integration, not a rewrite.
- FFmpeg remains the final renderer.
- Beat/audio analysis uses one shared analysis/event/signal pipeline; individual effects must not implement separate beat detectors.
- Spectrum must remain genuinely audio-reactive; decorative/random playhead motion must not be presented as audio reactivity.
- Audio analysis is source-relative and cached per source asset/profile.
- `MusicEventTimeline` is the shared derived-event layer.
- `AnimationSignalEngine` is the shared envelope/smoothing layer.
- Visual consumers read shared signal/binding state rather than duplicating beat math.
- Preview and final rendering must preserve parity contracts.
- Existing projects without Beat V2 assignments must remain backward compatible.
- AI Agent Beat controls must continue through the approved action/permission boundary, not arbitrary JSON/filesystem/FFmpeg access.
- Determinism, fail-closed quality/confidence behavior, and Undo/Redo safety remain mandatory.

## 5. Current Main Changes That Must Be Reconciled

The post-baseline `main` change touches these paths:
- `.github/workflows/step04-album-validation.yml`
- `docs/ui-album/POST_RELEASE_REMEDIATION_UI03.md`
- `src/full_album_maker/album_capture.py`
- `src/full_album_maker/album_remediation.py`
- `src/full_album_maker/main.py`
- `tests/test_ui03_album_remediation.py`

The integration resolution for `src/full_album_maker/main.py` must contain **both**:
- Beat V2 release smoke command paths (`--beat-runtime-smoke`, `--beat-export-smoke`), and
- `install_ui03_album_remediation()` installed after the existing STEP11 integration-completion layer.

No Beat V2 module should replace/remove Album UI remediation, and Album UI remediation must not remove Beat release smoke entry points.

## 6. Integration Branch Policy

The existing `feature/beat-animation-engine-v2` branch remains the canonical engine branch. Synchronization should be represented as an explicit merge/reconciliation commit with current `main` as a parent, rather than silently rewriting historical STEP commits.

Do not force-push/rebase away the audited STEP00–15 history unless a serious repository integrity issue requires it.

## 7. Release Candidate Policy After Synchronization

The old RC1 is valid evidence for the pre-sync engine, but it is not sufficient evidence for the combined source after UI-03 synchronization.

Create/validate a new integration candidate (**RC2**) from the synchronized source:
- app version remains `1.6.0`;
- expected main baseline for the integration run is `0e8e8a107415cd00e5dd458a166356854013f080`;
- run full repository regression;
- run Beat V2 runtime/export smoke;
- run real FFmpeg coverage already required by Beat STEP gates;
- build the Windows portable package from clean pinned dependencies;
- verify bundled FFmpeg/fonts/assets/notices;
- verify extracted portable ZIP in path containing spaces/Unicode/apostrophe;
- verify no dependency on global Python, global FFmpeg, or API key for local smoke paths.

## 8. Required Regression Coverage

At minimum the synchronized branch must prove:
- Beat STEP04 audio analysis tests PASS.
- STEP05 music-event derivation PASS.
- STEP06 signal/envelope engine PASS.
- STEP07 visual binding PASS.
- STEP08 preview/final-render integration PASS.
- STEP09 editor controls/spectrum expansion PASS.
- STEP10 preset/music-style/Vinyl BPM sync PASS.
- STEP11 AI Beat actions/NLU/provider PASS.
- STEP12 advanced motion/event phase/spark PASS.
- STEP13 combo/performance hardening PASS.
- STEP14 reliability/cache/cancellation/long-project/dependency gates PASS.
- STEP15 frozen runtime/export and Windows portable RC gate PASS.
- Existing non-Beat repository regression PASS.
- UI-03 Album remediation regression PASS.

A green historical RC1 alone is not enough after synchronization.

## 9. Merge Gate to `main`

A PR to main may be merged only when:
- synchronized branch CI is green;
- Windows portable integration candidate is green;
- PR-level `Build Windows Portable` is green;
- no unresolved conflict remains with UI-03 remediation;
- version identity is consistently `1.6.0`;
- release notes and third-party notices are present;
- no secrets or local machine paths were introduced.

Preferred merge method: a controlled merge that preserves the audited Beat Engine history. Do not squash hundreds of audited STEP commits into an opaque single commit unless explicitly requested.

## 10. Post-Merge Release Gate

After merge to main:
1. Wait for the stable `Build Windows Portable` workflow on the merged main commit.
2. Confirm full regression/build/smoke success.
3. Confirm the produced stable Windows portable artifact corresponds to the merged commit.
4. Only then create/publish the stable v1.6.0 release if the release workflow/process is authorized.
5. Record final merge SHA, workflow run ID, artifact ID/digest, release tag, and publication status in a final release note/handoff update.

## 11. Done / Not Done / Next Action

### Done
- Beat/Spectrum Engine V2 planning and implementation STEP00–15.
- RC1 technical gate: GO.
- Corrected Beat/Spectrum-only DOCX archive prepared separately from old Full-Album-Maker general planning.

### Not done yet at creation of this handoff
- Synchronization with current main UI-03 commit.
- RC2 verification on synchronized source.
- Integration PR to current main.
- Merge to main.
- Stable v1.6.0 publication.

### Immediate next action
Synchronize `feature/beat-animation-engine-v2` with current `main` while preserving UI-03 Album remediation and Beat V2 smoke/runtime entry points, then run the integration gates above.

## 12. Handoff Rule

Any AI/session continuing this work must first read the documents listed in Section 3 and verify current branch/main SHAs before changing code. If repository state differs from the SHAs recorded here, inspect the new commits before proceeding. Do not restart planning, do not invent STEP16, and do not remove previously accepted behavior merely to make a merge easier.
