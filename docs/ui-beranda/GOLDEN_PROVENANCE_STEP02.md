# STEP 02 Beranda Golden Provenance

Source specification: `STEP_02_BERANDA_PROJECT_HUB_FULL_ALBUM_MAKER_ASTRA_KE_SOL.docx`.

## Declared visual lock

- Declared golden viewport: `1672×941`
- Declared SHA-256 in the specification: `039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

## Embedded DOCX evidence checked during STEP 02

The DOCX contains an embedded PNG at exactly `1672×941` whose visual content is the Beranda golden shown in the specification. The exact embedded PNG bytes hash to:

`b339d432cf2378c14ad4c65fad16a2996fe0403741a25ec00302a1a29ef727bf`

This does **not** equal the declared canonical hash above.

## Final deterministic G02-A evidence

Validated implementation SHA:

`ec380f355dc12a4193285428068c84e98b68f8c1`

CI run / artifact:

- Run `36985869444`
- Artifact `11217771140` (`step02-home-evidence`)
- Artifact digest `sha256:fcd405714b79cd43e5c144a28b7951f810214a2169b0355d44ccf36a67d39173`

Final G02-A recovery screenshot SHA-256:

`205bd187446e3c85cdd51049d1df53bbd8a4ed2be8e0d62e9aead1eee8baaa81`

The final G02-A and the embedded DOCX visual have identical pixel dimensions (`1672×941`). A direct non-resized RGBA comparison gives normalized absolute difference:

`0.09869081147824202`

An evidence pack was also assembled with G02-A through G02-E, 1366/125%/150% captures, JSON geometry reports, the embedded DOCX visual evidence, overlay, diff and a manifest. Pack SHA-256:

`27e8e50fc388aa37f892ef58ec05836aac7d80d4942e49b3aeb54d8e731fb23c`

## Interpretation

The comparison above is useful visual/geometry evidence but it is **not** an exact canonical-golden proof because the supplied embedded PNG is not the binary identified by the declared canonical hash.

Known visible differences include the specification-permitted neutral recent-project thumbnail fallback and small icon/font/chrome rendering differences inherited from the frozen STEP 01 shell. STEP 02 did not hide these differences by resizing the reference or embedding the golden screenshot as application UI.

## Gate decision

Implementation work independent of binary identity is validated and may be handed to STEP 03. However, STEP 02 must not claim an exact locked-golden binary PASS until the source of the declared hash is resolved or the exact declared binary is supplied.

Golden-evidence status: `BLOCKED_BY_REFERENCE_PROVENANCE`  
Overall STEP 02 status: `READY_WITH_LIMITATIONS`
