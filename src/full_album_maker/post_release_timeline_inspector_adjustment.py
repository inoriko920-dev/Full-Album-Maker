from __future__ import annotations

"""Golden-aligned presentation for the STEP05 Timeline clip inspector.

All editable values and command emission remain owned by TimelineClipInspector.
This layer only rearranges those existing controls and adds a volume slider mirror
that writes back to the production ``self.volume`` spin box before Apply is used.
"""

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS

_installed = False


def _clear_layout(layout, preserve: set[QWidget]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        nested = item.layout()
        if nested is not None:
            _clear_layout(nested, preserve)
            continue
        widget = item.widget()
        if widget is None:
            continue
        if widget in preserve:
            widget.setParent(layout.parentWidget())
        else:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


def _field_row(parent: QWidget, text: str, control: QWidget, *, multiline: bool = False) -> QWidget:
    host = QWidget(parent)
    host.setObjectName("timelineInspectorFieldRow")
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(8)
    label = QLabel(text, host)
    label.setObjectName("timelineInspectorFieldLabel")
    label.setFixedWidth(96)
    label.setWordWrap(bool(multiline))
    row.addWidget(label)
    row.addWidget(control, 1)
    host.setMinimumHeight(34 if not multiline else 42)
    return host


def _build_header(inspector, root) -> None:
    card = QFrame(inspector)
    card.setObjectName("timelineInspectorIdentity")
    row = QHBoxLayout(card)
    row.setContentsMargins(10, 8, 8, 8)
    row.setSpacing(8)

    icon = QLabel(card)
    icon.setObjectName("timelineInspectorIdentityIcon")
    icon.setPixmap(foundation_icon("album", color=TOKENS.primary_600, size=23).pixmap(23, 23))
    icon.setFixedSize(28, 28)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(icon)

    text_host = QWidget(card)
    text_layout = QVBoxLayout(text_host)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(1)
    inspector.heading.setObjectName("timelineInspectorHeading")
    inspector.subtitle.setObjectName("timelineInspectorSubtitle")
    inspector.subtitle.setWordWrap(False)
    text_layout.addWidget(inspector.heading)
    text_layout.addWidget(inspector.subtitle)
    row.addWidget(text_host, 1)

    more = QLabel("•••", card)
    more.setObjectName("timelineInspectorMore")
    more.setAlignment(Qt.AlignmentFlag.AlignCenter)
    more.setFixedWidth(24)
    row.addWidget(more)
    root.addWidget(card)
    inspector._post_timeline_identity = card


def _prepare_spin(control) -> None:
    control.setObjectName("timelineInspectorSpin")
    control.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
    control.setAlignment(Qt.AlignmentFlag.AlignRight)
    control.setMinimumHeight(31)
    control.setMaximumHeight(33)


def _db_text(gain: float) -> str:
    value = max(0.0, float(gain))
    if value <= 0.0001:
        return "−∞ dB"
    db = 20.0 * math.log10(value)
    if abs(db) < 0.05:
        return "0 dB"
    return f"{db:+.1f} dB"


def _build_audio_section(inspector, root) -> None:
    section = QFrame(inspector)
    section.setObjectName("timelineInspectorAudio")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 8, 0, 0)
    layout.setSpacing(7)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title = QLabel("Audio", section)
    title.setObjectName("timelineInspectorAudioTitle")
    title_row.addWidget(title)
    title_row.addStretch(1)
    arrow = QLabel("⌃", section)
    arrow.setObjectName("timelineInspectorAudioArrow")
    title_row.addWidget(arrow)
    layout.addLayout(title_row)

    volume_row = QHBoxLayout()
    volume_row.setContentsMargins(14, 0, 0, 0)
    volume_row.setSpacing(8)
    label = QLabel("Volume", section)
    label.setObjectName("timelineInspectorFieldLabel")
    label.setFixedWidth(64)
    volume_row.addWidget(label)
    slider = QSlider(Qt.Orientation.Horizontal, section)
    slider.setObjectName("timelineInspectorVolumeSlider")
    slider.setRange(0, 400)
    slider.setSingleStep(5)
    slider.setPageStep(20)
    volume_row.addWidget(slider, 1)
    value = QLabel("0 dB", section)
    value.setObjectName("timelineInspectorDb")
    value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    value.setFixedWidth(54)
    volume_row.addWidget(value)
    layout.addLayout(volume_row)

    def slider_to_owner(raw: int) -> None:
        owner = inspector.volume
        target = max(owner.minimum(), min(owner.maximum(), int(raw) / 100.0))
        if abs(owner.value() - target) > 0.0001:
            owner.setValue(target)
        value.setText(_db_text(owner.value()))

    slider.valueChanged.connect(slider_to_owner)
    inspector.volume.valueChanged.connect(
        lambda gain: (
            slider.blockSignals(True),
            slider.setValue(max(0, min(400, int(round(float(gain) * 100))))),
            slider.blockSignals(False),
            value.setText(_db_text(float(gain))),
        )
    )
    inspector._post_timeline_audio = section
    inspector._post_timeline_volume_slider = slider
    inspector._post_timeline_db = value
    root.addWidget(section)


def _sync_presentation(inspector) -> None:
    audio = getattr(inspector, "_post_timeline_audio", None)
    slider = getattr(inspector, "_post_timeline_volume_slider", None)
    db = getattr(inspector, "_post_timeline_db", None)
    if audio is not None:
        audio.setVisible(bool(getattr(inspector, "_song_id", "")))
    if slider is not None:
        slider.blockSignals(True)
        slider.setValue(max(0, min(400, int(round(inspector.volume.value() * 100)))))
        slider.setEnabled(inspector.volume.isEnabled())
        slider.blockSignals(False)
    if db is not None:
        db.setText(_db_text(inspector.volume.value()))
        db.setEnabled(inspector.volume.isEnabled())


def _rebuild(inspector) -> None:
    root = inspector.layout()
    preserve = {
        inspector.heading,
        inspector.subtitle,
        inspector.start,
        inspector.duration,
        inspector.fade_in,
        inspector.fade_out,
        inspector.crossfade,
        inspector.volume,
        inspector.locked,
        inspector.apply_button,
    }
    _clear_layout(root, preserve)
    root.setContentsMargins(10, 8, 10, 8)
    root.setSpacing(6)

    _build_header(inspector, root)
    for label, control, multiline in (
        ("Start", inspector.start, False),
        ("Durasi", inspector.duration, False),
        ("Fade In", inspector.fade_in, False),
        ("Fade Out", inspector.fade_out, False),
        ("Crossfade\n(ke klip berikut)", inspector.crossfade, True),
    ):
        _prepare_spin(control)
        root.addWidget(_field_row(inspector, label, control, multiline=multiline))

    inspector.volume.hide()
    inspector.locked.setObjectName("timelineInspectorLock")
    inspector.locked.setMinimumHeight(28)
    root.addWidget(inspector.locked)

    _build_audio_section(inspector, root)

    inspector.apply_button.setObjectName("timelineInspectorApply")
    inspector.apply_button.setMinimumHeight(32)
    inspector.apply_button.setMaximumHeight(34)
    root.addWidget(inspector.apply_button)
    root.addStretch(1)

    inspector.setStyleSheet(
        inspector.styleSheet()
        + f"""
QFrame#timelineInspectorIdentity {{
    background: {TOKENS.surface};
    border: 1px solid {TOKENS.border};
    border-radius: 8px;
}}
QLabel#timelineInspectorHeading {{
    color: {TOKENS.text_primary};
    font-weight: 700;
    font-size: 12px;
}}
QLabel#timelineInspectorSubtitle {{
    color: {TOKENS.text_muted};
    font-size: 10px;
}}
QLabel#timelineInspectorMore {{
    color: {TOKENS.primary_600};
    font-weight: 700;
}}
QWidget#timelineInspectorFieldRow {{
    background: transparent;
    border: none;
}}
QLabel#timelineInspectorFieldLabel {{
    color: {TOKENS.text_primary};
    font-size: 10px;
}}
QDoubleSpinBox#timelineInspectorSpin {{
    min-height: 30px;
    max-height: 32px;
    padding: 0 8px;
    background: {TOKENS.surface};
    color: {TOKENS.text_primary};
    border: 1px solid {TOKENS.border};
    border-radius: 7px;
}}
QCheckBox#timelineInspectorLock {{
    color: {TOKENS.text_primary};
    font-size: 10px;
    spacing: 7px;
}}
QFrame#timelineInspectorAudio {{
    border-top: 1px solid {TOKENS.border};
    background: transparent;
}}
QLabel#timelineInspectorAudioTitle {{
    color: {TOKENS.text_primary};
    font-weight: 700;
    font-size: 11px;
}}
QLabel#timelineInspectorAudioArrow {{
    color: {TOKENS.text_primary};
    font-weight: 700;
}}
QLabel#timelineInspectorDb {{
    color: {TOKENS.text_muted};
    font-size: 10px;
}}
"""
    )
    _sync_presentation(inspector)


def install_post_release_timeline_inspector_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .timeline_workspace_step05 import TimelineClipInspector

    previous_init = TimelineClipInspector.__init__
    previous_none = TimelineClipInspector.set_none
    previous_song = TimelineClipInspector.set_song
    previous_layer = TimelineClipInspector.set_layer

    def wrapped_init(self, *args, **kwargs) -> None:
        previous_init(self, *args, **kwargs)
        _rebuild(self)

    def wrapped_none(self) -> None:
        previous_none(self)
        _sync_presentation(self)

    def wrapped_song(self, document, song_id: str) -> None:
        previous_song(self, document, song_id)
        _sync_presentation(self)

    def wrapped_layer(self, document, layer_id: str) -> None:
        previous_layer(self, document, layer_id)
        _sync_presentation(self)

    TimelineClipInspector.__init__ = wrapped_init
    TimelineClipInspector.set_none = wrapped_none
    TimelineClipInspector.set_song = wrapped_song
    TimelineClipInspector.set_layer = wrapped_layer
    _installed = True
