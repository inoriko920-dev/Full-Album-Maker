# STEP 01 Baseline Record

Project: **Full Album Maker**  
Repository: `inoriko920-dev/Full-Album-Maker`  
STEP 01 branch: `ui/step-01-foundation`

## 1. Source baseline

STEP 01 inherits the verified recovery baseline established by STEP 00:

- recovery branch: `recovery/step-00-r0`
- current STEP 00 recovery HEAD: `87860b7281c3c5e9731ccf082dac84ab14624402`
- STEP 00 decision: `READY_FOR_STEP_01_WITH_LIMITATIONS`
- historical `main` baseline recorded by STEP 00: `561970639a7a61d2cea583d6386e8912c9161512`
- exact implementation source baseline: recovered v1.4.0 source
- v1.4.1 portable: behavior/build evidence only; exact v1.4.1 source is not claimed recovered

STEP 01 does not overwrite or relabel the recovery provenance established in STEP 00.

## 2. STEP 01 validated implementation point

The foundation implementation that passed the authoritative Linux and Windows workflow is:

```text
commit: 084808da876d2bfd8a72764e7951515578a1a995
message: test(ui): clamp 100 percent capture to requested logical viewport
workflow run: 36977769859 (#23)
result: SUCCESS
```

Both validation jobs completed successfully:

- `validate-foundation` — Linux
- `validate-windows-foundation` — Windows Server 2025

Documentation-only closure commits after this validated implementation point do not alter the foundation runtime and are intentionally excluded from automatic STEP 01 reruns by workflow `paths-ignore` rules.

## 3. Frozen visual contract

- golden logical viewport: `1672×941`
- workspace routes: 9
- frozen reference hashes: `docs/ui-reference/manifest.json`
- exact binary references: external/not checked into this text-oriented branch workflow
- capture harness: `src/full_album_maker/foundation_capture.py`

The manifest is the immutable identity check for the nine references. The implementation must not resize a golden image to manufacture a match and must never use a reference screenshot as a flattened production background.

## 4. Foundation contract now established

STEP 01 establishes one shared application foundation:

- one global command bar;
- one 9-item workspace navigation rail;
- one workspace stack/registry;
- one shared right `Properti | AI` dock host;
- one shared timeline dock host;
- one shared status/event model;
- one design-token source;
- one reusable component/style system;
- responsive compact behavior at the 1366-class viewport;
- deterministic screenshot/evidence tooling;
- persistence and compatibility adapters around the recovered application behavior.

Final workspace bodies are not part of this baseline and remain intentionally deferred to STEP 02–10.

## 5. Validation summary

At the validated implementation commit:

- STEP 01 focused tests Linux: **15 passed**
- recovered Linux regression suite: **246 passed, 88 skipped**
- STEP 01 focused tests Windows: **15 passed**
- all nine 1672×941 route captures: **PASS**
- deterministic repeated Home capture: normalized absolute difference **0.0**
- 1366×768 compact capture: **PASS** on Linux and Windows
- 125% DPI capture: **PASS** on Linux and Windows
- 150% DPI capture: **PASS** on Linux and Windows
- high-confidence secret scan: **PASS**
- Linux evidence validator: **PASS**
- Windows geometry gate: **PASS**

See `STEP01_TEST_REPORT.md` for the acceptance matrix and evidence artifact identifiers.

## 6. Closure state

STEP 01 final state: **READY_WITH_LIMITATIONS**.

The only material visual-validation limitation at closure is that CI does not contain the exact external multi-megabyte golden PNG payloads, so full all-nine binary raster overlay against those exact files is not claimed. Structural shell landmark gates and deterministic screenshot machinery are verified and the branch is suitable as the foundation for STEP 02.
