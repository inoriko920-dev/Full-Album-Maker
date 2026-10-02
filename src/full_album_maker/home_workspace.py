from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMenu, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .home_state import HomeMode, HomeViewState, RecentAvailability, RecentProject


class HomeHeroIllustration(QWidget):
    """Small decorative music/media motif; never a screenshot/background substitute."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAccessibleName("Ilustrasi dekoratif media musik")
        self.setMinimumWidth(220)
        self.setMaximumWidth(330)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = float(self.width()), float(self.height())
        painter.setPen(QPen(QColor(TOKENS.accent_500 + "55"), 2))
        base_y = h * 0.60
        step = max(8.0, w / 26.0)
        x = max(4.0, w * 0.02)
        for value in (10, 22, 36, 19, 45, 28, 52, 24, 38, 17, 31, 13):
            amp = min(h * 0.34, float(value))
            painter.drawLine(int(x), int(base_y - amp / 2), int(x), int(base_y + amp / 2))
            x += step

        tile_w = min(112.0, w * 0.40)
        tile_h = min(88.0, h * 0.62)
        tile_x = w * 0.47
        tile_y = max(8.0, (h - tile_h) * 0.42)
        painter.setPen(QPen(QColor(TOKENS.primary_600 + "55"), 2))
        painter.setBrush(QColor(TOKENS.selection_soft))
        painter.drawRoundedRect(QRectF(tile_x, tile_y, tile_w, tile_h), 14, 14)
        painter.setPen(QPen(QColor(TOKENS.primary_600 + "99"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        stem_x = tile_x + tile_w * 0.62
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(stem_x), int(tile_y + tile_h * 0.68))
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(tile_x + tile_w * 0.79), int(tile_y + tile_h * 0.18))
        painter.setBrush(QColor(TOKENS.primary_600 + "99"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(tile_x + tile_w * 0.46, tile_y + tile_h * 0.60, 25, 18))

        small_w = min(68.0, w * 0.24)
        small_h = min(58.0, h * 0.42)
        sx = min(w - small_w - 8, tile_x + tile_w * 0.72)
        sy = min(h - small_h - 8, tile_y + tile_h * 0.55)
        painter.setPen(QPen(QColor(TOKENS.border), 1))
        painter.setBrush(QColor(TOKENS.surface))
        painter.drawRoundedRect(QRectF(sx, sy, small_w, small_h), 10, 10)
        painter.setBrush(QColor(TOKENS.accent_500 + "33"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(sx + 11, sy + 10, 12, 12))
        mountain = [
            (sx + 8, sy + small_h - 10),
            (sx + small_w * 0.45, sy + small_h * 0.46),
            (sx + small_w * 0.62, sy + small_h * 0.67),
            (sx + small_w - 8, sy + small_h * 0.36),
        ]
        painter.setPen(QPen(QColor(TOKENS.accent_500 + "66"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for left, right in zip(mountain, mountain[1:]):
            painter.drawLine(int(left[0]), int(left[1]), int(right[0]), int(right[1]))
        painter.end()


class RecoveryBanner(QFrame):
    restore_requested = Signal()
    dismiss_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("homeRecoveryBanner")
        self.setStyleSheet(
            "QFrame#homeRecoveryBanner { background: #FFF8E4; border: 1px solid #F0D48A; border-radius: 8px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, 6, TOKENS.space_2, 6)
        row.setSpacing(TOKENS.space_2)
        icon = QLabel("●")
        icon.setStyleSheet("color: #D69A00;")
        row.addWidget(icon)
        self.text = QLabel("Autosave tersedia")
        self.text.setObjectName("metadata")
        row.addWidget(self.text, 1)
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
        self.text.setText(f"Autosave tersedia — terakhir disimpan {stamp}")


class RecentProjectCard(QFrame):
    open_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, item: RecentProject, parent=None) -> None:
        super().__init__(parent)
        self.item = item
        self.setObjectName("famCard")
        self.setMinimumWidth(150)
        self.setMaximumWidth(260)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(TOKENS.space_2, TOKENS.space_2, TOKENS.space_2, TOKENS.space_2)
        lay.setSpacing(5)

        cover = QFrame()
        cover.setMinimumHeight(66)
        cover.setMaximumHeight(78)
        cover.setStyleSheet(
            f"background: {TOKENS.selection_soft}; border: 1px solid {TOKENS.border}; border-radius: 6px;"
        )
        cover_lay = QVBoxLayout(cover)
        cover_lay.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel("♪")
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        glyph.setStyleSheet(f"font-size: 28px; color: {TOKENS.primary_600};")
        cover_lay.addWidget(glyph)
        lay.addWidget(cover)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(item.display_name)
        self.title.setObjectName("sectionHeading")
        self.title.setStyleSheet("font-size: 13px;")
        self.title.setToolTip(item.display_name)
        head.addWidget(self.title, 1)
        menu_btn = FAMButton("…", kind="ghost")
        menu_btn.setFixedWidth(32)
        menu_btn.setAccessibleName(f"Menu proyek {item.display_name}")
        menu = QMenu(menu_btn)
        menu.addAction("Buka", lambda: self.open_requested.emit(item.path))
        menu.addAction("Hapus dari daftar", lambda: self.remove_requested.emit(item.project_id))
        menu_btn.setMenu(menu)
        head.addWidget(menu_btn)
        lay.addLayout(head)

        song_text = "— lagu" if item.song_count is None else f"{item.song_count} lagu"
        duration = "—" if item.duration_seconds is None else self._format_duration(item.duration_seconds)
        meta = QLabel(f"{song_text}  •  {duration}")
        meta.setObjectName("metadata")
        lay.addWidget(meta)

        if item.availability == RecentAvailability.MISSING:
            availability = QLabel("Tidak ditemukan")
            availability.setObjectName("metadata")
            availability.setStyleSheet("color: #A56D00;")
            lay.addWidget(availability)
        elif item.availability == RecentAvailability.CORRUPT:
            availability = QLabel("Proyek bermasalah")
            availability.setObjectName("metadata")
            availability.setStyleSheet("color: #B43A3A;")
            lay.addWidget(availability)

        open_btn = FAMButton("Cari" if item.availability == RecentAvailability.MISSING else "Buka", kind="ghost")
        open_btn.setAccessibleName(f"Buka proyek {item.display_name}")
        open_btn.clicked.connect(lambda: self.open_requested.emit(item.path))
        lay.addWidget(open_btn)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        value = max(0, int(round(seconds)))
        hours, rem = divmod(value, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours}:{minutes:02d}:{sec:02d}" if hours else f"{minutes}:{sec:02d}"


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
        # The STEP 01 stack initially has Home selected. Replacing its current
        # placeholder makes Qt temporarily select the next page (Media). During
        # startup Beranda must reclaim that same selected route before saved
        # preferences are applied. This one-shot parent-change guard does that
        # without changing shared shell geometry or later navigation behavior.
        self._activate_after_stack_insert = True
        self.setObjectName("workspaceHost")
        self.state = state or HomeViewState()
        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_4, TOKENS.space_4, TOKENS.space_4, TOKENS.space_3)
        root.setSpacing(TOKENS.space_2)

        self.hero = QFrame()
        self.hero.setObjectName("homeHero")
        self.hero.setMinimumHeight(154)
        self.hero.setMaximumHeight(172)
        self.hero.setStyleSheet(
            f"QFrame#homeHero {{ background: {TOKENS.selection_soft}; border: {TOKENS.border_width}px solid {TOKENS.border}; border-radius: {TOKENS.radius_card}px; }}"
        )
        hero_row = QHBoxLayout(self.hero)
        hero_row.setContentsMargins(TOKENS.space_5, TOKENS.space_4, TOKENS.space_4, TOKENS.space_4)
        hero_row.setSpacing(TOKENS.space_4)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(TOKENS.space_2)
        copy.addStretch(1)
        self.hero_title = QLabel("Mulai Full Album")
        self.hero_title.setObjectName("workspaceHeading")
        copy.addWidget(self.hero_title)
        self.hero_subtitle = QLabel(
            "Buat video album musik dengan mudah dan profesional\n"
            "secara offline, cepat, dan fleksibel."
        )
        self.hero_subtitle.setObjectName("muted")
        self.hero_subtitle.setWordWrap(True)
        self.hero_subtitle.setMaximumWidth(520)
        copy.addWidget(self.hero_subtitle)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(TOKENS.space_2)
        self.new_project_button = FAMButton("Proyek Baru", icon_name="new", kind="primary")
        self.new_project_button.setMinimumWidth(142)
        self.open_project_button = FAMButton("Buka Proyek", icon_name="open")
        self.open_project_button.setMinimumWidth(142)
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
        recent_header.addWidget(title)
        recent_header.addStretch(1)
        self.see_all = FAMButton("Lihat Semua", kind="ghost")
        self.see_all.clicked.connect(self.show_all_recent_requested.emit)
        recent_header.addWidget(self.see_all)
        root.addLayout(recent_header)

        self.recent_host = QWidget()
        self.recent_row = QHBoxLayout(self.recent_host)
        self.recent_row.setContentsMargins(0, 0, 0, 0)
        self.recent_row.setSpacing(TOKENS.space_2)
        root.addWidget(self.recent_host, 1)

        quick_title = QLabel("Mulai Cepat")
        quick_title.setObjectName("sectionHeading")
        root.addWidget(quick_title)
        self.quick = QFrame()
        self.quick.setObjectName("famCard")
        quick_row = QHBoxLayout(self.quick)
        quick_row.setContentsMargins(TOKENS.space_2, TOKENS.space_1, TOKENS.space_2, TOKENS.space_1)
        quick_row.setSpacing(TOKENS.space_1)
        for number, title_text, subtitle, route in (
            ("1", "Impor Lagu", "Masukkan file musik", "media"),
            ("2", "Susun Timeline", "Atur urutan lagu", "album"),
            ("3", "Render", "Hasilkan video album", "render"),
        ):
            button = FAMButton(f"{number}   {title_text}\n    {subtitle}", kind="ghost")
            button.setMinimumHeight(50)
            button.setAccessibleName(f"Langkah {number}: {title_text}")
            button.clicked.connect(lambda _checked=False, r=route: self.quick_route_requested.emit(r))
            quick_row.addWidget(button, 1)
        root.addWidget(self.quick)

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

    def _clear_recent(self) -> None:
        while self.recent_row.count():
            item = self.recent_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
            self.recent_row.addWidget(card, 1)
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
