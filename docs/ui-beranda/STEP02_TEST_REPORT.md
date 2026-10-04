# STEP 02 — Beranda / Project Hub — Test Report

Repository: `inoriko920-dev/Full-Album-Maker`  
Branch: `ui/step-02-beranda`  
STEP 01 baseline / rollback point: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`  
Validated implementation SHA: `ec380f355dc12a4193285428068c84e98b68f8c1`  
CI run: `36985869444` (`STEP02 Beranda validation`, run 14)  
CI artifact: `11217771140` / `step02-home-evidence`  
Artifact digest: `sha256:fcd405714b79cd43e5c144a28b7951f810214a2169b0355d44ccf36a67d39173`

## Automated validation

All checks below were actually executed on Ubuntu 24.04 / Python 3.12 / Qt offscreen at the validated implementation SHA.

| Check | Result |
|---|---|
| Source compile (`python -m compileall -q src`) | PASS |
| STEP 01 foundation regression | PASS — `15 passed` |
| STEP 02 focused state/services/UI tests | PASS — `24 passed` |
| Full recovered regression suite | PASS — `270 passed, 88 skipped` |
| G02-A recovery fixture | PASS for state + geometry evidence |
| G02-B no-recovery fixture | PASS |
| G02-C first-run fixture | PASS |
| G02-D portable-warning fixture | PASS |
| G02-E output-invalid fixture | PASS; writable warning is visibly populated |
| 1366×768 compact capture | PASS; compact navigation = 71 px |
| 125% DPI capture | PASS generated |
| 150% DPI capture | PASS generated |
| STEP 02 secret scan | PASS |
| Evidence artifact upload | PASS |

## G02-A geometry evidence

The deterministic recovery fixture produced:

- viewport `1672×941`;
- command bottom `95`;
- navigation right edge `171`;
- right dock width `348`;
- collapsed idle timeline height `34`;
- status bar height `28`;
- Noto Sans visual-QA font active;
- `HOME_RECOVERY_AVAILABLE` active;
- Beranda widget confirmed as the active stacked page;
- recovery banner visible;
- 4 recent-project cards visible.

This proves the STEP 02 composition is actually mounted inside the shared STEP 01 shell rather than a screenshot-only or detached fixture.

## Project-flow evidence

Focused tests exercise the real recovered project contract, not a fake Beranda-only schema:

- create a project to disk, then open that same project successfully;
- open missing file fails with `PROJECT_NOT_FOUND` and does not mutate a project;
- corrupt JSON fails with `PROJECT_CORRUPT` and does not crash;
- recent index persists, sorts newest-first, and marks a missing path without deleting it automatically;
- quick defaults persist and a writable path containing spaces is accepted;
- a valid recovery snapshot is written, discovered, restored, and retained;
- an invalid recovery snapshot is preserved and refused safely.

Production integration routes Home create/open/recovery/recent through `HomeProjectService` / `RecoveryService` and then adopts the recovered `Project` into the existing controller/editor compatibility layer.

## Portable/status/startup observation

- FFmpeg readiness is derived from `ffmpeg_path()` and therefore reflects a real local executable lookup rather than a decorative green label.
- AI status is based on the local Gemini key-pool summary. No AI/network request is required for Home startup; unconfigured AI remains optional.
- Recent projects read one bounded JSON index (maximum 100 records) and do not scan media directories.
- Recovery discovery validates one known local snapshot path. It is synchronous but bounded local I/O; there is no recursive disk scan or startup network operation.

## Golden reference evidence

Specification-declared canonical Beranda hash:

`039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

The PNG actually embedded in the supplied DOCX is `1672×941` but hashes to:

`b339d432cf2378c14ad4c65fad16a2996fe0403741a25ec00302a1a29ef727bf`

Therefore an exact canonical binary comparison cannot be claimed. Against the embedded DOCX visual evidence, final G02-A has normalized absolute difference:

`0.09869081147824202`

The comparison is recorded only as visual evidence; it is **not** presented as proof against the unavailable canonical binary.

## Environment limitations

- Native Windows 11 smoke was not executed by this Linux CI run: `LOCAL_PENDING`.
- Exact canonical-golden binary identity remains unresolved because the supplied embedded PNG does not match the declared hash.
- Recent thumbnails use the specification-permitted generic placeholder when no actual project thumbnail is available; no fake sample artwork is written into user projects.

## Result

Core Beranda behavior, recovery safety, persistence, responsive fixture states, shell regression, and secret checks pass. The remaining limitations are evidence/platform limitations and do not require redesigning the STEP 01 shell or project model.
