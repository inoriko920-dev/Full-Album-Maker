# HANDOFF — STEP 01 Foundation UI & Design System

Project / repo: **Full Album Maker — `inoriko920-dev/Full-Album-Maker`**  
Branch: `ui/step-01-foundation`  
STEP 00 recovery baseline: `recovery/step-00-r0` @ `87860b7281c3c5e9731ccf082dac84ab14624402`  
Authoritative tested STEP 01 SHA: `0bd0aa3769b2913900d6ba169b70bffff1d674ba`  
Authoritative CI: run `36978076538` (#24), **SUCCESS**

## 1. STEP 00 gate status

**READY_FOR_STEP_01_WITH_LIMITATIONS**

The STEP 00 provenance contract remains in force:

- recovered v1.4.0 is the exact source baseline;
- v1.4.1 portable is behavior/build evidence only;
- exact v1.4.1 source is not claimed;
- recovery evidence and source labels remain untouched.

## 2. STEP 01 decision

# READY_WITH_LIMITATIONS

STEP 02 **may begin** from the STEP 01 foundation. All acceptance criteria marked critical by the STEP 01 specification pass. The remaining limitations are explicit and non-blocking for Beranda.

## 3. Foundation files/components

Primary STEP 01 ownership:

- `src/full_album_maker/foundation_tokens.py`
- `src/full_album_maker/foundation_theme.py`
- `src/full_album_maker/foundation_icons.py`
- `src/full_album_maker/foundation_components.py`
- `src/full_album_maker/foundation_shell.py`
- `src/full_album_maker/foundation_preferences.py`
- `src/full_album_maker/foundation_window.py`
- `src/full_album_maker/foundation_capture.py`
- `tests/test_step01_foundation.py`
- `tests/test_step01_acceptance.py`
- `tests/step01_validate_evidence.py`
- `.github/workflows/step01-foundation-validation.yml`
- `docs/ui-reference/manifest.json`
- `docs/ui-foundation/UI_FOUNDATION_MAP.md`
- `docs/ui-foundation/KNOWN_LIMITATIONS.md`
- `docs/ui-foundation/STEP01_TEST_REPORT.md`
- `docs/ui-foundation/BASELINE.md`
- `docs/ui-foundation/HANDOFF_STEP01.md`

Recovered application modules remain the implementation baseline; STEP 01 does not introduce a parallel project/timeline/render/AI engine.

## 4. Shared contracts to reuse in STEP 02+

### Design tokens

Source: `src/full_album_maker/foundation_tokens.py`.

Key values:

- title evidence: 41 px
- command bar: 55 px
- navigation: 172 px
- compact navigation: 72 px
- context panel target: 264 px
- right dock: 348 px
- status bar: 28 px
- golden viewport: 1672×941
- compact breakpoint: 1450 px
- minimum supported width: 1366 px

### Workspace registry

`WORKSPACE_ORDER` in `foundation_tokens.py`:

`home → media → album → timeline → visual → template → spectrum → ai_agent → render`

Labels:

`Beranda → Media → Album → Timeline → Visual → Template → Spectrum → AI Agent → Render`

### Inspector dock

`InspectorDockHost` in `foundation_shell.py`:

- one shared right dock;
- tabs `Properti | AI`;
- collapse/expand;
- no duplicated per-workspace inspector shell.

### Timeline dock

`TimelineDockHost` in `foundation_shell.py`:

- one shared timeline host;
- collapse/expand;
- per-workspace preferred heights;
- Split/Ripple/Snap/Marker controls remain intentionally non-final until the Timeline step.

### Status model

`FoundationUiState` + `AppStatusBar` in `foundation_shell.py`.

Save, FFmpeg, AI, jobs and project-context status are event/model driven rather than directly coupled to workspace widgets.

## 5. Golden viewport, DPI and responsive evidence

Golden viewport: **1672×941 — PASS**.

100% shared-shell geometry:

- title strip: 41 px
- title + command region: 96 px
- navigation: 172 px
- right dock: 348 px
- status bar: 28 px
- Home/Render timeline: 34 px collapsed
- Media/Album: 194 px
- Timeline: 352 px
- Visual: 238 px
- Template: 158 px
- Spectrum: 252 px
- AI Agent: 178 px

DPI:

- 100%: PASS
- 125%: PASS
- 150%: PASS
- Linux and Windows validation paths both succeed.

Responsive:

- 1366×768: PASS on Linux + Windows
- compact navigation: 72 px with tooltip/accessible labels.

## 6. Tests and artifacts

At tested SHA `0bd0aa3769b2913900d6ba169b70bffff1d674ba`:

- Linux STEP 01 focused: **15 passed**
- Linux recovered regression: **246 passed, 88 skipped**
- Windows STEP 01 focused: **15 passed**
- all nine route captures: PASS
- deterministic Home repeat diff: **0.0**
- Linux evidence validator: PASS
- Windows geometry gate: PASS
- secret scan: PASS

Final run #24 artifacts:

- `step01-ui-evidence`
  - ID `11213948740`
  - SHA-256 `239fd0c4b6661b765edbcbbc2bf15965132910e7556e9ed4d0bdcbaa959cef19`
- `step01-ui-evidence-windows`
  - ID `11214850767`
  - SHA-256 `6ca8c179250286e783a93f3d3c677d8e9dfcae5a9d0f1c7afb21e1db5c240245`

See `STEP01_TEST_REPORT.md` for AC01–AC20 detail.

## 7. Known limitations carried into STEP 02

1. Exact v1.4.1 source is unavailable. Do not guess or reconstruct it; use exact recovered v1.4.0 implementation source and v1.4.1 portable only as behavior/build evidence.
2. The historical FFmpeg asset/pin issue from STEP 00 is not silently changed in STEP 01; packaging remediation belongs to the later release gate.
3. Exact multi-megabyte golden PNG binaries are verified/frozen by SHA-256 manifest but are not committed through the text-oriented connector. The harness accepts external originals and refuses golden resizing.
4. Offscreen evidence draws a deterministic Windows-like title strip because production uses native Windows title chrome and Qt `window.grab()` captures only the client surface.
5. Whole-window pixel parity of finished workspace content is not claimed at STEP 01 because final Beranda/Media/etc. bodies are intentionally placeholders.
6. Timeline editing semantics behind Split/Ripple/Snap/Marker are deferred to the later Timeline step.

## 8. Regression rules for STEP 02

- Do not create a second MainWindow/project store/timeline engine/render engine/AI state model.
- Do not duplicate navigation, command bar, right dock, timeline dock or status bar inside Beranda.
- Do not create a Home-only stylesheet that bypasses shared tokens/components.
- Do not change route IDs/order.
- Do not alter project schema, renderer contract, timeline data model or AI action contract just to implement Beranda.
- Global Render remains a route/preflight entry point; it must not auto-start a render.
- Preserve 1366 compact mode, DPI behavior, keyboard focus, dock state and status model.
- Run focused STEP 02 tests plus the full recovered regression suite before closing Beranda.

## 9. STEP 02 first task recommendation — Beranda only

Implement **UI-01 Beranda / Project Hub** before touching Media.

Required sequence:

1. Replace only route `home` placeholder with a real `HomeWorkspace`; keep the other eight routes as controlled placeholders.
2. Implement hero `Mulai Full Album` with `Proyek Baru` and `Buka Proyek`, wired to the existing foundation/recovered adapters.
3. Implement conditional `Autosave tersedia` banner. `Pulihkan` must load actual recoverable state; dismiss must not delete recovery data unless explicitly confirmed.
4. Implement four-column `Proyek Terakhir` cards at 1672×941 using real recent-project metadata or deterministic fixture data for screenshot tests. Card overflow menu may remove from recent/reveal/show metadata; it must not delete source media by default.
5. Implement `Mulai Cepat`: `Impor Lagu → Susun Timeline → Render`, gated by actual project context.
6. Bind the Home right dock to real `Status Portable` checks and `Pengaturan Cepat` state. AI unconfigured must remain non-blocking for manual editing.
7. Keep Home timeline collapsed and display `Belum ada proyek yang dibuka` when no project is active.
8. Add deterministic Home fixture, 1672×941 capture and overlay/diff against exact UI-01 when the external original is supplied. Tune the app to the golden; never resize the golden to the app.
9. Add New/Open/Recent/Autosave/quick-setting behavior tests and preserve all STEP 01 shell tests.
10. Do not start Media until Home golden/behavior acceptance is closed and evidence is written.

## 10. Closure

**FINAL STEP 01: READY_WITH_LIMITATIONS → STEP 02 MAY START.**

No runtime implementation task from STEP 01 remains uncommitted. Closure-document commits after the tested SHA only record evidence/handoff and do not change the validated foundation runtime.
