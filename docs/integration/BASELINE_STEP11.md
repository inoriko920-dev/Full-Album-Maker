# STEP 11 — Integrasi Semua Workspace & Project State

## Final gate

**Status: `READY_WITH_LIMITATIONS`**

STEP 11 is functionally complete and safe to hand off to STEP 12 QA/release. The remaining limitations are release-environment/evidence items and do **not** indicate duplicate authoritative project state, broken cross-workspace ownership, fragmented Undo/Redo, unsafe autosave, or AI/Render reading a different project representation.

## Repository evidence

- Repository: `inoriko920-dev/Full-Album-Maker`
- Branch: `integration/step-11-project-state`
- STEP 10 baseline/head used as integration base: `fdc352794f5fd67d50329f675e7b775e8ff56c9b`
- Validated STEP 11 implementation SHA: `7f9d6766bd2d03bc60d4b6da29ddefc2dc3388b9`
- Validation workflow: `STEP11 Integration validation`
- Final validated run: `37175437702`
- Final validated job: `111356969644`
- Recovery anchor intentionally left untouched: `integration/step-11-core-backup`

The documentation commit containing this file is intentionally **not** used as the implementation evidence SHA. The implementation evidence remains the parent SHA above, so the evidence record does not chase its own documentation commit.

## State ownership map

Persistent project truth has one authoritative owner: `EditorSession/EditorController(ProjectDocument)`.

- Project/document: `ProjectDocument`
- Media registry/source identity: `ProjectDocument.media` + source-integrity services
- Album/song order: `ProjectDocument.playlist`
- Timeline: playlist/layers/timeline extensions in the same `ProjectDocument`
- Visual assignments: `SongInstance` + media registry in the same document
- Applied template state: normal document layers/properties
- Spectrum: normal document layers/properties
- Legacy `Project` envelope: compatibility/persistence bridge only; not a second authoritative editor model
- Selection: transient `SelectionStore` stable IDs; not persisted project truth
- Undo/Redo: global `EditorController` history
- Active workspace: transient `FoundationUiState` / app preferences
- Preview/playhead: transient `EditorSession` + preview owner
- AI runtime/history: STEP 09 controller/runtime policy; project mutations still use normal action/command contracts
- Render jobs: STEP 10 queue/job store; queued render uses an immutable project snapshot

No workspace-local Media/Album/Timeline/Visual/Template/Spectrum state is allowed to become an alternate authoritative project model.

## Project revision and events

STEP 11 establishes typed project-domain integration without creating a second mutation layer.

- Committed mutations advance the authoritative project revision.
- View refresh and workspace navigation do not mutate the project or increment revision.
- `DomainEventHub` is typed, queued, and non-reentrant.
- Event delivery is notification/refresh plumbing only; it is not a mutation owner.
- Domain event categories cover project lifecycle, revision/dirty changes, selection, Media, Album, Timeline, Visual, Template, Spectrum, Undo stack, autosave, preview, AI, and Render jobs.
- Bulk/project changes are classified/coalesced from authoritative before/after document state instead of creating thousands of independent widget mutations.

## SelectionStore

`SelectionStore` carries transient stable IDs for songs, media, clips, layers, primary selection, playhead time, and optional time range.

- IDs are resolved against the current `ProjectDocument`.
- Invalid song/media/layer IDs are pruned after document mutations.
- Selection is not duplicated into persistent workspace-specific project state.
- Cross-workspace consumers therefore see one current selection context rather than manually synchronized copies.

## Workspace lifecycle

All nine workspaces remain views/editors over the same project state:

1. Beranda
2. Media
3. Album
4. Timeline
5. Visual
6. Template
7. Spectrum
8. AI Agent
9. Render Center

Workspace enter/re-enter refreshes from the current project revision. Navigation itself does not save, mutate, or deserialize a new project copy. Heavy/async surfaces use stale-generation/project-token guards so an old callback cannot overwrite a newer project/session.

## Project New / Open / Close

- Dirty guards are integrated for destructive project switches/close paths.
- Project switch/close invalidates stale async/runtime callbacks tied to the old project identity.
- Closing/switching does not silently mark dirty data saved.
- Recovery/autosave remains detached from canonical Save semantics.

## Save / Save As / schema

- Canonical Save persists the authoritative document through the existing compatibility envelope.
- Save success is the event that may clear canonical dirty state; failed save does not.
- Save As path identity changes only after successful persistence.
- STEP 05–10 fields remain part of the same `ProjectDocument` serializer/round-trip.
- Integration tests compare deterministic normalized project state, not transient caches/window/runtime fields.
- Unsupported future schema is not guessed or silently downgraded.

## Autosave / recovery

`DebouncedAutosaveCoordinator` captures an immutable committed revision/signature into an `AutosaveRequest`.

- Autosave never captures a half-transaction.
- Generation coalescing prevents stale worker completion from claiming a newer revision was saved.
- `IntegrationRecoveryStore` writes a separate atomic recovery envelope, not the canonical project file.
- Recovery validates project token, revision, normalized signature, and `ProjectDocument` payload before restore.
- Autosave success does not mark the canonical project clean.

## Global Undo / Redo

Global Undo/Redo remains the `EditorController` project history. Workspace commands and AI actions feed normal command/action contracts rather than independent per-workspace histories. STEP 11 E2E/integration tests cover cross-workspace editing and restoration through the same history owner.

## Topbar / preview / media identity

- Shared topbar commands delegate to authoritative owners; they do not write widget-local state.
- Preview/playhead uses the shared editor/session preview ownership established in previous steps.
- Async preview results are guarded against stale project/generation callbacks.
- Media identity/relink stays anchored to stable media IDs and source-integrity contracts; consumers in Visual/Timeline/Render resolve from current project state.

## Cross-workspace integration

The integration layer keeps these chains on the same project state:

- Media -> Album
- Album -> Timeline
- Timeline <-> Visual
- Template -> normal project layers/properties -> Preview/Timeline/Undo
- Spectrum -> normal project layers/properties -> Preview/Render
- AI Agent -> validated action plan -> normal project command/action contracts
- Render Center -> immutable snapshot of final integrated project revision

AI Preview does not silently mutate the live project. Render jobs do not follow later live edits after their immutable snapshot is queued.

## End-to-end scenario A–O

The STEP 11 focused suite includes the required integrated lifecycle from project/media work through Album, Timeline, Visual, Template, Spectrum, AI Preview/Execute, canonical Save, close/reopen normalized-state comparison, navigation across all nine workspaces, Render preflight/snapshot, and deterministic render verification smoke.

Final focused integration result on run `37175437702`:

- STEP 11 focused core/lifecycle/production/E2E: **17 passed**
- STEP 10 Render regression: **38 passed**
- STEP 09 AI focused/atomic regression: **74 passed, 1 skipped**
- Full recovered regression suite: **469 passed, 89 skipped**
- Compile: **PASS**

## Performance evidence

Measured on the final validated run using a deterministic 200-song / 10,800-second fixture:

- Packed resolver: **0.000924619 s**
- Free resolver: **0.001058221 s**
- Ceiling used by STEP 11 gate: **2.0 s**
- Recovered performance tests: **2 passed, 1 deselected**

These are measured CI values for this fixture/runner, not generalized production benchmarks.

## Nine-workspace visual evidence

All nine actual production workspace screenshots were captured at **1672×941** from deterministic fixtures and each required workspace-active flag passed.

- UI-01 Beranda actual: PASS
- UI-02 Media actual: PASS
- UI-03 Album actual: PASS
- UI-04 Timeline actual: PASS
- UI-05 Visual actual: PASS
- UI-06 Template actual: PASS
- UI-07 Spectrum actual: PASS
- UI-08 AI Agent actual: PASS
- UI-09 Render Center actual: PASS

Spectrum evidence additionally used deterministic real audio; the silence/loud frame hashes differ and the real-audio visual probe passed. Ubuntu real-FFmpeg render smoke also passed.

### Exact immutable golden limitation

All nine exact golden PNG binaries are external to this repository in the current environment. Therefore the final validation correctly records:

`UI-01..UI-09 = LOCAL_PENDING`

No overlay/diff is fabricated. If the exact immutable golden pack is supplied in STEP 12, each file must first match the SHA-256 recorded in `docs/ui-reference/manifest.json`, then overlay/diff can be generated and judged.

This missing binary evidence is why STEP 11 is not labeled `READY_FOR_STEP_12` without qualification.

## FFmpeg release-environment evidence

Ubuntu runner FFmpeg `6.1.1-3ubuntu5` successfully passes the real render smoke used in STEP 11.

The separate `-/filter_complex` file-indirection capability is **not** advertised by this Ubuntu FFmpeg build. The final evidence intentionally records:

`LOCAL_PENDING_PINNED_WINDOWS_FFMPEG`

This is not reported as a renderer PASS and is not treated as an application regression. That capability belongs to the exact pinned Windows portable FFmpeg used by the product and must be executed in STEP 12/native portable QA.

## Security / artifact evidence

- Secret scan: **PASS**
- STEP 11 evidence manifest SHA-256: `9f9483dafdd7191d38388c74553d3750239debe7e7cf88f7160123db27654b9a`
- Artifact name: `step11-integration-evidence`
- Artifact ID: `11293265801`
- Uploaded artifact SHA-256: `3d16c235ba389a602950a801427f3d97634807971c0eabe58482dfb31f23607f`
- Artifact final size: `1,804,967` bytes
- Artifact contains 25 evidence files from the validated implementation run.

## Self-review diff

Comparison against STEP 10 final baseline `fdc352794f5fd67d50329f675e7b775e8ff56c9b` at implementation SHA `7f9d6766...`:

- **21 commits ahead, 0 behind**
- 10 changed paths total
- Four additive STEP 11 integration modules
- Four additive STEP 11 test modules
- One STEP 11 workflow
- `main.py` changed only by +5 / -1 lines for integration activation
- No mass rewrite/redesign of Media, Album, Timeline, Visual, Template, Spectrum, AI Agent, or Render Center
- `integration/step-11-core-backup` remains untouched as a recovery anchor

## Known limitations

1. Exact immutable golden PNGs for UI-01..UI-09 are not present in the repository/runner, so exact pixel overlays/diffs remain `LOCAL_PENDING`.
2. `-/filter_complex` compatibility remains `LOCAL_PENDING_PINNED_WINDOWS_FFMPEG`; STEP 12 must run it against the exact pinned Windows portable FFmpeg, not Ubuntu system FFmpeg.
3. Final Windows portable folder relocation/startup/render and hardware-specific encoder verification belong to STEP 12 release QA; they are not claimed PASS here.

None of these limitations changes state ownership, project integrity, normalized Save/Reopen equality, global Undo, AI action semantics, or immutable Render snapshot ownership.

## STEP 12 constraints

STEP 12 is QA, pixel-match closure, regression, portable packaging, and release evidence. It must **not** redesign the architecture unless a release-blocking defect is proven.

Preserve these STEP 11 contracts:

- one authoritative `ProjectDocument` state;
- one global command/history owner;
- stable-ID shared selection;
- typed non-reentrant domain events;
- autosave only from committed revisions;
- separate validated recovery envelope;
- shared preview/session ownership with stale-result guards;
- AI through normal action/command contracts;
- Render from immutable project snapshots;
- normalized Save/Reopen equality;
- no workspace-local duplicate truth.

### First safe task for STEP 12

1. Verify repository/branch/head and this STEP 11 handoff.
2. Run Windows-native/portable smoke using the **exact pinned FFmpeg** and execute the `-/filter_complex` capability test there.
3. If the exact UI-01..UI-09 golden binary pack is available, verify every golden SHA against `docs/ui-reference/manifest.json` before generating nine overlays/diffs.
4. Run portable relocation/startup/open/save/preview/render/recovery smoke without weakening the STEP 11 ownership/integrity contracts.
5. Only after those gates are green, proceed to release packaging/evidence.

## Final decision

**`READY_WITH_LIMITATIONS`**

STEP 11 S11-01 through S11-36 is closed. The integrated application state model is ready for STEP 12 QA/release work, with the exact golden binary comparison and pinned-Windows-FFmpeg capability explicitly deferred and evidence-locked rather than falsely reported as PASS.
