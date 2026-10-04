# STEP 12 — QA, Windows Portable, dan Release Gate

## Entry state

- Repository: `inoriko920-dev/Full-Album-Maker`
- Branch: `release/step-12-qa`
- STEP 11 handoff commit: `c40685e912b7c27d6c08c58465f0198e76c51451`
- Validated STEP 11 implementation: `7f9d6766bd2d03bc60d4b6da29ddefc2dc3388b9`
- STEP 11 decision: `READY_WITH_LIMITATIONS`
- Application version at STEP 12 entry: `1.4.0`

STEP 12 is a release-validation phase. It must not redesign the editor architecture or create a second project-state owner.

## Preserved contracts

The following STEP 11 contracts remain release blockers if violated:

- one authoritative `ProjectDocument` state;
- one global command/history owner;
- stable-ID shared selection;
- typed non-reentrant domain events;
- autosave only from committed revisions;
- recovery is separate from canonical Save;
- shared preview/session ownership with stale-result guards;
- AI actions use normal action/command contracts;
- Render consumes immutable project snapshots;
- normalized Save/Reopen equality;
- no workspace-local duplicate project truth.

## Release gates

STEP 12 must prove on the exact candidate head:

1. full recovered regression suite is green;
2. 200-song / 3-hour Packed and Free resolver/compile gates are green;
3. pinned Windows FFmpeg accepts the external `-/filter_complex` script path used by S12;
4. PyInstaller one-folder build succeeds on `windows-2025` with Python `3.12.10`;
5. FFmpeg/ffprobe, Noto Sans, licenses/notices, assets, writable folders and `CAPABILITIES.json` are included;
6. the versioned ZIP is created and SHA-256 is recorded;
7. the *extracted ZIP*, not raw `dist/`, launches from a path containing spaces, Unicode and an apostrophe;
8. extracted portable smoke runs without global Python, global FFmpeg, Gemini key or Google API key;
9. portable smoke verifies rendered output contains audio + video;
10. release evidence and portable artifact are uploaded by CI.

## UI golden evidence

The repository contains `docs/ui-reference/manifest.json` but not the nine immutable golden PNG binaries. Therefore pixel overlays/diffs must remain `LOCAL_PENDING` unless the exact binaries are supplied and each SHA-256 matches the manifest first. No replacement golden image may be fabricated from current application output.

## Version and publication policy

STEP 12 starts without changing `__version__` and without publishing a GitHub Release. Version bump/tag/release publication may only happen after the QA candidate is green and the release version is explicitly selected.

## Initial status

`QA_RUNNING`
