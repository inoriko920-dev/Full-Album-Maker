# STEP 01 Golden UI References

The nine exact PNG assets were verified from the embedded ASTRA master-plan images and their immutable SHA-256 values are frozen in `manifest.json`. The connected-document source remains the visual authority used for STEP 01 tuning.

This branch intentionally does not check the multi-megabyte binary PNG payloads into GitHub through the text-oriented connector. When an exact local golden pack is available to the build machine, place the files using the names in `manifest.json`; `foundation_capture.py --golden <file>` produces a 50% overlay and diff heatmap without modifying the reference.

Rules:

- Never rescale, recompress, recolor, or annotate golden files.
- Golden acceptance viewport is 1672×941 at 96 DPI / 100% scale.
- Compare application output to the reference; never transform the golden to fit the application.
- STEP 01 focuses on shared shell landmarks, density, color system, and dock geometry; workspace bodies remain controlled placeholders.
- Actual workspace content begins in STEP 02 and later.
