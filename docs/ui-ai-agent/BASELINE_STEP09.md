# STEP 09 — AI Agent Workspace Baseline / Handoff

## Gate

**STEP 09 status: `READY_WITH_LIMITATIONS`**

STEP09 implementation is functionally complete and safe as the AI-planning/action-dispatch contract consumed by later work. The AI Agent is not allowed to mutate project state directly: provider output becomes a validated `AgentPlan`, Preview Perubahan is clone-only, and execution commits resolved normal editor commands through one `EditorController.dispatch(...)` transaction.

The remaining limitations are evidence/environment limitations, not hidden architecture gaps:

1. exact UI-08 pixel overlay/diff is `LOCAL_PENDING` because canonical `08-ai-agent.png` is not stored on this branch;
2. deterministic golden CI intentionally uses the Mock provider, so live Gemini network end-to-end is not claimed;
3. native Windows 11 full STEP09 UI/provider smoke is not claimed by the Ubuntu CI run.

This document closes S09-01 through S09-34. It does **not** implement STEP10 Render Center.

## Repository baseline

- Repository: `inoriko920-dev/Full-Album-Maker`
- Branch: `ui/step-09-ai-agent`
- STEP08 final baseline / merge-base: `a1efea56efe182ba578a176ede3f9b49dee85e55`
- STEP09 validated implementation/evidence SHA: `1015c69953dce399565577ea871ac6f8d65cdb10`
- Final implementation/evidence workflow: `STEP09 AI Agent validation`, run `37143767514`
- Final implementation/evidence workflow conclusion: `success`
- Compare against STEP08 at evidence SHA: **35 commits ahead, 0 behind**
- STEP09 closure documentation is committed after the validated implementation SHA so evidence remains reproducible and does not form a self-referential SHA cycle.

## S09-02 slowmo blocker

**RESOLVED.**

The initial blocker was valid: recovered modern Editor V2/V1.4 had no stable `ProjectDocument` slow-motion action and STEP09 was required to stop rather than invent an AI-only direct write.

The resolution is documented separately in:

`docs/ui-ai-agent/STEP09_BLOCKER_SLOWMO_CONTRACT.md`

The final normal editor contract now includes:

- persisted Visual-domain `video_speed` with default `1.0x`;
- explicit bounds `0.25x..4.0x`;
- `SetSongVideoSpeed` as a normal `EditorCommand`;
- prevalidation that every target song owns a video visual;
- no change to audible audio timing, song duration, playlist timing, or source trim ranges;
- normal Undo/Redo inverse through the existing Visual settings map;
- renderer parity through video `setpts`;
- AI action `set_song_video_speed` only as a resolver to that normal domain command.

The mandatory `0.5x` golden action is therefore no longer a blocker.

## State machine

PASS.

STEP09 uses explicit states:

- `IDLE`
- `INTERPRETING`
- `NEEDS_CLARIFICATION`
- `PLAN_READY`
- `PREVIEW_READY`
- `EXECUTING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

The UI does not equate free-form model text with an executed mutation. Mutation capability appears only after a structured plan survives validation and the user explicitly executes after Preview Perubahan.

## Sanitized context contract

PASS.

`AgentContextSnapshot` is built from bounded project context and stable identities rather than raw mutable Python objects.

Context includes only controlled data such as:

- stable `project_id` + revision;
- stable song IDs;
- stable selected layer IDs;
- allowlisted project media asset IDs;
- sanitized song/media descriptions;
- supported built-in template IDs;
- bounded user text;
- enabled workspace/context domains.

Validation rejects secret/path-shaped fields such as API keys, Authorization/Bearer data, `locator`, and vault paths from the provider payload.

"Semua media" in STEP09 means all media already inside the active `ProjectDocument`; it does not grant arbitrary filesystem browsing.

## Provider architecture

PASS.

### Mock provider

A deterministic `MockStep09Provider` exists for golden QA/offline tests. It does not require a network key and does not perform arbitrary reasoning outside the golden action fixture.

For the mandatory golden prompt it requires exact title ↔ video filename-stem matches. Missing or duplicate matches return clarification instead of guessing.

### Gemini provider

`GeminiStep09Provider` uses function/tool calls only. Its tool schema is restricted to actions present in the STEP09 whitelist.

The provider instruction explicitly forbids inventing:

- IDs;
- filesystem paths;
- media/song/layer/template targets;
- timestamps not requested by the user;
- shell commands;
- arbitrary executable code;
- API keys;
- render/save-template side effects outside the STEP09 scope.

If enough information is not available for a safe action, the provider must return clarification rather than a fabricated action.

Live Gemini network execution is **not claimed by final golden CI**; provider parsing/tool-schema behavior is covered using controlled test doubles and the recovered key-pool regression suite.

## Action whitelist / domain ownership

PASS.

STEP09 actions are mapped to existing normal editor/domain commands. The AI layer never writes project fields directly.

Validated action registry covers:

- set song visual;
- set song cover;
- set song video speed;
- Auto Susun Timeline;
- Timeline Packed/Free mode;
- per-song Free Timeline timing/crossfade;
- playlist reorder;
- apply built-in template;
- apply Spectrum preset.

Every resolver validates its target/scope and returns domain commands owned by the relevant editor subsystem.

## Permission model

PASS.

Each action declares required permissions. Before preview/execution:

- the action set is resolved to required permissions;
- the plan must declare every permission actually required by its actions;
- the current `PermissionGrant` must allow the complete set;
- plan scope must remain inside the context boundary.

Changing provider or permission state invalidates/cancels an existing plan/preview instead of silently reusing stale authorization.

## Stale-plan protection

PASS.

An `AgentPlan` is bound to:

- `project_id`;
- expected revision;
- context fingerprint.

Dry-run and execution reject a plan when project identity/revision/context no longer match. Production UI surfaces a stale warning and requires a new interpretation/preview after manual project changes.

## Send / interpretation

PASS.

`Kirim` begins interpretation only.

It does not apply domain commands and does not create a project revision by itself.

Provider execution is asynchronous. Completion is delivered back through a Qt `QObject` bridge, and stale request tokens are ignored so an older provider result cannot replace a newer request.

## Preview Perubahan / dry-run

PASS.

`Step09TransactionEngine.dry_run()`:

1. takes a controller snapshot;
2. validates plan/context/project identity/revision/fingerprint/permissions;
3. resolves every action only through the whitelist;
4. applies the generated commands to a **clone** using the normal transaction helper;
5. computes a structured impact summary;
6. returns the resolved domain commands without committing them.

The final UI-08 deterministic evidence proves that after Send + Preview:

- live project content signature is unchanged;
- live project revision is unchanged;
- no visual assignment has been applied;
- no slowmo setting has been applied.

Therefore `PREVIEW_READY` is a real zero-live-mutation state.

## Execute / atomicity

PASS.

Execution does not individually commit provider actions.

After revalidation, all commands from the already-proven dry-run are committed through one:

`EditorController.dispatch(preview.commands, expected_revision=...)`

This gives STEP09:

- all-or-nothing validation/commit semantics;
- one project revision for the logical AI plan;
- one normal Undo history entry;
- no partially applied plan when a later command is invalid.

A cancellation request can stop interpretation/dry-run before commit. It cannot interrupt inside the one atomic controller commit and leave half a plan behind.

## Duplicate-submit protection

PASS.

Executed `plan_id` values are remembered by the transaction engine. Re-executing the same plan does not apply the mutation a second time.

The duplicate result reports the unchanged current signature/revision rather than silently doubling timeline/media changes.

## Undo AI

PASS.

`Undo AI` is intentionally stricter than generic Undo.

It is available only when:

- an AI transaction was successfully executed;
- it has not already been undone;
- normal controller Undo is available;
- current revision equals the AI result revision;
- current content signature equals the AI result signature.

If a manual edit occurs after the AI transaction, `Undo AI` refuses to jump over it; the user must use normal Undo order. When safe, one Undo must restore the exact pre-AI signature.

## History / saved commands / privacy

PASS.

STEP09 stores sanitized human-readable history and saved prompts rather than raw provider/network payloads.

Tests prove redaction of:

- Gemini-like API keys;
- Authorization/Bearer strings;
- Windows absolute paths;
- Unix absolute paths.

Corrupt history/saved-command files fail closed instead of crashing project editing.

The STEP09 evidence workflow also runs a repository/evidence secret scan and reports:

`STEP09_AI_SECRET_SCAN_PASS`

No live API key is inserted into golden screenshots or evidence.

## Production workspace

PASS.

The recovered shared shell route `ai_agent` is replaced by STEP09 production surfaces rather than a second standalone editor window.

Production composition includes:

- left Conversation / saved-command panel;
- central AI task canvas;
- user instruction card;
- AI interpretation card;
- structured plan cards;
- scope card;
- Impact Summary;
- Preview Perubahan;
- Jalankan;
- Batalkan;
- Undo AI;
- prompt composer + context chips + Save Command;
- right Context & Izin / provider controls;
- shared Timeline surface below.

Workspace activation preserves the project model and shared Undo/Redo architecture from STEP01–08.

## Deterministic UI-08 golden fixture

PASS for production capture/state contract.

Golden instruction:

`Pilih 20 lagu, pasangkan visual yang cocok, slowmo footage 0,5x, lalu susun timeline.`

Deterministic fixture contains:

- 20 songs;
- 20 exact-match video candidates;
- stable IDs only;
- Mock provider;
- no network/API-key dependency.

At `PREVIEW_READY` the plan contains:

- 20 `set_song_visual` actions;
- 1 `set_song_video_speed` action at `0.5x`;
- 1 `auto_arrange_timeline` action;
- **22 actions total**;
- **22 resolved domain commands**;
- 20-song scope;
- 40 allowed project media assets;
- 2 required permission classes;
- impact summary with 41 changed entities/fields represented by the deterministic impact contract.

The fixture deliberately stops before execution so CI can prove the required zero-mutation Preview behavior.

## UI geometry evidence

### 1672×941

Final production capture from run `37143767514`:

- workspace: `ai_agent`
- AI workspace active: true
- Conversation panel visible: true
- Context & Izin dock active: true
- Timeline visible: true
- context width: **264 px**
- right dock: **348 px**
- Timeline height: **178 px**
- status bar: **28 px**
- state: `PREVIEW_READY`
- provider: `mock`
- screenshot SHA-256: `3fdf65b55622f56f742429717cb9dc2007c2a46a747b74b059cfec63521a597f`

### 1366×768

Compact evidence also passed:

- context width: **264 px**
- right dock: **300 px**
- Timeline height: **178 px**
- status bar: **28 px**
- state: `PREVIEW_READY`
- 20-song / 22-action golden contract retained
- project content/revision still unchanged by Send + Preview
- screenshot SHA-256: `0a6f3779417c80af9463a1a660cbd279276306726ee231b9ce1d23ac876f6654`

## Golden UI-08

- Canonical file: `08-ai-agent.png`
- Canonical expected SHA-256: `276a602d2617762e87b2007e7191f9042217b41dd3bf75ce42da7a5fa5be29f3`
- Exact binary present on this branch: **no**
- Deterministic production capture: **PASS**
- Geometry/state contract: **PASS**
- Exact immutable pixel overlay/diff: **`LOCAL_PENDING`**

The CI rule is fail-closed: if the exact binary appears, its SHA must equal the canonical hash before an overlay/diff is accepted. Missing binary is never called pixel-parity PASS.

## Final test evidence — run 37143767514

Validated implementation/evidence SHA:

`1015c69953dce399565577ea871ac6f8d65cdb10`

Results:

- Compile source: PASS
- STEP09 focused core/provider/workspace/slowmo/history/session: **36 passed**
- Recovered AI atomic regression: **19 passed, 1 skipped**
- Provider + key-pool regression: **19 passed**
- STEP08 Spectrum regression gate: **18 passed**
- Full recovered regression suite: **414 passed, 88 skipped**
- UI-08 deterministic capture 1672×941: PASS
- UI-08 deterministic capture 1366×768: PASS
- Golden state/geometry validation: `STEP09_AI_GOLDEN_GEOMETRY_PASS`
- Secret scan: `STEP09_AI_SECRET_SCAN_PASS`
- Golden exact overlay: `STEP09_GOLDEN_REFERENCE_LOCAL_PENDING`
- Evidence upload: PASS

Evidence artifact:

- Name: `step09-ai-evidence`
- Artifact ID: `11281157359`
- Size: `447981` bytes
- SHA-256 digest: `5785ed45f2509755893d86dee94d05d708a6ccd44737fcb58e4002a53a0215c2`
- Artifact is bound to workflow run `37143767514` / head SHA `1015c69953dce399565577ea871ac6f8d65cdb10`.

## Self-review / changed files

Compare STEP08 final `a1efea56efe182ba578a176ede3f9b49dee85e55` → STEP09 validated implementation/evidence `1015c69953dce399565577ea871ac6f8d65cdb10`:

- **35 commits ahead**
- **0 commits behind**
- **21 changed paths** at implementation/evidence closure.

The diff is contained to:

- STEP09 AI model/provider/action/session/history/async/workspace/feature/capture;
- STEP09 tests and workflow;
- slowmo Visual-domain prerequisite in `visual_precision.py`;
- renderer consumption of persisted video speed in `v13_render_graph.py`;
- two-line production installer activation in `main.py`;
- STEP09 documentation.

No STEP10 Render Center implementation is part of the STEP09 implementation evidence.

## Tests NOT TESTED / LOCAL_PENDING

1. Exact UI-08 pixel-to-pixel overlay/diff: `LOCAL_PENDING` because immutable `08-ai-agent.png` is external to the branch.
2. Live Gemini network end-to-end with a real account/key: `NOT TESTED` in final golden CI. Golden uses Mock by design; parser/schema/key-pool behavior is automated separately.
3. Native Windows 11 end-to-end STEP09 UI/provider session: `LOCAL_PENDING`; final automated evidence run is Ubuntu/offscreen Qt.
4. Provider service availability, quotas, and external Gemini behavior are environmental and must never be inferred from mocked CI.

None of these items weakens the project transaction/permission/stale-plan contract needed by STEP10.

## Known limitations

- STEP09 executes only actions present in the explicit whitelist. Unsupported requests must remain clarification/unsupported rather than falling back to direct project mutation.
- AI Agent does not receive arbitrary filesystem access. Media is restricted to project asset IDs inside the permission boundary.
- `Undo AI` intentionally refuses when a later manual edit sits above the AI transaction.
- Golden exact-match visual assignment is deterministic and conservative; ambiguous/missing video names require clarification.
- Mock provider exists for deterministic QA and is not presented as evidence of live Gemini availability.

# STEP 09 → STEP 10 Handoff

**Status: `READY_WITH_LIMITATIONS`**

### Contract STEP10 must preserve

- Do not let Render Center or export code bypass `ProjectDocument` state produced by validated editor/controller actions.
- Preserve the STEP09 transaction boundary: AI plans must remain whitelist → dry-run → explicit execute → one controller transaction.
- Do not let AI trigger hidden Render Center side effects merely from `Kirim` or `Preview Perubahan`.
- Keep Render as an explicit user action/workspace transition; STEP09 provider system prompt currently forbids render side effects.
- Preserve stable IDs, project revision checks, context fingerprints, permission boundaries and stale-plan rejection.
- Preserve secret/key separation. API keys must never enter project JSON, render metadata, evidence artifacts, history, screenshots, or handoff docs.
- Preserve Visual `video_speed` semantics: video presentation `setpts`, no implicit audio speed change.
- Preserve STEP08 Spectrum final/accurate renderer ownership and STEP07 Template/STEP06 Visual/STEP05 Timeline project contracts.
- Render Center may consume the final project state; it must not create a second model representation simply for AI-generated projects.

### First safe task for STEP10

Verify this STEP09 handoff and the live repository HEAD first. Then audit the recovered Render/export queue, output, FFmpeg ownership, cancellation, retry, and completion/failure state contracts **read-only before coding**.

Do not infer a Windows/live-provider PASS from STEP09 Linux Mock evidence.

## Final decision

`READY_WITH_LIMITATIONS`

Reason: STEP09 state machine, sanitized context, strict provider tool schema, permissions, stale-plan guard, zero-mutation Preview, atomic execution, duplicate protection, one-Undo AI semantics, slowmo 0.5x domain ownership/render parity, production UI-08 deterministic capture, security scan, and full regression are proven. Exact UI-08 canonical overlay plus native Windows/live Gemini end-to-end remain explicit external/local validation items.
