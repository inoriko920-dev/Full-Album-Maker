# STEP 09 — AI Agent Workspace — BLOCKER S09-02

## Status

**STEP 09 implementation is intentionally STOPPED at S09-02.**

Reason: the required STEP 09 golden instruction includes `slowmo footage 0,5x`, but the recovered modern Editor V2/V1.4 action contract has no stable `ProjectDocument` / Timeline / Visual slow-motion action owner. The STEP 09 execution document explicitly says this request must not be implemented through direct property writes merely to make the golden prompt appear to work.

This blocker record is documentation only. No STEP 09 production source implementation has been added on this branch.

## Repository baseline

- Repository: `inoriko920-dev/Full-Album-Maker`
- STEP 08 final branch: `ui/step-08-spectrum`
- STEP 08 final HEAD used as STEP 09 baseline: `a1efea56efe182ba578a176ede3f9b49dee85e55`
- STEP 09 branch: `ui/step-09-ai-agent`
- STEP 08 final workflow on the baseline: `STEP08 Spectrum validation`, run `37137930205`, conclusion `success`
- STEP 08 handoff status: `READY_WITH_LIMITATIONS`; its limitations do not block AI use of Timeline/Visual/Template/Spectrum action contracts.

## S09-02 recovered action audit

Recovered owners inspected:

- `src/full_album_maker/agent_actions.py`
- `src/full_album_maker/ai_editor.py`
- `src/full_album_maker/ai_editor_v14.py`
- `src/full_album_maker/visual_precision.py`
- `src/full_album_maker/song_visuals.py`
- `tests/test_editor_v2_v14_ai_parity.py`
- STEP 08 handoff `docs/ui-spectrum/BASELINE_STEP08.md`

### What is already safe/reusable

The recovered modern AI editor has important STEP 09 prerequisites already:

1. `AgentAction` uses a fixed allowlist; unknown action names are rejected.
2. `EditorAIContextBuilder` / `V14EditorAIContextBuilder` build bounded context without exposing source paths or API keys.
3. Layer/song/media resolution uses stable IDs and fails closed on ambiguity.
4. `AIEditorExecutor.execute()` verifies project identity and expected revision.
5. It simulates all action commands on a cloned `ProjectDocument` before committing.
6. All accumulated `EditorCommand` objects are committed through one `EditorController.dispatch(commands, expected_revision=...)` call.
7. Therefore normal Editor V2/V1.4 project mutations can be one revision / one normal Undo transaction.
8. Duplicate `action_id` is ignored rather than applied twice.
9. Existing modern V1.4 action contracts cover song cover/visual assignment, deterministic auto-match, song visual style, timeline mode, song timing/crossfade and circular Spectrum.

These findings mean the general transaction architecture itself is **not** the blocker.

## Exact blocker

`agent_actions.py` contains `set_slowmo` only inside `LEGACY_ACTIONS`.

That legacy action is executed by `AppIntentExecutor`, which operates on the legacy `Project` / `ProjectController` model.

The modern AI path used by STEP 09 is `AIEditorExecutor` / `V14AIEditorExecutor` over `ProjectDocument` and `EditorController`.

`V14_EDITOR_TOOLS` exposes modern actions for:

- cover / visual assignment
- visual style
- circular Spectrum
- timeline mode
- per-song Free Timeline timing / crossfade

but it does **not** expose a modern slow-motion/playback-speed action.

`V14AIEditorExecutor._commands_for_action()` also has no handler for `set_slowmo`. Falling through to the parent `AIEditorExecutor` does not make it valid because that executor handles Editor V2 actions, not legacy `set_slowmo`.

The STEP 06 Visual contract confirms there is no speed field. Its persisted per-song settings cover:

- fit / crop / position / scale
- image motion / pan-zoom
- video loop / freeze
- visual transition

but no video playback speed or slow-motion multiplier.

The recovered v1.4 AI parity tests likewise exercise modern cover, visual, visual-style, circular Spectrum, timeline mode and timing; they do not establish a slow-motion contract.

## Why SOL must stop here

The STEP 09 ASTRA execution document explicitly states:

- if slowmo `0,5x` has no stable recovered STEP 05/06 action contract, the plan cannot be READY;
- do not create a direct property write only to make the golden prompt appear to work;
- missing stable slowmo/timeline/template/spectrum action ownership is a review trigger/blocker;
- AI must use normal controller/domain actions and must not bypass transaction/Undo contracts.

Continuing to S09-03+ while pretending the full deterministic golden instruction can become executable would violate that contract.

## Required resolution before STEP 09 can continue

ASTRA/product decision is required for one of these safe paths:

### Option A — add a real modern slowmo contract first (recommended if slowmo must remain in the golden instruction)

Define and validate a normal domain owner in the appropriate Timeline/Visual layer, for example a persisted per-video/per-song playback-rate contract with:

- explicit target semantics (which footage/clip/song visual is slowed)
- stable IDs
- supported numeric bounds including `0.5x`
- renderer/preview parity
- lock and permission checks
- project persistence
- one-command Undo/Redo inverse
- dry-run/change-summary support
- tests proving no change to audible song timing unless explicitly intended

Only after that normal editor action is stable should STEP 09 expose it through the AI action registry.

### Option B — revise the STEP 09 golden instruction/scope

Remove the slowmo requirement from the mandatory READY fixture and keep slowmo explicitly unsupported in STEP 09. The AI planner must then surface it as unsupported rather than silently omitting or fabricating execution.

## Gate decision

**Current STEP 09 gate: `NOT_READY` / `BLOCKED_AT_S09_02`.**

No S09-03 state-machine/schema/provider/UI implementation should be started until the slowmo contract decision is resolved, because the documented mandatory golden plan cannot truthfully reach READY in the current recovered action architecture.
