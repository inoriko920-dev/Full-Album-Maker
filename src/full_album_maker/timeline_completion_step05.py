from __future__ import annotations

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .preview_scene import PreviewCanvas
from .timeline_precision import (
    DEFAULT_MARKER_COLOR,
    DeleteTimelineMarker,
    UpdateTimelineMarker,
    timeline_markers,
)
from .timeline_resolver import TimelineResolver
from .timeline_workspace_step05 import TimelineContextWidget, TimelinePrecisionCanvas, TimelinePreviewWorkspace

_installed = False
_original_context_init: Any = None
_original_canvas_init: Any = None
_original_canvas_key_press: Any = None
_original_preview_init: Any = None
_original_preview_rect: Any = None


def _selected_marker_id(context: TimelineContextWidget) -> str:
    item = context.marker_list.currentItem()
    if item is None:
        return ""
    value = item.data(Qt.ItemDataRole.UserRole)
    return str(value or "")


def _edit_selected_marker(context: TimelineContextWidget) -> None:
    window = context.window()
    if not hasattr(window, "editor_workspace"):
        return
    marker_id = _selected_marker_id(context)
    if not marker_id:
        return
    document = window.editor_workspace.document()
    marker = next((item for item in timeline_markers(document) if item.marker_id == marker_id), None)
    if marker is None:
        return
    label, ok = QInputDialog.getText(window, "Edit Marker", "Nama marker:", text=marker.label)
    if not ok or not label.strip():
        return
    color = QColorDialog.getColor(QColor(marker.color), window, "Warna Marker")
    color_text = color.name().upper() if color.isValid() else marker.color
    try:
        window.editor_workspace.session.controller.dispatch(
            UpdateTimelineMarker(marker.marker_id, marker.tick, label.strip(), color_text)
        )
        window.editor_workspace._after_edit()
        if hasattr(window, "_s05_status"):
            window._s05_status(f"Marker '{label.strip()}' diperbarui.")
    except Exception as exc:
        if hasattr(window, "_s05_status"):
            window._s05_status(f"Edit marker gagal: {exc}")


def _delete_selected_marker(context: TimelineContextWidget) -> None:
    window = context.window()
    if not hasattr(window, "editor_workspace"):
        return
    marker_id = _selected_marker_id(context)
    if not marker_id:
        return
    try:
        window.editor_workspace.session.controller.dispatch(DeleteTimelineMarker(marker_id))
        window.editor_workspace._after_edit()
        if hasattr(window, "_s05_status"):
            window._s05_status("Marker dihapus sebagai satu transaksi Undo.")
    except Exception as exc:
        if hasattr(window, "_s05_status"):
            window._s05_status(f"Hapus marker gagal: {exc}")


def _wrap_marker_page(context: TimelineContextWidget) -> None:
    marker_list = context.marker_list
    index = context.stack.indexOf(marker_list)
    if index < 0:
        return
    context.stack.removeWidget(marker_list)
    page = QWidget(context.stack)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(marker_list, 1)
    actions = QHBoxLayout()
    actions.setContentsMargins(0, 0, 0, 0)
    edit = QPushButton("Edit Marker")
    delete = QPushButton("Hapus Marker")
    edit.setToolTip("Ubah nama dan warna marker terpilih")
    delete.setToolTip("Hapus marker terpilih")
    edit.clicked.connect(lambda: _edit_selected_marker(context))
    delete.clicked.connect(lambda: _delete_selected_marker(context))
    actions.addWidget(edit)
    actions.addWidget(delete)
    layout.addLayout(actions)
    context.stack.insertWidget(index, page)
    context.marker_page_s05 = page
    context.marker_edit_s05 = edit
    context.marker_delete_s05 = delete


def _context_init(self, *args, **kwargs) -> None:
    _original_context_init(self, *args, **kwargs)
    _wrap_marker_page(self)


def _canvas_init(self, *args, **kwargs) -> None:
    _original_canvas_init(self, *args, **kwargs)
    self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def _canvas_key_press(self, event) -> None:
    key = event.key()
    if key not in {
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
        Qt.Key.Key_Home,
        Qt.Key.Key_End,
    }:
        _original_canvas_key_press(self, event)
        return
    resolved = TimelineResolver().resolve(self._document)
    end = max(0, int(resolved.duration_tick))
    if key == Qt.Key.Key_Home:
        target = 0
    elif key == Qt.Key.Key_End:
        target = end
    else:
        step = self._document.timebase * (5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
        target = self._playhead_tick + (step if key == Qt.Key.Key_Right else -step)
        target = max(0, min(end, target))
    self.playhead_requested.emit(int(target))
    event.accept()


def _preview_rect(self) -> QRectF:
    ratio = getattr(self, "_s05_display_aspect", None)
    if ratio is None:
        return _original_preview_rect(self)
    margin = 12.0
    available_w = max(1.0, self.width() - margin * 2)
    available_h = max(1.0, self.height() - margin * 2)
    width = min(available_w, available_h * float(ratio))
    height = width / float(ratio)
    if height > available_h:
        height = available_h
        width = height * float(ratio)
    return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)


def _set_aspect(workspace: TimelinePreviewWorkspace, value: str) -> None:
    ratios = {"16:9": 16 / 9, "1:1": 1.0, "9:16": 9 / 16}
    workspace.preview._s05_display_aspect = ratios.get(str(value), 16 / 9)
    workspace.preview.update()


def _preview_init(self, *args, **kwargs) -> None:
    _original_preview_init(self, *args, **kwargs)
    self.aspect.currentTextChanged.connect(lambda value: _set_aspect(self, value))
    _set_aspect(self, self.aspect.currentText())
    # Recovered preview transport advances the playhead only; it has no audio
    # monitor backend. Keep the golden control visible but never pretend it changes
    # audible output. Clip gain remains editable in the inspector and is rendered.
    self.monitor_volume.setEnabled(False)
    self.monitor_volume.setToolTip(
        "Audio monitor belum tersedia pada engine preview recovered. Atur Volume clip di inspector untuk output render."
    )


def install_step05_timeline_completion() -> None:
    global _installed
    global _original_context_init, _original_canvas_init, _original_canvas_key_press
    global _original_preview_init, _original_preview_rect
    if _installed:
        return

    _original_context_init = TimelineContextWidget.__init__
    _original_canvas_init = TimelinePrecisionCanvas.__init__
    _original_canvas_key_press = TimelinePrecisionCanvas.keyPressEvent
    _original_preview_init = TimelinePreviewWorkspace.__init__
    _original_preview_rect = PreviewCanvas._canvas_rect

    TimelineContextWidget.__init__ = _context_init
    TimelinePrecisionCanvas.__init__ = _canvas_init
    TimelinePrecisionCanvas.keyPressEvent = _canvas_key_press
    TimelinePreviewWorkspace.__init__ = _preview_init
    PreviewCanvas._canvas_rect = _preview_rect
    _installed = True
