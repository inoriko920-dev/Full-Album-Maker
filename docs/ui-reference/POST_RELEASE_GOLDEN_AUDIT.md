# Post-Release UI Golden Recovery & Gap Audit

Date: 2026-10-06

## Scope

This is the first post-release follow-up after STEP 12. It does **not** redesign the UI and it does **not** alter any golden reference.

Release baseline:
- `main`: `f4d522584156f8546cf9e7d7841e8bea729801c6`
- STEP 12 tested head: `84f0e2ba9a6ed5c6cae5d4a7be180406e319c564`
- STEP 11 validated UI implementation head: `7f9d6766bd2d03bc60d4b6da29ddefc2dc3388b9`

Git comparison from STEP 11 validated UI head to STEP 12 tested head shows no production UI source file changes; changes are limited to release workflows/build scripts/docs/tests. Therefore STEP 11 current screenshots are suitable as a **pre-remediation structural baseline**. Final closure still requires fresh screenshots from the remediated release candidate.

## Canonical golden source recovered

Original source document:

`ASTRA_MASTER_PLAN_UI_FULL_ALBUM_MAKER_PIXEL_MATCH_9_REFERENSI.docx`

The DOCX contains ten embedded PNGs. `image2.png` through `image10.png` are the nine canonical UI goldens. All nine are exactly `1672 x 941` and each SHA-256 matches `docs/ui-reference/manifest.json`.

| ID | Workspace | Embedded source | Canonical filename | SHA-256 verification |
|---|---|---|---|---|
| UI-01 | Beranda | image2.png | 01-beranda.png | PASS |
| UI-02 | Media | image3.png | 02-media.png | PASS |
| UI-03 | Album | image4.png | 03-album.png | PASS |
| UI-04 | Timeline | image5.png | 04-timeline.png | PASS |
| UI-05 | Visual | image6.png | 05-visual.png | PASS |
| UI-06 | Template | image7.png | 06-template.png | PASS |
| UI-07 | Spectrum | image8.png | 07-spectrum.png | PASS |
| UI-08 | AI Agent | image9.png | 08-ai-agent.png | PASS |
| UI-09 | Render | image10.png | 09-render.png | PASS |

Exact manifest hashes remain authoritative and unchanged.

## Pre-remediation pixel gap measurement

Comparison input:
- Golden: exact recovered PNGs above.
- Actual: `step11-integration-evidence/current/*.png`.
- Resolution: 1672 x 941 for both.
- Metric below is a raw RGB absolute-difference diagnostic only. It is **not** the final visual acceptance score.

| ID | Workspace | Mean abs. RGB diff | Pixels > 25 RGB delta | Initial result |
|---|---|---:|---:|---|
| UI-01 | Beranda | 25.17 | 21.45% | GAP |
| UI-02 | Media | 38.86 | 38.48% | GAP |
| UI-03 | Album | 22.50 | 20.41% | GAP |
| UI-04 | Timeline | 41.02 | 41.35% | GAP |
| UI-05 | Visual | 39.08 | 41.86% | GAP |
| UI-06 | Template | 45.34 | 39.16% | GAP |
| UI-07 | Spectrum | 38.24 | 41.90% | GAP |
| UI-08 | AI Agent | 23.92 | 23.05% | GAP |
| UI-09 | Render | 19.92 | 19.25% | GAP |

All nine screens require visual remediation before pixel-match closure can be claimed.

## Observed gap classes

The current implementation is functionally integrated but visually less dense and materially different from the canonical references. The largest recurring classes are:

1. shell geometry / density drift: command bar, navigation rail, right dock and timeline proportions are not consistently aligned to the golden composition;
2. typography / control sizing drift: current controls are generally smaller/lighter and use more whitespace than the golden;
3. fixture-content mismatch: golden cards/thumbnails/previews are content-rich while several current captures use placeholders or simplified deterministic art;
4. workspace-specific composition drift: Timeline, Visual, Template and Spectrum have major center-canvas and inspector-layout differences;
5. shared component drift: icons, tabs, buttons, status treatment and panel borders do not yet visually converge on the same golden language.

## Decision

Status: `GOLDEN_RECOVERED_AUDIT_COMPLETE`

What is now proven:
- canonical 9 golden PNGs are recoverable from the original master-plan DOCX;
- every canonical SHA-256 matches the frozen manifest;
- the release-era UI has measurable pixel-match gaps on all nine workspaces;
- no golden reference needs to be replaced, regenerated, resized, recolored or rehashed.

What is **not** done in this step:
- no production UI remediation;
- no golden file mutation;
- no final acceptance claim;
- no release v1.4.0 rewrite.

## Next safe task

Remediate **UI-01 Beranda only** against the exact golden at 1672 x 941, using the shared shell contracts and without breaking project behavior. After Beranda is visually closed and regression-tested, continue workspace-by-workspace rather than changing all nine at once.
