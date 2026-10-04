# STEP 00 Build / Dependency Recovery

## Exact v1.4.0 source-side contracts recovered

The following were recovered from historical commit `1d52b73e35f9df8272978e7b93a7a8c87896d7bd` and are `VERIFIED_SOURCE` for v1.4.0:

- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `build/build_portable.ps1`
- `build/generate_icon.py`
- `build/requirements-windows.lock`
- `build/write_release_capabilities.py`
- `.github/workflows/build-windows-portable.yml`
- project license / third-party notice files
- release notes and historical build/release documentation

The exact historical Windows workflow was restored at its canonical path with Git blob SHA `d8e8f39ad43052dbeb03df74fac85b1265a2ef02`.

## Recovered Windows dependency lock

Key exact v1.4.0 lock entries include:

- Python target: `3.12.10`
- PySide6: `6.11.2`
- PyInstaller: `6.22.3`
- pytest: `8.4.2`
- Pillow: `11.3.0`
- pip pin in build script: `26.2.1`

These align with the major Python/tool versions reported by portable v1.4.1, but that alignment does not make the v1.4.0 source an exact v1.4.1 source snapshot.

## Exact v1.4.0 build flow recovered

The historical build script/workflow defines a Windows x64 PyInstaller **onedir** portable build, bundles FFmpeg/ffprobe and Noto Sans, runs the regression suite, writes `CAPABILITIES.json`, produces a versioned ZIP + `SHA256SUMS.txt`, and performs an isolated portable smoke path.

## Reproducibility result in STEP 00

The source-side build path is **known**, but the recovered exact historical Windows build cannot currently complete unchanged because its pinned BtbN asset ID `595476894` returns HTTP 404. STEP 00 therefore records:

- build contract recovered: **PASS**
- pinned Python dependency installation on Windows: **PASS**
- current end-to-end v1.4.0 portable rebuild using exact historical external pin: **FAIL / EXTERNAL INPUT UNAVAILABLE**
- change historical FFmpeg pin during STEP 00: **NOT DONE**

The preserved v1.4.1 build report records a later FFmpeg asset and is treated as `VERIFIED_FROM_BUILD`, not copied backward into v1.4.0 source as if it were exact history.
