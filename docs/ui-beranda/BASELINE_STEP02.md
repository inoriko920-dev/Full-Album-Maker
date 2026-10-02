# STEP 02 — Beranda / Project Hub Baseline

Repository: `inoriko920-dev/Full-Album-Maker`  
Working branch: `ui/step-02-beranda`  
STEP 02 base SHA: `33aac775a1a4b500aeabea2b268b15ad9b34ad9c`  
Base branch: `ui/step-01-foundation`  
STEP 01 closure: `READY_WITH_LIMITATIONS` / `NEXT=STEP02_BERANDA`

## Golden contract

- Workspace: Beranda / Project Hub
- Golden viewport: `1672×941` at 100%
- Golden SHA-256: `039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`
- Center order: Hero → Autosave/Recovery → Proyek Terakhir → Quick Start
- Right dock: shared STEP 01 dock, `Properti` selected; Beranda supplies Status Portable + Pengaturan Cepat content
- Timeline: shared STEP 01 timeline, collapsed in idle Home
- Status: shared STEP 01 status/event system

## Re-verification before implementation

1. `ui/step-02-beranda` was created from the final STEP 01 closure head, so STEP 02 writes are isolated from the concurrent STEP 01 documentation closure activity.
2. No pre-existing STEP 02 branch was found before branch creation.
3. STEP 01 shell remains the foundation source of truth; STEP 02 must not duplicate navigation, command bar, right dock, timeline dock, status bar, tokens, or screenshot infrastructure.
4. Existing project behavior is real and reusable:
   - legacy `Project` format is JSON and validated through `Project.from_dict` / `project_io`;
   - Editor V2 uses `ProjectDocument` schema v2 and `project_repository` for validated load/migration;
   - `FoundationMainWindow` already adapts New/Open/Save/Import/Auto/Preview to recovered application behavior.
5. STEP 02 will add Home-specific state/services/widgets around those contracts rather than inventing a second project engine.

## Scope lock

STEP 02 implements Beranda only. Media, Album, Timeline editor, Visual, Template, Spectrum, AI Agent, and Render keep their STEP 01 placeholders except for stable route navigation initiated from Beranda.

## Serial execution order

`S02-01` baseline → `S02-02` Home state contract → `S02-03` Hero → `S02-04` Create → `S02-05` Open → `S02-06` Recovery → `S02-07` Recent service → `S02-08` Recent cards → `S02-09` Lihat Semua → `S02-10` Quick Start → `S02-11` Status Portable → `S02-12` Quick Settings → `S02-13` timeline/status integration → `S02-14` accessibility → `S02-15` async/performance → `S02-16` golden fixture → `S02-17` edge states → `S02-18` evidence/handoff.

## Stop/escalation conditions

Do not materially redesign STEP 01 shell geometry or project schema merely to simplify Beranda. Stop only the affected part and document evidence if Home cannot meet its contract without a major cross-workspace architectural change, if recovery cannot be made safe, or if verified project behavior materially contradicts the STEP 02 specification.
