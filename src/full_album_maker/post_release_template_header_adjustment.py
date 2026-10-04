from __future__ import annotations

"""Presentation-only UI-06 gallery header alignment.

Moves the existing authoritative sort QComboBox from the narrow context rail to
the gallery header. No sorting/filtering semantics are reimplemented. Preview
state remains owned by the production QLabel while the header matches the
approved Template Video composition.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

_installed = False


def _install_header(window) -> None:
    gallery = getattr(window, "template_workspace_s07", None)
    context = getattr(window, "template_context_s07", None)
    if gallery is None or context is None or getattr(gallery, "_post_template_header", False):
        return

    root = gallery.layout()
    if root is None or root.count() < 1:
        return
    header = root.itemAt(0).layout()
    if header is None:
        return

    # Rename the existing workspace labels rather than creating duplicate text.
    for label in gallery.findChildren(QLabel):
        text = label.text().strip()
        if text == "Template Studio":
            label.setText("Template Video")
            label.setStyleSheet("font-size:20px;font-weight:700;color:#10234A;")
        elif text == "Preview non-destruktif • Built-in immutable • Custom portabel":
            label.setText("Pilih template untuk video album Anda. Sesuaikan dengan mudah dan gunakan langsung.")

    # Keep the production preview-state QLabel alive and writable so STEP07
    # behavior/tests remain authoritative. It is only hidden from permanent
    # header chrome; the current value is exposed as a passive tooltip snapshot.
    gallery.preview_state.hide()
    gallery.setToolTip(gallery.preview_state.text())

    # The context rail already owns and wires this sort control. Reparent/move
    # that exact widget so sort_key and filters_changed behavior remain unchanged.
    sort_combo = context.sort
    old_layout = context.layout()
    if old_layout is not None:
        old_layout.removeWidget(sort_combo)
    sort_combo.setParent(gallery)
    sort_combo.show()
    sort_combo.setMinimumWidth(160)
    sort_combo.setMaximumWidth(185)
    sort_combo.setMinimumHeight(34)

    host = QWidget(gallery)
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    label = QLabel("⇅  Urutkan:")
    label.setObjectName("metadata")
    row.addWidget(label)
    row.addWidget(sort_combo)
    header.addWidget(host)

    gallery._post_template_header = True


def install_post_release_template_header_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .foundation_window import FoundationMainWindow as Window

    previous_route = Window._s07_route

    def route_with_header(self, route: str) -> None:
        if route == "template":
            _install_header(self)
        previous_route(self, route)

    Window._s07_route = route_with_header
    _installed = True
