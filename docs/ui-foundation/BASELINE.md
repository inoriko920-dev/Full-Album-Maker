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

## 2. STEP 01 final validated implementation point

The foundation implementation and its finalized limitation record passed the authoritative Linux and Windows workflow at:

```text
commit: 0bd0aa3769b2913900d6ba169b70bffff1d674ba
message: docs(ui): finalize STEP01 known limitations after Windows gate
workflow run: 36978076538 (#24)
result: SUCCESS
```

Both jobs completed successfully:

- `validate-foundation` — Ubuntu 24.04 / Python 3.12.14
- `validate-windows-foundation` — Windows Server 2025 / Python 3.12.10

The runtime code immediately preceding this documentation closure is unchanged by the final limitation-record commit. The three closure documents `BASELINE.md`, `STEP01_TEST_REPORT.md`, and `HANDOFF_STEP01.md` are intentionally excluded from reruns by the STEP 01 workflow because they summarize already-produced evidence rather than modify runtime behavior.

## 3. Frozen visual contract

- golden logical viewport: `1672×941`
- workspace routes: 9
- frozen reference hashes: `docs/ui-reference/manifest.json`
- exact binary references: verified from the ASTRA source document but not committed through the text-oriented GitHub connector
- capture harness: `src/full_album_maker/foundation_capture.py`
- mechanical evidence validator: `tests/step01_validate_evidence.py`

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
- keyboard/focus/hover/disabled state handling;
- app-local UI preference persistence with corrupt-preference fallback;
- responsive compact navigation at the 1366-class viewport;
- deterministic 1672×941 screenshot/evidence tooling;
- compatibility adapters that reuse the recovered save/open/project/timeline/AI/render infrastructure rather than introducing a second engine.

Final workspace bodies are intentionally **not** part of STEP 01 and remain deferred to STEP 02–10.

## 5. Final validation summary

At tested SHA `0bd0aa3769b2913900d6ba169b70bffff1d674ba`:

- STEP 01 focused tests Linux: **15 passed**
- recovered Linux regression suite: **246 passed, 88 skipped**
- STEP 01 focused tests Windows: **15 passed**
- source compile: **PASS** on Linux and Windows validation paths
- all nine 1672×941 foundation route captures: **PASS**
- deterministic repeated Home capture: normalized absolute difference **0.0**
- shell landmark validator: **PASS**
- 1366×768 compact capture: **PASS** on Linux and Windows
- 125% DPI capture: **PASS** on Linux and Windows
- 150% DPI capture: **PASS** on Linux and Windows
- high-confidence secret scan: **PASS**
- Linux evidence artifact: `step01-ui-evidence`, ID `11213948740`, SHA-256 `239fd0c4b6661b765edbcbbc2bf15965132910e7556e9ed4d0bdcbaa959cef19`
- Windows evidence artifact: `step01-ui-evidence-windows`, ID `11214850767`, SHA-256 `6ca8c179250286e783a93f3d3c677d8e9dfcae5a9d0f1c7afb21e1db5c240245`

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
