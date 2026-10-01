# Recovery notes from ChatGPT/Library

Date: 2026-10-01

This repository is a recovery target after the previous GitHub account became unavailable.

## Known previous repositories

- `tonitarung099-creator/Full-Album-Video-Maker`
- later migration: `tonitaru6-cloud/Full-Album-Video-Maker`

## Recovered source structure

ChatGPT Library audit/planning documents record these source paths from the real repository:

- `src/full_album_maker/main.py`
- `src/full_album_maker/project.py`
- `src/full_album_maker/project_io.py`
- `src/full_album_maker/timeline.py`
- `src/full_album_maker/controller.py`
- `src/full_album_maker/playlist_feature.py`
- `src/full_album_maker/visual_feature.py`
- `src/full_album_maker/ui.py`
- `src/full_album_maker/renderer.py`
- `src/full_album_maker/atomic_bundle.py`
- `src/full_album_maker/render_lifecycle.py`
- `src/full_album_maker/project_dirty.py`
- `src/full_album_maker/async_import.py`
- `src/full_album_maker/source_integrity.py`
- `src/full_album_maker/agent_actions.py`
- `src/full_album_maker/paths.py`
- `.github/workflows/build-windows-portable.yml`
- `build/build_portable.ps1`
- `docs/ARCHITECTURE.md`

Recorded test files include `test_visual_feature.py`, `test_ai_playlist_feature.py`, `test_atomic_render_bundle.py`, `test_source_integrity.py`, `test_ui_layout.py`, `test_renderer_integration.py`, `test_project_dirty_state.py`, and `test_async_import.py`.

## Known historical commits/evidence

- audit baseline: `bb5f8c397a1bf820c6b44e141da21455478c3528`
- later planning baseline: `6ac77f197a4161cd108678d936c84f983e53e1ba`
- later history records a v1.4.1 release on migrated repo, with release commit beginning `809b4d1` and Windows build #104 reported successful.

## Portable artifact recovered

Recovered archive: `Full-Album-Maker-Windows-Portable.zip`.

Inner archive `Full-Album-Maker-v1.4.1-Windows-Portable.zip` SHA-256:

`b0d571692f925296022f146c39dce388b4717a43417e7f80132bd3aa52a9d853`

The portable package is a build artifact, not a complete source snapshot. Do not treat bundled runtime/DLL/FFmpeg files as reconstructed source.

## Recovery rule

Do not rebuild from scratch until all surviving ChatGPT Library documents, local clones, ZIPs, and any restored GitHub access have been checked. Any reconstructed source should be compared against the recovered portable behavior and historical tests.
