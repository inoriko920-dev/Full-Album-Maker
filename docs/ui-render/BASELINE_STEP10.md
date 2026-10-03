# STEP10 — Render / Export Center Baseline & Handoff

## Gate Decision

**READY_WITH_LIMITATIONS**

STEP10 — Render / Export Center is functionally complete on the `ui/step-10-render` branch and is safe to use as the baseline for the next explicitly requested step. The remaining limitations are evidence/environment limitations, not known blockers in the Render Center state machine or verified-output path.

Do **not** treat the exact UI-09 pixel overlay, native Windows portable smoke, or NVIDIA NVENC execution as PASS unless those checks are actually run in the required environment.

---

## Baseline Identity

| Item | Value |
| --- | --- |
| Repository | `inoriko920-dev/Full-Album-Maker` |
| Branch | `ui/step-10-render` |
| Previous-step baseline | `7edeb8c8d5999ee22298df649f5c674bd9df0d70` (`ui/step-09-ai-agent`) |
| STEP10 validated implementation SHA | `851baa4dea7a1c2768b5512c61a459a5e644b293` |
| Final implementation validation run | `37148414201` / workflow run #30 |
| Validate-render job | `111277005852` — SUCCESS |
| Real-FFmpeg-smoke job | `111277005460` — SUCCESS |
| Golden UI reference | UI-09 `09-render.png` |
| Canonical UI-09 SHA-256 | `8739b225d83089772b19f05b133b98b3ea8e448d1fb905ba613751f46d988618` |
| Exact golden overlay | `LOCAL_PENDING` — canonical binary is not committed on this branch |

The implementation SHA above is intentionally recorded separately from this documentation commit. This avoids circular evidence where changing the baseline document itself changes the SHA being described.

---

## Implementation Summary

STEP10 extends the recovered renderer instead of replacing it.

The Render Center now owns these responsibilities:

- immutable `RenderSnapshot` creation from a validated `ProjectDocument`;
- normalized `RenderSettings` and safe filename/output-path rules;
- portable-first FFmpeg/ffprobe discovery and capability probing;
- encoder selection with runtime capability checks and safe fallback behavior;
- strict preflight checks before job creation/start;
- persistent `RenderJob` + stable `job_id` + unique `attempt_id`;
- explicit render state machine;
- serialized queue scheduling;
- fresh critical preflight before `Render Now` and retry attempts;
- staged output in the destination directory;
- FFmpeg progress parsing for percent/FPS/speed/ETA;
- cancel via terminate followed by bounded kill fallback;
- fail-closed Pause control because proven pause/resume semantics are not available;
- ffprobe verification of staged output before final publication;
- transactional/atomic final output publication;
- crash/restart recovery of active jobs as `INTERRUPTED`, never fake auto-resume;
- retry as a new attempt using the original immutable snapshot/settings;
- sanitized bounded logs;
- verified-output-only `Buka Output`;
- redacted `Salin Log`;
- production Render route integrated after STEP09 without bypassing the shared shell;
- deterministic performance graph that visualizes reported FFmpeg metrics only;
- deterministic UI-09 evidence capture without executing FFmpeg in the screenshot fixture.

### Renderer truth remains recovered

STEP10 continues to use the existing compiler/render chain. It does not introduce a second render engine. The existing lifecycle, Spectrum/Visual/Timeline/Template semantics, atomic bundle publication, source-integrity checks, and STEP09 boundary remain in force.

AI Agent still has no direct shortcut that can bypass Render Center preflight or output verification.

---

## Important Bug Fixed During STEP10

A real-FFmpeg smoke exposed a genuine settings bug: Render Center requested `24 fps`, but the compiler still produced `30 fps`.

Root cause:

- `CanvasSettings` persists FPS as `fps_num/fps_den`;
- STEP10 originally wrote a dynamic `canvas.fps` attribute that the recovered compiler never read.

Fix:

- per-attempt render document now sets `canvas.fps_num = settings.fps` and `canvas.fps_den = 1`;
- the immutable frozen job snapshot remains unchanged;
- focused regression now explicitly verifies this contract;
- real FFmpeg + ffprobe then proved the requested 24 fps output is actually produced.

The verifier was **not** weakened to make the test pass.

---

## Render Success Semantics

`COMPLETED` means more than FFmpeg exit code 0 or UI progress reaching 100%.

A final output is published only after all of the following are true:

1. critical preflight is valid for the immutable snapshot/settings;
2. FFmpeg finishes the staged render;
3. staged output exists and is non-empty;
4. ffprobe can parse the staged output;
5. expected video and audio streams exist;
6. output resolution matches the requested settings;
7. video codec matches the requested H.264/HEVC family;
8. audio codec is AAC with the requested sample rate;
9. MP4 container is valid;
10. duration is within bounded tolerance of the frozen snapshot;
11. FPS is within bounded tolerance of the requested FPS;
12. atomic publication of the verified staged file succeeds.

Only then is `verified_output` populated and the job transitioned to `COMPLETED`.

`Buka Output` is fail-closed and requires a `COMPLETED` job whose verified output still exists and is non-empty.

---

## State Machine & Queue Contract

Primary states used by STEP10:

`DRAFT → PREFLIGHTING → READY → QUEUED/STARTING → RUNNING → FINALIZING → COMPLETED`

Terminal/error states include:

- `FAILED`
- `CANCELLED`
- `BLOCKED`
- `INTERRUPTED`

`PAUSED` exists in the model only for compatibility/future proofing. The production Pause button remains disabled because safe pause/resume semantics have not been proven. STEP10 does not simulate pause by lying about process state.

Additional queue guarantees:

- only one active render attempt is allowed per executor;
- jobs with the same active final output are rejected;
- retry creates a fresh `attempt_id` while retaining the immutable snapshot/settings;
- active jobs recovered after a crash become `INTERRUPTED` and are not silently auto-resumed;
- orphan `.rendering.mp4` stages are cleaned under the queue recovery contract;
- terminal `COMPLETED VERIFIED` history can be shown in the Render Center without being reclassified as queued work.

---

## Preflight Contract

The engine evaluates more checks than the five golden cards. Presentation is intentionally separated from engine truth.

Golden card surface:

- Timeline Valid — PASS
- Media — PASS
- FFmpeg — PASS
- Output — PASS
- Disk Space — WARN in the deterministic golden fixture

Encoder capability continues to be checked by the engine/preflight and inspector even though the dedicated Encoder card is hidden from the UI-09 golden card row.

The Render Center invalidates cached preflight readiness when project content or render settings change. A stale preflight cannot create a new job.

---

## Test Evidence — Implementation SHA `851baa4…`

Final workflow run `37148414201` completed successfully on the same implementation SHA.

### `validate-render` job

- STEP10 focused tests: **38 passed**
- STEP09 AI Agent regression gate: **36 passed**
- recovered render lifecycle regression: **21 passed, 10 skipped**
- full recovered regression suite: **452 passed, 89 skipped**
- deterministic STEP10 UI capture: **PASS**
- golden geometry/state contract: **PASS**
- secret scan: **PASS**
- evidence artifact upload: **PASS**

### `real-ffmpeg-smoke` job

- isolated real FFmpeg + ffprobe smoke: **1 passed**
- output is actually rendered and then verified before final publication;
- this job proved the corrected requested-FPS behavior with real media/container probing.

The full regression job intentionally does not install system FFmpeg. The real integration smoke is isolated in its dedicated runtime job so legacy/recovered tests are not accidentally activated by an unrelated Linux FFmpeg build.

---

## Deterministic UI-09 Evidence

### 1672×941 capture

- workspace: `render`
- Render Center active: PASS
- inspector active: PASS
- context width: `0 px`
- right dock: `348 px`
- collapsed timeline height: `34 px`
- status bar: `28 px`
- project content signature unchanged by opening Render Center/golden fixture: PASS
- preflight: **4 PASS / 1 WARN**
- Timeline Valid: PASS
- Media: PASS
- FFmpeg: PASS
- Output: PASS
- Disk Space: WARN
- Encoder card: hidden in golden presentation, still enforced by engine
- selected preset: `youtube_1080p`
- filename: `Senja di Kota Ini - Full Album`
- resolution: `1920×1080`
- FPS: `30`
- video: H.264, `16,000,000 bps`
- audio: AAC, `320,000 bps`, `48 kHz`
- hardware mode shown: `h264_nvenc` **MOCK VISUAL FIXTURE ONLY**
- running fixture: `Senja di Kota Ini`, `63%`, `112 fps` **MOCK VISUAL FIXTURE ONLY**
- queued fixture: `Jalan Pulang`, `0%`
- completed fixture: `Perjalanan Kita`, `COMPLETED VERIFIED`
- visible queue/history rows: `3`
- active job status count: `2`
- performance graph points: `5`
- Pause enabled: `false`
- buttons present: `Tambah ke Antrian`, `Salin Log`, `Buka Output`
- screenshot SHA-256: `8700d677b183e6c73b9d155f1bbfaf3e9f99739816230463bbfb25247b971c44`

### 1366×768 capture

- context width: `0 px`
- right dock: `300 px`
- collapsed timeline height: `34 px`
- status bar: `28 px`
- same 4 PASS / 1 WARN golden state
- same three queue/history fixture rows
- project content signature unchanged: PASS
- screenshot SHA-256: `0d11dde8b749ccc6877670c3398882a62c389c31ef03d3033a8f2c1059dea02d`

The screenshot fixture deliberately mocks progress/NVENC/GPU-facing state for deterministic UI evidence. It does **not** constitute a real NVIDIA NVENC execution test. Real rendering truth is covered separately by the real-FFmpeg smoke.

---

## Golden Reference Status

Expected canonical reference:

- file: `09-render.png`
- SHA-256: `8739b225d83089772b19f05b133b98b3ea8e448d1fb905ba613751f46d988618`

Status: **LOCAL_PENDING**

The exact UI-09 binary is not stored on this branch. Therefore STEP10 does not claim an exact pixel-diff PASS. The workflow will verify the SHA and build overlay/diff automatically when the canonical binary is supplied locally at the documented path.

Geometry/state/capture evidence is PASS; exact canonical pixel overlay remains pending.

---

## Evidence Artifact

Final implementation evidence artifact:

- workflow run: `37148414201`
- artifact name: `step10-render-evidence`
- artifact ID: `11282529262`
- artifact digest: `sha256:6f6a404ada035c5eb27f3c5ee3761fe6f073e1e0b2aa87ddc8cf4ddc12adbfe4`
- artifact head SHA: `851baa4dea7a1c2768b5512c61a459a5e644b293`

The artifact contains deterministic current captures, JSON geometry/state reports, golden-reference status, and comparison outputs when an exact canonical golden is available.

---

## Security & Portable Status

PASS:

- output path normalization and filename safety;
- output cannot overwrite project media sources;
- log redaction for secret-like values;
- bounded logs in persisted jobs;
- no API key/token is required by Render Center itself;
- staged output is isolated from final output until verification succeeds;
- transactional publication/rollback contract retained;
- bundled `tools/ffmpeg` / `tools/ffprobe` discovery remains preferred before global fallback;
- secret scan over STEP10 source/tests/evidence is PASS.

LOCAL_PENDING / limitations:

- native Windows 11 full Render Center smoke was not executed by this Linux runner;
- native Windows portable ZIP smoke with the project's exact bundled FFmpeg/ffprobe was not executed in this final run;
- real NVIDIA NVENC execution was not proven here;
- the historical portable FFmpeg pin remains a recovery/provenance concern documented from earlier recovery work and must not be silently replaced merely to make a build pass.

The Ubuntu real-FFmpeg job proves the render/verify/publish pipeline with a real encoder/container, but it is not a substitute for final Windows portable validation.

---

## STEP10 Completion Matrix

| Task | Result | Notes |
| --- | --- | --- |
| S10-01 verify STEP09 handoff | PASS | STEP09 final baseline verified before work |
| S10-02 audit recovered render stack | PASS | renderer/lifecycle/atomic/path/source-integrity audited |
| S10-03 RenderJob state machine | PASS | stable job/attempt IDs and explicit transitions |
| S10-04 RenderSettings | PASS | normalized codec/FPS/bitrate/path/hardware settings |
| S10-05 immutable snapshot | PASS | frozen canonical project/render plan/hash |
| S10-06 FFmpeg discovery | PASS | bundled-first discovery retained |
| S10-07 encoder probe | PASS | presence + runtime verification/fallback rules |
| S10-08 preflight | PASS | timeline/media/ffmpeg/encoder/output/disk/source checks |
| S10-09 workspace geometry | PASS | production Render route integrated and captured |
| S10-10 presets | PASS | 1080p/1440p/4K/Custom contract |
| S10-11 output path/name | PASS | safe filename/path and collision rules |
| S10-12 codec/container validation | PASS | H.264/HEVC + AAC + MP4 verifier contract |
| S10-13 hardware acceleration | PASS_WITH_LIMITATION | runtime probe/fallback tested; real NVENC execution pending |
| S10-14 FFmpeg argv | PASS | recovered compiler + requested encoder/bitrates/sample rate |
| S10-15 temp lifecycle | PASS | unique staged file, cleanup, no partial-final publish |
| S10-16 queue | PASS | serialized persistent queue, collision protection |
| S10-17 Render Now critical preflight | PASS | fresh recheck before start |
| S10-18 progress | PASS | FFmpeg progress protocol, no fake time-only progress |
| S10-19 ETA/performance | PASS | reported metrics + UI-only graph |
| S10-20 cancel | PASS | terminate then bounded kill fallback; no fake final |
| S10-21 pause gate | PASS | disabled/fail-closed because safe semantics unproven |
| S10-22 orphan protection | PASS | stale stage cleanup and crash recovery |
| S10-23 output verification | PASS | real ffprobe contract tested |
| S10-24 atomic finalization | PASS | verified staged output published transactionally |
| S10-25 history | PASS | terminal history retained; VERIFIED completion visible |
| S10-26 copy log/open output | PASS | redacted logs; verified-output-only open action |
| S10-27 live edit vs snapshot | PASS | live project changes do not mutate queued snapshot |
| S10-28 crash/restart recovery | PASS | active attempts become INTERRUPTED; no fake resume |
| S10-29 AI boundary | PASS | no AI direct bypass around Render Center |
| S10-30 security/portable | PASS_WITH_LIMITATION | security PASS; native Windows portable smoke pending |
| S10-31 job store | PASS | atomic persistent queue/job JSON with sanitized logs |
| S10-32 golden fixture | PASS_WITH_LIMITATION | deterministic state/geometry PASS; exact UI-09 overlay pending |
| S10-33 tuning/regression | PASS | full recovered suite + STEP09 + lifecycle clean |
| S10-34 evidence/handoff | PASS | this document + CI evidence/artifact |

---

## Self-Review / Scope Containment

Compared with STEP09 final baseline `7edeb8c8d5999ee22298df649f5c674bd9df0d70`, implementation SHA `851baa4…` is **34 commits ahead and 0 behind**.

The STEP10 diff is confined to:

- STEP10 workflow;
- `render_*_step10.py` modules;
- STEP10 tests;
- minimal installer activation in `main.py`.

No STEP02–STEP09 feature engine was redesigned as part of STEP10.

No force-push was used.

---

## Handoff Contract

A future step may rely on the following STEP10 invariants:

1. Render Center is the only approved UI path for starting/exporting a render job.
2. A RenderJob owns an immutable validated snapshot and normalized settings.
3. AI Agent must not bypass Render Center preflight, queue, verification, or atomic publish.
4. `verified_output` is the only output path trusted by completion/open-output flows.
5. A non-empty file or FFmpeg exit code 0 alone is not success.
6. Retry must create a fresh attempt and rerun critical preflight.
7. Queue recovery must never silently resume a crashed FFmpeg attempt.
8. Pause remains disabled until safe semantics are implemented and proven.
9. Encoder capability is still enforced even though the dedicated card is hidden from the UI-09 golden row.
10. Golden fixture NVENC/progress values are visual mocks only; they cannot be cited as hardware execution evidence.
11. Exact UI-09 pixel overlay remains pending until the canonical binary is available.
12. Native Windows portable validation remains required before a production release claim.

## Final STEP10 Decision

**READY_WITH_LIMITATIONS**

Functional Render Center, queue/state machine, strict preflight, immutable snapshotting, real FFmpeg rendering, ffprobe verification, cancellation, crash recovery, atomic finalization, UI integration, deterministic evidence, security scan, and regression gates are complete.

Remaining limitations:

- exact canonical UI-09 pixel overlay is `LOCAL_PENDING`;
- native Windows 11 portable ZIP smoke is `LOCAL_PENDING`;
- real NVIDIA NVENC execution is `LOCAL_PENDING`.

**STEP11 has not been started in this branch.**
