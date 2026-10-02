# STEP 04 — Album Baseline

Repository: `inoriko920-dev/Full-Album-Maker`
Baseline branch: `ui/step-03-media`
Baseline HEAD: `152379fe0dfeb54e1040708126ce61060fd7c0cb`
STEP 04 branch: `ui/step-04-album`
Validated implementation HEAD before documentation-only closure: `efcb1eb7bf808817567f5469b4c534b9538d41b8`
Validation run: `37003744459`

## Scope decision

STEP 04 implements UI-03 / Album on top of the shared foundation and the recovered editor-v2 model. It does not create a second application shell and it does not redesign STEP 03 Media.

Album uses the existing `ProjectDocument` / playlist / editor controller as the behavioral source of truth. Album presentation is layered into the shared route `album`; bulk actions are dispatched through the editor command stack so one bulk operation remains one Undo transaction.

## Functional contract validated

The deterministic Album fixture represents the master-plan target:

- 100 songs total.
- 12 songs missing cover.
- 18 songs missing visual.
- 6 songs requiring review.
- total duration `2j 47m`.
- 12 selected songs in the bulk-action state.
- table pagination renders 10 rows per page and reports `Halaman 1 dari 10`.
- right-side heading reports `Alat Massal (12 lagu dipilih)`.
- Album context, workspace, right inspector and compact timeline are simultaneously active on route `album`.

Reorder is undoable. Auto Susun is idempotent for the same recipe: running it again replaces its owned auto layers instead of duplicating them, while manual layers remain outside that ownership contract.

## Persistence bridge

The complete Album state is persisted as the v2 document extension `album_document_v2`.

The legacy `active_audio_paths` field remains only a compatibility mirror and is constrained to paths that are actually present in the legacy media list. STEP 04 does not invent missing legacy media merely to satisfy that mirror. This preserves the older referential validator while retaining all Album-v2 song/order/cover/visual state in the v2 payload.

Older project files without `album_document_v2` remain loadable through the existing legacy-to-v2 synchronization path.

## Route compatibility

STEP 03 contains a zero-delay activation guard that can re-apply the current workspace after startup. STEP 04 therefore installs its own final deferred route reactivation after the older guard. This keeps shared navigation/context/timeline geometry coherent while ensuring Album owns the Album inspector at the end of the event turn.

The compatibility patch is intentionally layered after STEP 03 rather than modifying STEP 03 behavior.

## Final validation evidence

GitHub Actions run `37003744459` on commit `efcb1eb7bf808817567f5469b4c534b9538d41b8` completed successfully.

Executed checks:

- STEP 04 focused + acceptance: `12 passed`.
- STEP 03 regressions: `16 passed`.
- recovered media regressions: `11 passed`.
- full recovered regression suite: `298 passed, 88 skipped`.
- source compile: PASS.
- STEP 04 secret scan: PASS.
- deterministic Album capture: PASS.
- Album geometry/fixture contract: PASS.
- evidence artifact upload: PASS.

## Deterministic geometry evidence

At `1672×941` / scale `1.0` / Noto Sans:

- context width: `264 px`.
- right dock width: `348 px`.
- compact timeline height: `194 px`.
- status height: `28 px`.
- visible table rows: `10`.

At `1366×768`:

- right dock width: `300 px`.
- Album route/context/inspector/timeline remain active.
- 10 table rows and 12-song selection remain valid.

## Visual golden provenance

The immutable UI-03 canonical reference is identified as `03-album.png` with expected SHA-256:

`42756121fc9a0b18b03d006710d1fb528388b3cf86eaf25c0e72afdac11062b9`

That exact binary is intentionally not committed in the repository and was not available inside the CI runner. Therefore pixel-overlay status is honestly recorded as:

`LOCAL_PENDING`

STEP 04 must not claim exact pixel-diff PASS until the immutable local golden pack containing the exact binary is provided and its SHA-256 matches the value above.

## Evidence artifact

Workflow artifact: `step04-album-evidence`

Artifact ID: `11224428778`

Artifact SHA-256 digest:

`d14a241f36b57da44913e3a0894b825248735ec08fa2f28fe4e1504627ca835b`

The artifact contains the final 1672×941 Album capture, empty-state capture, 1366×768 compact capture, geometry reports, and golden-reference status report. It is tied to head SHA `efcb1eb7bf808817567f5469b4c534b9538d41b8`.

## Diff audit

Compared with STEP 03 baseline `152379fe0dfeb54e1040708126ce61060fd7c0cb`, the validated STEP 04 implementation is strictly ahead with no divergence. Before this documentation-only closure it was 19 commits ahead / 0 behind and changed only the STEP 04 workflow, Album modules, STEP 04 tests, and the small `main.py` activation wiring.

No STEP 03 source file was rewritten as part of the Album implementation.

## STEP 04 decision

`STEP04_IMPLEMENTATION_READY`

Limitation carried forward: exact UI-03 pixel overlay remains `LOCAL_PENDING` until the immutable canonical golden binary is supplied locally. This limitation does not invalidate the functional, persistence, geometry, regression, or evidence gates above.
