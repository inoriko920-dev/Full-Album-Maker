# STEP 02 Beranda Golden Provenance

Source specification: `STEP_02_BERANDA_PROJECT_HUB_FULL_ALBUM_MAKER_ASTRA_KE_SOL.docx`.

## Declared visual lock

- Declared golden viewport: `1672×941`
- Declared SHA-256 in the specification: `039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`

## Embedded DOCX evidence checked during STEP 02

The DOCX contains an embedded PNG at exactly `1672×941` whose visual content is the Beranda golden shown on the cover/specification pages. The exact embedded PNG bytes hash to:

`b339d432cf2378c14ad4c65fad16a2996fe0403741a25ec00302a1a29ef727bf`

This does **not** equal the declared hash above.

## Decision

Implementation work that does not depend on binary identity may continue because the embedded image is unambiguous visual evidence and the STEP 01 shell is already stable. However, STEP 02 must not claim an exact locked-golden binary PASS until the source of the declared hash is resolved or the exact declared binary is supplied.

The deterministic `home_capture.py` fixture and CI evidence may be used for geometry, layout, responsive and regression tuning. Any overlay against the embedded DOCX PNG must be labeled as **embedded visual evidence**, not as proof that the declared SHA-256 binary was matched.

This is a visual-gate limitation only; it does not authorize redesigning the STEP 01 shell or weakening create/open/recovery safety tests.
