# STEP 01 Baseline Record

Project: **Full Album Maker**  
Repository: `inoriko920-dev/Full-Album-Maker`  
STEP 01 branch: `ui/step-01-foundation`

## 1. Source baseline

STEP 01 inherits the verified recovery baseline established by STEP 00:

- recovery branch: `recovery/step-00-r0`
- STEP 00 recovery HEAD used as branch base: `87860b7281c3c5e9731ccf082dac84ab14624402`
- STEP 00 decision: `READY_FOR_STEP_01_WITH_LIMITATIONS`
- historical `main` baseline recorded by STEP 00: `561970639a7a61d2cea583d6386e8912c9161512`
- exact implementation source baseline: recovered v1.4.0 source
- v1.4.1 portable: behavior/build evidence only; exact v1.4.1 source is not claimed recovered

STEP 01 does not overwrite, relabel, or guess recovery provenance from STEP 00.

## 2. STEP 01 authoritative validated snapshot

The final STEP 01 foundation snapshot passed the authoritative Linux and Windows validation workflow at:

```text
commit: 33aac775a1a4b500aeabea2b268b15ad9b34ad9c
message: docs(ui): mark STEP01 closure
workflow run: 36978745032 (#34)
result: SUCCESS
```

Both jobs completed successfully:

- `validate-foundation` — Ubuntu 24.04 / Python 3.12.14
- `validate-windows-foundation` — Windows Server 2025 / Python 3.12.10

The closure documents `BASELINE.md`, `STEP01_TEST_REPORT.md`, and `HANDOFF_STEP01.md` are excluded from automatic STEP 01 reruns because they only summarize evidence already produced by the validated snapshot. Commits that modify only those closure documents do not supersede the tested runtime snapshot above.

## 3. Frozen visual contract

- golden logical viewport: `1672×941`
- workspace routes: 9
- frozen reference hashes: `docs/ui-reference/manifest.json`
- exact binary references: verified from the ASTRA source document but not committed through the text-oriented GitHub connector
- capture harness: `src/full_album_maker/foundation_capture.py`
- mechanical evidence validator: `tests/step01_validate_evidence.py`
- visual-QA font: pinned Noto Sans is staged by CI and installed through `foundation_font.py`

The manifest is the immutable identity check for the nine references. The harness refuses to resize a supplied golden image to manufacture a match and never uses a reference screenshot as a production background.

## 4. Foundation contract established

STEP 01 establishes one shared application foundation around the recovered application behavior:

- native Windows title chrome plus one shared global command bar;
- exact 9-route navigation contract;
- one workspace stack/registry without rebuilding project state on navigation;
- one shared collapsible right `Properti | AI` dock host;
- one shared per-workspace timeline dock host;
- one event-driven status model for save/FFmpeg/AI/jobs/project context;
- one white-blue design-token source and shared stylesheet/component system;
- pinned Noto Sans visual-QA path with system-font fallback for development when the portable font is absent;
- keyboard/focus/hover/disabled state handling;
- app-local UI preference persistence with corrupt-preference fallback;
- responsive compact navigation at the 1366-class viewport;
- deterministic 1672×941 screenshot/evidence tooling;
- compatibility adapters that reuse the recovered save/open/project/timeline/AI/render infrastructure rather than introducing a second engine.

Final workspace bodies are intentionally **not** part of STEP 01 and remain deferred to STEP 02–10.

## 5. Final validation summary

At tested SHA `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`:

- STEP 01 focused tests Linux: **15 passed**
- recovered Linux regression suite: **246 passed, 88 skipped**
- STEP 01 focused tests Windows: **15 passed**
- source compile: **PASS** on Linux and Windows validation paths
- all nine 1672×941 foundation route captures: **PASS**
- deterministic repeated Home capture: normalized absolute difference **0.0**
- shell landmark validator: **PASS** (`LINUX_STEP01_EVIDENCE_PASS`)
- pinned font gate: **PASS** (`FONT_GATE_PASS Noto Sans`)
- 1366×768 compact capture: **PASS** on Linux and Windows
- 125% DPI capture: **PASS** on Linux and Windows
- 150% DPI capture: **PASS** on Linux and Windows
- high-confidence secret scan: **PASS**
- Linux evidence artifact: `step01-ui-evidence`, ID `11214059138`, size `1,355,315` bytes, SHA-256 `5ff6708d490fb052f26975907391b53970bc64bc7e2109164363ae0e29baf368`
- Windows evidence artifact: `step01-ui-evidence-windows`, ID `11214706528`, size `327,445` bytes, SHA-256 `8664c7e9c50a80d17615a1c27ffec50cf60f82a2baeb66549fb4865764c60952`

Measured 100% golden-view shell landmarks:

| Landmark | Verified value |
| --- | ---: |
| Native title strip | 41 px |
| Title + command region | 96 px |
| Navigation rail | 172 px |
| Right dock | 348 px |
| Bottom status bar | 28 px |
| Home / Render timeline | 34 px |
| Media / Album timeline | 194 px |
| Timeline workspace dock | 352 px |
| Visual timeline | 238 px |
| Template timeline | 158 px |
| Spectrum timeline | 252 px |
| AI Agent timeline | 178 px |

See `STEP01_TEST_REPORT.md` for the AC01–AC20 matrix and `KNOWN_LIMITATIONS.md` for the non-blocking limitations.

## 6. Closure state

STEP 01 decision: **READY_WITH_LIMITATIONS**.

All critical acceptance criteria required by the STEP 01 document pass. The remaining limitations do not block Beranda/STEP 02: exact v1.4.1 source is still unavailable; full final-workspace pixel parity is intentionally deferred; and exact golden PNG binaries are not present inside CI even though their immutable hashes are committed and the harness can consume them externally.
