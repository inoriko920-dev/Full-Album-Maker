from __future__ import annotations

"""Show the STEP09 dry-run result on the AI timeline without mutating project state.

PlanPreview already contains the exact domain commands proven by the transaction
engine. We replay those commands against a clone solely for presentation, then
feed that clone to the existing TimelinePrecisionPanel. The authoritative
ProjectDocument, revision, undo stack, and AI execution state remain untouched.
"""

_installed = False


def install_post_release_ai_timeline_preview_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_agent_core_step09 import AgentState
    from .editor_controller import EditorController
    from .foundation_window import FoundationMainWindow as Window

    original_refresh = Window._s09_refresh

    def refresh_with_preview_timeline(self) -> None:
        original_refresh(self)
        if getattr(self.foundation_state, "workspace", "") != "ai_agent":
            return
        session = getattr(self, "_s09_agent_session", None)
        if session is None:
            return
        snapshot = session.snapshot()
        preview = snapshot.preview
        if snapshot.state != AgentState.PREVIEW_READY or preview is None or not preview.commands:
            return

        # Recreate the already-proven dry-run result on a clone. This is a pure
        # visualization path: no controller dispatch and no live project mutation.
        simulation = self.editor_workspace.document().clone()
        simulation, _inverse = EditorController._apply_transaction(simulation, preview.commands)
        self.ai_timeline_s09.apply_document(
            simulation,
            self.editor_workspace.session.playhead_tick,
            ripple=bool(getattr(self, "_s05_ripple", False)),
            snap=self.editor_workspace.session.snap_enabled,
        )
        selected = self._s09_selected_song_ids()
        layers = self._s09_selected_layer_ids()
        self.ai_timeline_s09.canvas.set_selection(
            song_id=(selected[0] if len(selected) == 1 else ""),
            layer_id=(layers[0] if len(layers) == 1 else ""),
        )
        self._post_release_ai_preview_signature = simulation.content_signature()

    Window._s09_refresh = refresh_with_preview_timeline
    _installed = True
