# Third-party notices

## FFmpeg

Windows portable builds bundle the GPL x86_64 variant from BtbN/FFmpeg-Builds because Full Album Maker uses libx264/libx265 and FFmpeg filter functionality.

Release input currently pinned by the Windows workflow:
- Provider: `BtbN/FFmpeg-Builds`
- Release tag: `autobuild-2026-10-03-18-14`
- Asset: `ffmpeg-N-127142-g12b7b9891b-win64-gpl.zip`
- SHA-256: `a885f564dee2b60f69ab866c6c89b96ae531fc2ee1f24ff8b5b1a6d29960a96b`

The build verifies the digest before extraction and copies upstream license/readme files into the portable folder when available.

## Noto Sans

The portable build includes Noto Sans as deterministic fallback font.
- Source: `google/fonts`
- Pinned commit: `23e54b51ddffbc7713c583748e3bd86f62b1fa4a`
- License: SIL Open Font License 1.1

## PySide6 / Qt

The desktop UI uses PySide6 / Qt. Their licensing terms are separate from the MIT license of Full Album Maker. Windows builds pin PySide6 `6.11.2`.

## Beat Analysis scientific runtime

Beat Animation V2 bundles a Python scientific/audio-analysis runtime in the Windows onedir build. Key direct/runtime packages include:
- librosa 1.0.0 — ISC
- NumPy 2.5.3 — BSD-3-Clause
- SciPy 1.18.1 — BSD-3-Clause
- scikit-learn 1.9.1 — BSD-3-Clause
- Numba 0.68.0 and llvmlite 0.50.0 — BSD-family upstream licenses
- SoundFile 0.14.0 — BSD-family upstream license
- python-soxr 1.1.0 and its bundled/native components — upstream license terms apply
- joblib, pooch, cffi, requests and transitive runtime packages — upstream licenses apply

These components are third-party software and are not covered by Full Album Maker's MIT license. Before redistribution, retain the license metadata/files shipped by the corresponding wheels and review their upstream terms. STEP14 release gates verify exact package pins and frozen-runtime functionality.
