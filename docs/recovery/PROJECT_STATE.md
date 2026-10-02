# Full Album Maker — R0 / STEP 00 Project State

## Baseline locked before write

```text
repo: inoriko920-dev/Full-Album-Maker
default_branch: main
STEP00_BASELINE_SHA: 561970639a7a61d2cea583d6386e8912c9161512
baseline_tree: 24e3ccc15a0bd6220426228aadfb478ed8b660da
baseline_root: README.md + docs/
source_present_on_main_at_start: no
open_recovery_prs_at_start: none
write_permission: verified by recovery branch creation
local_dirty: not-applicable (no persistent local clone)
working_branch: recovery/step-00-r0
```

`main` was not used as the STEP 00 write target. Recovery work stayed on one branch.

## R0 canonical source decision

- Exact source recovered: **v1.4.0**, historical commit `1d52b73e35f9df8272978e7b93a7a8c87896d7bd` — `VERIFIED_SOURCE`.
- Preserved portable: **v1.4.1**, build commit `809b4d130c30f12e9df272395c2dd85941931c24` — `VERIFIED_FROM_BUILD` only.
- Exact v1.4.1 source: **NOT FOUND / UNKNOWN**.
- Decompiled source imported: **none**.
- Reconstructed app source imported: **none**.
- 20 module names occur in the v1.4.1 build but lack exact recovered v1.4.0 source; they remain source `UNKNOWN`.

## STEP 00 task closure

| Task | Status | Closure |
|---|---|---|
| S00-01 Freeze rescue inputs | PASS | hashes recorded; rescue originals untouched; staging used |
| S00-02 Verify live repo baseline | PASS | repo/main/HEAD/tree/source state/write access verified before write |
| S00-03 Recovery working branch | PASS | one branch `recovery/step-00-r0`; no force push |
| S00-04 Inventory surviving inputs | PASS | rescue/docs/UI refs/source/build evidence inventoried |
| S00-05 Verify portable v1.4.1 | PASS WITH LIMITATION | hash/layout/CAPABILITIES verified; executable smoke NOT TESTED |
| S00-06 Recover/locate exact source | PASS WITH LIMITATION | exact v1.4.0 recovered; exact v1.4.1 unresolved |
| S00-07 Recover history/docs | PASS | historical source docs/release notes and recovery history retained; planned vs implemented kept separate |
| S00-08 Recover build/dependency contracts | PASS WITH LIMITATION | exact v1.4.0 contracts restored; historical FFmpeg pin now 404 |
| S00-09 Recover tests/behavior baseline | PASS WITH LIMITATION | Linux suite 231 passed / 88 skipped; preserved v1.4.1 Windows smoke NOT TESTED |
| S00-10 Security/license/secret scan | PASS WITH REVIEW ITEM | targeted secret scan PASS; MIT + notices present; FFmpeg pin/notices divergence recorded |
| S00-11 Backup/restore gate | LOCAL_PENDING | rescue hashes + remote branch verified; local Git bundle/restore rehearsal pending |
| S00-12 Finalize R0 state/handoff | COMPLETE WITH LIMITATIONS | state docs + handoff on recovery branch; no merge to main |

## Executed validation summary

Final Linux validation candidate on commit `a297c8367bfe51d945f911d1676b10af1ce921c0`:

- compile: PASS
- core imports: PASS
- source/build module evidence comparison: PASS
- high-confidence secret scan: PASS
- pytest: **231 passed, 88 skipped in 24.94s**

Windows recovered-v1.4.0 source build run `36970755675` reached exact Python dependency installation successfully, then stopped when historical BtbN asset ID `595476894` returned HTTP 404. This is an external historical input failure, not rewritten away.

## UI freeze

The nine golden UI images were hash-verified and frozen as reference evidence only. No UI implementation, redesign, pixel-match coding, layout cleanup, or STEP 01 work was performed in STEP 00.

## R0 readiness

The source baseline is sufficiently trustworthy to begin UI foundation work **only with explicit awareness of the unresolved v1.4.1 exact-source/build gaps**. Final decision is recorded in `HANDOFF_STEP00.md`.
