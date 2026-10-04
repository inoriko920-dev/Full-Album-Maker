# STEP 00 Recovery Test Status

Only checks that were actually executed are marked PASS. Historical claims and portable metadata are not converted into test PASS results.

## Final Linux validation candidate

GitHub Actions run: `36970645326` on commit `a297c8367bfe51d945f911d1676b10af1ce921c0`.

| Check | Result | Evidence |
|---|---|---|
| checkout recovery branch | PASS | triggering commit checked out |
| dependency install | PASS | recovered project + dev dependencies installed |
| `python -m compileall -q src` | PASS | executed on runner |
| core imports (`main`, `project`, `project_io`, `timeline`, `controller`, `renderer`, `paths`) | PASS | `CORE_IMPORT_PASS` |
| source vs portable module-name comparison | PASS | 68 exact source modules vs 87 build-evidence names; 20 build-only names |
| high-confidence secret pattern scan | PASS | `SECRET_SCAN_PASS` |
| recovered pytest suite | PASS | **231 passed, 88 skipped in 24.94s** |

The first three validation attempts were retained as audit history rather than hidden: an initial missing editable install, then missing Linux Qt runtime libraries, then two expected canonical recovery-evidence paths not yet restored. After the exact workflow and exact release notes were restored, the final run above passed.

## Windows recovered-source validation

GitHub Actions run: `36970755675` on commit `abd0d0c41909be87c27147ef7b63bc312960765d`, Windows Server 2025, Python 3.12.10.

Result: **FAIL / EXTERNAL BUILD INPUT UNAVAILABLE**.

Executed successfully before failure:

- checkout: PASS
- Python 3.12.10 setup: PASS
- pinned Windows Python dependency installation: PASS

Failure point:

- exact recovered v1.4.0 `build/build_portable.ps1` requested BtbN release asset API ID `595476894`;
- GitHub returned HTTP 404;
- an independent STEP 00 GitHub API probe of that exact asset ID also returned 404.

Therefore the exact historical v1.4.0 Windows build contract is recovered, but it is **not currently reproducible end-to-end without an explicit future update of the external FFmpeg pin**. STEP 00 does not silently alter the exact recovered source to fix that historical external dependency.

Portable v1.4.1 `CAPABILITIES.json` reports a different later FFmpeg input (`release_id` 399159964, `asset_id` 598254888, SHA-256 `11f676f2ee62c39768cef1892e2e171adf00fd04c85620b771520e985e7c7a69`), reinforcing that the v1.4.1 build contract differs from the recovered v1.4.0 source contract.

## Preserved portable v1.4.1 smoke status

The exact preserved portable artifact hash and layout were verified, but the original preserved Windows executable was not uploaded to a Windows runner and was not executed in this STEP 00 environment.

- preserved portable startup: **NOT TESTED**
- preserved portable manual workflow: **NOT TESTED**
- preserved portable preview/render with bundled FFmpeg: **NOT TESTED**
- preserved portable relocation smoke: **NOT TESTED**
- portable metadata/layout/hash: **VERIFIED_FROM_BUILD**

Do not reinterpret the failed recovered-source Windows build as a failure of the already-preserved v1.4.1 portable executable. They are different evidence paths.
