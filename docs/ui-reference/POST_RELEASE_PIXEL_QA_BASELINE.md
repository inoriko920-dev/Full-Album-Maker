# Post-release UI Pixel QA Baseline

Status: ACTIVE REMEDIATION BASELINE

Release protected: `v1.4.0`
Release/main merge commit at baseline: `f4d522584156f8546cf9e7d7841e8bea729801c6`
Working branch: `ui/post-release-pixel-match`
Issue: #3

## Canonical reference recovery

The exact immutable 9-reference pack was recovered from the original source document `ASTRA_MASTER_PLAN_UI_FULL_ALBUM_MAKER_PIXEL_MATCH_9_REFERENSI.docx`.

Embedded `image2.png` through `image10.png` match the frozen SHA-256 values in `docs/ui-reference/manifest.json` exactly. All nine references are 1672x941 at the 96 DPI baseline. No reference was regenerated, recompressed, upscaled, or replaced.

The binary reference pack is intentionally not reconstructed from screenshots. Until the exact original binaries are safely placed in repository storage, `manifest.json` remains the source of the immutable filename/hash contract.

## Baseline comparison

Each current image below is the final 1672x941 screenshot from the successful GitHub Actions evidence artifact for its original implementation step. Comparison uses per-channel absolute RGB difference with no resize.

| Workspace | Golden | Evidence step | Normalized abs diff | RMSE | PSNR | Changed pixels |
|---|---|---:|---:|---:|---:|---:|
| Beranda | `01-beranda.png` | STEP02 | 0.098691 | 58.951 | 12.72 dB | 96.51% |
| Media | `02-media.png` | STEP03 | 0.154863 | 73.992 | 10.75 dB | 96.61% |
| Album | `03-album.png` | STEP04 | 0.088242 | 53.761 | 13.52 dB | 98.41% |
| Timeline | `04-timeline.png` | STEP05 | 0.160862 | 77.143 | 10.38 dB | 98.75% |
| Visual | `05-visual.png` | STEP06 | 0.153272 | 70.928 | 11.11 dB | 98.30% |
| Template | `06-template.png` | STEP07 | 0.177813 | 84.748 | 9.57 dB | 98.34% |
| Spectrum | `07-spectrum.png` | STEP08 | 0.149946 | 74.083 | 10.74 dB | 97.56% |
| AI Agent | `08-ai-agent.png` | STEP09 | 0.097324 | 57.488 | 12.94 dB | 98.00% |
| Render | `09-render.png` | STEP10 | 0.079150 | 52.125 | 13.79 dB | 95.11% |

## Interpretation

The prior `LOCAL_PENDING` condition caused by unavailable canonical binaries is resolved: the exact originals exist and their hashes are verified. However, none of the nine implementation screenshots is pixel-matched to its canonical reference.

This is a post-release visual fidelity task, not a reason to mutate or replace the published `v1.4.0` tag/release.

## Remediation order

Work serially and preserve all runtime/domain contracts.

1. Establish shared shell/token parity first: title bar, global toolbar, left navigation, right inspector tabs, bottom timeline/status bar, typography, spacing, borders, radii, and blue/white palette.
2. Re-capture all nine screens after every shared-shell change because one foundation fix can improve every workspace.
3. Finish the closest screens first once the shared shell stabilizes: Render, Album, AI Agent, Beranda.
4. Then remediate Spectrum, Visual, Media, Timeline, and Template.
5. Never loosen regression/runtime gates to improve visual scores.
6. Never alter the canonical SHA-256 manifest to match implementation output.
7. Acceptance requires new evidence at exactly 1672x941 and the same 96 DPI baseline.

## Release safety

- `v1.4.0` remains immutable historical release evidence.
- Changes happen only on `ui/post-release-pixel-match` until reviewed.
- No provider/key-pool/project-schema/renderer behavior may be changed solely for visual parity.
