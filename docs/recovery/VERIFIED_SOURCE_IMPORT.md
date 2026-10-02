# VERIFIED_SOURCE import — legacy v1.4.0

- Source repository: `tonitarung099-creator/Full-Album-Video-Maker`
- Source commit: `1d52b73e35f9df8272978e7b93a7a8c87896d7bd`
- Source branch observed before recovery: `main`
- Source commit message: `feat: publish Full Album Maker v1.4.0 Gemini AI parity`
- Provenance: `VERIFIED_SOURCE` for files copied from this commit.
- Important limitation: portable v1.4.1 reports build commit `809b4d130c30f12e9df272395c2dd85941931c24`; that commit was not reachable in the public legacy repository during STEP 00. Therefore this import is an exact v1.4.0 source baseline, not a claim of exact v1.4.1 source.

## Imported groups

`src/`, `tests/`, `build/`, `assets/`, dependency/project metadata present at the source commit, and historical docs/build-workflow evidence under `docs/legacy-source-v1.4.0/`.

## Canonical build/release evidence restored later in STEP 00

The initial import preserved the historical Windows workflow under `docs/legacy-source-v1.4.0/` because the source-recovery workflow token could not create workflow files. STEP 00 later restored the exact historical workflow directly at `.github/workflows/build-windows-portable.yml` and verified its Git blob SHA as `d8e8f39ad43052dbeb03df74fac85b1265a2ef02`, matching the legacy source commit. The exact `docs/RELEASE_NOTES_v1.4.0.md` was also restored with Git blob SHA `6ead220a0df7eb7047bd82f7fe29a0e0f14bec3a`.

These restorations do not upgrade the recovered application to v1.4.1; they complete the exact v1.4.0 source/build baseline only.
