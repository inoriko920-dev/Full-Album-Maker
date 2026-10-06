from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .home_state import HomeMode, HomeViewState, RecentAvailability, RecentProject


def _alpha_color(hex_color: str, alpha: int) -> QColor:
    color = QColor(hex_color)
    color.setAlpha(max(0, min(255, int(alpha))))
    return color


class HomeHeroIllustration(QWidget):
    """Decorative media motif drawn from primitives, never from a golden screenshot."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName("Ilustrasi dekoratif media musik")
        self.setMinimumWidth(455)
        self.setMaximumWidth(520)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        painter.setPen(QPen(_alpha_color(TOKENS.accent_500, 78), 3))
        base_y = h * 0.58
        step = max(10.0, w / 32.0)
        x = max(4.0, w * 0.02)
        for value in (12, 28, 48, 24, 64, 36, 78, 42, 62, 31, 50, 20):
            amp = min(h * 0.46, float(value))
            painter.drawLine(int(x), int(base_y - amp / 2), int(x), int(base_y + amp / 2))
            x += step

        tile_w = min(188.0, w * 0.43)
        tile_h = min(142.0, h * 0.72)
        tile_x = w * 0.28
        tile_y = max(8.0, (h - tile_h) * 0.42)
        painter.setPen(QPen(_alpha_color(TOKENS.primary_600, 92), 2))
        painter.setBrush(_alpha_color(TOKENS.selection_soft, 236))
        painter.drawRoundedRect(QRectF(tile_x, tile_y, tile_w, tile_h), 16, 16)
        painter.setPen(QPen(_alpha_color(TOKENS.primary_600, 150), 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        stem_x = tile_x + tile_w * 0.62
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(stem_x), int(tile_y + tile_h * 0.69))
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(tile_x + tile_w * 0.80), int(tile_y + tile_h * 0.18))
        painter.setBrush(_alpha_color(TOKENS.primary_600, 150))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(tile_x + tile_w * 0.44, tile_y + tile_h * 0.61, 35, 25))

        small_w = min(94.0, w * 0.25)
        small_h = min(78.0, h * 0.46)
        sx = min(w - small_w - 8, tile_x + tile_w * 0.76)
        sy = min(h - small_h - 8, tile_y + tile_h * 0.55)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.setBrush(_alpha_color("#FFFFFF", 220))
        painter.drawRoundedRect(QRectF(sx, sy, small_w, small_h), 11, 11)
        painter.setBrush(_alpha_color(TOKENS.accent_500, 58))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(sx + 13, sy + 11, 15, 15))
        mountain = [
            (sx + 10, sy + small_h - 12),
            (sx + small_w * 0.46, sy + small_h * 0.47),
            (sx + small_w * 0.63, sy + small_h * 0.68),
            (sx + small_w - 10, sy + small_h * 0.35),
        ]
        painter.setPen(QPen(_alpha_color(TOKENS.accent_500, 110), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for left, right in zip(mountain, mountain[1:]):
            painter.drawLine(int(left[0]), int(left[1]), int(right[0]), int(right[1]))
        painter.end()


class RecoveryBanner(QFrame):
    restore_requested = Signal()
    dismiss_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homeRecoveryBanner")
        self.setFixedHeight(60)
        self.setStyleSheet(
            "QFrame#homeRecoveryBanner { background: #FFF8E4; border: 1px solid #F0D48A; border-radius: 8px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, 6, TOKENS.space_2, 6)
        row.setSpacing(TOKENS.space_4)
        icon = QLabel("!")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(34, 34)
        icon.setStyleSheet(
            "background:#F2A900;color:white;border-radius:17px;font-weight:800;font-size:17px;"
        )
        row.addWidget(icon)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(0)
        self.title = QLabel("Autosave tersedia")
        self.title.setStyleSheet("font-weight:650;")
        self.text = QLabel("")
        self.text.setObjectName("metadata")
        copy.addWidget(self.title)
        copy.addWidget(self.text)
        row.addLayout(copy, 1)
        self.restore = FAMButton("Pulihkan", kind="secondary")
        self.restore.setAccessibleName("Pulihkan autosave")
        self.dismiss = FAMButton("×", kind="ghost")
        self.dismiss.setFixedWidth(34)
        self.dismiss.setAccessibleName("Tutup pemberitahuan autosave")
        row.addWidget(self.restore)
        row.addWidget(self.dismiss)
        self.restore.clicked.connect(self.restore_requested.emit)
        self.dismiss.clicked.connect(self.dismiss_requested.emit)

    def set_timestamp(self, timestamp: float) -> None:
        stamp = datetime.fromtimestamp(timestamp).strftime("%d %b %Y %H:%M")
        self.text.setText(f"Ditemukan data autosave dari sesi sebelumnya ({stamp}).")


class RecentThumbnail(QFrame):
    """Lightweight deterministic artwork fallback; real thumbnail_ref wins when available."""

    _PALETTE = (
        ("#755C61", "#B8755B"),
        ("#5E829E", "#314E68"),
        ("#617460", "#314B3A"),
        ("#C5A786", "#E0C6A7"),
    )

    def __init__(self, item: RecentProject, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def _palette_index(self) -> int:
        tail = self.item.project_id.rsplit("-", 1)[-1]
        if tail.isdigit():
            return (int(tail) - 1) % len(self._PALETTE)
        return sum(ord(ch) for ch in self.item.display_name) % len(self._PALETTE)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        top, bottom = self._PALETTE[self._palette_index()]
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(top))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setClipRect(self.rect().adjusted(1, 1, -1, -1))

        thumbnail = str(self.item.thumbnail_ref or "").strip()
        source = Path(thumbnail) if thumbnail else None
        if source is not None and source.is_file():
            pixmap = QPixmap(str(source))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = max(0, (scaled.width() - self.width()) // 2)
                y = max(0, (scaled.height() - self.height()) // 2)
                painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
                painter.setClipping(False)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(TOKENS.border), 1))
                painter.drawRoundedRect(rect, 6, 6)
                painter.end()
                return

        painter.setBrush(QColor(bottom))
        painter.drawEllipse(int(rect.width() * 0.60), int(rect.height() * 0.12), int(rect.width() * 0.48), int(rect.height() * 0.95))
        painter.setBrush(_alpha_color("#10234A", 72))
        painter.drawEllipse(int(rect.width() * -0.12), int(rect.height() * 0.55), int(rect.width() * 0.72), int(rect.height() * 0.72))

        painter.setPen(QColor("#FFFFFF"))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        text_rect = self.rect().adjusted(18, 12, -18, -14)
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.item.display_name,
        )

        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.drawRoundedRect(rect, 6, 6)
        painter.end()


class RecentProjectCard(QFrame):
    open_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, item: RecentProject, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.setObjectName("famCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Proyek {item.display_name}")
        self.setMinimumWidth(150)
        self.setMaximumWidth(270)
        self.setFixedHeight(244)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(9, 9, 9, 9)
        lay.setSpacing(5)

        self.cover = RecentThumbnail(item)
        self.cover.setObjectName("recentProjectCover")
        self.cover.setFixedHeight(128)
        cover_lay = QVBoxLayout(self.cover)
        cover_lay.setContentsMargins(7, 7, 7, 7)
        cover_lay.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        menu_btn = FAMButton("…", kind="secondary")
        menu_btn.setFixedSize(30, 28)
        menu_btn.setAccessibleName(f"Menu proyek {item.display_name}")
        menu = QMenu(menu_btn)
        menu.addAction("Buka", lambda: self.open_requested.emit(item.path))
        menu.addAction("Hapus dari daftar", lambda: self.remove_requested.emit(item.project_id))
        menu_btn.setMenu(menu)
        top.addWidget(menu_btn)
        cover_lay.addLayout(top)

        cover_lay.addStretch(1)

        duration = "—" if item.duration_seconds is None else self._format_duration(item.duration_seconds)
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.addStretch(1)
        self.duration_badge = QLabel(duration)
        self.duration_badge.setStyleSheet(
            "background:rgba(16,35,74,210);color:white;border-radius:4px;padding:2px 5px;font-size:11px;font-weight:650;"
        )
        bottom.addWidget(self.duration_badge)
        cover_lay.addLayout(bottom)
        lay.addWidget(self.cover)

        self.title = QLabel(item.display_name)
        self.title.setObjectName("sectionHeading")
        self.title.setStyleSheet("font-size: 13px;")
        self.title.setToolTip(item.display_name)
        lay.addWidget(self.title)

        song_text = "— lagu" if item.song_count is None else f"{item.song_count} lagu"
        self.meta = QLabel(f"♪  {song_text}      ◷  {duration}")
        self.meta.setObjectName("metadata")
        lay.addWidget(self.meta)

        opened = datetime.fromtimestamp(item.last_opened).strftime("%d %b %Y")
        availability = ""
        if item.availability == RecentAvailability.MISSING:
            availability = "  • Tidak ditemukan"
        elif item.availability == RecentAvailability.CORRUPT:
            availability = "  • Bermasalah"
        self.last_opened = QLabel(f"▣  Dibuka {opened}{availability}")
        self.last_opened.setObjectName("metadata")
        if availability:
            self.last_opened.setStyleSheet("color: #A56D00;")
        lay.addWidget(self.last_opened)

    def set_compact(self, compact: bool) -> None:
        self.setFixedHeight(174 if compact else 244)
        self.cover.setFixedHeight(76 if compact else 128)
        self.last_opened.setVisible(not compact)
        self.layout().setContentsMargins(7 if compact else 9, 7 if compact else 9, 7 if compact else 9, 7 if compact else 9)
        self.layout().setSpacing(3 if compact else 5)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        value = max(0, int(round(seconds)))
        hours, rem = divmod(value, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours}:{minutes:02d}:{sec:02d}" if hours else f"{minutes}:{sec:02d}"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit(self.item.path)
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_requested.emit(self.item.path)
            event.accept()
            return
        super().keyPressEvent(event)


class QuickStepCard(QFrame):
    clicked = Signal()

    def __init__(self, number: str, title: str, subtitle: str, glyph: str, *, show_arrow: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Langkah {number}: {title}")
        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(10, 4, 10, 4)
        self._row.setSpacing(10)
        self.number_label = QLabel(number)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFixedSize(36, 36)
        self.number_label.setStyleSheet(
            f"background:{TOKENS.primary_600};color:white;border-radius:18px;font-weight:750;font-size:15px;"
        )
        self._row.addWidget(self.number_label)
        self.icon = QLabel(glyph)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedWidth(28)
        self.icon.setStyleSheet(f"font-size:22px;color:{TOKENS.primary_600};font-weight:650;")
        self._row.addWidget(self.icon)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight:650;")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("metadata")
        self.subtitle_label.setWordWrap(True)
        copy.addWidget(self.title_label)
        copy.addWidget(self.subtitle_label)
        self._row.addLayout(copy, 1)
        self.arrow = None
        if show_arrow:
            self.arrow = QLabel("›")
            self.arrow.setStyleSheet(f"font-size:32px;color:{TOKENS.text_muted};")
            self._row.addWidget(self.arrow)

    def set_compact(self, compact: bool) -> None:
        self.subtitle_label.setVisible(not compact)
        size = 30 if compact else 36
        self.number_label.setFixedSize(size, size)
        self.number_label.setStyleSheet(
            f"background:{TOKENS.primary_600};color:white;border-radius:{size // 2}px;font-weight:750;font-size:14px;"
        )
        self.icon.setFixedWidth(22 if compact else 28)
        self._row.setContentsMargins(6 if compact else 10, 2 if compact else 4, 6 if compact else 10, 2 if compact else 4)
        self._row.setSpacing(6 if compact else 10)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class HomeWorkspace(QWidget):
    """STEP 02 Beranda composition root inside the immutable STEP 01 shell."""

    create_project_requested = Signal()
    open_project_requested = Signal()
    restore_recovery_requested = Signal()
    dismiss_recovery_requested = Signal()
    recent_open_requested = Signal(str)
    recent_remove_requested = Signal(str)
    show_all_recent_requested = Signal()
    quick_route_requested = Signal(str)

    def __init__(
        self,
        *,
        state: HomeViewState | None = None,
        on_create_project: Callable[[], None] | None = None,
        on_open_project: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._activate_after_stack_insert = True
        self._vertical_compact = False
        self.setObjectName("workspaceHost")
        self.setStyleSheet("QWidget#workspaceHost { background: #FFFFFF; }")
        self.state = state or HomeViewState()
        self._root_layout = QVBoxLayout(self)
        root = self._root_layout
        root.setContentsMargins(10, TOKENS.space_5, 14, TOKENS.space_3)
        root.setSpacing(TOKENS.space_3)

        self.hero = QFrame()
        self.hero.setObjectName("homeHero")
        self.hero.setFixedHeight(218)
        self.hero.setStyleSheet(
            f"QFrame#homeHero {{ background: {TOKENS.selection_soft}; border: {TOKENS.border_width}px solid {TOKENS.border}; border-radius: {TOKENS.radius_card}px; }}"
        )
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(35, TOKENS.space_4, TOKENS.space_4, TOKENS.space_4)
        hero_row.setSpacing(TOKENS.space_4)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(TOKENS.space_2)
        copy.addStretch(1)
        self.hero_title = QLabel("Mulai Full Album")
        self.hero_title.setObjectName("workspaceHeading")
        self.hero_title.setStyleSheet("font-size: 32px;")
        copy.addWidget(self.hero_title)
        self.hero_subtitle = QLabel(
            "Buat video album musik dengan mudah dan profesional\n"
            "secara offline, cepat, dan fleksibel."
        )
        self.hero_subtitle.setObjectName("muted")
        self.hero_subtitle.setWordWrap(True)
        self.hero_subtitle.setMaximumWidth(560)
        copy.addWidget(self.hero_subtitle)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 12, 0, 0)
        buttons.setSpacing(TOKENS.space_4)
        self.new_project_button = FAMButton("Proyek Baru", icon_name="new", kind="primary")
        self.new_project_button.setFixedSize(214, 52)
        self.open_project_button = FAMButton("Buka Proyek", icon_name="open")
        self.open_project_button.setFixedSize(214, 52)
        buttons.addWidget(self.new_project_button)
        buttons.addWidget(self.open_project_button)
        buttons.addStretch(1)
        copy.addLayout(buttons)
        copy.addStretch(1)
        hero_row.addLayout(copy, 1)
        self.hero_illustration = HomeHeroIllustration()
        hero_row.addWidget(self.hero_illustration, 0)
        root.addWidget(self.hero)

        self.error_banner = QFrame()
        self.error_banner.setFixedHeight(60)
        self.error_banner.setStyleSheet("background: #FFF1F1; border: 1px solid #EDB8B8; border-radius: 8px;")
        error_row = QHBoxLayout(self.error_banner)
        error_row.setContentsMargins(TOKENS.space_3, 6, TOKENS.space_3, 6)
        self.error_text = QLabel("")
        self.error_text.setWordWrap(True)
        error_row.addWidget(self.error_text)
        root.addWidget(self.error_banner)

        self.recovery_banner = RecoveryBanner()
        self.recovery_banner.restore_requested.connect(self.restore_recovery_requested.emit)
        self.recovery_banner.dismiss_requested.connect(self.dismiss_recovery_requested.emit)
        root.addWidget(self.recovery_banner)

        recent_header = QHBoxLayout()
        recent_header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Proyek Terakhir")
        title.setObjectName("sectionHeading")
        title.setStyleSheet("font-size: 16px;font-weight:700;")
        recent_header.addWidget(title)
        recent_header.addStretch(1)
        self.see_all = FAMButton("Lihat Semua  →", kind="ghost")
        self.see_all.setFixedHeight(20)
        self.see_all.setStyleSheet(
            "min-height:20px;max-height:20px;padding:0 2px;border:none;background:transparent;"
        )
        self.see_all.clicked.connect(self.show_all_recent_requested.emit)
        recent_header.addWidget(self.see_all)
        root.addLayout(recent_header)

        self.recent_host = QWidget()
        self.recent_host.setFixedHeight(244)
        self.recent_row = QHBoxLayout(self.recent_host)
        self.recent_row.setContentsMargins(0, 0, 0, 0)
        self.recent_row.setSpacing(TOKENS.space_2)
        root.addWidget(self.recent_host)

        quick_section = QVBoxLayout()
        quick_section.setContentsMargins(0, 0, 0, 0)
        quick_section.setSpacing(TOKENS.space_1)
        quick_title = QLabel("Mulai Cepat")
        quick_title.setObjectName("sectionHeading")
        quick_title.setStyleSheet("font-size:16px;font-weight:700;")
        quick_title.setFixedHeight(24)
        quick_section.addWidget(quick_title)
        self.quick = QFrame()
        self.quick.setObjectName("famCard")
        self.quick.setFixedHeight(86)
        quick_row = QHBoxLayout(self.quick)
        quick_row.setContentsMargins(TOKENS.space_2, 4, TOKENS.space_2, 4)
        quick_row.setSpacing(2)
        self._quick_cards: list[QuickStepCard] = []
        quick_specs = (
            ("1", "Impor Lagu", "Tambahkan file musik, gambar, atau video ke proyek.", "▭", "media"),
            ("2", "Susun Timeline", "Atur urutan lagu, tambah visual, transisi, dan teks.", "☷", "album"),
            ("3", "Render", "Pratinjau hasilnya, lalu render video album Anda.", "▶", "render"),
        )
        for idx, (number, title_text, subtitle, glyph, route) in enumerate(quick_specs):
            card = QuickStepCard(number, title_text, subtitle, glyph, show_arrow=idx < 2)
            card.clicked.connect(lambda r=route: self.quick_route_requested.emit(r))
            quick_row.addWidget(card, 1)
            self._quick_cards.append(card)
        quick_section.addWidget(self.quick)
        root.addLayout(quick_section)

        self.new_project_button.clicked.connect(self.create_project_requested.emit)
        self.open_project_button.clicked.connect(self.open_project_requested.emit)
        if on_create_project is not None:
            self.create_project_requested.connect(on_create_project)
        if on_open_project is not None:
            self.open_project_requested.connect(on_open_project)
        self.apply_state(self.state)

    def event(self, event) -> bool:
        result = super().event(event)
        if (
            self._activate_after_stack_insert
            and event.type() == QEvent.Type.ParentChange
            and isinstance(self.parentWidget(), QStackedWidget)
        ):
            stack = self.parentWidget()
            self._activate_after_stack_insert = False

            def activate() -> None:
                if stack.indexOf(self) >= 0:
                    stack.setCurrentWidget(self)

            QTimer.singleShot(0, activate)
        return result

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._set_vertical_compact(event.size().height() < 690)

    def _set_vertical_compact(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._vertical_compact:
            self._apply_recent_density(compact)
            return
        self._vertical_compact = compact
        if compact:
            self._root_layout.setContentsMargins(12, 12, 12, 8)
            self._root_layout.setSpacing(6)
            self.hero.setFixedHeight(150)
            self.error_banner.setFixedHeight(46)
            self.recovery_banner.setFixedHeight(46)
            self.recent_host.setFixedHeight(174)
            self.quick.setFixedHeight(60)
            self.hero_illustration.setMinimumWidth(240)
            self.hero_illustration.setMaximumWidth(330)
            self.new_project_button.setFixedSize(150, 36)
            self.open_project_button.setFixedSize(150, 36)
        else:
            self._root_layout.setContentsMargins(10, TOKENS.space_5, 14, TOKENS.space_3)
            self._root_layout.setSpacing(TOKENS.space_3)
            self.hero.setFixedHeight(218)
            self.error_banner.setFixedHeight(60)
            self.recovery_banner.setFixedHeight(60)
            self.recent_host.setFixedHeight(244)
            self.quick.setFixedHeight(86)
            self.hero_illustration.setMinimumWidth(455)
            self.hero_illustration.setMaximumWidth(520)
            self.new_project_button.setFixedSize(214, 52)
            self.open_project_button.setFixedSize(214, 52)
        self._apply_recent_density(compact)
        for card in self._quick_cards:
            card.set_compact(compact)

    def _apply_recent_density(self, compact: bool) -> None:
        for card in getattr(self, "_recent_cards", []):
            card.set_compact(compact)

    def _clear_recent(self) -> None:
        while self.recent_row.count():
            item = self.recent_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._recent_cards: list[RecentProjectCard] = []

    def _render_recent(self, projects: tuple[RecentProject, ...]) -> None:
        self._clear_recent()
        if not projects:
            empty = QFrame()
            empty.setObjectName("emptyState")
            lay = QVBoxLayout(empty)
            lay.setContentsMargins(TOKENS.space_3, TOKENS.space_3, TOKENS.space_3, TOKENS.space_3)
            label = QLabel("Belum ada proyek terakhir. Buat proyek baru atau buka proyek yang sudah ada.")
            label.setObjectName("muted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            lay.addWidget(label)
            self.recent_row.addWidget(empty, 1)
            return
        for project in projects[:4]:
            card = RecentProjectCard(project)
            card.open_requested.connect(self.recent_open_requested.emit)
            card.remove_requested.connect(self.recent_remove_requested.emit)
            card.set_compact(self._vertical_compact)
            self.recent_row.addWidget(card, 1)
            self._recent_cards.append(card)
        if len(projects) < 4:
            self.recent_row.addStretch(4 - len(projects))

    def apply_state(self, state: HomeViewState) -> None:
        state.validate()
        self.state = state
        busy = bool(state.loading_action)
        self.new_project_button.setEnabled(not busy)
        self.open_project_button.setEnabled(not busy)
        self.new_project_button.setToolTip("Tunggu sampai operasi proyek selesai." if busy else "Buat proyek Full Album baru")
        self.open_project_button.setToolTip("Tunggu sampai operasi proyek selesai." if busy else "Buka file proyek Full Album yang sudah ada")

        self.error_banner.setVisible(state.mode == HomeMode.OPEN_ERROR and bool(state.error_message))
        self.error_text.setText(state.error_message)
        show_recovery = state.mode == HomeMode.RECOVERY_AVAILABLE and state.recovery is not None
        self.recovery_banner.setVisible(show_recovery)
        if state.recovery is not None:
            self.recovery_banner.set_timestamp(state.recovery.timestamp)
        self._render_recent(state.recent_projects)
        self.see_all.setEnabled(bool(state.recent_projects))
