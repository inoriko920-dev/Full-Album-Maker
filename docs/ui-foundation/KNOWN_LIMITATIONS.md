# STEP 01 Known Limitations

- Workspace bodies are controlled placeholders by specification; visual/content parity of individual workspaces is not claimed until STEP 02–10.
- Exact v1.4.1 source remains unavailable. STEP 01 uses recovered exact v1.4.0 source plus the verified v1.4.1 portable only as behavior/build evidence.
- The historical Windows v1.4.0 build workflow still references an upstream FFmpeg asset that returned HTTP 404 during STEP 00. STEP 01 does not silently change that historical pin.
- Linux/offscreen screenshot rasterization can differ from Windows 96-DPI text rasterization. Geometry/landmark tests are deterministic; final pixel-perfect release validation remains a Windows gate.
- Timeline host controls Split/Ripple/Snap/Marker are shell placeholders and intentionally disabled until timeline semantics are implemented in STEP 05.
- The exact multi-megabyte golden PNG payloads were verified from the connected ASTRA document, but are not checked into this branch through the text-oriented GitHub connector. Their exact SHA-256 manifest is committed; the screenshot harness accepts local exact golden files and emits overlay/diff when supplied.
