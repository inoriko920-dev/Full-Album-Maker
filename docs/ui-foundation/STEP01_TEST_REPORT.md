# STEP 01 Test Report

Status: **PASS — READY_WITH_LIMITATIONS**

Authoritative validation:

- branch: `ui/step-01-foundation`
- tested SHA: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`
- GitHub Actions run: `36978745032` (run #34)
- Linux job: **PASS**
- Windows Server 2025 job: **PASS**

The decision is `READY_WITH_LIMITATIONS`, not an unqualified final pixel-match claim. STEP 01 intentionally validates the shared foundation while the nine workspace bodies remain controlled placeholders. Exact multi-megabyte golden PNG binaries are frozen by SHA-256 but are not checked into this text-oriented branch/CI; final full-workspace raster parity remains a later workspace/integration gate.

## 1. Validation environments

### Linux CI

- Ubuntu 24.04.5 LTS
- Python 3.12.14
- PySide6 6.11.2
- `QT_QPA_PLATFORM=offscreen`
- pinned Noto Sans staged before visual QA capture
- 100%, 125%, 150%, 1366×768, and all-nine-route capture gates

### Windows CI

- Windows Server 2025
- Python 3.12.10
- PySide6 6.11.2
- pinned Noto Sans staged before visual QA capture
- 100%, 125%, 150%, and 1366×768 compact-state validation

## 2. Automated results

| Gate | Result |
|---|---|
| Frozen 9-reference manifest | PASS |
| Compile `src/` | PASS |
| STEP 01 focused tests — Linux | **15 passed** |
| Full recovered regression — Linux | **246 passed, 88 skipped** |
| STEP 01 focused tests — Windows | **15 passed** |
| 9 route captures at 1672×941 | PASS |
| Deterministic repeated Home capture | PASS — normalized absolute difference **0.0** |
| Pinned font gate | PASS — `FONT_GATE_PASS Noto Sans` |
| 1366×768 compact gate | PASS — Linux + Windows |
| 125% DPI | PASS — Linux + Windows |
| 150% DPI | PASS — Linux + Windows |
| Linux landmark/evidence validator | PASS — `LINUX_STEP01_EVIDENCE_PASS` |
| Windows geometry gate | PASS — `WINDOWS_STEP01_GATE_PASS` |
| High-confidence secret scan | PASS — `SECRET_SCAN_PASS` |
| Portable/app-local resource-path test | PASS |

## 3. Measured shared-shell landmarks

At the 1672×941 / 100% foundation gate:

| Landmark | Measured |
|---|---:|
| Native title strip | 41 px |
| Title + command region | 96 px |
| Navigation rail | 172 px |
| Right dock | 348 px |
| Status bar | 28 px |
| Home / Render timeline | 34 px |
| Media / Album timeline | 194 px |
| Timeline workspace dock | 352 px |
| Visual timeline | 238 px |
| Template timeline | 158 px |
| Spectrum timeline | 252 px |
| AI Agent timeline | 178 px |

The 1366×768 capture reports a 72 px compact navigation rail with labels available through tooltips. The 100% capture report also records `font_family: Noto Sans`.

## 4. Acceptance criteria AC01–AC20

The STEP 01 specification marks AC01, AC02, AC04, AC05, AC06, AC07, AC08, AC09, AC10, AC14, AC15, AC16, AC17 and AC18 as critical. None fail.

| ID | Status | Evidence / interpretation |
|---|---|---|
| AC01 | **PASS** | White-blue production foundation window launches in focused Linux/Windows validation without fatal error. |
| AC02 | **PASS** | Exact requested 1672×941 capture is repeatable; repeat diff is 0.0. |
| AC03 | **PASS** | Native-title evidence + global command hierarchy are present and measured. |
| AC04 | **PASS** | Nine routes exist in exact required order; selected/focus/keyboard behavior is tested. |
| AC05 | **PASS** | Workspace switch reuses shared stack/project state; no project reset. |
| AC06 | **PASS** | Shared `Properti | AI` dock exists, switches tab, collapses, and restores safely. |
| AC07 | **PASS** | Shared timeline host collapses/expands and uses per-workspace heights; preference schema persists state. |
| AC08 | **PASS** | Status bar observes `FoundationUiState` events for save/FFmpeg/AI/jobs/project context. |
| AC09 | **PASS** | Foundation colors/geometry/spacing/radii/breakpoints are centralized in `foundation_tokens.py`; pinned visual-QA font is installed by `foundation_font.py`. |
| AC10 | **PASS** | Reusable controls and shell states are covered by the focused suite. |
| AC11 | **PASS** | STEP 01 itself introduces no background scan/render/AI work during route/layout/status operations; heavy recovered actions remain explicit user actions. |
| AC12 | **PASS** | 100/125/150% states complete on both CI platforms; 100% remains the golden gate. |
| AC13 | **PASS** | 1366×768 compact state remains usable; main navigation is not permanently lost. |
| AC14 | **PASS WITH DOCUMENTED LIMITATION** | Structural shell landmark validator passes and deterministic overlay/diff machinery is proven. Exact whole-window overlays against external finished-workspace PNGs are not claimed in CI. |
| AC15 | **PASS** | Final workspace bodies are not hard-coded into the shared shell. |
| AC16 | **PASS** | Secret scan passes; no API keys/personal absolute paths were introduced. |
| AC17 | **PASS** | Open/save adapters reuse recovered behavior; the full recovered regression suite remains green. |
| AC18 | **PASS** | Portable resources remain app-relative. |
| AC19 | **PASS** | Required docs plus Linux/Windows evidence packs exist; external golden-binary limitation is explicit. |
| AC20 | **PASS** | `HANDOFF_STEP01.md` records the closure decision and concrete STEP 02 entry task. |

## 5. Evidence artifacts

Run `36978745032` produced:

- `step01-ui-evidence`
  - artifact ID: `11214059138`
  - size: `1,355,315` bytes
  - SHA-256: `5ff6708d490fb052f26975907391b53970bc64bc7e2109164363ae0e29baf368`
  - contains all nine current foundation PNGs, 1366 capture, 125/150% captures, JSON reports, deterministic repeat overlay/diff, and Noto Sans font evidence in the reports.
- `step01-ui-evidence-windows`
  - artifact ID: `11214706528`
  - size: `327,445` bytes
  - SHA-256: `8664c7e9c50a80d17615a1c27ffec50cf60f82a2baeb66549fb4865764c60952`
  - contains Windows 100/125/150% plus 1366×768 evidence and reports.

## 6. Pixel-match scope at STEP 01

The screenshot harness uses the exact requested logical viewport at 100%, never rescales a supplied golden to manufacture a match, and models native title chrome only in offscreen evidence because production uses the real Windows title bar. Whole-image diff against the completed Beranda/Media/etc. golden references is expected to be large while their centers are intentional placeholders. Therefore STEP 01 claims **shared-shell foundation parity**, not completion of STEP 02–10 workspace content.

## 7. Remaining limitations and final decision

The exact v1.4.1 source is still unavailable; the historical FFmpeg download pin remains a later packaging/release issue; exact golden PNG binaries are external to CI; and final real-Windows full-workspace raster validation remains a later integration/release gate. These limitations are non-blocking for Beranda.

**Final decision: READY_WITH_LIMITATIONS.**

Closure-document commits made after tested SHA `33aac775a1a4b500aeabea2b268b15ad9b34ad9c` only update the evidence summary/handoff and do not modify the validated foundation runtime.
