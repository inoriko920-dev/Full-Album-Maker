# STEP 01 Test Report

Status: **PASS — READY_WITH_LIMITATIONS**

Authoritative validation:

- branch: `ui/step-01-foundation`
- validated candidate: `084808da876d2bfd8a72764e7951515578a1a995`
- GitHub Actions run: `36977769859` (run #23)
- Linux job: **PASS**
- Windows job: **PASS**

The decision is `READY_WITH_LIMITATIONS`, not `READY_FOR_STEP_02` without qualification, because the exact multi-megabyte external golden PNG binaries are not checked into the branch/CI. Structural shell landmarks, deterministic screenshot generation, responsive states, DPI states, and Windows validation pass; exact whole-window pixel overlay against all frozen external golden PNGs remains an external final comparison.

## 1. Validation environments

### Linux CI

- Ubuntu 24.04.5 LTS
- Python 3.12.14
- PySide6 6.11.2
- `QT_QPA_PLATFORM=offscreen`
- `QT_SCALE_FACTOR=1` for the 100% gate, with explicit 1.25 and 1.5 DPI captures

### Windows CI

- Windows Server 2025
- Python 3.12.10
- PySide6 6.11.2
- `QT_QPA_PLATFORM=offscreen`
- 100%, 125%, 150%, and 1366×768 compact-state validation

## 2. Automated results

| Gate | Result | Evidence |
|---|---|---|
| Golden manifest integrity | PASS | Frozen viewport `1672×941`, 9 unique reference hashes |
| Source compile | PASS | `python -m compileall -q src` |
| STEP 01 focused tests — Linux | PASS | **15 passed** |
| Full recovered regression — Linux | PASS | **246 passed, 88 skipped** |
| STEP 01 focused tests — Windows | PASS | **15 passed** |
| 9 route captures at golden viewport | PASS | Home, Media, Album, Timeline, Visual, Template, Spectrum, AI Agent, Render |
| Deterministic repeat capture | PASS | Home repeat normalized absolute difference **0.0** |
| 1366×768 compact gate | PASS | Compact navigation width measured at 72 px |
| 125% DPI gate | PASS | Linux + Windows |
| 150% DPI gate | PASS | Linux + Windows |
| Landmark/evidence validator | PASS | `LINUX_STEP01_EVIDENCE_PASS` |
| Windows geometry gate | PASS | `WINDOWS_STEP01_GATE_PASS` |
| High-confidence secret scan | PASS | `SECRET_SCAN_PASS` |
| Evidence artifact upload | PASS | Linux and Windows evidence archives uploaded |

## 3. Measured shell landmarks at 1672×941

The deterministic 100% captures report these shared-shell measurements:

| Landmark | Measured |
|---|---:|
| Native-title evidence height | 41 px (`title_bottom=40`) |
| Command bar bottom | y=95 |
| Navigation width | 172 px (`nav_right=171`) |
| Right dock width | 348 px |
| Status bar height | 28 px |
| Home timeline | 34 px |
| Media timeline | 194 px |
| Album timeline | 194 px |
| Timeline workspace timeline | 352 px |
| Visual timeline | 238 px |
| Template timeline | 158 px |
| Spectrum timeline | 252 px |
| AI Agent timeline | 178 px |
| Render timeline | 34 px |

The 1366×768 capture reports `nav_right=71`, corresponding to the intended 72 px compact navigation rail.

## 4. Acceptance criteria AC01–AC20

| ID | Status | Result |
|---|---|---|
| AC01 | PASS | White-blue app shell launches in automated Qt validation without fatal error. |
| AC02 | PASS | 1672×941 capture is repeatable; repeated Home capture produced normalized absolute difference 0.0. |
| AC03 | PASS | Native-title evidence and shared command-bar hierarchy are present and measured by the screenshot harness. |
| AC04 | PASS | All 9 navigation routes exist in the exact required order; selected/focus/keyboard behavior is covered by tests. |
| AC05 | PASS | Workspace switching preserves shared project state; production fixture test verifies the same project object remains active. |
| AC06 | PASS | Shared `Properti | AI` right dock exists and collapse/expand behavior is tested. |
| AC07 | PASS | Shared timeline host supports workspace-specific height and collapse/expand; preference persistence is covered. |
| AC08 | PASS | Status bar observes `FoundationUiState` events rather than direct workspace-widget coupling. |
| AC09 | PASS | Main colors, dimensions, spacing, radius, and breakpoints are centralized in `foundation_tokens.py`. |
| AC10 | PASS | Reusable foundation controls and their relevant shell states are exercised by the focused suite. |
| AC11 | PASS | STEP 01 introduces no blocking render/AI/heavy-work path on the foundation UI thread; workspace content remains controlled placeholders. |
| AC12 | PASS | 100%, 125%, and 150% DPI screenshot states complete on Linux and Windows CI. |
| AC13 | PASS | 1366×768 compact state passes on Linux and Windows; navigation remains usable through icon/tooltips. |
| AC14 | PASS_WITH_LIMITATION | Structural shell landmark gates pass after tuning and deterministic overlay/diff machinery is proven. Exact whole-window comparison against the external frozen PNG binaries is not executed in CI because those binary payloads are not checked into this branch. |
| AC15 | PASS | Final workspace contents are not hard-coded into the shell; STEP 02–10 bodies remain placeholders. |
| AC16 | PASS | High-confidence secret scan passes; no personal path/API key is intentionally hard-coded. |
| AC17 | PASS | Save/open adapters are covered and the full recovered regression suite passes. |
| AC18 | PASS | Portable resource-path test confirms app-relative resource resolution. |
| AC19 | PASS | Linux and Windows evidence packs were successfully uploaded by the authoritative CI run. |
| AC20 | PASS | `HANDOFF_STEP01.md` records the final decision and explicit limitations. |

## 5. Evidence artifacts

Authoritative run `36977769859` produced:

- `step01-ui-evidence`
  - artifact id: `11213744092`
  - files: 28
  - size: 1,418,167 bytes
  - SHA-256: `000d9f812c826d2c3eaf1ad3d9a5ab1b5fb23d8a620619ee23a409bd02fbcb74`
  - includes `ui-golden/current/`, `ui-golden/diff/`, and `ui-golden/reports/`
- `step01-ui-evidence-windows`
  - artifact id: `11213354895`
  - files: 8
  - size: 111,487 bytes
  - SHA-256: `dd478dbe74ff74730a9e2c0c9cd72e6db44f4c33dc5b36e7788baf4ebb1a45a9`
  - includes Windows 100%, 125%, 150%, and 1366×768 evidence

## 6. Remaining limitation

The exact external golden PNG payloads are frozen by SHA-256 in `docs/ui-reference/manifest.json`, but the binaries themselves are not committed through the text-oriented repository workflow. Consequently:

- exact all-nine golden raster overlay is **not claimed** as completed in CI;
- the harness is ready to perform exact comparison when those binaries are supplied;
- no golden image is resized or used as a flattened UI background;
- this limitation does not block beginning STEP 02 because STEP 01 intentionally contains placeholder workspace bodies.

## 7. Final decision

**READY_WITH_LIMITATIONS**

The shared foundation is stable enough for STEP 02. STEP 02 must reuse the existing shell/tokens/navigation/docks/status system rather than duplicating them, and it must not reinterpret this report as proof that final whole-window pixel parity for unfinished workspace contents is already complete.
