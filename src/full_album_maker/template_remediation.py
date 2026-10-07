from __future__ import annotations

import hashlib
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .editor_models import TIMEBASE
from .foundation_components import FAMButton, FAMSegmented
from .foundation_tokens import TOKENS
from .template_studio_step07 import CATEGORIES, ORIGIN_BUILT_IN, ORIGIN_CUSTOM
from .template_workspace_step07 import (
    TemplateCard,
    TemplateFilterContext,
    TemplateGalleryWorkspace,
    TemplateInspector,
    TemplateThumbnailPlaceholder,
)
from .timeline_resolver import TimelineResolver
from .visual_workspace_step06 import VisualAlignmentCanvas

_installed = False
_originals: dict[str, Any] = {}


def _seed_colors(value: str) -> tuple[QColor, QColor, QColor]:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    families = (
        ("#274763", "#E79B6A", "#17283B"),
        ("#355B70", "#D4A36E", "#233B4B"),
        ("#2F604F", "#D7B774", "#1F3A31"),
        ("#384C70", "#D88B65", "#202E48"),
        ("#4B4A68", "#D5A06E", "#24253B"),
        ("#27556B", "#E0BD87", "#163743"),
        ("#374C72", "#D6916B", "#1E2A43"),
        ("#356170", "#E3BC82", "#243F46"),
    )
    top, mid, bottom = families[digest[0] % len(families)]
    return QColor(top), QColor(mid), QColor(bottom)


def _paint_template_scene(
    painter: QPainter,
    rect: QRectF,
    name: str,
    template_id: str,
    *,
    show_play: bool = False,
) -> None:
    top, mid, bottom = _seed_colors(template_id)
    grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    grad.setColorAt(0.0, top)
    grad.setColorAt(0.62, mid)
    grad.setColorAt(1.0, bottom)
    painter.fillRect(rect, grad)

    # Landscape silhouettes keep the thumbnail deterministic and readable.
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(bottom.red(), bottom.green(), bottom.blue(), 235))
    painter.drawPolygon(QPolygonF([
        QPointF(rect.left(), rect.top() + rect.height() * 0.74),
        QPointF(rect.left() + rect.width() * 0.14, rect.top() + rect.height() * 0.58),
        QPointF(rect.left() + rect.width() * 0.28, rect.top() + rect.height() * 0.70),
        QPointF(rect.left() + rect.width() * 0.45, rect.top() + rect.height() * 0.52),
        QPointF(rect.left() + rect.width() * 0.62, rect.top() + rect.height() * 0.69),
        QPointF(rect.left() + rect.width() * 0.80, rect.top() + rect.height() * 0.55),
        QPointF(rect.right(), rect.top() + rect.height() * 0.66),
        QPointF(rect.right(), rect.bottom()),
        QPointF(rect.left(), rect.bottom()),
    ]))

    # Golden's selected template uses a portrait at sunset; other cards keep
    # distinct generated compositions instead of copying the reference pixels.
    if template_id in {"spotify_clean", "dark_cinematic"}:
        painter.setBrush(QColor("#1D222A"))
        head = QRectF(
            rect.left() + rect.width() * 0.72,
            rect.top() + rect.height() * 0.20,
            rect.width() * 0.10,
            rect.height() * 0.22,
        )
        painter.drawEllipse(head)
        painter.drawPolygon(QPolygonF([
            QPointF(rect.left() + rect.width() * 0.69, rect.top() + rect.height() * 0.41),
            QPointF(rect.left() + rect.width() * 0.79, rect.top() + rect.height() * 0.35),
            QPointF(rect.left() + rect.width() * 0.88, rect.bottom()),
            QPointF(rect.left() + rect.width() * 0.63, rect.bottom()),
        ]))

    painter.setPen(QColor("#FFFFFF"))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(max(8, int(rect.height() * 0.09)))
    painter.setFont(font)
    title_rect = rect.adjusted(rect.width() * 0.08, rect.height() * 0.12, -rect.width() * 0.20, -rect.height() * 0.12)
    painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap, name)

    if show_play:
        bar = QRectF(rect.left(), rect.bottom() - 28, rect.width(), 28)
        painter.fillRect(bar, QColor(0, 0, 0, 150))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(bar.adjusted(10, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter, "▶   00:00 / 00:42")


class TemplateSelectionPreview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._name = "Pilih template"
        self._template_id = ""
        self.setMinimumHeight(145)
        self.setMaximumHeight(190)

    def set_template(self, name: str, template_id: str) -> None:
        self._name = str(name or "Template")
        self._template_id = str(template_id or "")
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#F5F8FC"))
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        _paint_template_scene(painter, rect, self._name, self._template_id or "preview", show_play=True)
        painter.setPen(QPen(QColor("#C9D6E5"), 1))
        painter.drawRoundedRect(rect, 7, 7)
        painter.end()


class TemplateRemediationTimelineCanvas(VisualAlignmentCanvas):
    """Presentation-only three-lane Template timeline; state still comes from shared resolver."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(104)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        resolved = TimelineResolver().resolve(self._document)
        left = 112
        ruler = 20
        usable_h = max(84, self.height() - ruler)
        row_h = usable_h / 3.0
        duration = max(TIMEBASE, resolved.duration_tick)
        pps = max(0.01, max(140, self.width() - left - 8) / (duration / TIMEBASE))

        painter.fillRect(QRectF(0, 0, left, self.height()), QColor("#F8FBFF"))
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawLine(left, 0, left, self.height())
        for row in range(4):
            y = ruler + row * row_h
            painter.drawLine(0, int(y), self.width(), int(y))

        labels = ("▣  Video", "♫  Audio", "T  Teks")
        for index, label in enumerate(labels):
            painter.setPen(QColor(TOKENS.text_primary))
            painter.drawText(
                QRectF(10, ruler + index * row_h, left - 18, row_h),
                Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        duration_seconds = max(1, int(round(duration / TIMEBASE)))
        major = 30 if duration_seconds <= 360 else 60
        for second in range(0, duration_seconds + major, major):
            x = left + second * pps
            if x > self.width():
                break
            painter.setPen(QColor(TOKENS.text_muted))
            painter.drawText(QRectF(x + 2, 1, 52, 16), Qt.AlignmentFlag.AlignLeft, f"{second // 60:02d}:{second % 60:02d}")

        songs = self._document.song_map()
        for event in resolved.songs:
            x = left + (event.start_tick / TIMEBASE) * pps
            width = max(5.0, ((event.end_tick - event.start_tick) / TIMEBASE) * pps)
            selected = event.song_id in self._selected_ids
            title = songs[event.song_id].display_title or "Lagu"

            video = QRectF(x + 1, ruler + 3, max(4, width - 2), row_h - 6)
            painter.setPen(QPen(QColor("#1766E8" if selected else "#75A0D5"), 2 if selected else 1))
            painter.setBrush(QColor("#DDEEFF"))
            painter.drawRoundedRect(video, 3, 3)
            painter.setPen(QColor("#174C88"))
            painter.drawText(video.adjusted(5, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, title)

            audio = QRectF(x + 1, ruler + row_h + 3, max(4, width - 2), row_h - 6)
            painter.setPen(QPen(QColor("#48A68B"), 1))
            painter.setBrush(QColor("#CFF4E8"))
            painter.drawRoundedRect(audio, 3, 3)
            painter.setPen(QColor("#256F61"))
            painter.drawText(audio.adjusted(5, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, title)

            text_rect = QRectF(x + 1, ruler + row_h * 2 + 3, max(4, width - 2), row_h - 6)
            painter.setPen(QPen(QColor("#9B78D2"), 1))
            painter.setBrush(QColor("#EADDFC"))
            painter.drawRoundedRect(text_rect, 3, 3)
            painter.setPen(QColor("#69479A"))
            painter.drawText(text_rect.adjusted(5, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter, title)

        play_x = left + (self._playhead_tick / TIMEBASE) * pps
        painter.setPen(QPen(QColor(TOKENS.primary_600), 2))
        painter.drawLine(int(play_x), 0, int(play_x), self.height())
        painter.end()


def _thumbnail_paint(self, _event) -> None:
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
    if not self._pixmap.isNull():
        target = rect.toRect()
        scaled = self._pixmap.scaled(
            target.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(target, scaled)
    else:
        _paint_template_scene(painter, rect, self.name, self.template_id)
    painter.setPen(QPen(QColor("#B9C9DB"), 1))
    painter.drawRoundedRect(rect, 7, 7)
    painter.end()


def _card_init(self, *args, **kwargs) -> None:
    _originals["card_init"](self, *args, **kwargs)
    self.setMinimumWidth(170)
    self.setMaximumWidth(235)
    self.thumbnail.setMinimumHeight(92)
    self.thumbnail.setMaximumHeight(108)
    root = self.layout()
    root.setContentsMargins(6, 6, 6, 6)
    root.setSpacing(3)
    self.preview.setText("Preview")
    self.use.setText("▷  Gunakan")


def _context_init(self, *args, **kwargs) -> None:
    _originals["context_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(8, 8, 8, 8)
    root.setSpacing(7)

    for label in self.findChildren(QLabel):
        if label.text() in {"Template", "Built-in, Custom, dan Favorit", "Kategori", "Urutkan"}:
            label.hide()
        elif label.text() == "Rasio":
            label.setText("Rasio Video")
        elif label is self.result_count:
            label.hide()

    self.origin.hide()
    self.category.hide()
    self.sort.hide()

    origin_box = QWidget(self)
    origin_lay = QVBoxLayout(origin_box)
    origin_lay.setContentsMargins(0, 0, 0, 0)
    origin_lay.setSpacing(3)
    self.ui06_origin_buttons: dict[str, QPushButton] = {}
    for key, label, glyph in (
        (ORIGIN_BUILT_IN, "Built-in", "▣"),
        (ORIGIN_CUSTOM, "Custom", "▤"),
        ("FAVORITE", "Favorit", "♡"),
    ):
        button = QPushButton(f"{glyph}  {label}")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setObjectName("tabButton")
        button.setMinimumHeight(34)
        button.setChecked(key == self.origin_key)
        button.clicked.connect(lambda _checked=False, value=key: _sync_origin(self, value))
        origin_lay.addWidget(button)
        self.ui06_origin_buttons[key] = button
    root.insertWidget(0, origin_box)

    category_box = QWidget(self)
    category_lay = QGridLayout(category_box)
    category_lay.setContentsMargins(0, 0, 0, 0)
    category_lay.setHorizontalSpacing(5)
    category_lay.setVerticalSpacing(5)
    title = QLabel("Kategori")
    title.setObjectName("sectionHeading")
    category_lay.addWidget(title, 0, 0, 1, 2)
    self.ui06_category_buttons: dict[str, QPushButton] = {}
    for index, value in enumerate(CATEGORIES):
        button = QPushButton(value)
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setObjectName("tabButton")
        button.setChecked(value == self.category_key)
        button.clicked.connect(lambda _checked=False, category=value: _sync_category(self, category))
        category_lay.addWidget(button, 1 + index // 2, index % 2)
        self.ui06_category_buttons[value] = button

    # Insert after search. Hidden legacy labels/widgets remain the behavior owners.
    root.insertWidget(4, category_box)
    self.ui06_category_box = category_box


def _sync_origin(context: TemplateFilterContext, key: str) -> None:
    button = context.origin._buttons.get(key)
    if button is not None:
        button.setChecked(True)
    context.filters_changed.emit()


def _sync_category(context: TemplateFilterContext, value: str) -> None:
    index = context.category.findText(value)
    if index >= 0:
        context.category.setCurrentIndex(index)
    context.filters_changed.emit()


def _context_counts(self, count: int, *, custom_errors=()) -> None:
    _originals["context_counts"](self, count, custom_errors=custom_errors)
    origin = self.origin_key
    category = self.category_key
    for key, button in getattr(self, "ui06_origin_buttons", {}).items():
        button.setChecked(key == origin)
    for key, button in getattr(self, "ui06_category_buttons", {}).items():
        button.setChecked(key == category)


def _gallery_init(self, *args, **kwargs) -> None:
    _originals["gallery_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(10, 8, 10, 7)
    root.setSpacing(6)
    header = root.itemAt(0).layout()
    if header is not None:
        box = header.itemAt(0).layout()
        if box is not None:
            heading = box.itemAt(0).widget()
            subtitle = box.itemAt(1).widget()
            if isinstance(heading, QLabel):
                heading.setText("Template Video")
            if isinstance(subtitle, QLabel):
                subtitle.setText("Pilih template untuk video album Anda. Sesuaikan dengan mudah dan gunakan langsung.")
        self.preview_state.hide()
        self.ui06_sort = QComboBox()
        self.ui06_sort.addItems(["Terbaru", "Nama A-Z"])
        self.ui06_sort.setMinimumWidth(160)
        header.addWidget(QLabel("⇅"))
        header.addWidget(self.ui06_sort)

    self.grid.setHorizontalSpacing(7)
    self.grid.setVerticalSpacing(7)


def _inspector_init(self, *args, **kwargs) -> None:
    _originals["inspector_init"](self, *args, **kwargs)
    root = self.layout()
    root.setContentsMargins(10, 8, 10, 8)
    root.setSpacing(5)

    self.ui06_preview = TemplateSelectionPreview(self)
    root.insertWidget(0, self.ui06_preview)
    self.heading.setText("Pengaturan Template")
    self.identity.hide()

    # Renderer behavior remains Noto-safe. The display text mirrors the approved
    # visual reference while the tooltip is explicit about the deterministic fallback.
    if self.typography.count():
        self.typography.setItemText(0, "Playfair Display")
    self.typography.setToolTip("Tampilan referensi: Playfair Display. Renderer memakai fallback deterministic Noto Sans bila font exact tidak tersedia.")

    self.scope.hide()
    scope_host = QWidget(self)
    scope_row = QHBoxLayout(scope_host)
    scope_row.setContentsMargins(0, 0, 0, 0)
    scope_row.setSpacing(7)
    self.ui06_scope_buttons: dict[str, QRadioButton] = {}
    for key, label in (("current", "Lagu Ini"), ("selected", "Pilihan"), ("all", "Semua Lagu")):
        radio = QRadioButton(label)
        radio.setChecked(key == self.scope_key)
        radio.toggled.connect(lambda checked, value=key: _sync_scope(self, value) if checked else None)
        scope_row.addWidget(radio)
        self.ui06_scope_buttons[key] = radio
    root.insertWidget(max(0, root.count() - 4), scope_host)

    self.preview.hide()
    self.use.setText("▷  Gunakan Template")
    self.use.setMinimumHeight(34)


def _sync_scope(inspector: TemplateInspector, key: str) -> None:
    index = inspector.scope.findData(key)
    if index >= 0:
        inspector.scope.setCurrentIndex(index)


def _inspector_set_template(self, descriptor, draft) -> None:
    _originals["inspector_set_template"](self, descriptor, draft)
    self.heading.setText("Pengaturan Template")
    self.ui06_preview.set_template(descriptor.name, descriptor.template_id)
    for key, radio in getattr(self, "ui06_scope_buttons", {}).items():
        radio.setChecked(key == self.scope_key)


def _ensure_timeline_panel(window) -> None:
    if hasattr(window, "_ui06_timeline_panel"):
        return
    shell = window.foundation_shell
    host = shell.timeline

    panel = QFrame()
    panel.setObjectName("ui06TemplateTimelinePanel")
    root = QVBoxLayout(panel)
    root.setContentsMargins(0, 0, 0, 0)
    root.setSpacing(0)

    toolbar_widget = QWidget()
    toolbar = QHBoxLayout(toolbar_widget)
    toolbar.setContentsMargins(8, 3, 8, 3)
    toolbar.setSpacing(8)
    title = QLabel("☷  Timeline")
    title.setObjectName("sectionHeading")
    toolbar.addWidget(title)
    split = FAMButton("⌁  Split", kind="ghost")
    split.setEnabled(False)
    split.setToolTip("Split tidak dimiliki Template Studio; timing tetap mengikuti Timeline Editor.")
    delete = FAMButton("♲  Hapus", kind="ghost")
    delete.setEnabled(False)
    delete.setToolTip("Template tidak menghapus clip source dari Timeline.")
    toolbar.addWidget(split)
    toolbar.addWidget(delete)
    toolbar.addStretch(1)
    toolbar.addWidget(QLabel("−"))
    toolbar.addWidget(QLabel("100%"))
    toolbar.addWidget(QLabel("+"))
    root.addWidget(toolbar_widget)

    canvas = window.template_timeline_s07
    old_parent = canvas.parentWidget()
    if old_parent is not None and old_parent.layout() is not None:
        old_parent.layout().removeWidget(canvas)
    root.addWidget(canvas, 1)
    host.layout().addWidget(panel, 1)
    panel.hide()
    window._ui06_timeline_panel = panel

    header = host.layout().itemAt(0).layout()
    window._ui06_timeline_header_widgets = []
    if header is not None:
        for index in range(header.count()):
            widget = header.itemAt(index).widget()
            if widget is not None:
                window._ui06_timeline_header_widgets.append(widget)


def _connect_ui06_once(window) -> None:
    if getattr(window, "_ui06_connected", False):
        return
    gallery = window.template_workspace_s07
    context = window.template_context_s07
    if hasattr(gallery, "ui06_sort"):
        gallery.ui06_sort.setCurrentText(context.sort_key)
        gallery.ui06_sort.currentTextChanged.connect(
            lambda value: _set_sort(context, value)
        )
    window._ui06_connected = True


def _set_sort(context: TemplateFilterContext, value: str) -> None:
    index = context.sort.findText(value)
    if index >= 0 and index != context.sort.currentIndex():
        context.sort.setCurrentIndex(index)


def _apply_template_geometry(window) -> None:
    shell = window.foundation_shell
    compact = bool(getattr(shell, "_responsive_compact", False))
    total = max(1, shell.width())
    nav = TOKENS.nav_compact_width if compact else TOKENS.nav_width
    context = 198 if compact else 208
    right = 38 if shell.inspector.collapsed else (300 if compact else 320)
    center = max(520 if compact else 690, total - nav - context - right - TOKENS.splitter_handle * 3)

    shell.navigation.setMinimumWidth(nav)
    shell.navigation.setMaximumWidth(nav)
    shell.context.setMinimumWidth(context)
    shell.context.setMaximumWidth(context)
    if not shell.inspector.collapsed:
        shell.inspector._expanded_width = right
        shell.inspector.setMinimumWidth(right)
        shell.inspector.setMaximumWidth(420)
    shell.horizontal_splitter.setSizes([nav, context, center, right])

    host = shell.timeline
    host.body.hide()
    inherited_header = host.layout().itemAt(0).layout() if host.layout().count() else None
    if inherited_header is not None:
        for index in range(inherited_header.count()):
            widget = inherited_header.itemAt(index).widget()
            if widget is not None:
                widget.hide()
    panel = getattr(window, "_ui06_timeline_panel", None)
    if panel is not None:
        panel.show()

    timeline_h = 180 if not compact else 170
    host._preferred_height = timeline_h
    host.setMinimumHeight(timeline_h)
    host.setMaximumHeight(timeline_h)
    top_h = max(330 if compact else 420, shell.height() - timeline_h - TOKENS.status_height - TOKENS.command_height)
    shell.vertical_splitter.setSizes([top_h, timeline_h])


def _window_route(self, route: str) -> None:
    _originals["window_route"](self, route)
    _ensure_timeline_panel(self)
    _connect_ui06_once(self)
    active = route == "template"

    self._ui06_timeline_panel.setVisible(active)
    for widget in getattr(self, "_ui06_timeline_header_widgets", ()):
        widget.setVisible(not active)

    if active:
        self.foundation_shell.timeline.body.hide()
        self.template_timeline_s07.show()
        self.foundation_shell._apply_shell_sizes("template")
        _apply_template_geometry(self)
        QTimer.singleShot(
            0,
            lambda: _apply_template_geometry(self)
            if getattr(self, "foundation_state", None) is not None and self.foundation_state.workspace == "template"
            else None,
        )
    else:
        self._ui06_timeline_panel.hide()
        self.foundation_shell._apply_shell_sizes(route)


def _shell_workspace(self, route: str) -> None:
    _originals["shell_workspace"](self, route)
    if route == "template":
        _apply_template_geometry(self.window())


def _shell_resize(self, event) -> None:
    _originals["shell_resize"](self, event)
    if getattr(getattr(self, "state", None), "workspace", "") == "template":
        _apply_template_geometry(self.window())


def _shell_sizes(self, route: str) -> None:
    _originals["shell_sizes"](self, route)
    if route == "template":
        _apply_template_geometry(self.window())


def install_ui06_template_remediation() -> None:
    """UI-06 presentation remediation; STEP07 semantic/template contracts remain authoritative."""
    global _installed
    if _installed:
        return

    from .foundation_shell import FoundationShellWidget
    from .foundation_window import FoundationMainWindow
    from . import template_feature_step07 as feature

    _originals.update(
        thumbnail_paint=TemplateThumbnailPlaceholder.paintEvent,
        card_init=TemplateCard.__init__,
        context_init=TemplateFilterContext.__init__,
        context_counts=TemplateFilterContext.set_counts,
        gallery_init=TemplateGalleryWorkspace.__init__,
        inspector_init=TemplateInspector.__init__,
        inspector_set_template=TemplateInspector.set_template,
        window_route=FoundationMainWindow._s07_route,
        shell_workspace=FoundationShellWidget._apply_workspace,
        shell_resize=FoundationShellWidget.resizeEvent,
        shell_sizes=FoundationShellWidget._apply_shell_sizes,
    )

    # The STEP07 feature resolves this factory at window construction time.
    feature.VisualAlignmentCanvas = TemplateRemediationTimelineCanvas

    TemplateThumbnailPlaceholder.paintEvent = _thumbnail_paint
    TemplateCard.__init__ = _card_init
    TemplateFilterContext.__init__ = _context_init
    TemplateFilterContext.set_counts = _context_counts
    TemplateGalleryWorkspace.__init__ = _gallery_init
    TemplateInspector.__init__ = _inspector_init
    TemplateInspector.set_template = _inspector_set_template
    FoundationMainWindow._s07_route = _window_route
    FoundationShellWidget._apply_workspace = _shell_workspace
    FoundationShellWidget.resizeEvent = _shell_resize
    FoundationShellWidget._apply_shell_sizes = _shell_sizes
    _installed = True
