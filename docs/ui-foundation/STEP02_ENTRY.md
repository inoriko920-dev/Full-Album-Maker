# STEP 02 Entry Scope — Beranda Only

This file freezes the next implementation boundary after STEP 01.

- Implement only `home` / Beranda first.
- Reuse the existing STEP 01 shell, tokens, navigation, right dock, timeline dock, status model, preference store and screenshot harness.
- Keep Media, Album, Timeline, Visual, Template, Spectrum, AI Agent and Render as controlled placeholders until their own steps.
- Target golden UI-01 at 1672×941.
- Required Home behavior: New Project, Open Project, conditional autosave recovery, recent projects, quick start, real portable status, quick settings, collapsed idle timeline.
- Do not change project schema/renderer/timeline/AI action contracts to implement Home.
- Close Beranda golden + behavioral acceptance before starting Media.

The authoritative implementation details remain in `HANDOFF_STEP01.md`.
