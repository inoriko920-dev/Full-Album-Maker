# STEP 00 Rescue Manifest

Status recorded during STEP 00. Rescue inputs were hashed before analysis. Analysis used staging copies; no rescue ZIP or original planning file was overwritten or deleted.

| Input | Size (bytes) | SHA-256 observed | Baseline comparison | STEP 00 treatment |
|---|---:|---|---|---|
| `Full-Album-Maker-Windows-Portable.zip` | 194464242 | `eadd0453d2e4b7d253e5cfd4e0b79ee07dccd0fd8df71d028e2c31b63ec7523d` | MATCH | `READ_ONLY_SOURCE`; outer rescue archive |
| `Full-Album-Maker-v1.4.1-Windows-Portable.zip` (inside outer rescue) | 194828242 | `b0d571692f925296022f146c39dce388b4717a43417e7f80132bd3aa52a9d853` | MATCH | `VERIFIED_FROM_BUILD`; extracted only to staging |
| `PAKET_PENYELAMATAN_SEMUA_REPO_5_CHAT.zip` | 108714 | `4ca895caa9437229ba89a3b3342798edbc4fb2cf30c0c3032786fba1c10ed323` | MATCH | recovery-doc evidence only; no exact app source inside Full Album subtree |
| `MASTER_PROMPT_ASTRA_SOL_PORTABLE_FOLDER(2).txt` | 44304 | `479eb3b5fd7a42dba7d17c71b09b5c040693a1c4467a34fdbec5c4ac1dc680d8` | MATCH | planning/build-contract evidence only |
| `RENCANA_PEMULIHAN_FULL_ALBUM_MAKER_ASTRA_KE_SOL.docx` | 59232 | `ec17a2ad0c17fdba6a8f504607eaf1ef6d39360d071586f51318c674e9710506` | MATCH | recovery-plan evidence |
| `ASTRA_MASTER_PLAN_UI_FULL_ALBUM_MAKER_PIXEL_MATCH_9_REFERENSI.docx` | 15607720 | `3a672d55d0abf1029604f1ee2eb943be0cc6f9bc444ad308b40341e9c4ef7cc4` | DOES NOT MATCH historical lock `34fec93f...` | `INPUT_VERSION_DRIFT`; preserve current revision, do not call it corrupt |
| `STEP_00_BASELINE_RECOVERY_GATE_FULL_ALBUM_MAKER_ASTRA_KE_SOL.docx` | 1791707 | `086d242f3aa2ff49bd24f98d096a4546bbf5943deefecea08dca178365010643` | current execution pack | operational instruction source |
| `Full-Album_Audit_Bug_dan_Rencana_SOL.txt` | 43927 | `150b30d85415ef0fe8734b61094d26730e9c90965e70d050eafac38332d96581` | additional input | docs/planning evidence only |
| `Full-Album_MASTER_PLAN_EDITOR_TEMPLATE_SPECTRUM.txt` | 71021 | `f8aa70f9ea54a57b61239a15f69a014114c3627ed0c73d250cc70a05d433a7c8` | additional input | docs/planning evidence only |

## Frozen UI references

All nine 1672×941 reference images were hash-verified against the STEP 00 registry. Their locked SHA-256 values are:

1. UI-01 Beranda — `039f548c4938c4d56ba7a92fc1cbfcbf5befb566732be24a6393ab9791f677b0`
2. UI-02 Media — `117572570f900d7f25e2fd0dc822bd59c4496dcc6f23bfb9af8cb8b9d10aa3a5`
3. UI-03 Album — `42756121fc9a0b18b03d006710d1fb528388b3cf86eaf25c0e72afdac11062b9`
4. UI-04 Timeline — `d559b1d380f03bbb68ab832d3174b32e9d63d64fe7c1c4af98d11e5e7d3839c3`
5. UI-05 Visual — `8b661752b235de74843950945126ab80837dec01953b796fcdcd6ad2ac317ef8`
6. UI-06 Template — `cd2dcd55dcfcf16b947737e459129178a71f76b52b625e398c0fc2f1e87f5895`
7. UI-07 Spectrum — `ffd89d91c8679b819264ce012742e2387313fdfef90e2ea9a2f590685cb7d87f`
8. UI-08 AI Agent — `276a602d2617762e87b2007e7191f9042217b41dd3bf75ce42da7a5fa5be29f3`
9. UI-09 Render — `8739b225d83089772b19f05b133b98b3ea8e448d1fb905ba613751f46d988618`

STEP 00 only inventories/freezes these references. No pixel-match implementation or UI redesign was performed.
