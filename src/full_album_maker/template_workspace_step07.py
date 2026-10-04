from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .editor_models import ProjectDocument
from .foundation_components import FAMButton, FAMCard, FAMSegmented, set_dynamic_property
from .foundation_tokens import TOKENS
from .template_studio_step07 import (
    BACKGROUND_STYLES,
    CATEGORIES,
    COVER_POSITIONS,
    ORIGIN_BUILT_IN,
    ORIGIN_CUSTOM,
    RATIOS,
    SPACING_OPTIONS,
    TITLE_LAYOUTS,
    TemplateStudioDescriptor,
    TemplateStudioDraft,
)


TITLE_LABELS = {
    "left": "Judul di Kiri",
    "center": "Judul di Tengah",
    "right": "Judul di Kanan",
}
COVER_LABELS = {
    "left": "Cover di Kiri",
    "right": "Cover di Kanan",
    "full": "Penuh Layar",
}
BACKGROUND_LABELS = {
    "template": "Bawaan Template",
    "photo_dark_overlay": "Foto + Overlay Gelap",
    "solid_dark": "Gelap Solid",
}
SPACING_LABELS = {
    "compact": "Rapat",
    "normal": "Normal",
    "relaxed": "Lega",
}
SCOPE_LABELS = {
    "current": "Lagu Ini",
    "selected": "Pilihan",
    "all": "Semua Lagu",
}


class TemplateFilterContext(QFrame):
    filters_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("templateFilterContext")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        heading = QLabel("Template")
        heading.setObjectName("sectionHeading")
        root.addWidget(heading)
        subtitle = QLabel("Built-in, Custom, dan Favorit")
        subtitle.setObjectName("muted")
        root.addWidget(subtitle)

        self.origin = FAMSegmented([
            (ORIGIN_BUILT_IN, "Built-in"),
            (ORIGIN_CUSTOM, "Custom"),
            ("FAVORITE", "Favorit"),
        ])
        root.addWidget(self.origin)
        for button in self.origin._buttons.values():
            button.clicked.connect(self.filters_changed.emit)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari template...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self.filters_changed.emit())
        root.addWidget(self.search)

        root.addWidget(self._label("Kategori"))
        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.currentIndexChanged.connect(lambda _index: self.filters_changed.emit())
        root.addWidget(self.category)

        root.addWidget(self._label("Rasio"))
        self.ratio = FAMSegmented([(ratio, ratio) for ratio in RATIOS])
        root.addWidget(self.ratio)
        for button in self.ratio._buttons.values():
            button.clicked.connect(self.filters_changed.emit)

        root.addWidget(self._label("Urutkan"))
        self.sort = QComboBox()
        self.sort.addItems(["Terbaru", "Nama A-Z"])
        self.sort.currentIndexChanged.connect(lambda _index: self.filters_changed.emit())
        root.addWidget(self.sort)

        self.result_count = QLabel("0 template")
        self.result_count.setObjectName("metadata")
        root.addWidget(self.result_count)
        self.warning = QLabel("")
        self.warning.setObjectName("metadata")
        self.warning.setWordWrap(True)
        root.addWidget(self.warning)
        root.addStretch(1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("metadata")
        return label

    @property
    def origin_key(self) -> str:
        return self.origin.checked_value() or ORIGIN_BUILT_IN

    @property
    def category_key(self) -> str:
        return self.category.currentText() or "Semua"

    @property
    def ratio_key(self) -> str:
        return self.ratio.checked_value() or "16:9"

    @property
    def sort_key(self) -> str:
        return self.sort.currentText() or "Terbaru"

    def set_counts(self, count: int, *, custom_errors: Iterable[str] = ()) -> None:
        self.result_count.setText(f"{max(0, int(count))} template")
        errors = tuple(custom_errors)
        self.warning.setText(
            f"⚠ {len(errors)} template Custom rusak dilewati."
            if errors else ""
        )


class TemplateThumbnailPlaceholder(QWidget):
    def __init__(self, name: str, template_id: str, parent=None) -> None:
        super().__init__(parent)
        self.name = name
        self.template_id = template_id
        self._pixmap = QPixmap()
        self._status = "FALLBACK"
        self.setMinimumHeight(98)

    @property
    def thumbnail_status(self) -> str:
        return self._status

    def set_image_path(self, path: str, status: str = "RENDERED") -> None:
        pixmap = QPixmap(str(path)) if path and Path(path).is_file() else QPixmap()
        if not pixmap.isNull():
            self._pixmap = pixmap
            self._status = status
        elif status == "FALLBACK":
            self._pixmap = QPixmap()
            self._status = "FALLBACK"
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.fillRect(rect, QColor("#EAF3FF"))
        painter.setPen(QPen(QColor("#BFD6F4"), 1))
        painter.drawRoundedRect(rect, 8, 8)
        inner = rect.adjusted(6, 6, -6, -6)
        if not self._pixmap.isNull():
            target = inner.toRect()
            scaled = self._pixmap.scaled(
                target.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            source_x = max(0, (scaled.width() - target.width()) // 2)
            source_y = max(0, (scaled.height() - target.height()) // 2)
            painter.drawPixmap(target, scaled, scaled.rect().adjusted(source_x, source_y, -source_x, -source_y))
        else:
            painter.fillRect(inner, QColor("#10234A"))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(
                inner.adjusted(10, 8, -10, -8),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                self.name,
            )
        painter.end()


class TemplateCard(FAMCard):
    selected = Signal(str)
    preview_requested = Signal(str)
    use_requested = Signal(str)
    favorite_requested = Signal(str, bool)

    def __init__(self, descriptor: TemplateStudioDescriptor, *, favorite: bool = False, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.descriptor = descriptor
        self._favorite = bool(favorite)
        self._selected = bool(selected)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(175)
        self.setMaximumWidth(260)
        self.setProperty("templateSelected", self._selected)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)
        self.thumbnail = TemplateThumbnailPlaceholder(descriptor.name, descriptor.template_id)
        root.addWidget(self.thumbnail)

        top = QHBoxLayout()
        badge = QLabel("Built-in" if descriptor.origin == ORIGIN_BUILT_IN else "Custom")
        badge.setObjectName("statusChip")
        top.addWidget(badge)
        top.addStretch(1)
        self.heart = QPushButton("♥" if self._favorite else "♡")
        self.heart.setObjectName("tabButton")
        self.heart.setFixedWidth(32)
        self.heart.setAccessibleName("Favorit")
        self.heart.clicked.connect(self._toggle_favorite)
        top.addWidget(self.heart)
        root.addLayout(top)

        title = QLabel(descriptor.name)
        title.setObjectName("sectionHeading")
        title.setWordWrap(True)
        root.addWidget(title)
        tags = QLabel(" • ".join(descriptor.categories[:2]) + f"   {descriptor.ratios[0]}")
        tags.setObjectName("metadata")
        tags.setWordWrap(True)
        root.addWidget(tags)

        actions = QHBoxLayout()
        self.preview = FAMButton("Preview", kind="ghost")
        self.use = FAMButton("Gunakan", kind="primary")
        self.preview.clicked.connect(lambda: self.preview_requested.emit(descriptor.template_id))
        self.use.clicked.connect(lambda: self.use_requested.emit(descriptor.template_id))
        actions.addWidget(self.preview)
        actions.addWidget(self.use)
        root.addLayout(actions)
        self._refresh_selected()

    def _refresh_selected(self) -> None:
        set_dynamic_property(self, "templateSelected", self._selected)
        border = TOKENS.primary_600 if self._selected else TOKENS.border
        width = 2 if self._selected else 1
        self.setStyleSheet(
            f"QFrame#famCard {{ border: {width}px solid {border}; border-radius: {TOKENS.radius_card}px; background: {TOKENS.surface}; }}"
        )

    def _toggle_favorite(self) -> None:
        self._favorite = not self._favorite
        self.heart.setText("♥" if self._favorite else "♡")
        self.favorite_requested.emit(self.descriptor.template_id, self._favorite)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.descriptor.template_id)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.selected.emit(self.descriptor.template_id)
            self.preview_requested.emit(self.descriptor.template_id)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Space:
            self._toggle_favorite()
            event.accept()
            return
        super().keyPressEvent(event)


class TemplateGalleryWorkspace(QFrame):
    template_selected = Signal(str)
    preview_requested = Signal(str)
    use_requested = Signal(str)
    favorite_requested = Signal(str, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("templateGalleryWorkspace")
        self._cards: dict[str, TemplateCard] = {}
        self._selected_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)
        header = QHBoxLayout()
        box = QVBoxLayout()
        heading = QLabel("Template Studio")
        heading.setObjectName("workspaceHeading")
        box.addWidget(heading)
        subtitle = QLabel("Preview non-destruktif • Built-in immutable • Custom portabel")
        subtitle.setObjectName("muted")
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch(1)
        self.preview_state = QLabel("Pilih template untuk melihat preview draft")
        self.preview_state.setObjectName("metadata")
        header.addWidget(self.preview_state)
        root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(9)
        self.grid.setVerticalSpacing(9)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty)

    @property
    def selected_template_id(self) -> str:
        return self._selected_id

    def set_templates(self, descriptors: Iterable[TemplateStudioDescriptor], *, selected_id: str = "", favorites: Iterable[str] = ()) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._cards.clear()
        items = tuple(descriptors)
        favorite_ids = {str(value) for value in favorites}
        self._selected_id = selected_id if any(item.template_id == selected_id for item in items) else (items[0].template_id if items else "")
        for index, descriptor in enumerate(items):
            card = TemplateCard(
                descriptor,
                favorite=descriptor.template_id in favorite_ids,
                selected=descriptor.template_id == self._selected_id,
            )
            card.selected.connect(self._select)
            card.preview_requested.connect(self.preview_requested.emit)
            card.use_requested.connect(self.use_requested.emit)
            card.favorite_requested.connect(self.favorite_requested.emit)
            self.grid.addWidget(card, index // 4, index % 4)
            self._cards[descriptor.template_id] = card
        self.empty.setText("Tidak ada template yang cocok dengan filter." if not items else "")
        if items:
            self.grid.setRowStretch((len(items) + 3) // 4, 1)

    def set_thumbnail(self, template_id: str, path: str, status: str) -> None:
        card = self._cards.get(str(template_id))
        if card is not None:
            card.thumbnail.set_image_path(path, status)

    def _select(self, template_id: str) -> None:
        if template_id == self._selected_id:
            self.template_selected.emit(template_id)
            return
        self._selected_id = template_id
        for key, card in self._cards.items():
            card._selected = key == template_id
            card._refresh_selected()
        self.template_selected.emit(template_id)

    def set_preview_summary(self, descriptor: TemplateStudioDescriptor, document: ProjectDocument, target_count: int) -> None:
        template_layers = len([layer for layer in document.layers if layer.origin == "template"])
        self.preview_state.setText(
            f"Preview: {descriptor.name} • {template_layers} layer • target {target_count} lagu • belum diterapkan"
        )

    def clear_preview(self) -> None:
        self.preview_state.setText("Draft direset • proyek tidak berubah")


class TemplateInspector(QFrame):
    draft_changed = Signal()
    preview_requested = Signal()
    use_requested = Signal()
    create_requested = Signal()
    duplicate_requested = Signal()
    save_custom_requested = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("templateInspector")
        self._template_id = ""
        self._origin = ORIGIN_BUILT_IN
        self._updating = False
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(7)

        self.heading = QLabel("Template")
        self.heading.setObjectName("sectionHeading")
        root.addWidget(self.heading)
        self.identity = QLabel("Pilih template")
        self.identity.setObjectName("metadata")
        self.identity.setWordWrap(True)
        root.addWidget(self.identity)

        self.title_layout = self._combo(root, "Title Layout", [(value, TITLE_LABELS[value]) for value in TITLE_LAYOUTS])
        self.cover_position = self._combo(root, "Posisi Cover", [(value, COVER_LABELS[value]) for value in COVER_POSITIONS])
        self.background = self._combo(root, "Background", [(value, BACKGROUND_LABELS[value]) for value in BACKGROUND_STYLES])
        self.spacing = self._combo(root, "Spacing", [(value, SPACING_LABELS[value]) for value in SPACING_OPTIONS])

        root.addWidget(self._field_label("Tipografi"))
        self.typography = QComboBox()
        self.typography.addItem("Noto Sans — fallback aman", "noto_sans_safe")
        self.typography.setToolTip("Renderer recovered belum menyediakan kontrak font-family bebas; STEP07 memakai fallback deterministic.")
        root.addWidget(self.typography)

        root.addWidget(self._field_label("Overlay Opacity"))
        opacity_row = QHBoxLayout()
        self.overlay = QSlider(Qt.Orientation.Horizontal)
        self.overlay.setRange(0, 100)
        self.overlay.setValue(60)
        self.overlay_value = QLabel("60%")
        self.overlay_value.setObjectName("metadata")
        opacity_row.addWidget(self.overlay, 1)
        opacity_row.addWidget(self.overlay_value)
        root.addLayout(opacity_row)
        self.overlay.valueChanged.connect(self._opacity_changed)

        root.addWidget(self._field_label("Terapkan ke"))
        self.scope = QComboBox()
        for value, label in SCOPE_LABELS.items():
            self.scope.addItem(label, value)
        root.addWidget(self.scope)

        action_row = QHBoxLayout()
        self.preview = FAMButton("Preview", kind="ghost")
        self.use = FAMButton("Gunakan", kind="primary")
        action_row.addWidget(self.preview)
        action_row.addWidget(self.use)
        root.addLayout(action_row)

        custom_row = QGridLayout()
        self.create = FAMButton("Buat Template", kind="secondary")
        self.duplicate = FAMButton("Duplikat", kind="secondary")
        self.save_custom = FAMButton("Simpan Custom", kind="secondary")
        self.reset = FAMButton("Reset", kind="ghost")
        custom_row.addWidget(self.create, 0, 0)
        custom_row.addWidget(self.duplicate, 0, 1)
        custom_row.addWidget(self.save_custom, 1, 0)
        custom_row.addWidget(self.reset, 1, 1)
        root.addLayout(custom_row)
        root.addStretch(1)

        for combo in (self.title_layout, self.cover_position, self.background, self.spacing, self.typography):
            combo.currentIndexChanged.connect(lambda _index: self._emit_changed())
        self.preview.clicked.connect(self.preview_requested.emit)
        self.use.clicked.connect(self.use_requested.emit)
        self.create.clicked.connect(self.create_requested.emit)
        self.duplicate.clicked.connect(self.duplicate_requested.emit)
        self.save_custom.clicked.connect(self.save_custom_requested.emit)
        self.reset.clicked.connect(self.reset_requested.emit)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("metadata")
        return label

    def _combo(self, root: QVBoxLayout, label: str, options: Iterable[tuple[str, str]]) -> QComboBox:
        root.addWidget(self._field_label(label))
        combo = QComboBox()
        for value, text in options:
            combo.addItem(text, value)
        root.addWidget(combo)
        return combo

    def _opacity_changed(self, value: int) -> None:
        self.overlay_value.setText(f"{int(value)}%")
        self._emit_changed()

    def _emit_changed(self) -> None:
        if not self._updating:
            self.draft_changed.emit()

    def set_template(self, descriptor: TemplateStudioDescriptor, draft: TemplateStudioDraft) -> None:
        self._updating = True
        try:
            self._template_id = descriptor.template_id
            self._origin = descriptor.origin
            self.heading.setText(descriptor.name)
            self.identity.setText(
                f"{'Built-in • immutable' if descriptor.origin == ORIGIN_BUILT_IN else 'Custom • dapat disimpan'} • {draft.ratio}"
            )
            self._set_combo(self.title_layout, draft.title_layout)
            self._set_combo(self.cover_position, draft.cover_position)
            self._set_combo(self.background, draft.background_style)
            self._set_combo(self.spacing, draft.spacing)
            self._set_combo(self.typography, draft.typography)
            self.overlay.setValue(round(float(draft.overlay_opacity) * 100))
            self.overlay_value.setText(f"{self.overlay.value()}%")
            self.save_custom.setEnabled(descriptor.origin == ORIGIN_CUSTOM)
            self.save_custom.setToolTip(
                "Simpan perubahan template Custom secara atomic."
                if descriptor.origin == ORIGIN_CUSTOM
                else "Built-in immutable. Gunakan Duplikat untuk membuat Custom."
            )
        finally:
            self._updating = False

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def draft(self) -> TemplateStudioDraft:
        draft = TemplateStudioDraft(
            template_id=self._template_id,
            title_layout=str(self.title_layout.currentData()),
            cover_position=str(self.cover_position.currentData()),
            background_style=str(self.background.currentData()),
            spacing=str(self.spacing.currentData()),
            typography=str(self.typography.currentData()),
            overlay_opacity=self.overlay.value() / 100.0,
        )
        draft.validate()
        return draft

    @property
    def scope_key(self) -> str:
        return str(self.scope.currentData() or "current")
