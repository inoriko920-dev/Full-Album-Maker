# Full Album Maker v1.5.0

## Reliability fixes

- Unifies STEP11 ProjectDocument/EditorSession as the authoritative save/dirty/close lifecycle.
- Prevents duplicate close/save prompts from the legacy compatibility envelope.
- Saves through a staged same-filesystem file, verifies authoritative ProjectDocument state before publish, then atomically replaces the canonical project file.
- Preserves the opened project path so normal Save targets the same file without an unnecessary Save As dialog.
- Makes portable release smoke construct the same FoundationMainWindow factory used by the production entrypoint and exercises the primary workspaces.
- Synchronizes release identity to v1.5.0 while preserving the documented v1.4.1 recovery provenance.

## Release gate

The release is valid only after the full regression suite, real FFmpeg checks, Windows PyInstaller portable build, extracted-ZIP smoke, checksum generation, and production-window smoke pass.
