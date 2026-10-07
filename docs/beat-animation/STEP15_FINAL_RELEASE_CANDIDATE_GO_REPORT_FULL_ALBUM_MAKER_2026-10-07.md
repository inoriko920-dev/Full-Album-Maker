# STEP 15 — Final Release Candidate GO Report

## Decision
**GO**

All STEP15 technical gates G1-G10 passed on the clean Windows release-candidate workflow.

- Release candidate: `v1.6.0 RC1`
- Tested source commit: `ccbd8f3a9d2b5b98942e0bfd939c464c7cb4db5a`
- Stable main: `584c94774e6197ecf60ecedb3bffd5a8797e7737` (v1.5.0)
- GitHub Actions run: `37618681554` — SUCCESS
- Full regression: **955 passed**
- Artifact: `Full-Album-Maker-v1.6.0-RC1-Windows-Portable`
- Artifact ID: `11481790505`
- Artifact size: `299,726,591 bytes`
- Artifact digest: `sha256:b404c1018a75840b601274feeba6bd38a9e6879c2250e8467674ddcd2bea00d9`
- RC ZIP SHA256: `e3c815a28e12ebeb09e43146344dadda0d815d3b5f3dce414e3e3cbc78355438`
- Artifact expiry: 2026-11-06

## Final gate evidence
1. Version identity 1.6.0 — PASS.
2. Exact Windows dependency install + pip check — PASS.
3. Full compile + repository pytest suite — **955 passed**.
4. Source-level Beat V2 export smoke — PASS.
5. Clean PyInstaller onedir build — PASS.
6. Portable runtime/assets/capabilities bundle — PASS.
7. RC ZIP + checksum — PASS.
8. Extracted ZIP smoke in Unicode + spaces + apostrophe path — PASS.
9. No global Python, no global FFmpeg, no Gemini/Google API key — PASS.
10. Frozen `--beat-runtime-smoke` — PASS.
11. Frozen `--beat-export-smoke` — PASS.
12. RC provenance manifest source/checksum/main verification — PASS.
13. Artifact upload/finalize — PASS.
14. Workflow emitted `STEP15_GO`.

## Release-blocking bug fixed during RC
Earlier RC runs exposed an FFmpeg filter-path escaping failure when the extracted application path contained an apostrophe, e.g. `O'Brien`. The fix centralizes filter-option path escaping for Beat, Spark, Beat Text, and drawtext paths. Final evidence is the successful frozen Beat V2 export from the extracted apostrophe path, not only a unit test.

## Publication state
The following actions are intentionally **not** performed by STEP15:
- no merge to `main`;
- no `v1.6.0` tag;
- no public GitHub Release;
- stable v1.5.0 remains intact.

Recommended next action: download and manually test RC1 on Windows 11. If manual validation is satisfactory, perform a controlled merge to main, run the stable Windows build workflow, then publish v1.6.0.
