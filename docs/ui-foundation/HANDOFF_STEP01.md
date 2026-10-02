# HANDOFF — STEP 01 Foundation UI & Design System

Project / repo: **Full Album Maker — `inoriko920-dev/Full-Album-Maker`**  
Branch: `ui/step-01-foundation`  
STEP 00 recovery baseline: `recovery/step-00-r0` @ `87860b7281c3c5e9731ccf082dac84ab14624402`  
Validated STEP 01 runtime HEAD: `084808da876d2bfd8a72764e7951515578a1a995`  
Documentation closure pre-handoff HEAD: `670847a23fe96699754acfaac23979ef88f91359`  
Authoritative CI: run `36977769859` (#23), **SUCCESS**

## 1. STEP 00 gate status

**READY_FOR_STEP_01_WITH_LIMITATIONS**

The STEP 00 provenance contract remains in force:

- recovered v1.4.0 is the exact source baseline;
- v1.4.1 portable is behavior/build evidence only;
- exact v1.4.1 source is not claimed;
- historical recovery evidence and source labels remain untouched.

## 2. STEP 01 decision

**READY_WITH_LIMITATIONS**

STEP 02 may begin from the STEP 01 branch/foundation.

The limitation is explicit: the exact external multi-megabyte golden PNG binaries are not checked into this branch/CI, so the final all-nine whole-window raster overlay against those exact files is not claimed. The structural shell landmark gates, deterministic capture/diff mechanism, responsive behavior, DPI states, Linux regression suite, Windows focused suite, and secret scan all pass.

## 3. Foundation files/components created or modified

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
- `docs/ui-foundation/UI_FOUNDATION_MAP.md`
- `docs/ui-foundation/KNOWN_LIMITATIONS.md`
- `docs/ui-foundation/STEP01_TEST_REPORT.md`
- `docs/ui-foundation/BASELINE.md`
- `docs/ui-foundation/HANDOFF_STEP01.md`

Recovered application modules outside this list remain part of the v1.4.0 source baseline and were not opportunistically redesigned as STEP 01 workspace features.

## 4. Design token source

`src/full_album_maker/foundation_tokens.py`

Key shell contract values include:

- title evidence height: 41 px
- command bar: 55 px
- navigation: 172 px
- compact navigation: 72 px
- context panel: 264 px
- right dock: 348 px
- status bar: 28 px
- golden viewport: 1672×941
- compact breakpoint: 1450 px
- minimum supported width: 1366 px

Colors/spacing/radius/control/icon metrics are likewise centralized in the same token source.

## 5. Workspace registry source

`WORKSPACE_ORDER` in `src/full_album_maker/foundation_tokens.py`.

Exact route order:

```text
home → media → album → timeline → visual → template → spectrum → ai_agent → render
```

Labels:

```text
Beranda → Media → Album → Timeline → Visual → Template → Spectrum → AI Agent → Render
```

STEP 01 owns only the shared routing host and controlled placeholder bodies. Final workspace content starts in STEP 02.

## 6. InspectorDockHost source

`InspectorDockHost` in `src/full_album_maker/foundation_shell.py`.

Contract:

- one shared right dock;
- `Properti | AI` reusable host;
- collapse/expand behavior;
- no duplicated per-workspace inspector shell.

## 7. TimelineDockHost source

`TimelineDockHost` and `TimelineFoundationCanvas` in `src/full_album_maker/foundation_shell.py`.

Contract:

- one shared timeline host;
- collapse/expand behavior;
- workspace-specific preferred heights;
- stable shell geometry;
- Split/Ripple/Snap/Marker remain intentionally non-final placeholders until later timeline semantics.

## 8. Status bar/event source

`FoundationUiState` + `AppStatusBar` in `src/full_album_maker/foundation_shell.py`.

Status data is event/model driven for save state, FFmpeg, AI, jobs, and project context; final workspace bodies are not coupled directly to status widgets.

## 9. Golden viewport tested

**PASS — 1672×941**

Linux CI generated deterministic 100% captures for all nine routes:

- `foundation-home.png`
- `foundation-media.png`
- `foundation-album.png`
- `foundation-timeline.png`
- `foundation-visual.png`
- `foundation-template.png`
- `foundation-spectrum.png`
- `foundation-ai-agent.png`
- `foundation-render.png`

The repeated Home capture produced normalized absolute difference `0.0` against the immediately repeated deterministic capture.

## 10. DPI tested

**PASS — 100%, 125%, 150%**

Validated in both Linux/offscreen and Windows Server 2025 CI for the foundation shell evidence states.

## 11. 1366×768 tested

**PASS — Linux + Windows**

The compact navigation rail measures 72 px (`nav_right=71`) and preserves access through icons, accessible names, and tooltips.

## 12. Screenshot evidence paths

Linux artifact `step01-ui-evidence` (artifact `11213744092`):

```text
ui-golden/current/
ui-golden/diff/
ui-golden/reports/
```

Windows artifact `step01-ui-evidence-windows` (artifact `11213354895`):

```text
ui-golden-windows/foundation-home-100.png
ui-golden-windows/foundation-home-125.png
ui-golden-windows/foundation-home-150.png
ui-golden-windows/foundation-1366.png
ui-golden-windows/*.json
```

Artifact digests:

```text
step01-ui-evidence
sha256:000d9f812c826d2c3eaf1ad3d9a5ab1b5fb23d8a620619ee23a409bd02fbcb74

step01-ui-evidence-windows
sha256:dd478dbe74ff74730a9e2c0c9cd72e6db44f4c33dc5b36e7788baf4ebb1a45a9
```

## 13. Landmark drift summary

Validated 100% shell geometry at 1672×941:

- native title evidence: 41 px
- command bar bottom: y=95
- navigation width: 172 px
- right dock width: 348 px
- status bar: 28 px
- Home timeline: 34 px
- Media/Album timeline: 194 px
- Timeline workspace: 352 px
- Visual: 238 px
- Template: 158 px
- Spectrum: 252 px
- AI Agent: 178 px
- Render: 34 px

The mechanical repeat-capture diff is exactly 0.0. The remaining visual limitation is not shell instability; it is the absence of the exact external golden binary payloads inside CI for a final all-nine raster overlay.

## 14. Tests PASS / FAIL / NOT TESTED

### PASS

- source compile
- frozen golden manifest integrity
- Linux focused STEP 01: **15 passed**
- Linux recovered regression: **246 passed, 88 skipped**
- Windows focused STEP 01: **15 passed**
- all-nine Linux 1672×941 route captures
- deterministic repeat capture/diff
- Linux 1366×768
- Windows 1366×768
- Linux 125% / 150%
- Windows 125% / 150%
- Linux evidence validator
- Windows geometry validator
- high-confidence secret scan
- evidence artifact uploads
- save/open compatibility fixtures
- portable app-relative resource-path fixture

### FAIL

- none in authoritative run `36977769859`

### NOT TESTED / externally pending

- exact all-nine whole-window raster overlay against the external original golden PNG binaries themselves
- manual real-user workflow of final workspace bodies, because those bodies are intentionally STEP 02–10 scope
- packaging remediation for the historical FFmpeg 404 pin, which is deliberately outside STEP 01

## 15. Known limitations

1. Exact v1.4.1 source remains unavailable; no source is guessed from portable module names.
2. External exact golden PNG binaries are not stored on this branch through the text-oriented connector; only their frozen hashes/manifest are committed.
3. Final workspace bodies remain placeholders by design.
4. Historical v1.4.0 FFmpeg asset pin still returns 404 and remains a separate release/build remediation task.
5. Timeline editing semantics behind placeholder controls are deferred to the later Timeline step.

See `KNOWN_LIMITATIONS.md` for the maintained canonical list.

## 16. Regression risk

**Low to moderate, controlled.**

Reasons:

- STEP 01 wraps the recovered implementation rather than creating a parallel project/timeline/AI engine;
- workspace switching is shared-state based;
- production save/open adapters remain connected to recovered behavior;
- the full recovered Linux regression suite passes;
- Windows focused UI/geometry tests pass;
- workspace bodies are deliberately deferred instead of being mixed into foundation refactoring.

Main remaining risk is future workspace implementation accidentally duplicating or bypassing the shared foundation. STEP 02+ must reuse the established shell contracts.

## 17. Uncommitted files/processes

No local working tree is maintained by this connector workflow. All STEP 01 implementation and closure documentation described here are committed on the remote branch. No background implementation process is assumed to remain running after this handoff.

## 18. STEP 02 first-task recommendation

Implement **Beranda only** on top of the existing shared shell.

Rules for STEP 02:

1. Do not recreate navigation, command bar, right dock, timeline dock, or status bar.
2. Reuse `foundation_tokens.py` and shared reusable components.
3. Preserve the recovered project/save/open behavior and shared state.
4. Keep the other eight workspace bodies as controlled placeholders until their assigned steps.
5. Add Beranda-specific deterministic screenshot/evidence tests against the frozen reference contract.
6. Do not treat the STEP 01 placeholder-center screenshot as final Beranda parity.
7. Keep the exact-golden-binary limitation explicit until the external originals are available for direct overlay.

## 19. Gate closure

STEP 01 is closed as:

**FINAL: READY_WITH_LIMITATIONS → STEP 02 MAY START**
