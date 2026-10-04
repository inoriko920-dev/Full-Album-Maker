from __future__ import annotations

"""Compact three-lane project timeline for the post-release Template workspace.

UI-06 uses a small Video / Audio / Teks overview instead of the STEP06
VisualAlignmentCanvas.  The surface below reuses the already-proven three-lane
ProjectDocument painter used by the AI workspace, but it always paints the live
Template project document.  It is presentation-only: no project state, history,
undo stack, template draft, or render state is mutated here.
"""

from .post_release_ai_preview_timeline_surface import AIPreviewTimelineCanvas

_installed = False


def _install_surface(window) -> None:
    old = getattr(window, "template_timeline_s07", None)
    if old is None or getattr(old, "_post_release_template_three_lane", False):
        return

    parent = old.parentWidget()
    layout = parent.layout() if parent is not None else None
    if layout is None:
        return

    index = layout.indexOf(old)
    layout.removeWidget(old)
    old.hide()
    old.setParent(None)

    canvas = AIPreviewTimelineCanvas(parent)
    canvas.setObjectName("templateThreeLaneTimelineCanvas")
    canvas.setMinimumHeight(104)
    canvas._post_release_template_three_lane = True
    if index < 0:
        layout.addWidget(canvas, 1)
    else:
        layout.insertWidget(index, canvas, 1)
    window.template_timeline_s07 = canvas


def install_post_release_template_timeline_surface() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_init = Window.__init__
    previous_refresh_timeline = Window._s07_refresh_timeline

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_surface(self)
        self._s07_refresh_timeline()

    def refresh_three_lane(self) -> None:
        _install_surface(self)
        canvas = getattr(self, "template_timeline_s07", None)
        if canvas is None or not getattr(canvas, "_post_release_template_three_lane", False):
            previous_refresh_timeline(self)
            return

        document = self.editor_workspace.document()
        valid = set(document.song_map())
        selected = {
            str(value)
            for value in getattr(self, "_s06_selected_ids", set())
            if str(value) in valid
        }
        primary = str(getattr(self, "_s06_primary_song_id", "") or "")
        if primary not in valid:
            primary = document.playlist.entries[0].song_id if document.playlist.entries else ""
        if primary:
            selected.add(primary)

        canvas.set_document(document)
        canvas.set_playhead(self.editor_workspace.session.playhead_tick)
        canvas.set_selection(song_id=(primary if primary in selected else ""), layer_id="")

    Window.__init__ = wrapped_init
    Window._s07_refresh_timeline = refresh_three_lane
    _installed = True
