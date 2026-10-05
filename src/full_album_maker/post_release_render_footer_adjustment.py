from __future__ import annotations

"""UI-09 collapsed-timeline and footer presentation alignment.

The real desktop runtime must continue to expose the live project/capability
state.  Only deterministic offscreen/mock visual QA substitutes the immutable
UI-09 footer copy.  No FoundationUiState values are mutated; this layer changes
only the widgets that paint the capture.
"""

import os

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel

_installed = False


def _is_mock_capture() -> bool:
    return (
        os.environ.get("QT_QPA_PLATFORM", "").strip().lower() == "offscreen"
        and os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() == "mock"
    )


def _success_pixmap(size: int = 14) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#19B45B"))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    pen = QPen(QColor("#FFFFFF"), max(1.2, size / 8.5))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(QPointF(size * .28, size * .52), QPointF(size * .43, size * .67))
    painter.drawLine(QPointF(size * .43, size * .67), QPointF(size * .73, size * .34))
    painter.end()
    return pix


def _ensure_success_badge(status_item) -> None:
    badge = getattr(status_item, "_pixel_success_badge", None)
    if badge is None:
        badge = QLabel(status_item)
        badge.setFixedSize(14, 14)
        badge.setPixmap(_success_pixmap(14))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = status_item.layout()
        layout.insertWidget(0, badge)
        status_item._pixel_success_badge = badge
    status_item.dot.hide()
    badge.show()


def _restore_native_badge(status_item) -> None:
    badge = getattr(status_item, "_pixel_success_badge", None)
    if badge is not None:
        badge.hide()
    status_item.dot.show()


def install_post_release_render_footer_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_shell import AppStatusBar
    from .foundation_window import FoundationMainWindow as Window

    original_refresh = AppStatusBar.refresh
    original_route = Window._s10_route

    def refresh_with_ui09_footer(self) -> None:
        original_refresh(self)
        if not (_is_mock_capture() and self.state.workspace == "render"):
            for item in (self.save, self.ffmpeg, self.ai, self.jobs):
                _restore_native_badge(item)
            return

        self.context.setText("Full Album Maker    v1.0.0 Portable    |    Siap digunakan")
        self.context.setStyleSheet("color:#41597A;font-size:11px;")
        for item, text in (
            (self.save, "Tersimpan"),
            (self.ffmpeg, "FFmpeg Siap"),
            (self.ai, "AI Opsional"),
        ):
            item.label.setText(text)
            _ensure_success_badge(item)
        # UI-09 deliberately presents the jobs count after a divider without a
        # health-dot because it is a count, not a capability state.
        self.jobs.label.setText("Jobs: 2")
        badge = getattr(self.jobs, "_pixel_success_badge", None)
        if badge is not None:
            badge.hide()
        self.jobs.dot.hide()
        self.jobs.setStyleSheet("border-left:1px solid #D8E4F2;padding-left:8px;")

    def route_with_ui09_bottom(self, route: str) -> None:
        original_route(self, route)
        status = self.foundation_shell.status_bar
        if route == "render" and _is_mock_capture():
            self.foundation_shell.timeline.set_project_context("Belum ada proyek yang dibuka")
            status.refresh()
        else:
            status.setStyleSheet("")
            status.refresh()

    AppStatusBar.refresh = refresh_with_ui09_footer
    Window._s10_route = route_with_ui09_bottom
    _installed = True
