from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMenu, QPushButton,
    QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from .foundation_components import (
    FAMButton, FAMDockHeader, FAMEmptyState, FAMIconButton, FAMSectionHeader,
    FAMSegmented, TabbedEmptyHost,
)
from .foundation_icons import foundation_icon
from .foundation_theme import FOUNDATION_STYLE
from .foundation_tokens import TIMELINE_HEIGHT_BY_WORKSPACE, TOKENS, WORKSPACE_LABELS, WORKSPACE_ORDER


class FoundationUiState(QObject):
    workspace_changed = Signal(str)
    status_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.workspace = "home"
        self.save_text, self.save_state = "Tersimpan", "success"
        self.ffmpeg_text, self.ffmpeg_state = "FFmpeg Siap", "success"
        self.ai_text, self.ai_state = "AI Opsional", "neutral"
        self.jobs_text, self.jobs_state = "Jobs: 0", "neutral"
        self.project_context = "Belum ada proyek yang dibuka"

    def set_workspace(self, route: str) -> None:
        if route not in WORKSPACE_LABELS or route == self.workspace:
            return
        self.workspace = route
        self.workspace_changed.emit(route)

    def set_status(self, *, save=None, ffmpeg=None, ai=None, jobs=None, project_context=None) -> None:
        if save:
            self.save_text, self.save_state = save
        if ffmpeg:
            self.ffmpeg_text, self.ffmpeg_state = ffmpeg
        if ai:
            self.ai_text, self.ai_state = ai
        if jobs:
            self.jobs_text, self.jobs_state = jobs
        if project_context is not None:
            self.project_context = project_context
        self.status_changed.emit()


@dataclass
class FoundationCommandAdapter:
    new_project: Callable[[], None] = lambda: None
    open_project: Callable[[], None] = lambda: None
    save_project: Callable[[], None] = lambda: None
    undo: Callable[[], None] = lambda: None
    redo: Callable[[], None] = lambda: None
    import_audio: Callable[[], None] = lambda: None
    import_video: Callable[[], None] = lambda: None
    auto_arrange: Callable[[], None] = lambda: None
    preview: Callable[[], None] = lambda: None
    render_route: Callable[[], None] = lambda: None
    can_save: Callable[[], bool] = lambda: False
    can_undo: Callable[[], bool] = lambda: False
    can_redo: Callable[[], bool] = lambda: False
    can_project_action: Callable[[], bool] = lambda: False


class GlobalCommandBar(QFrame):
    def __init__(self, adapter: FoundationCommandAdapter, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("globalCommandBar")
        self.setFixedHeight(TOKENS.command_height)
        self.adapter = adapter
        self.buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, 6, TOKENS.space_3, 6)
        row.setSpacing(TOKENS.space_1)

        self.app_name = QLabel("Full Album Maker")
        self.app_name.setObjectName("appName")
        self.app_name.setMinimumWidth(138)
        row.addWidget(self.app_name)
        row.addSpacing(TOKENS.space_2)
        self._add(row, "new", "Baru", "new", adapter.new_project, "Ctrl+N")
        self._add(row, "open", "Buka", "open", adapter.open_project, "Ctrl+O")
        self._add(row, "save", "Simpan", "save", adapter.save_project, "Ctrl+S")
        self._divider(row)
        self._add(row, "undo", "Undo", "undo", adapter.undo, "Ctrl+Z")
        self._add(row, "redo", "Redo", "redo", adapter.redo, "Ctrl+Y")
        self._divider(row)

        import_button = FAMButton("Impor +", icon_name="import", kind="ghost")
        import_button.setToolTip("Impor audio atau video (Ctrl+I)")
        menu = QMenu(import_button)
        menu.addAction("Audio / Lagu", adapter.import_audio)
        menu.addAction("Video / Footage", adapter.import_video)
        import_button.setMenu(menu)
        self.buttons["import"] = import_button
        row.addWidget(import_button)
        import_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        import_shortcut.activated.connect(import_button.showMenu)

        self._add(row, "auto", "Auto Susun", "auto", adapter.auto_arrange, "Ctrl+Shift+A")
        # Plain Space must remain available to a focused button/navigation item.
        # FoundationShellWidget handles Preview on Space only after checking focus.
        self._add(row, "preview", "Preview", "preview", adapter.preview, None)
        self.buttons["preview"].setToolTip("Preview (Space saat fokus bukan kontrol interaktif)")
        row.addStretch(1)

        render = FAMButton("Render", icon_name="render", kind="primary")
        render.setToolTip("Buka workspace Render (Ctrl+R)")
        render.clicked.connect(adapter.render_route)
        render.setMinimumWidth(96)
        self.buttons["render"] = render
        row.addWidget(render)
        render_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        render_shortcut.activated.connect(adapter.render_route)
        self.refresh_enabled()

    def _divider(self, row: QHBoxLayout) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setStyleSheet(f"color: {TOKENS.border};")
        line.setFixedHeight(28)
        row.addWidget(line)
        row.addSpacing(2)

    def _add(self, row, key: str, text: str, icon_name: str, callback: Callable[[], None], shortcut: str | None) -> None:
        button = FAMButton(text, icon_name=icon_name, kind="ghost")
        button.clicked.connect(callback)
        button.setToolTip(f"{text} ({shortcut})" if shortcut else text)
        self.buttons[key] = button
        row.addWidget(button)
        if shortcut:
            key_shortcut = QShortcut(QKeySequence(shortcut), self)
            key_shortcut.activated.connect(callback)

    def refresh_enabled(self) -> None:
        self.buttons["save"].setEnabled(bool(self.adapter.can_save()))
        self.buttons["save"].setToolTip("Simpan (Ctrl+S)" if self.buttons["save"].isEnabled() else "Simpan — belum ada proyek aktif")
        self.buttons["undo"].setEnabled(bool(self.adapter.can_undo()))
        self.buttons["redo"].setEnabled(bool(self.adapter.can_redo()))
        active = bool(self.adapter.can_project_action())
        for key in ("import", "auto", "preview"):
            self.buttons[key].setEnabled(active)
        if not active:
            self.buttons["import"].setToolTip("Impor — buat atau buka proyek terlebih dahulu")
            self.buttons["auto"].setToolTip("Auto Susun — proyek belum memiliki konteks aktif")
            self.buttons["preview"].setToolTip("Preview — belum ada proyek aktif")


class WorkspaceNavButton(QPushButton):
    """Navigation button with explicit Space/Enter activation on every Qt backend."""

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
            return
        super().keyPressEvent(event)


class WorkspaceNavigation(QFrame):
    route_requested = Signal(str)

    def __init__(self, state: FoundationUiState, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceNavigation")
        self.state = state
        self._compact = False
        self.buttons: dict[str, QPushButton] = {}
        self.setMinimumWidth(TOKENS.nav_width)
        self.setMaximumWidth(TOKENS.nav_width)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 15, 7, TOKENS.space_2)
        lay.setSpacing(2)
        for route, label, icon_name in WORKSPACE_ORDER:
            button = WorkspaceNavButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            button.setIcon(foundation_icon(icon_name, size=TOKENS.icon_nav))
            button.setIconSize(QSize(TOKENS.icon_nav, TOKENS.icon_nav))
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.clicked.connect(lambda _checked=False, r=route: self.route_requested.emit(r))
            self.buttons[route] = button
            lay.addWidget(button)
        lay.addStretch(1)
        self.select("home")

    def select(self, route: str) -> None:
        for key, button in self.buttons.items():
            button.setChecked(key == route)

    def set_compact(self, compact: bool) -> None:
        compact = bool(compact)
        if compact == self._compact:
            return
        self._compact = compact
        width = TOKENS.nav_compact_width if compact else TOKENS.nav_width
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)
        for route, label, _ in WORKSPACE_ORDER:
            self.buttons[route].setText("" if compact else label)
            self.buttons[route].setAccessibleName(label)
            self.buttons[route].setToolTip(label)


class ContextPlaceholder(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("contextHost")
        self.setMinimumWidth(0)
        self.setMaximumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(TOKENS.space_3, TOKENS.space_3, TOKENS.space_3, TOKENS.space_3)
        lay.setSpacing(TOKENS.space_3)
        self.heading = FAMSectionHeader("Beranda")
        lay.addWidget(self.heading)
        lay.addWidget(FAMEmptyState(
            "Konteks workspace",
            "Panel konteks akan diisi pada langkah workspace terkait. STEP 01 hanya menguji host, resize, dan state.",
        ), 1)

    def set_workspace(self, label: str) -> None:
        self.heading.title_label.setText(label)


class WorkspacePlaceholder(QFrame):
    def __init__(self, route: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceHost")
        self.route = route
        lay = QVBoxLayout(self)
        lay.setContentsMargins(TOKENS.space_5, TOKENS.space_5, TOKENS.space_5, TOKENS.space_5)
        lay.setSpacing(TOKENS.space_3)
        heading = QLabel(label)
        heading.setObjectName("workspaceHeading")
        lay.addWidget(heading)
        subtitle = QLabel(f"Workspace: {label} — content implemented in later step")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)
        lay.addSpacing(TOKENS.space_2)
        lay.addWidget(FAMEmptyState(
            "Foundation Preview",
            "Shared shell aktif: navigation, command bar, dock kanan, timeline host, status system, tokens, dan responsive behavior. Isi workspace sengaja belum diimplementasikan pada STEP 01.",
        ), 1)


class WorkspaceStack(QStackedWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(360)
        self._index: dict[str, int] = {}
        for route, label, _ in WORKSPACE_ORDER:
            self._index[route] = self.addWidget(WorkspacePlaceholder(route, label))

    def set_route(self, route: str) -> None:
        self.setCurrentIndex(self._index.get(route, 0))


class InspectorDockHost(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("inspectorDock")
        self._collapsed = False
        self._expanded_width = TOKENS.right_dock_width
        self.setMinimumWidth(TOKENS.right_dock_width)
        self.setMaximumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.header = FAMDockHeader("", collapsible=True)
        self.header.title.hide()
        self.header.setFixedHeight(16)
        self.header.collapse_button.hide()
        self.header.collapse_button.clicked.connect(self.toggle_collapsed)
        lay.addWidget(self.header)
        self.content = TabbedEmptyHost()
        lay.addWidget(self.content, 1)

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def set_expanded_width(self, width: int) -> None:
        self._expanded_width = min(520, max(280, int(width)))
        if not self._collapsed:
            self.setMinimumWidth(self._expanded_width)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.content.setVisible(not self._collapsed)
        if self._collapsed:
            self.setMinimumWidth(38)
            self.setMaximumWidth(38)
            self.header.setFixedHeight(40)
            self.header.collapse_button.show()
            self.header.collapse_button.setIcon(foundation_icon("expand", size=TOKENS.icon_inline))
            self.header.collapse_button.setToolTip("Buka Properti / AI")
        else:
            self.setMaximumWidth(520)
            self.setMinimumWidth(self._expanded_width)
            self.header.setFixedHeight(16)
            self.header.collapse_button.hide()
            self.header.collapse_button.setIcon(foundation_icon("collapse", size=TOKENS.icon_inline))
            self.header.collapse_button.setToolTip("Ciutkan Properti / AI")


class TimelineFoundationCanvas(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(TOKENS.surface))
        left, ruler_h = 72, 22
        p.setPen(QPen(QColor(TOKENS.border), 1))
        p.drawLine(left, ruler_h, self.width(), ruler_h)
        usable = max(1, self.width() - left)
        for i in range(11):
            x = left + int(usable * i / 10)
            p.drawLine(x, 0, x, self.height())
            p.setPen(QColor(TOKENS.text_muted))
            p.drawText(QRectF(x + 3, 2, 55, 16), Qt.AlignmentFlag.AlignLeft, f"{i * 30:02d}:00")
            p.setPen(QPen(QColor(TOKENS.border), 1))
        track_h = max(26, int((self.height() - ruler_h) / 3))
        for idx, label in enumerate(("Video", "Audio", "Teks")):
            y = ruler_h + idx * track_h
            p.fillRect(QRectF(0, y, left, track_h), QColor("#F8FBFF"))
            p.drawLine(0, y, self.width(), y)
            p.setPen(QColor(TOKENS.text_primary))
            p.drawText(QRectF(10, y, left - 15, track_h), Qt.AlignmentFlag.AlignVCenter, label)
            p.setPen(QPen(QColor(TOKENS.border), 1))
        p.end()


class TimelineDockHost(QFrame):
    collapse_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("timelineDock")
        self._collapsed = True
        self._preferred_height = TOKENS.timeline_collapsed_height
        self.setMinimumHeight(TOKENS.timeline_collapsed_height)
        self.setMaximumHeight(TOKENS.timeline_collapsed_height)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        head = QHBoxLayout()
        head.setContentsMargins(TOKENS.space_2, 1, TOKENS.space_2, 1)
        head.setSpacing(TOKENS.space_1)
        self.collapse_button = FAMIconButton("expand", "Buka Timeline")
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        head.addWidget(self.collapse_button)
        title = QLabel("Timeline")
        title.setObjectName("sectionHeading")
        head.addWidget(title)
        self.message = QLabel("Belum ada proyek yang dibuka")
        self.message.setObjectName("metadata")
        head.addWidget(self.message)
        head.addStretch(1)
        self.zoom_out = FAMIconButton("zoom_out", "Perkecil timeline")
        self.zoom_in = FAMIconButton("zoom_in", "Perbesar timeline")
        self.zoom_out.setEnabled(False)
        self.zoom_in.setEnabled(False)
        head.addWidget(self.zoom_out)
        head.addWidget(QLabel("100%"))
        head.addWidget(self.zoom_in)
        lay.addLayout(head)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(TOKENS.space_2, 0, TOKENS.space_2, TOKENS.space_2)
        body.setSpacing(2)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(TOKENS.space_1)
        self.mode = FAMSegmented([("packed", "Packed"), ("free", "Free")])
        toolbar.addWidget(self.mode)
        for text in ("Split", "Ripple", "Snap", "Marker"):
            button = FAMButton(text, kind="ghost")
            button.setEnabled(False)
            button.setToolTip(f"{text} — semantics diselesaikan pada STEP 05")
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        body.addLayout(toolbar)
        self.canvas = TimelineFoundationCanvas()
        body.addWidget(self.canvas, 1)
        lay.addWidget(self.body, 1)
        self.body.hide()

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    @property
    def preferred_height(self) -> int:
        return self._preferred_height

    def set_workspace(self, route: str) -> None:
        height = TIMELINE_HEIGHT_BY_WORKSPACE.get(route, TOKENS.timeline_compact_height)
        self._preferred_height = height
        self.set_collapsed(height <= TOKENS.timeline_collapsed_height)
        if not self._collapsed:
            self._apply_height(height)

    def set_project_context(self, text: str) -> None:
        self.message.setText(text)

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = bool(collapsed)
        self.body.setVisible(not self._collapsed)
        self.collapse_button.setIcon(foundation_icon("expand" if self._collapsed else "collapse", size=TOKENS.icon_inline))
        self.collapse_button.setToolTip("Buka Timeline" if self._collapsed else "Ciutkan Timeline")
        self._apply_height(TOKENS.timeline_collapsed_height if self._collapsed else self._preferred_height)
        self.collapse_changed.emit(self._collapsed)

    def _apply_height(self, height: int) -> None:
        height = max(TOKENS.timeline_collapsed_height, int(height))
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)


class _StatusItem(QWidget):
    def __init__(self, text: str, status: str = "neutral", parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(5)
        self.dot = QFrame()
        self.dot.setFixedSize(8, 8)
        self.label = QLabel(text)
        self.label.setObjectName("metadata")
        row.addWidget(self.dot)
        row.addWidget(self.label)
        self.set_value(text, status)

    def set_value(self, text: str, status: str) -> None:
        colors = {"success": TOKENS.success, "warning": TOKENS.warning, "error": TOKENS.danger, "neutral": "#8190A7"}
        self.dot.setStyleSheet(f"background: {colors.get(status, colors['neutral'])}; border-radius: 4px;")
        self.label.setText(text)


class AppStatusBar(QFrame):
    def __init__(self, state: FoundationUiState, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("appStatusBar")
        self.setFixedHeight(TOKENS.status_height)
        self.state = state
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, 0, TOKENS.space_3, 0)
        row.setSpacing(TOKENS.space_3)
        self.context = QLabel(state.project_context)
        self.context.setObjectName("metadata")
        row.addWidget(self.context)
        row.addStretch(1)
        self.save = _StatusItem(state.save_text, state.save_state)
        self.ffmpeg = _StatusItem(state.ffmpeg_text, state.ffmpeg_state)
        self.ai = _StatusItem(state.ai_text, state.ai_state)
        self.jobs = _StatusItem(state.jobs_text, state.jobs_state)
        for widget in (self.save, self.ffmpeg, self.ai, self.jobs):
            row.addWidget(widget)
        state.status_changed.connect(self.refresh)

    def refresh(self) -> None:
        s = self.state
        self.context.setText(s.project_context)
        self.save.set_value(s.save_text, s.save_state)
        self.ffmpeg.set_value(s.ffmpeg_text, s.ffmpeg_state)
        self.ai.set_value(s.ai_text, s.ai_state)
        self.jobs.set_value(s.jobs_text, s.jobs_state)


class FoundationShellWidget(QWidget):
    """Shared STEP 01 shell. Workspace content remains controlled placeholders."""

    def __init__(self, *, state: FoundationUiState | None = None, adapter: FoundationCommandAdapter | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("foundationRoot")
        self.state = state or FoundationUiState()
        self.adapter = adapter or FoundationCommandAdapter()
        self._responsive_compact = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.command_bar = GlobalCommandBar(self.adapter)
        root.addWidget(self.command_bar)

        self.vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        self.vertical_splitter.setHandleWidth(TOKENS.splitter_handle)
        self.vertical_splitter.setChildrenCollapsible(False)
        self.horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.horizontal_splitter.setHandleWidth(TOKENS.splitter_handle)
        self.horizontal_splitter.setChildrenCollapsible(False)

        self.navigation = WorkspaceNavigation(self.state)
        self.context = ContextPlaceholder()
        self.workspace_stack = WorkspaceStack()
        self.inspector = InspectorDockHost()
        for widget in (self.navigation, self.context, self.workspace_stack, self.inspector):
            self.horizontal_splitter.addWidget(widget)
        self.horizontal_splitter.setStretchFactor(0, 0)
        self.horizontal_splitter.setStretchFactor(1, 0)
        self.horizontal_splitter.setStretchFactor(2, 1)
        self.horizontal_splitter.setStretchFactor(3, 0)

        self.timeline = TimelineDockHost()
        self.vertical_splitter.addWidget(self.horizontal_splitter)
        self.vertical_splitter.addWidget(self.timeline)
        self.vertical_splitter.setStretchFactor(0, 1)
        self.vertical_splitter.setStretchFactor(1, 0)
        root.addWidget(self.vertical_splitter, 1)

        self.status_bar = AppStatusBar(self.state)
        root.addWidget(self.status_bar)
        self.navigation.route_requested.connect(self.state.set_workspace)
        self.state.workspace_changed.connect(self._apply_workspace)
        self._apply_workspace(self.state.workspace)

    def _apply_workspace(self, route: str) -> None:
        route = route if route in WORKSPACE_LABELS else "home"
        self.navigation.select(route)
        self.workspace_stack.set_route(route)
        self.context.set_workspace(WORKSPACE_LABELS[route])
        self.timeline.set_workspace(route)
        self._apply_shell_sizes(route)

    def _apply_shell_sizes(self, route: str) -> None:
        total = max(1, self.width())
        if self._responsive_compact:
            nav = TOKENS.nav_compact_width
        elif route == "home":
            nav = TOKENS.home_nav_width
        else:
            nav = TOKENS.nav_width
        self.navigation.setMinimumWidth(nav)
        self.navigation.setMaximumWidth(nav)
        context = 0 if route in {"home", "render"} else TOKENS.context_width
        right = 38 if self.inspector.collapsed else (TOKENS.right_dock_compact_width if self._responsive_compact else TOKENS.right_dock_width)
        minimum_center = 360 if self._responsive_compact else 560
        center = max(minimum_center, total - nav - context - right - TOKENS.splitter_handle * 3)
        self.context.setMinimumWidth(context)
        self.context.setMaximumWidth(420 if context else 0)
        self.horizontal_splitter.setSizes([nav, context, center, right])

        timeline_h = TOKENS.timeline_collapsed_height if self.timeline.collapsed else self.timeline.preferred_height
        top_h = max(300 if self._responsive_compact else 360, self.height() - timeline_h - TOKENS.status_height - TOKENS.command_height)
        self.vertical_splitter.setSizes([top_h, timeline_h])

    def set_workspace(self, route: str) -> None:
        self.state.set_workspace(route)

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        self._responsive_compact = compact
        self.navigation.set_compact(compact)
        self._apply_shell_sizes(self.state.workspace)

    def set_viewport_width(self, width: int) -> None:
        self.set_compact_mode(int(width) < TOKENS.compact_breakpoint)

    def refresh_commands(self) -> None:
        self.command_bar.refresh_enabled()

    def _focus_consumes_space(self) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        if isinstance(focus, QPushButton):
            return True
        return focus.metaObject().className() in {
            "QLineEdit", "QPlainTextEdit", "QTextEdit", "QSpinBox",
            "QDoubleSpinBox", "QComboBox", "QSlider", "QCheckBox", "QRadioButton",
        }

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not self._focus_consumes_space():
            if self.command_bar.buttons["preview"].isEnabled():
                self.adapter.preview()
                event.accept()
                return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.set_viewport_width(event.size().width())


class FoundationFixtureWindow(QMainWindow):
    """Deterministic shell-only window for screenshot regression."""

    def __init__(self, workspace: str = "home") -> None:
        super().__init__()
        self.setWindowTitle("Full Album Maker")
        self.setStyleSheet(FOUNDATION_STYLE)
        state = FoundationUiState()
        adapter = FoundationCommandAdapter(can_save=lambda: True, can_project_action=lambda: True)
        self.shell = FoundationShellWidget(state=state, adapter=adapter)
        self.setCentralWidget(self.shell)
        self.resize(TOKENS.golden_width, TOKENS.golden_height)
        self.shell.set_workspace(workspace)
        state.set_status(
            save=("Tersimpan", "success"),
            ffmpeg=("FFmpeg Siap", "success"),
            ai=("AI Opsional", "neutral"),
            jobs=("Jobs: 0", "neutral"),
            project_context="Foundation Preview",
        )
        self.shell.timeline.set_project_context("Foundation Preview")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "shell"):
            self.shell.set_viewport_width(event.size().width())
