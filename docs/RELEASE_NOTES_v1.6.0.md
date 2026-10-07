# Full Album Maker v1.6.0

## Beat Animation Engine V2

- Adds real audio analysis for beat, onset, tempo, energy, and bass/mid/high frequency bands with a content-addressed analysis cache.
- Adds 18 Beat Animation visual presets, including Beat/Bass pulses, zooms, glow, punch, tilt, energy and cinematic variants.
- Adds six deterministic motion effects: Alternating Wobble, Bass Sway, Camera Shake, Beat Bounce, Four-Way Kick, and Spark Burst.
- Adds nine Music Style recipes: Chill, Ambient, Pop, Rock, EDM, Hip-Hop, Dangdut Remix, Acoustic, and Cinematic.
- Adds eight visual+motion combinations such as Club Impact, Bass Rider, Cinematic Spark, Remix Wobble, and Rock Shake.
- Adds confidence-gated Vinyl BPM Sync with deterministic preview/render timing and safe fallback to the existing static spin.

## Editor and AI Agent

- Adds Beat preset, intensity, motion, combo, and Vinyl BPM controls to the editor with Undo/Redo-safe project mutations.
- Extends the AI Agent with permission-gated Beat, motion, style, combo, intensity, and BPM Sync actions.
- Keeps AI changes behind the existing Preview Diff, permission checks, atomic transaction, and one-step Undo workflow.

## Reliability and performance

- Adds deterministic random-seek behavior for Beat signals, motion, shake, Spark Burst, and BPM-synced Vinyl.
- Adds bounded command batching and preflight limits for long-project FFmpeg sendcmd workloads.
- Adds responsive analysis cancellation, corrupt-cache quarantine/recovery, bounded cache maintenance, and Accurate Preview runtime memoization.
- Aligns Python/runtime metadata with Python 3.12 and bundles the pinned scientific Beat runtime into the Windows portable build.

## Release gate

The v1.6.0 release is valid only after the full regression suite, Windows clean PyInstaller build, extracted portable ZIP isolation smoke, frozen Beat runtime smoke, real Beat V2 export smoke, checksum verification, and release-candidate provenance checks pass.
