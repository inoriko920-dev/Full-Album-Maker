from __future__ import annotations

"""Attach deterministic vector scene thumbnails to UI-09 Render rows.

The underlying queue/history widgets, jobs and settings are untouched.  This is
purely a child-paint overlay on the presentation thumbnail frames.
"""

from pathlib import Path

from PySide6.QtWidgets import QFrame

from .post_release_render_mock_thumbnail import RenderMockThumbnail

_installed = False


def _attach_scene(parent, title: str, width: int, height: int) -> None:
    target = next(
        (
            frame for frame in parent.findChildren(QFrame)
            if frame is not parent and frame.width() == width and frame.height() == height
        ),
        None,
    )
    if target is None or getattr(target, "_pixel_scene_attached", False):
        return
    target._pixel_scene_attached = True
    scene = RenderMockThumbnail(title, target)
    scene.setGeometry(target.rect())
    scene.show()
    scene.raise_()
    target._pixel_scene = scene


def install_post_release_render_thumbnail_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_render_history_adjustment import _CompletedHistoryRow
    from .post_release_render_queue_adjustment import GoldenRenderQueueRow

    original_queue_init = GoldenRenderQueueRow.__init__
    original_history_init = _CompletedHistoryRow.__init__

    def queue_init(self, job, number: int, parent=None) -> None:
        original_queue_init(self, job, number, parent)
        title = Path(job.settings.final_output).stem.replace(" - Full Album", "")
        _attach_scene(self, title, 92, 58)

    def history_init(self, job, parent=None) -> None:
        original_history_init(self, job, parent)
        title = Path(job.settings.final_output).stem.replace(" - Full Album", "")
        _attach_scene(self, title, 68, 43)

    GoldenRenderQueueRow.__init__ = queue_init
    _CompletedHistoryRow.__init__ = history_init
    _installed = True
