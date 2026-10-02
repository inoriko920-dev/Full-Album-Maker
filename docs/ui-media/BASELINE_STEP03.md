# STEP 03 — Media Library Baseline

Repository: `inoriko920-dev/Full-Album-Maker`
Baseline branch: `ui/step-02-beranda`
Baseline HEAD: `c0c4baefcf2394095c8a26dbbd045360e4f5e67e`
Validated STEP 02 implementation: `ec380f355dc12a4193285428068c84e98b68f8c1`
STEP 01 rollback: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`

## Gate evidence

- STEP 02 CI run `36985869444`: success.
- Existing recovered media engine is reused: `media.py`, `async_import.py`, `Project`, `visual_feature.images(project)`.
- STEP 03 does not introduce a second application shell.
- Media route already exists as stable route ID `media`.
- Shared timeline contract already assigns Media a 194 px expanded timeline target.

## Golden provenance

The STEP 03 DOCX contains two 1672×941 PNGs:

- clean Media golden: `image1.png`, SHA-256 `3c17c23a8bd88191ca94d4b7ae8257c404e7bc26398ba0ead5d1bbee4619f4a8`
- annotated region map: `image2.png`, SHA-256 `f29da7bf6ef533093527c2f33739e3d2966883847d991d716c19baf16308c367`

The STEP 01 canonical manifest declares `02-media.png` SHA-256:
`117572570f900d7f25e2fd0dc822bd59c4496dcc6f23bfb9af8cb8b9d10aa3a5`.

The embedded clean DOCX golden does not match that declared canonical binary. The embedded clean image remains valid visual evidence, but exact canonical binary PASS must not be claimed unless the canonical binary becomes available.

## Architecture decision for S03-02 onward

- Project `videos`, `audios`, and recovered `visual_feature.images(project)` remain the media source of truth.
- Search/filter/sort/selection operate over an in-memory projection and never scan disk per interaction.
- STEP 03 UI-only metadata (favorite, tags, description, logical collections, imported_at) uses an optional atomic sidecar `<project>.json.media.json`, avoiding a recovered project-schema version change.
- Sidecar does not store source media bytes and default import never moves/deletes source files.
- Unsaved/recovery-only projects keep metadata in memory until a stable project path exists; persistence in that state must not be represented as saved.
- Missing source paths remain indexed and may be relinked.
- Heavy probe/import/thumbnail work must remain off the QWidget/UI thread and stale results must be rejected.

## Local staging validation

Before first GitHub write, pure STEP 03 model/service tests run in staging:

`7 passed`

This is not a substitute for repository CI; it only validates the dependency-light projection, selection, sidecar, source-mutation safety and folder-scan contracts before remote integration.
