# STEP 01 Test Report

Status: **PENDING CI** at the initial foundation commit.

The STEP 01 validation workflow is the authoritative execution record. It must run:

1. Python compile of `src/`.
2. Targeted STEP 01 foundation tests.
3. Full recovered regression suite.
4. Deterministic shell captures at 1672×941 for Home, Media, Timeline, and Render.
5. 1366×768 compact capture.
6. 150% DPI/readability capture.
7. Screenshot-diff mechanism smoke plus JSON landmark reports.
8. High-confidence secret scan.

The workflow uploads `step01-ui-evidence` containing current PNGs, mechanical overlay/diff proof, and JSON landmark reports. Full overlay against the exact external golden PNG pack remains recorded separately in `KNOWN_LIMITATIONS.md` until those immutable binaries are available directly to CI.
