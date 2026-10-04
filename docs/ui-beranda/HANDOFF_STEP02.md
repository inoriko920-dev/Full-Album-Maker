# HANDOFF — STEP 02 Beranda / Project Hub → STEP 03 Media Library

## Identity

Project / repo: `Full Album Maker` / `inoriko920-dev/Full-Album-Maker`  
Branch: `ui/step-02-beranda`  
Validated final implementation SHA: `ec380f355dc12a4193285428068c84e98b68f8c1`  
Documentation state before this handoff: `2bab111241ee696963b67047d2981d2a88237db7`  
STEP 01 baseline / rollback SHA: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`

Golden Beranda hash declared by STEP 02 specification:
`039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

Embedded DOCX visual hash actually available:
`b339d432cf2378c14ad4c65fad16a2996fe0403741a25ec00302a1a29ef727bf`

## Status

**`READY_WITH_LIMITATIONS`**

Core Beranda is real, safe and regression-tested. The limitation is not a fake/broken project flow; it is that the supplied embedded golden PNG does not match the specification-declared canonical hash, so exact canonical pixel identity cannot be proven honestly. Native Windows smoke is also still local-pending.

## Shell regression check

PASS.

- Shared STEP 01 shell remains the owner of navigation, command bar, right dock, timeline dock and status bar.
- STEP 01 regression: `15 passed` at CI run `36985869444`.
- G02-A confirms Home is the active stacked page in the shared shell.
- No STEP 01 foundation geometry/token redesign was introduced to make Home easier.

## Create project proof

PASS.

`HomeProjectService.create()` creates the real recovered `Project`, applies Quick Defaults resolution, writes through existing project I/O, and the focused test immediately reopens the same file successfully. Production Home uses the same service and then adopts the project into the recovered controller/editor compatibility layer.

## Open project proof

PASS.

- Valid project loads through the real project I/O path.
- Missing project returns `PROJECT_NOT_FOUND` safely.
- Corrupt JSON returns `PROJECT_CORRUPT` safely.
- No failed open is presented as success.
- Missing Recent entry can enter the Locate-file flow rather than being silently deleted.

## Recovery proof

PASS.

- Snapshot is written atomically to a known recovery location.
- Discovery parses and validates the candidate before `HOME_RECOVERY_AVAILABLE` can be shown.
- Valid snapshot restores the real `Project`.
- Invalid snapshot is preserved and refused.
- Dismiss only hides recovery for the current session; it does not delete the snapshot.

## Recent projects proof

PASS.

- Persistent bounded JSON index.
- Newest-first ordering.
- Missing path is marked missing without crash or silent deletion.
- G02-A/G02-B show four cards.
- First-run G02-C uses a real empty state, not fake project data.
- Lihat Semua dialog reads the same Recent service and opens through the same Home path.
- Neutral thumbnail fallback is used when no real thumbnail is available; no expensive startup media scan is introduced.

## Quick Start route IDs

Stable route IDs:

- `media` — Impor Lagu / project-entry route.
- `album` — Susun Timeline intent enters Album when audio context exists; otherwise it safely directs through Media/project creation.
- `render` — routes to the shared Render placeholder/preflight workspace without implementing STEP 09 final render UI.

## Portable status proof

PASS within current source/environment.

- FFmpeg status derives from the real local `ffmpeg_path()` lookup.
- Editing Manual Offline is explicitly ready independently from AI.
- AI readiness derives from local Gemini key-pool summary; unconfigured AI is `Opsional`, not a startup failure.
- No Home startup network request is required.

Native Windows portable smoke: `LOCAL_PENDING`.

## Quick settings persistence proof

PASS.

- Ratio ID and resolution ID are persisted via `QuickDefaultsStore`.
- Resolution maps to real even width/height values.
- Output folder is user-selectable, not hard-coded to a drive.
- Writable validation is exercised with a path containing spaces.
- G02-E proves `HOME_OUTPUT_INVALID` plus a visible corrective output warning.

## Golden screenshot G02-A result

Deterministic state/geometry gate: PASS.

Final validated G02-A:

- `1672×941`
- navigation right edge `171`
- right dock `348`
- idle timeline `34`
- status bar `28`
- `HOME_RECOVERY_AVAILABLE`
- active Home page = true
- recovery visible = true
- four Recent cards = true

G02-B through G02-E are also generated and state-validated. 1366×768 and 125%/150% captures are generated successfully.

Exact canonical visual gate: **NOT CLAIMED**.

Final G02-A SHA-256:
`205bd187446e3c85cdd51049d1df53bbd8a4ed2be8e0d62e9aead1eee8baaa81`

Embedded DOCX visual comparison normalized absolute difference:
`0.09869081147824202`

Reason exact canonical PASS cannot be claimed: the only embedded `1672×941` PNG supplied by the DOCX hashes to `b339...`, while the specification names canonical hash `039f...`.

## Known visual mismatch + severity

- `REFERENCE_PROVENANCE / REQUIRED_FOR_EXACT_PASS`: canonical golden binary is unavailable/mismatched.
- `EXPECTED_FALLBACK`: four recent-project cards use generic music/media thumbnails until real project thumbnails exist.
- `MINOR / inherited`: some icon glyph, anti-alias, typography and native-chrome details differ from the embedded visual because STEP 02 preserves the frozen STEP 01 foundation instead of redesigning it.

No golden screenshot is used as an application background, and the reference was not resized to force a false match.

## Known functional limitations

- Native Windows 11 startup/create/open/recovery smoke has not been executed in this Linux CI environment (`LOCAL_PENDING`).
- Recovery discovery parses one known local JSON snapshot synchronously. This is bounded local I/O and not a recursive scan/network operation, but it is not an asynchronous deep-probe architecture.
- Real Recent thumbnail extraction is intentionally deferred; the safe placeholder prevents Home startup from scanning media.
- STEP 03 must not reinterpret Home stable IDs or invent a new project format merely for Media UI convenience.

## Files changed by STEP 02 implementation

Implementation scope from STEP 01 baseline includes:

- `.github/workflows/step02-home-validation.yml`
- `src/full_album_maker/foundation_components.py`
- `src/full_album_maker/foundation_window.py`
- `src/full_album_maker/home_capture.py`
- `src/full_album_maker/home_inspector.py`
- `src/full_album_maker/home_services.py`
- `src/full_album_maker/home_state.py`
- `src/full_album_maker/home_workspace.py`
- `tests/test_step02_home_services.py`
- `tests/test_step02_home_state.py`
- `tests/test_step02_home_ui.py`
- `docs/ui-beranda/BASELINE_STEP02.md`
- `docs/ui-beranda/GOLDEN_PROVENANCE_STEP02.md`
- `docs/ui-beranda/STEP02_TEST_REPORT.md`
- `docs/ui-beranda/SELF_REVIEW_STEP02.md`
- this handoff document.

## Tests run + result

Validated CI run: `36985869444` on implementation SHA `ec380f355dc12a4193285428068c84e98b68f8c1`.

- Compile: PASS.
- STEP 01 foundation regression: `15 passed`.
- STEP 02 focused state/services/UI: `24 passed`.
- Full recovered regression: `270 passed, 88 skipped`.
- G02 A-E fixture/state/geometry gate: PASS.
- 1366 compact gate: PASS.
- 125% and 150% capture: PASS generated.
- Secret scan: PASS.
- Artifact upload: PASS.

CI evidence artifact:

- ID `11217771140`
- digest `sha256:fcd405714b79cd43e5c144a28b7951f810214a2169b0355d44ccf36a67d39173`

Supplemental evidence-pack SHA-256:
`27e8e50fc388aa37f892ef58ec05836aac7d80d4942e49b3aeb54d8e731fb23c`

## Uncommitted files / processes

No intentional source change is being held outside the STEP 02 branch. CI evidence is stored as a workflow artifact; the supplemental comparison/evidence ZIP is an external evidence package, not application source.

## Rollback point

Rollback to the immutable STEP 01 closure baseline:

`33aac775a1a4b500aeabea2b268b15ad9b34ad9c`

Do not force-push or delete recovery evidence to perform rollback.

## STEP 03 contract

Next task: **STEP 03 — Media Library**.

STEP 03 must consume the existing shared shell and Home/project state rather than rebuilding them. In particular, preserve:

- real `Project`/project I/O as the source contract;
- route ID `media`;
- Home create/open/recovery behavior;
- Recent index safety;
- offline/manual operation without Gemini;
- shared navigation/command/dock/timeline/status ownership;
- STEP 01 + STEP 02 regression suites.

Do not start STEP 03 by redesigning the whole shell or by replacing recovered project behavior with a new convenience schema.

---

STEP 02 closure decision: **`READY_WITH_LIMITATIONS`**  
NEXT: **STEP 03 — Media Library**
