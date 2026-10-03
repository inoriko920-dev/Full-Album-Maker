# STEP 08 — Spectrum & Overlay Baseline / Handoff

## Gate

**STEP 08 status: `READY_WITH_LIMITATIONS`**

STEP 08 implementation is functionally complete and safe as the Spectrum contract consumed by later work. The only gate item preventing `READY_FOR_STEP_09` is exact pixel overlay/diff against the immutable UI-07 binary: the canonical `07-spectrum.png` is not stored on this branch, so CI correctly records `LOCAL_PENDING` instead of fabricating a pixel-parity PASS.

This document is the closure/evidence record for S08-01 through S08-30. It does **not** start STEP 09.

## Repository baseline

- Repository: `inoriko920-dev/Full-Album-Maker`
- Branch: `ui/step-08-spectrum`
- STEP 07 baseline / merge-base: `60a5d798f552886537a44c781c7ad52a085b86d3`
- STEP 08 validated implementation/evidence HEAD: `1f62f547d288449c2067e504f96a88f394d6e0bd`
- Final implementation workflow: `STEP08 Spectrum validation`, run `37137578668` / run #20
- Compare against STEP 07: **28 commits ahead, 0 behind, 19 changed paths**.

## SpectrumLayer contract

Spectrum remains a normal persisted `Layer` with the recovered stable layer identity and existing project schema. No breaking schema migration was introduced.

Persisted/recovered layer fields remain authoritative for:

- stable `layer_id`
- `type="spectrum"`
- `enabled`
- per-layer `locked`
- `opacity`
- project-coordinate `Transform`
- album time binding
- Spectrum semantic properties

STEP 08 extends Spectrum properties backward-compatibly. Recovered aliases `gain` / `color` remain accepted, while the semantic contract exposes:

- `spectrum_type`: `linear` / `circular`
- `band_count`: 16..512
- `thickness`: project/render-pixel semantic thickness
- `smoothing`: 0..1
- `reactive_scale`: visual analysis sensitivity only
- `accent_color`: validated `#RRGGBB`
- `frequency_scale`
- `amplitude_scale`
- `mirror`
- `inner_ratio`
- `audio_binding="project_mix"`
- preset identifier

UI is not the source of truth. Mutations go through editor commands/controller so Undo/Redo, dirty state, persistence and lock rules stay intact.

## Audio analyzer / renderer owner

STEP 08 did not create a second FFT/render architecture.

Recovered renderer ownership is preserved and extended additively:

- final/accurate pipeline owner: recovered V13/S11 FFmpeg compiler chain
- STEP 08 additive owner: `Step08FFmpegCompiler`
- Linear/Bars: FFmpeg `showfreqs`
- Waveform: FFmpeg `showwaves`
- Circular: recovered `showfreqs` + bounded polar remap
- Free Timeline audio binding remains the recovered project/master mix semantics
- Accurate Preview and final render read the same Spectrum semantic parameters

The Spectrum visual analysis branch is separate from the audible master audio path. `reactive_scale` changes visual response; it does not multiply final audible master gain.

### Cross-platform large filter-graph compatibility

PASS.

The recovered Windows compiler can externalize large filter graphs with `-/filter_complex <file>` to avoid Windows command-line limits. Ubuntu FFmpeg 6.1.1 used by CI does not recognize that newer generic option-file spelling, but supports the semantically equivalent `-filter_complex_script <file>`.

`FFmpegProcessRunner` now normalizes only the host process invocation:

- Windows keeps the recovered `-/filter_complex` syntax unchanged.
- Non-Windows bridges that argument to `-filter_complex_script`.
- The generated filter graph file is not rewritten, so preview/final filter semantics remain identical.

Dedicated tests lock both Windows and non-Windows behavior. This bridge allowed the richer UI-07 evidence fixture to render on FFmpeg 6.1.1 without weakening the production graph.

## Linear

PASS.

Linear Spectrum persists and renders through the recovered FFmpeg path. `band_count` controls real analysis resolution; `smoothing` maps to FFmpeg time averaging; `thickness` is applied in render-space geometry; opacity/reactive/color values are consumed by the renderer rather than being UI-only fields.

## Circular

PASS.

Circular Spectrum preserves the recovered polar-remap representation. STEP 08 maps Bands, Thickness and Smoothing into the existing circular filter while preserving the same semantic properties used by Accurate Preview and final render.

Final deterministic UI-07 fixture state:

- Type: Circular
- X: **835.2 px**
- Y: **540 px**
- Size: **70%**
- Bands: 128
- Thickness: 12 px
- Opacity: 90%
- Smoothing: 0.65
- Reactive Scale: 1.20
- Accent: `#1B8DFF`

The fixture intentionally positions the circular Spectrum left of canvas center to balance the 10-song playlist on the right. This is a deterministic QA fixture choice; the production geometry model still supports Center/Reset and arbitrary validated project-coordinate placement.

## Position / Size / Center / Reset

PASS.

Position and Size are stored in project/render coordinate semantics, not widget pixels. The Center action resolves to project center (`960,540` for a 1920×1080 canvas). Linear/Circular conversion preserves the semantic center. Reset Transform has explicit deterministic defaults and is Undo-able.

The final golden-tuned capture fixture itself uses `835.2 / 540` and 70% to match the intended UI-07 composition rather than exercising the Center command.

## Bands / Thickness

PASS.

- Bands affects real `showfreqs` analysis/image resolution.
- Circular thickness changes radial ring geometry.
- Linear thickness is applied after mapping to render geometry through bounded morphology.
- Values are validated before mutation.

## Opacity

PASS.

Layer opacity remains persisted in the normal Layer model and is applied to Spectrum render alpha.

## Smoothing

PASS.

Normalized smoothing maps deterministically to FFmpeg `showfreqs:averaging` (1..16 analysis frames). Async preview uses generation/stale-result guards, so a result from an older seek/parameter state cannot overwrite the latest request.

## Reactive Scale / silence behavior

PASS.

Reactive Scale maps to the visual analyzer branch only. Final CI real-audio evidence proves the result is audio-reactive rather than playhead/random animation:

- silence frame SHA-256: `c6321864942ff0bdefd6d0c0dca7726bf6b6eb1097290b0b78ad498efc45be8a`
- loud frame SHA-256: `fbbb440fd0ee7fa2c28b1a4ae780cb7a4e286ac36d4b6566265ba59a905ccd2b`
- frames different: true
- mean absolute difference: `0.01388647762345679`
- max difference: `142`
- changed pixels (>2): `1052`

While Accurate Preview is pending/unavailable, the lightweight Spectrum fallback is intentionally a deterministic resting geometry and does **not** synthesize fake reactivity from playhead math.

## Accent Color

PASS.

Accent Color is validated as `#RRGGBB`, persisted, and consumed by Accurate Preview/final rendering.

## Presets

PASS with intentional renderer-capability constraints.

Real parameter bundles are available for supported presets including Classic, Minimal, Wave, Retro, Trance and Ambient. Applying a supported preset is an Undo-able project mutation and manual edits may follow it normally.

The mockup names `Neon Glow`, `Rainbow`, and `Particles` are deliberately fail-closed/unsupported because the recovered final renderer has no parity-safe glow compositor, multi-color spectrum mapping, or particle renderer. STEP 08 does not fake preview-only effects that final render cannot reproduce.

## Layer stack

PASS.

Selection, visibility, lock state, add Spectrum, duplicate, and normal layer identity use project state. Locked Spectrum layers reject mutation. Duplicate produces a new stable ID rather than shared mutable runtime identity.

## Apply to All

PASS.

Apply-to-All prevalidates eligible Spectrum targets and executes through one editor transaction. Style/geometry/opacity may be propagated, while each target keeps its own audio binding rather than blindly copying one source audio ID.

## Timeline binding

PASS.

Spectrum is represented on the existing editor/timeline model. Playhead/seek drives Accurate Preview at the correct project time. STEP02–07 workspace smoke remained green.

## Template integration

PASS.

Template-produced Spectrum becomes normal editable Spectrum layer state rather than a special preview-only object. STEP07 regression remained green.

## Async / cache / stale guard

PASS.

`SpectrumAccuratePreview` runs Accurate Preview off the UI thread with:

- one-worker bounded execution
- deterministic cache key from document content signature + tick
- generation token
- invalidation on newer request
- stale-result discard
- graceful error status without project mutation

## Missing audio / failure behavior

PASS.

Failure-path tests cover unavailable/missing analysis/render input. Analyzer/preview failure cannot corrupt project state. The editor remains usable, and no fake audio response is substituted as if it were real analysis.

## Persistence / Undo / autosave safety

PASS.

Complex Spectrum state round-trips through the existing ProjectDocument persistence. Add/edit/type/preset/geometry/duplicate/bulk mutations remain controller-owned and Undo/Redo-safe. Half-gesture/UI transient state is not promoted as authoritative persisted Spectrum data.

## Deterministic UI evidence

Final 1672×941 production capture from run #20:

- workspace: `spectrum`
- Spectrum active: true
- context visible: true
- inspector active: true
- timeline visible: true
- context width: 264 px
- right dock: 348 px
- timeline: 252 px
- status: 28 px
- layer count: 4
- Spectrum count: 1
- preset cards: 9
- Type: Circular
- Bands: 128
- Thickness: 12
- Opacity: 0.90
- Smoothing: 0.65
- Reactive Scale: 1.20
- Accent: `#1B8DFF`
- X/Y: **835.2 / 540**
- Size: **0.70**
- preview status: `Audio reaktif`
- Accurate frame installed: true
- Accurate frame source: `deterministic_real_audio_loud_probe`
- route/preview mutation of project content: false
- QA font: Noto Sans

Compact 1366×768 evidence also passed:

- context width: 264 px
- right dock: 300 px
- timeline: 252 px
- status: 28 px
- same persisted Spectrum geometry/state (`835.2 / 540`, 70%)

## Golden UI-07

- Canonical file: `07-spectrum.png`
- Canonical expected SHA-256: `ffd89d91c8679b819264ce012742e2387313fdfef90e2ea9a2f590685cb7d87f`
- Current branch contains exact binary: **no**
- Golden status: **`LOCAL_PENDING`**
- Actual deterministic production screenshot: PASS
- 50% overlay/diff against exact canonical binary: **LOCAL_PENDING**

CI is intentionally conditional: if the exact binary becomes available, its SHA must match the canonical hash before overlay/diff may be produced. Absence of the binary is never reported as pixel-parity PASS.

## Final test evidence — run 37137578668 / #20

Validated SHA: `1f62f547d288449c2067e504f96a88f394d6e0bd`

- Compile source: PASS
- STEP08 focused engine + persistence: **13 passed**
- STEP08 production UI + async + failure + FFmpeg bridge: **13 passed**
- Recovered Spectrum regression: **6 passed, 13 skipped**
- STEP02–07 workspace regression smoke: **24 passed**
- STEP07 Template regression: **24 passed**
- Full recovered regression suite: **378 passed, 88 skipped**
- Real-audio capture: PASS
- Geometry/audio validation: `STEP08_SPECTRUM_GEOMETRY_AUDIO_PASS`
- Secret scan: `STEP08_SPECTRUM_SECRET_SCAN_PASS`
- Golden check: `STEP08_GOLDEN_REFERENCE_LOCAL_PENDING`

Evidence artifact:

- Name: `step08-spectrum-evidence`
- Artifact ID: `11279346118`
- Final size: `560581` bytes
- SHA-256: `b2bef12cabda7f6ee7bfabc3d9572a5af1169d6102734f9b663132e0f5baa8d2`
- Files uploaded: 7

## Tests NOT TESTED / BLOCKED

- Exact UI-07 binary pixel overlay/diff: `LOCAL_PENDING` because the immutable canonical PNG is not present on this branch.
- Native Windows-only full visual/render smoke is not claimed by this Linux CI evidence unless executed separately; no Windows PASS is invented here.
- Windows command-line syntax is contract-tested, but run #20 itself executes on Ubuntu; the existing recovered Windows `-/filter_complex` path is intentionally preserved.

## Self-review / changed files

Compare STEP07 baseline `60a5d798…` → STEP08 validated implementation/evidence `1f62f547…`:

- **28 commits ahead**
- **0 commits behind**
- **19 changed paths**

Changed areas are contained to:

- STEP08 workflow/test/evidence files
- Spectrum model/normalization
- Circular Spectrum filter mapping
- STEP08 compiler extension
- Accurate Preview service compiler owner
- final render service compiler owner / cross-platform process bridge
- STEP08 workspace/feature/async preview/capture
- `main.py` production activation
- this STEP08 closure document

No STEP09 AI Agent implementation and no Render Center redesign were added.

## Known limitations

1. Exact pixel-to-pixel UI-07 overlay/diff is pending the canonical binary.
2. `Neon Glow`, `Rainbow`, and `Particles` are visible product concepts but remain unsupported/fail-closed rather than being simulated inconsistently with final render.
3. Linux evidence uses FFmpeg 6.1.1 only in the dedicated real-audio evidence phase; recovered regression is deliberately executed before installing system FFmpeg so legacy tests are not activated against the wrong historical Windows build.
4. Native Windows end-to-end execution of the final rich UI-07 evidence fixture is still a local validation item; no Windows result is inferred from Linux CI.

These limitations do not undermine the Spectrum action/model contract needed by the next step.

# STEP 08 → STEP 09 Handoff

**Status: `READY_WITH_LIMITATIONS`**

### Contract that STEP 09 must preserve

- AI Agent must call existing Spectrum / Visual / Timeline action/controller contracts.
- AI must not write `SpectrumLayer`/Layer fields directly behind controller/history.
- Ambiguous target or audio-binding requests must require clear scope/preview rather than guessing.
- Preserve shared shell, Undo/Redo, project persistence, autosave and permission boundaries.
- Do not create a second Spectrum analyzer/render representation.
- Preserve semantic parity between Accurate Preview and final rendering.
- Preserve stable layer IDs and target-specific audio binding during bulk operations.
- Unsupported renderer effects must remain explicit; do not turn them into AI-only preview illusions.
- Preserve the cross-platform FFmpeg process bridge; do not replace the recovered Windows option-file strategy with a Linux-only workaround.

### First safe task for STEP 09

Verify this STEP08 handoff and the live branch/HEAD, then audit STEP09's recovered AI Agent/action-dispatch capability **read-only before coding**. Map existing intent/action APIs to the stable Spectrum/Visual/Timeline controller contracts and identify any permission/confirmation boundaries. Do not implement direct project-field mutation.

## Final decision

`READY_WITH_LIMITATIONS`

Reason: Spectrum model/analyzer/preview/render/timeline/persistence/Undo behavior, real-audio reactivity, rich UI-07 deterministic evidence, and cross-platform FFmpeg evidence execution are proven. Exact immutable UI-07 pixel overlay/diff remains `LOCAL_PENDING` until the canonical `07-spectrum.png` binary is available.