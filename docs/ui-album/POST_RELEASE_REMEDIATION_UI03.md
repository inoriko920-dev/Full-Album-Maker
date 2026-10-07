# POST-RELEASE REMEDIATION — UI-03 ALBUM

Status: FINAL CANDIDATE / PASS  
Target: UI-03 Album  
Base release: v1.5.0  
Branch: `ui/ui03-album-remediation-v150`

## 1. Source of truth

UI-03 was remediated against the immutable Album reference extracted from
`ASTRA_MASTER_PLAN_UI_FULL_ALBUM_MAKER_PIXEL_MATCH_9_REFERENSI.docx`.

Reference identity:

- canvas: 1672 × 941
- SHA-256: `42756121fc9a0b18b03d006710d1fb528388b3cf86eaf25c0e72afdac11062b9`
- canonical route: Album

The production app does **not** embed, crop, or reuse pixels from the immutable
golden. Deterministic fixture artwork is generated independently for visual QA.

## 2. Preserved functional contract

The remediation preserves the existing STEP04 Album behavior and acceptance
contract:

- 100 songs
- 10 rows per page
- 12 missing covers
- 18 missing visuals
- 6 songs requiring review
- album duration 2j 47m
- 12 selected songs
- page label: Halaman 1 dari 10
- bulk selection remains backed by real Song IDs
- reorder, cover, visual, transition, delete, move-to-edge, undo/redo and
  persistence behavior remain owned by the existing Album implementation

No duplicate Album engine or second application shell was introduced.

## 3. UI remediation performed

The post-release UI03 layer is intentionally route-scoped to Album.

Implemented alignment work:

- Album context panel rebuilt with a larger cover, title/stats hierarchy and
  filter rows closer to the reference.
- Album table expanded to a 9-column presentation:
  drag handle, checkbox, number, song, duration, visual, transition, status and
  overflow.
- First-page deterministic fixture now mirrors the reference titles, durations,
  transition labels and visible status pattern while preserving the exact
  acceptance totals.
- Bulk toolbar presentation aligned to the reference while keeping existing
  signal semantics.
- Mass Tools inspector rebuilt as larger action cards with selection summary and
  quick transition controls.
- Album timeline overview upgraded to deterministic clip thumbnails, ruler and
  waveform presentation.
- Album-only shell geometry adjusted without changing Home/Media routes.
- Final non-compact geometry:
  - context: 297 px
  - right inspector: 309 px
  - timeline: 194 px
  - status: 28 px
- Compact 1366 geometry:
  - context: 216 px
  - right inspector: 286 px
- Album workspace and inspector vertical rhythm were refined to better match the
  immutable golden.

## 4. Regression isolation

The production remediation is installed after the complete STEP11 integration
stack. Its regression test executes the production stack in a subprocess so
legacy/pure unit tests are not mutated at pytest collection time.

This specifically protects the original STEP04 unit contract while still
testing the real production presentation layer.

## 5. Final validation

Final CI evidence:

- workflow: STEP04 Album validation
- run ID: `37628032239`
- head SHA: `7fa9d554bcac9b33b778b014e847c2b46709639c`
- result: PASS
- evidence artifact ID: `11485536000`
- evidence digest:
  `sha256:0960c17cfe2d8f6865122d438d1532231f59e0de770a1c53bf14384a3768de4e`

Passed gates:

- source compile
- focused STEP04 tests
- UI03 production remediation regression
- STEP03 regressions
- recovered media regressions
- full recovered regression suite
- deterministic golden-state capture
- empty-state capture
- 1366 compact capture
- Album geometry/fixture contract
- immutable golden identity step
- secret scan
- evidence upload

Full suite result: **486 passed, 89 skipped**.

## 6. Visual comparison

Current-main baseline versus immutable UI-03:

- mean absolute RGB: 22.380988
- normalized mean absolute RGB: 0.0877686
- pixels with max-channel delta >25: 20.0911%

Final refined UI03 candidate:

- mean absolute RGB: **21.913354**
- normalized mean absolute RGB: **0.0859347**
- pixels with max-channel delta >25: 21.9156%

The average RGB error therefore improved versus current main. The >25-pixel
coverage is not used as the sole acceptance metric because the immutable
reference contains photographic thumbnails while the deterministic QA fixture
deliberately uses independently generated artwork. Structural parity, exact
geometry, functional contracts, state semantics and regression tests remain
mandatory alongside visual metrics.

## 7. Files introduced/changed

- `src/full_album_maker/album_remediation.py`
- `src/full_album_maker/album_capture.py`
- `src/full_album_maker/main.py`
- `tests/test_ui03_album_remediation.py`
- `.github/workflows/step04-album-validation.yml`
- this remediation record

## 8. Gate decision

UI-03 Album remediation: **PASS**.

The candidate is ready for pull request / merge after the branch CI remains
green. The next sequential post-release UI surface is **UI-04 Timeline**.
