# STEP 09 — AI Agent Workspace — S09-02 SLOWMO RESOLUTION RECORD

## Current status

**RESOLVED.**

This file preserves the original S09-02 blocker as an audit trail. The blocker was valid when STEP09 first audited the recovered action surface: the modern `ProjectDocument` / Visual domain did not yet own a stable slow-motion action, and implementing AI-only direct property writes would have violated the ASTRA contract.

The blocker has since been resolved by adding and validating a normal Visual-domain playback-speed contract **before** exposing it to AI Agent execution.

STEP09 may therefore continue and the mandatory golden instruction containing `slowmo footage 0,5x` is now truthfully executable through a normal domain command.

## Repository baseline

- Repository: `inoriko920-dev/Full-Album-Maker`
- STEP08 final branch: `ui/step-08-spectrum`
- STEP08 baseline used by STEP09: `a1efea56efe182ba578a176ede3f9b49dee85e55`
- STEP09 branch: `ui/step-09-ai-agent`
- STEP09 implementation/evidence SHA proving the resolution: `1015c69953dce399565577ea871ac6f8d65cdb10`
- STEP09 final evidence workflow: `STEP09 AI Agent validation`, run `37143767514`, conclusion `success`

## Why the initial blocker was correct

At the first S09-02 audit:

- legacy `set_slowmo` existed only on the old `Project` / `ProjectController` path;
- the modern `ProjectDocument` / `EditorController` Visual contract had no persisted playback-speed field;
- the recovered modern AI action registry therefore had no safe slowmo owner;
- inventing an AI-specific property write would have bypassed normal validation, persistence, renderer parity, and Undo ownership.

Stopping at that point was required by the STEP09 execution document.

## Resolution implemented

### 1. Visual domain now owns `video_speed`

`src/full_album_maker/visual_precision.py` extends the existing per-song Visual settings contract with:

- `video_speed`
- default `1.0x`
- supported bounds `0.25x..4.0x`
- backward-compatible persistence inside the existing Visual extension map
- preservation of an existing speed when older STEP06 UI payloads omit the field.

No project schema version bump or AI-only data store is used.

### 2. Normal editor command owns the mutation

`SetSongVideoSpeed` is a normal `EditorCommand`.

It:

- accepts stable `song_id` targets;
- validates every target before mutation;
- requires each target song to already reference a video asset;
- rejects mixed image/video scopes before any project change;
- writes only Visual presentation speed;
- does not alter audio timing, playlist timing, song source ranges, or source files;
- returns the normal inverse state through the existing Visual settings restore command;
- therefore participates in standard `EditorController` Undo/Redo transactions.

### 3. Renderer owns the real effect

`src/full_album_maker/v13_render_graph.py` consumes the persisted Visual speed as video presentation timing using FFmpeg `setpts` semantics.

For the mandatory `0.5x` fixture the validated render graph contains:

`setpts=PTS/0.50000000`

The audible song path does **not** receive `atempo` and the audio render-plan start/end ticks remain unchanged.

### 4. AI registry only calls the domain action

`src/full_album_maker/ai_action_registry_step09.py` exposes:

`set_song_video_speed`

The resolver validates AI scope and numeric input, then creates `SetSongVideoSpeed`.

The AI layer does not write `ProjectDocument.extensions` directly.

### 5. Provider contract is explicit

`src/full_album_maker/ai_provider_step09.py` exposes the Gemini/mock function contract:

- `song_ids`: stable IDs
- `speed`: number in `0.25..4.0`

The system instruction explicitly says slowmo must use `set_song_video_speed` and must not alter audio timing to simulate the effect.

## Validation evidence

`tests/test_step09_slowmo_contract.py` proves:

1. `0.5x` persists through the normal Visual settings contract.
2. The change is one normal Undo transaction and Redo restores it.
3. Timeline song start/end ticks remain identical before and after slowmo.
4. Audio source-in/source-out values remain unchanged.
5. Mixed image/video targets fail before mutation.
6. Later STEP06 Visual edits that omit `video_speed` preserve the existing speed.
7. Project `to_dict()` / `from_dict()` round-trip keeps `video_speed` without a schema bump.
8. Renderer emits video `setpts` for `0.5x`.
9. Renderer does not add audio `atempo` for the slowmo action.
10. Explicit bounds reject unsupported speed values.

The STEP09 final workflow run `37143767514` passed the complete focused group containing these tests.

## Golden-plan proof

The deterministic STEP09 golden evidence uses the instruction:

> Pilih 20 lagu, pasangkan visual yang cocok, slowmo footage 0,5x, lalu susun timeline.

At `PREVIEW_READY` the mock provider produced:

- 20 `set_song_visual` actions;
- 1 `set_song_video_speed` action at `0.5x` targeting the 20 songs;
- 1 `auto_arrange_timeline` action;
- 22 total actions / 22 resolved domain commands.

The golden capture also proves Send + Preview did not mutate the live project before explicit execution.

## Final blocker decision

**The S09-02 slowmo blocker is closed.**

It must not be reintroduced as an active STEP09 limitation unless the Visual playback-speed domain contract is later removed or broken.

This resolution does **not** authorize direct AI writes. Future AI capabilities must continue to use validated normal editor/domain commands through the whitelist + transaction engine.
