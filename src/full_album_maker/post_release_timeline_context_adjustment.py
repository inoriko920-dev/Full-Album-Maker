from __future__ import annotations

"""Golden-aligned presentation for the STEP05 Timeline context rail.

The production TimelineContextWidget remains the source of all lane state and
signals. This layer only regroups/reorders the existing row widgets, adds a
project title presentation label, and tightens spacing/card chrome for UI-04.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .foundation_tokens import TOKENS

_installed = False

_GROUPS = (
    ("Video (3)", ("V1", "V2", "V3")),
    ("Audio (2)", ("A1", "A2")),
    ("Elemen (2)", ("S1", "S2")),
)


def _remove_original_track_layout(track_layout, rows: set[QWidget]) -> None:
    while track_layout.count():
        item = track_layout.takeAt(0)
        widget = item.widget()
        if widget is None or widget in rows:
            continue
        widget.hide()
        widget.setParent(None)
        widget.deleteLater()


def _prepare_row(row: QWidget, *, last: bool) -> None:
    row.setObjectName("timelineContextRow")
    row.setProperty("lastRow", bool(last))
    row.setMinimumHeight(31)
    row.setMaximumHeight(33)
    layout = row.layout()
    if layout is not None:
        layout.setContentsMargins(9, 2, 6, 2)
        layout.setSpacing(5)

    labels = [label for label in row.findChildren(QLabel) if label is not row.name]
    if labels:
        labels[0].setObjectName("timelineContextKey")
        labels[0].setFixedWidth(28)
    row.name.setObjectName("timelineContextName")

    for button in (row.lock, row.eye):
        button.setObjectName("timelineContextMiniButton")
        button.setFixedSize(24, 24)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


def _group_heading(title: str, parent: QWidget) -> QWidget:
    host = QWidget(parent)
    host.setObjectName("timelineContextGroupHeading")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(5)
    chevron = QLabel("⌄", host)
    chevron.setObjectName("timelineContextChevron")
    chevron.setFixedWidth(12)
    row.addWidget(chevron)
    label = QLabel(title, host)
    label.setObjectName("timelineContextGroupTitle")
    row.addWidget(label, 1)
    host.setFixedHeight(22)
    return host


def _rebuild_track_page(widget) -> None:
    track_page = widget.stack.widget(0)
    track_layout = track_page.layout()
    if track_layout is None:
        return

    rows = set(widget.track_rows.values())
    _remove_original_track_layout(track_layout, rows)
    track_layout.setContentsMargins(0, 3, 0, 0)
    track_layout.setSpacing(4)

    widget._post_timeline_group_cards = []
    for title, keys in _GROUPS:
        track_layout.addWidget(_group_heading(title, track_page))
        card = QFrame(track_page)
        card.setObjectName("timelineContextGroupCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        for index, key in enumerate(keys):
            row = widget.track_rows[key]
            _prepare_row(row, last=index == len(keys) - 1)
            card_layout.addWidget(row)
        track_layout.addWidget(card)
        widget._post_timeline_group_cards.append(card)
    track_layout.addStretch(1)


def _install_header(widget) -> None:
    root = widget.layout()
    if root is None:
        return
    root.setContentsMargins(12, 8, 10, 8)
    root.setSpacing(6)

    header = QFrame(widget)
    header.setObjectName("timelineContextProjectHeader")
    row = QHBoxLayout(header)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    label = QLabel("Proyek: —", header)
    label.setObjectName("timelineContextProjectTitle")
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    row.addWidget(label, 1)
    more = QLabel("•••", header)
    more.setObjectName("timelineContextMore")
    more.setAlignment(Qt.AlignmentFlag.AlignCenter)
    more.setFixedWidth(22)
    row.addWidget(more)
    header.setFixedHeight(27)
    root.insertWidget(0, header)
    widget._post_timeline_project_label = label


def _apply_style(widget) -> None:
    widget.setStyleSheet(
        widget.styleSheet()
        + f"""
QFrame#timelineContextProjectHeader {{
    background: transparent;
    border: none;
}}
QLabel#timelineContextProjectTitle {{
    color: {TOKENS.text_primary};
    font-weight: 700;
    font-size: 12px;
}}
QLabel#timelineContextMore {{
    color: {TOKENS.primary_600};
    font-weight: 700;
}}
QWidget#timelineContextGroupHeading {{
    background: transparent;
    border: none;
}}
QLabel#timelineContextChevron {{
    color: {TOKENS.text_primary};
    font-weight: 700;
}}
QLabel#timelineContextGroupTitle {{
    color: {TOKENS.text_primary};
    font-weight: 700;
    font-size: 11px;
}}
QFrame#timelineContextGroupCard {{
    background: {TOKENS.surface};
    border: 1px solid {TOKENS.border};
    border-radius: 7px;
}}
QWidget#timelineContextRow {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {TOKENS.border};
}}
QWidget#timelineContextRow[lastRow="true"] {{
    border-bottom: none;
}}
QLabel#timelineContextKey {{
    color: {TOKENS.text_muted};
    font-size: 10px;
}}
QLabel#timelineContextName {{
    color: {TOKENS.text_primary};
    font-size: 10px;
}}
QPushButton#timelineContextMiniButton {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 0;
    color: {TOKENS.primary_600};
}}
QPushButton#timelineContextMiniButton:hover {{
    background: {TOKENS.selection_soft};
}}
"""
    )


def install_post_release_timeline_context_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .timeline_workspace_step05 import TimelineContextWidget

    previous_init = TimelineContextWidget.__init__
    previous_apply = TimelineContextWidget.apply_document

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _install_header(self)
        _rebuild_track_page(self)
        _apply_style(self)

    def wrapped_apply(self, document) -> None:
        previous_apply(self, document)
        label = getattr(self, "_post_timeline_project_label", None)
        if label is not None:
            title = str(getattr(document, "name", "") or getattr(document, "album_title", "") or "Proyek")
            label.setText(f"Proyek: {title}")
            label.setToolTip(title)

    TimelineContextWidget.__init__ = wrapped_init
    TimelineContextWidget.apply_document = wrapped_apply
    _installed = True
