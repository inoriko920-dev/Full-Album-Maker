# STEP05 — Timeline Baseline & Handoff

Status: **READY_FOR_STEP06_WITH_LIMITATIONS**  
Branch: `ui/step-05-timeline`  
Baseline STEP04: `0c0d9adf235a197de8694432d18dab07bbfc3526`  
Verified implementation SHA before this documentation commit: `a640d09432335b800e8dd01173d699c0ccf5d7de`  
Validation run: `37009766519`  
Evidence artifact: `step05-timeline-evidence` / artifact `11227387424`  
Artifact digest: `sha256:94488f5f2d42af609e2121f7965856985b147776c6e94eea840e496af2ab39bf`

## 1. Scope actually implemented

STEP05 binds the recovered editor/timeline engine into the production Foundation shell. It does not create a second `ProjectDocument` or a second timeline engine.

Implemented and verified:

- Packed / Free timeline mode using the recovered `SetPlaylistTimingMode` contract.
- Free song positioning with explicit silence gaps and resolver validation.
- Explicit song crossfade; invalid/ambiguous overlaps remain rejected by the recovered resolver.
- Song drag/move with Snap and optional Ripple behavior.
- Delete Gap as an atomic undoable operation.
- Split for audio songs and visual/editor layers.
- Timeline markers persisted in `ProjectDocument.extensions`, including add, select/jump, rename, recolor, delete and Undo/Redo.
- Zoom out / zoom in / Fit.
- Ruler/playhead mouse scrub plus keyboard navigation (`Left`, `Right`, `Shift+Left`, `Shift+Right`, `Home`, `End`).
- Track navigator for V3/V2/V1/A1/A2/S1/S2 and Marker / Daftar Klip navigator states.
- Clip inspector for song Start, Duration, Fade In, Fade Out, Crossfade, Volume/Gain and Lock.
- Layer inspector editing Start, Duration and Lock as one atomic transaction.
- Fade/gain data persists through project save/reopen and is consumed by the Free Timeline render audio graph.
- Preview aspect selector `16:9`, `1:1`, `9:16` changes display geometry without mutating project content.
- Shared Undo/Redo/dirty state remains the existing `EditorController` implementation.
- Switching into Timeline workspace does not mutate project content.
- Production routing keeps Media/Album compatibility layers intact.

## 2. Architecture / provenance decisions

The implementation intentionally extends the recovered model rather than replacing it.

- Canonical audio timing remains `SongInstance.free_start_tick` + `crossfade_in_tick`.
- Canonical layer timing remains `TimeBinding` + `TimelineResolver`.
- Marker data uses `extensions["timeline_markers_v1"]`; no schema-version bump was required.
- Per-song editor mix metadata uses `extensions["timeline_song_mix_v1"]`; base song gain stays on `SongInstance.gain`.
- All mutations route through `EditorController` commands so history and dirty state stay authoritative.
- Existing Free Timeline rendering remains the base path; STEP05 only extends it for verified gain/fade behavior.

## 3. Automated validation evidence

Run `37009766519` on implementation SHA `a640d09432335b800e8dd01173d699c0ccf5d7de` completed the full STEP05 gate successfully.

Results:

- Compile source: **PASS**.
- STEP05 focused tests: **16 passed**.
- STEP04 Album regression gate: **12 passed**.
- Full recovered regression suite: **314 passed, 88 skipped**.
- Deterministic Timeline capture: **PASS**.
- Timeline geometry / fixture contract: **PASS**.
- Secret scan: **PASS**.
- Evidence artifact upload: **PASS**.

## 4. Deterministic golden-state fixture

The capture fixture is engine-backed, not a hardcoded screenshot. It contains:

- Free Timeline mode.
- 3 active songs.
- 1 explicit five-second crossfade.
- 1 intentional five-second silence gap.
- 4 persisted markers: Intro, Reff, Bridge, Outro.
- V1/V2/V3/S1/S2 example layers.
- Real song inspector selection.
- Valid resolver result with zero `Audio:` errors.

Golden viewport geometry measured in CI:

| Item | Measured |
| --- | ---: |
| Full capture | 1672 × 941 |
| Context panel | 264 px |
| Right dock | 348 px |
| Timeline dock | 352 px |
| Precision canvas area | 298 px |
| Status bar | 28 px |
| Workspace | `timeline` |
| Route preserved content | `true` |

Responsive 1366 × 768 capture also passed; right dock measured 300 px and Timeline remained 352 px high.

## 5. Golden reference status

Canonical manifest entry:

- UI ID: `UI-04`
- File: `docs/ui-reference/04-timeline.png`
- Expected SHA-256: `d559b1d380f03bbb68ab832d3174b32e9d63d64fe7c1c4af98d11e5e7d3839c3`
- Golden viewport: 1672 × 941

Repository status: **LOCAL_PENDING**.

The exact immutable UI-04 PNG is not present in the repository. Therefore this STEP does **not** claim pixel-overlay PASS. The CI produces the deterministic current screenshot and will automatically verify hash + create overlay/diff if the exact canonical file is later supplied.

## 6. Known limitations — explicit, not hidden

### L1 — A2 Background Audio engine is not recovered

The golden UI includes A2 Background Audio. The recovered `ProjectDocument`, `TimelineResolver`, and render graph have no second/background-audio clip model. A2 is therefore displayed as part of the lane structure but its controls remain disabled. Implementing A2 correctly would require an explicit persisted data contract, resolver semantics, editor commands, render mixing, and tests; it is not represented as a fake working control.

Recommended follow-up: architecture task before final UI-11 Integration Regression, or a dedicated approved extension if A2 is required before STEP06.

### L2 — Preview audio monitor is unavailable

The recovered preview transport advances playhead/time visually using a Qt timer. There is no `QMediaPlayer` / `QAudioOutput` monitoring subsystem. The preview volume slider remains visible for reference parity but is intentionally disabled with a tooltip. This must not be confused with clip Volume/Gain in the inspector, which is functional and consumed by render.

Recommended follow-up: implement a dedicated timeline-aware audio monitor only if its gap/crossfade behavior can match the canonical resolver; do not wire a single-file player and call it parity.

### L3 — Exact media waveform/thumbnail cache is not implemented in STEP05 presentation

The precision timeline uses lightweight deterministic waveform/clip cues so dragging remains non-blocking. It does not yet claim a real decoded waveform/thumbnail cache. Any future cache must remain asynchronous/non-blocking and must not alter timeline data.

## 7. Self-review of diff

Compared with STEP04 baseline `0c0d9adf...`, STEP05 is forward-only and localized. The implementation primarily adds STEP05 source/test/workflow files. Existing production source changes are intentionally narrow:

- `src/full_album_maker/main.py` — activates the STEP05 compatibility/presentation layers after STEP04.
- `src/full_album_maker/s11_render_graph.py` — extends the proven Free Timeline audio path for verified clip gain/fade semantics.

No force-push, rescue deletion, schema rewrite, renderer replacement, or unrelated Media/Album redesign was performed.

## 8. Gate decision

**READY_FOR_STEP06_WITH_LIMITATIONS**

Rationale: the required Timeline precision-edit behavior and production routing are implemented, undoable, persistent, render-aware where applicable, and pass the full recovered regression suite. The remaining gaps are explicitly architectural/external-reference limitations rather than hidden failing controls.

Do not reinterpret this decision as exact pixel parity. Exact UI-04 overlay remains `LOCAL_PENDING` until the immutable canonical PNG is supplied.
