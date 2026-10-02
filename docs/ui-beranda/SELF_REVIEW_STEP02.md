# STEP 02 — Self Review / Acceptance

Repository: `inoriko920-dev/Full-Album-Maker`  
Branch: `ui/step-02-beranda`  
Baseline: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`  
Validated implementation SHA: `ec380f355dc12a4193285428068c84e98b68f8c1`

## Diff review

The implementation candidate is a direct descendant of the STEP 01 closure baseline (`ahead`, not behind) and changes only the STEP 02 integration surface, Home modules/tests/docs, the STEP 02 CI workflow, and a small shared-component extension.

Implementation diff at the validated SHA:

- `.github/workflows/step02-home-validation.yml` — STEP 02 validation/evidence only.
- `src/full_album_maker/foundation_components.py` — small reusable component support; no foundation geometry/token redesign.
- `src/full_album_maker/foundation_window.py` — mounts Beranda into the recovered application and adapts real commands/services.
- `src/full_album_maker/home_state.py` — stable Home state contract.
- `src/full_album_maker/home_services.py` — create/open/recent/recovery/default persistence services.
- `src/full_album_maker/home_workspace.py` — Beranda workspace composition.
- `src/full_album_maker/home_inspector.py` — Status Portable + Pengaturan Cepat.
- `src/full_album_maker/home_capture.py` — deterministic G02 fixture capture.
- `tests/test_step02_home_state.py`, `tests/test_step02_home_services.py`, `tests/test_step02_home_ui.py` — focused regression coverage.
- `docs/ui-beranda/*` — baseline, provenance, test/evidence, review and handoff documentation.

No Media Library final grid, Album manager, Timeline editor behavior, Visual inspector, Template gallery, Spectrum editor, AI task execution, Render queue, installer, or large project-schema migration was implemented in STEP 02.

`main` was not used as the STEP 02 working branch.

## Acceptance matrix

| ID | Status | Evidence / note |
|---|---|---|
| AC02-01 | PASS | Beranda is active in shared STEP 01 shell; STEP 01 regression `15 passed`. |
| AC02-02 | PASS_WITH_LIMITATION | Hero/geometry at 1672×941 is stable and unclipped; exact canonical binary proof is unavailable. |
| AC02-03 | PASS | Real `Project` is created and saved; create→open focused test passes. |
| AC02-04 | PASS | Valid project opens; missing/corrupt paths fail safely. |
| AC02-05 | PASS | Recovery banner requires a validated candidate. |
| AC02-06 | PASS | Recovery service restores a real saved project snapshot. |
| AC02-07 | PASS | Dismiss is session-only; snapshot is not silently deleted. |
| AC02-08 | PASS | G02-A confirms 4 recent cards. |
| AC02-09 | PASS | Recent card emits the same Home open path pipeline. |
| AC02-10 | PASS | Missing recent remains indexed/marked missing; click can locate another file. |
| AC02-11 | PASS | Lihat Semua opens the recent-project dialog and uses the same open flow. |
| AC02-12 | PASS | Stable quick routes are `media`, `album`, `render`. |
| AC02-13 | PASS | FFmpeg state derives from local `ffmpeg_path()` lookup. |
| AC02-14 | PASS | AI unconfigured state is optional/neutral and does not block startup. |
| AC02-15 | PASS | Ratio/resolution defaults persist via `QuickDefaultsStore`. |
| AC02-16 | PASS | Output path is user-selected/persisted and checked writable; no fixed drive. |
| AC02-17 | PASS | G02-A proves collapsed idle timeline and shared status bar geometry. |
| AC02-18 | PASS | Startup uses bounded local index/snapshot reads; no recursive media scan or network call. |
| AC02-19 | PASS | Recent cards and shared navigation expose keyboard/focus behavior; STEP 01 keyboard regression passes. |
| AC02-20 | PASS | CI secret scan passes; fixture paths are explicit non-secret fixture values. |
| AC02-21 | LIMITATION | G02-A structure is tuned and compared to the embedded DOCX visual, but the canonical declared PNG bytes are not available/matching; exact canonical golden PASS is not claimed. |
| AC02-22 | PASS | G02-B `HOME_NO_RECOVERY` capture validated. |
| AC02-23 | PASS | G02-C `HOME_FIRST_RUN` capture validated with empty recent state. |
| AC02-24 | PASS | Open error remains recoverable through visible create/open controls; missing recent opens Locate flow; invalid output shows corrective warning. |
| AC02-25 | PASS | Test report, provenance, self-review and handoff are written before STEP 03. |

## Golden visual review

Declared canonical SHA-256:
`039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

Embedded DOCX visual SHA-256:
`b339d432cf2378c14ad4c65fad16a2996fe0403741a25ec00302a1a29ef727bf`

Final G02-A screenshot SHA-256 from the validated evidence pack:
`205bd187446e3c85cdd51049d1df53bbd8a4ed2be8e0d62e9aead1eee8baaa81`

Normalized absolute difference versus the embedded DOCX visual:
`0.09869081147824202`

Known visible differences that remain:

1. **Evidence limitation / REQUIRED-to-claim-exact-PASS:** supplied DOCX embedded PNG bytes do not match the declared canonical hash. This blocks an honest `READY_FOR_STEP_03` exact-golden claim, but does not block Media implementation.
2. **Expected fallback:** recent-project artwork uses a generic media placeholder when no real user thumbnail exists. The specification permits a neutral placeholder and forbids invented user artwork.
3. **Minor/inherited:** icon glyph/anti-aliasing and some typography/chrome details differ from the embedded visual because STEP 02 preserves the frozen STEP 01 shell instead of materially redesigning it.

No visual mismatch was hidden by resizing the golden image or embedding the golden screenshot as application UI.

## Safety / architecture review

- No fake-success create/open/recovery response was introduced.
- Recovery failure is fail-closed and source snapshots are preserved.
- Existing recovered project schema remains authoritative.
- No API key is serialized into Home debug state.
- No network request is needed to decide AI optional status.
- The user can operate manual/offline Home behavior without Gemini.
- Source paths remain portable/app-relative where inherited from STEP 01.

## Remaining limitations

- Native Windows 11 smoke: `LOCAL_PENDING`.
- Exact canonical golden binary comparison: `BLOCKED_BY_REFERENCE_PROVENANCE`.
- Deeper thumbnail extraction is intentionally deferred; Home uses the allowed fallback rather than starting a Media scan on the UI thread.

## Self-review decision

The implementation is functionally stable and safe enough to hand off to STEP 03, but the exact-golden evidence requirement cannot be honestly closed with the supplied binary evidence.

**Decision: `READY_WITH_LIMITATIONS`**
