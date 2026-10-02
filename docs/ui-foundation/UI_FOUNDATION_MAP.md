# Full Album Maker — STEP 01 UI Foundation Map

## Source boundary

STEP 01 starts from recovered `VERIFIED_SOURCE` v1.4.0 on `recovery/step-00-r0`. Exact v1.4.1 source remains unknown. No v1.4.1-only module is reconstructed in this step.

The recovered v1.4 application behavior remains alive behind `V14EditorMainWindow`. `FoundationMainWindow` wraps that recovered implementation and swaps only the visible central surface. This avoids a parallel project/timeline/AI engine.

## Shared foundation ownership

| Contract area | Implementation |
|---|---|
| Design tokens | `foundation_tokens.py` |
| Single white-blue QSS | `foundation_theme.py` |
| Outline icon renderer | `foundation_icons.py` |
| Reusable primitives | `foundation_components.py` |
| Global command bar | `GlobalCommandBar` in `foundation_shell.py` |
| Navigation rail | `WorkspaceNavigation` |
| Workspace host | `WorkspaceStack` with controlled placeholders |
| Right dock | `InspectorDockHost` (`Properti | AI`) |
| Timeline dock | `TimelineDockHost` + `TimelineFoundationCanvas` |
| Status system | `FoundationUiState` + `AppStatusBar` |
| App/local preferences | `foundation_preferences.py` |
| Production compatibility wrapper | `foundation_window.py` |
| Deterministic screenshot harness | `foundation_capture.py` |

## Navigation contract

`home → media → album → timeline → visual → template → spectrum → ai_agent → render`.

Switching route changes only the shared UI route. It does not create a new `Project`, run render, invoke AI, or mutate the timeline.

## Command adapter contract

Open/Save/import/Auto Susun/Preview are adapters to recovered application methods. Undo/Redo bind to the recovered Editor V2 session. Render only navigates to the Render workspace. New Project resets recovered project/controller state only after confirmation if user state exists.

## Deferred content

Every center page in STEP 01 is deliberately a `Foundation Preview` placeholder. Context, inspector, and timeline hosts exist now; detailed Beranda/Media/Album/Timeline/Visual/Template/Spectrum/AI/Render content is deferred to STEP 02–10.
