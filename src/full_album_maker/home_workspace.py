from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .foundation_components import FAMButton
from .foundation_tokens import TOKENS
from .home_state import HomeViewState


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

        # Quiet waveform behind the cards.
        wave_pen = QPen(QColor(TOKENS.accent_500 + "55"), 2)
        painter.setPen(wave_pen)
        base_y = h * 0.60
        step = max(8.0, w / 26.0)
        x = max(4.0, w * 0.02)
        heights = (10, 22, 36, 19, 45, 28, 52, 24, 38, 17, 31, 13)
        for value in heights:
            amp = min(h * 0.34, float(value))
            painter.drawLine(int(x), int(base_y - amp / 2), int(x), int(base_y + amp / 2))
            x += step

        # Main music tile.
        tile_w = min(112.0, w * 0.40)
        tile_h = min(88.0, h * 0.62)
        tile_x = w * 0.47
        tile_y = max(8.0, (h - tile_h) * 0.42)
        painter.setPen(QPen(QColor(TOKENS.primary_600 + "55"), 2))
        painter.setBrush(QColor(TOKENS.selection_soft))
        painter.drawRoundedRect(QRectF(tile_x, tile_y, tile_w, tile_h), 14, 14)

        # Music note.
        painter.setPen(QPen(QColor(TOKENS.primary_600 + "99"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        stem_x = tile_x + tile_w * 0.62
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(stem_x), int(tile_y + tile_h * 0.68))
        painter.drawLine(int(stem_x), int(tile_y + tile_h * 0.24), int(tile_x + tile_w * 0.79), int(tile_y + tile_h * 0.18))
        painter.setBrush(QColor(TOKENS.primary_600 + "99"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRectF(tile_x + tile_w * 0.46, tile_y + tile_h * 0.60, 25, 18))

        # Secondary image tile.
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


class HomeWorkspace(QWidget):
    """STEP 02 Beranda composition root.

    Only Beranda-specific UI is owned here. Shared command/navigation/dock/timeline/status
    chrome stays owned by the STEP 01 foundation shell.
    """

    create_project_requested = Signal()
    open_project_requested = Signal()

    def __init__(
        self,
        *,
        state: HomeViewState | None = None,
        on_create_project: Callable[[], None] | None = None,
        on_open_project: Callable[[], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceHost")
        self.state = state or HomeViewState()

        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_4, TOKENS.space_4, TOKENS.space_4, TOKENS.space_3)
        root.setSpacing(TOKENS.space_3)

        self.hero = QFrame()
        self.hero.setObjectName("homeHero")
        self.hero.setMinimumHeight(154)
        self.hero.setMaximumHeight(172)
        self.hero.setStyleSheet(
            f"QFrame#homeHero {{"
            f"background: {TOKENS.selection_soft};"
            f"border: {TOKENS.border_width}px solid {TOKENS.border};"
            f"border-radius: {TOKENS.radius_card}px;"
            "}"
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
        self.hero_title.setAccessibleName("Mulai Full Album")
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
        self.new_project_button.setAccessibleName("Proyek Baru")
        self.open_project_button = FAMButton("Buka Proyek", icon_name="open")
        self.open_project_button.setMinimumWidth(142)
        self.open_project_button.setAccessibleName("Buka Proyek")
        buttons.addWidget(self.new_project_button)
        buttons.addWidget(self.open_project_button)
        buttons.addStretch(1)
        copy.addLayout(buttons)
        copy.addStretch(1)

        hero_row.addLayout(copy, 1)
        self.hero_illustration = HomeHeroIllustration()
        hero_row.addWidget(self.hero_illustration, 0)
        root.addWidget(self.hero)

        # S02-03 intentionally stops after the real Hero. Later serial tasks insert
        # recovery, recent-project, and Quick Start regions here without rebuilding
        # the shell or changing this ordering contract.
        self.body_slot = QWidget()
        self.body_slot.setObjectName("homeBodySlot")
        body_layout = QVBoxLayout(self.body_slot)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(TOKENS.space_3)
        body_layout.addStretch(1)
        root.addWidget(self.body_slot, 1)

        self.new_project_button.clicked.connect(self.create_project_requested.emit)
        self.open_project_button.clicked.connect(self.open_project_requested.emit)
        if on_create_project is not None:
            self.create_project_requested.connect(on_create_project)
        if on_open_project is not None:
            self.open_project_requested.connect(on_open_project)

        self.apply_state(self.state)

    def apply_state(self, state: HomeViewState) -> None:
        state.validate()
        self.state = state
        busy = bool(state.loading_action)
        self.new_project_button.setEnabled(not busy)
        self.open_project_button.setEnabled(not busy)
        if busy:
            self.new_project_button.setToolTip("Tunggu sampai operasi proyek selesai.")
            self.open_project_button.setToolTip("Tunggu sampai operasi proyek selesai.")
        else:
            self.new_project_button.setToolTip("Buat proyek Full Album baru")
            self.open_project_button.setToolTip("Buka file proyek Full Album yang sudah ada")
