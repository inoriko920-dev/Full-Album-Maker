# STEP 00 Security / License / Secret Status

## Secret scan

Final Linux recovery validation executed a high-confidence scan over `src/`, `tests/`, `build/`, `assets/`, `docs/`, and `.github/` for private-key blocks and common GitHub/Google/AWS/OpenAI-style credential patterns.

Result: **PASS — no high-confidence secret candidate found**.

This is a targeted recovery gate, not a claim that regex scanning can prove the total absence of every possible secret format. No `.env`, PEM/key, credential JSON, API key, cookie, or user-local private path was intentionally committed during STEP 00.

## Project license

Recovered exact v1.4.0 source contains an **MIT License** (`LICENSE`, Git blob `fb5d612341578a229707a3c87290d218cb77f39e`).

## Third-party notices recovered

`THIRD_PARTY_NOTICES.md` is present and records separate obligations for:

- FFmpeg / BtbN GPL static build used for libx264/libx265;
- Noto Sans under SIL Open Font License 1.1;
- PySide6 / Qt under their separate licensing terms.

The portable also contains `LICENSE.txt`, `THIRD_PARTY_NOTICES.md`, `FFMPEG-LICENSE.txt`, and the Noto Sans OFL file as build evidence.

## Build-contract conflict requiring future review

There is a genuine evidence difference that STEP 00 does not hide or auto-resolve:

- recovered exact v1.4.0 `THIRD_PARTY_NOTICES.md` records FFmpeg release ID `397659030`, asset ID `592976307`, SHA-256 `b745ed683204c8e154d627bf75f2e530b7b2eec51d14fabdc8771912423ba67e`;
- recovered exact v1.4.0 build script/workflow requests asset ID `595476894` with SHA-256 `e6db684f1527f4c2280b017c7af19ebd359424eee8b35974bc35b4d7ee110989`;
- preserved portable v1.4.1 `CAPABILITIES.json` reports still another later input: release ID `399159964`, asset ID `598254888`, SHA-256 `11f676f2ee62c39768cef1892e2e171adf00fd04c85620b771520e985e7c7a69`.

The v1.4.0 Windows validation additionally proved asset ID `595476894` now returns HTTP 404. This is recorded as an external build-input limitation, not silently rewritten during STEP 00.

## STEP 00 security decision

- secret gate: **PASS** for executed high-confidence scan;
- project license present: **PASS**;
- third-party notices present: **PASS**;
- third-party/build-pin consistency: **NEEDS REVIEW / LIMITATION** before a future release pipeline is treated as reproducible.
