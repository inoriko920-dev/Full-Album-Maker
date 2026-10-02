# STEP 00 Source Provenance

## Canonical baseline decision

The best exact source located during STEP 00 is the historical public repository `tonitarung099-creator/Full-Album-Video-Maker` at commit `1d52b73e35f9df8272978e7b93a7a8c87896d7bd` (`feat: publish Full Album Maker v1.4.0 Gemini AI parity`). Files imported from that commit are `VERIFIED_SOURCE` for v1.4.0.

The preserved portable reports v1.4.1 and build commit `809b4d130c30f12e9df272395c2dd85941931c24`. That commit was searched directly and was not reachable in the available historical repository. Therefore the recovered v1.4.0 source MUST NOT be relabeled as v1.4.1 source.

| Evidence group | Version / commit | Provenance | Confidence | Action | Notes |
|---|---|---|---|---|---|
| `src/full_album_maker/` recovered from historical commit | v1.4.0 / `1d52b73...` | `VERIFIED_SOURCE` | HIGH | KEEP | Exact Git source snapshot |
| `tests/` recovered from historical commit | v1.4.0 / `1d52b73...` | `VERIFIED_SOURCE` | HIGH | KEEP | Historical tests, not recreated |
| `build/` recovered from historical commit | v1.4.0 / `1d52b73...` | `VERIFIED_SOURCE` | HIGH | KEEP | Force-tracked because historical `.gitignore` ignores `build/` |
| `.github/workflows/build-windows-portable.yml` | v1.4.0 / `1d52b73...` | `VERIFIED_SOURCE` | HIGH | KEEP | Restored byte-identically; Git blob `d8e8f39ad43052dbeb03df74fac85b1265a2ef02` |
| `docs/RELEASE_NOTES_v1.4.0.md` | v1.4.0 / `1d52b73...` | `VERIFIED_SOURCE` | HIGH | KEEP | Restored byte-identically; Git blob `6ead220a0df7eb7047bd82f7fe29a0e0f14bec3a` |
| Portable `CAPABILITIES.json`, executable layout, runtime files | v1.4.1 / build `809b4d1...` | `VERIFIED_FROM_BUILD` | HIGH for observed build metadata | DO_NOT_IMPORT_AS_SOURCE | Behavior/build evidence only |
| 87 portable module names | v1.4.1 build evidence | `VERIFIED_FROM_BUILD` | HIGH for names, LOW for implementation | KEEP AS EVIDENCE | Names do not prove source contents |
| Recovery plans/chat/package docs | mixed | `RECONSTRUCTED_FROM_DOCS` / docs evidence | MEDIUM | KEEP IN RECOVERY DOCS ONLY | Planned does not mean implemented |
| Decompiled application source | none imported | `DECOMPILED_FROM_BUILD` | N/A | DO_NOT_IMPORT | Exact source search took precedence; no decompiled code mixed into `src/` |
| Reconstructed application modules | none imported | `RECONSTRUCTED_FROM_BEHAVIOR` / `RECONSTRUCTED_FROM_DOCS` | N/A | DO_NOT_IMPORT IN STEP 00 | Missing modules were not recreated from names/plans |

## Exact v1.4.0 source vs v1.4.1 portable module-name evidence

Executed comparison on the final Linux validation candidate:

- exact v1.4.0 source modules: **68**
- portable v1.4.1 module names: **87**
- module names present in v1.4.1 build evidence but without exact v1.4.0 source: **20**
- source-only item in v1.4.0 comparison: `full_album_maker.main`

The following 20 names are NOT reconstructed in STEP 00. Their source status remains `UNKNOWN`; only the fact that the names occur in v1.4.1 build evidence is `VERIFIED_FROM_BUILD`:

- `full_album_maker.advanced_feature_dialog`
- `full_album_maker.approved_ui_geometry`
- `full_album_maker.canonical_shell_adapter`
- `full_album_maker.pixel_reference_ui`
- `full_album_maker.reference_geometry_guard`
- `full_album_maker.reference_media_import`
- `full_album_maker.reference_ui`
- `full_album_maker.reference_visual_polish`
- `full_album_maker.sol_ai_status`
- `full_album_maker.sol_av_preview`
- `full_album_maker.sol_editor_extensions`
- `full_album_maker.sol_interactive_chrome`
- `full_album_maker.sol_property_controls`
- `full_album_maker.sol_real_media_visuals`
- `full_album_maker.sol_responsive_accessibility`
- `full_album_maker.sol_slowmo`
- `full_album_maker.sol_transport_navigation`
- `full_album_maker.sol_v13_render_graph`
- `full_album_maker.sol_workspace_hardening`
- `full_album_maker.ui_font`

The complete 87-name build-evidence list is stored in `docs/recovery/PORTABLE_V1_4_1_MODULES.txt`.
