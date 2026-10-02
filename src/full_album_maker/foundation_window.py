from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from .controller import ProjectController
from .editor_models import ProjectDocument
from .foundation_preferences import FoundationPreferenceStore, FoundationPreferences
from .foundation_shell import FoundationCommandAdapter, FoundationShellWidget, FoundationUiState
from .foundation_theme import FOUNDATION_STYLE
from .foundation_tokens import TOKENS
from .paths import ffmpeg_path
from .project import Project
from .v14_window import V14EditorMainWindow


class FoundationMainWindow(V14EditorMainWindow):
    """STEP 01 visible shell wrapped around recovered v1.4 behavior.

    The recovered widget tree remains alive as an internal compatibility surface,
    avoiding a second project/timeline/AI engine while later workspace steps bind
    real views into the new shared shell.
    """

    def __init__(self) -> None:
        self._foundation_ready = False
        self._foundation_project_open = False
        self._foundation_pref_store = FoundationPreferenceStore()
        super().__init__()
        self._foundation_project_open = bool(self.project.videos or self.project.audios)
        legacy = self.takeCentralWidget()
        self._legacy_root = legacy
        if legacy is not None:
            legacy.hide()
            legacy.setParent(self)
        self.foundation_state = FoundationUiState()
        self.foundation_shell = FoundationShellWidget(state=self.foundation_state, adapter=self._foundation_adapter())
        self.setCentralWidget(self.foundation_shell)
        self.setStyleSheet(FOUNDATION_STYLE)
        self.setWindowTitle("Full Album Maker")
        self.setMinimumSize(1180, 720)
        self._foundation_ready = True
        self._apply_foundation_preferences()
        # Qt/Windows may not deliver the child resize event before first show.
        # Resolve responsive mode from the outer window explicitly so a saved
        # 1366-wide window cannot start with the 172 px desktop rail.
        self.foundation_shell.set_compact_mode(self.width() < TOKENS.compact_breakpoint)
        self._sync_foundation_state()

    def _foundation_adapter(self) -> FoundationCommandAdapter:
        return FoundationCommandAdapter(
            new_project=self._foundation_new_project,
            open_project=self._foundation_open_project,
            save_project=self._foundation_save_project,
            undo=self._foundation_undo,
            redo=self._foundation_redo,
            import_audio=self._foundation_import_audio,
            import_video=self._foundation_import_video,
            auto_arrange=self._foundation_auto_arrange,
            preview=self._foundation_preview,
            render_route=lambda: self.foundation_shell.set_workspace("render"),
            can_save=lambda: self._foundation_project_open,
            can_undo=lambda: bool(getattr(getattr(self, "editor_workspace", None), "session", None) and self.editor_workspace.session.can_undo),
            can_redo=lambda: bool(getattr(getattr(self, "editor_workspace", None), "session", None) and self.editor_workspace.session.can_redo),
            can_project_action=lambda: self._foundation_project_open,
        )

    def _foundation_new_project(self) -> None:
        session = getattr(getattr(self, "editor_workspace", None), "session", None)
        if self.project.videos or self.project.audios or bool(session and session.is_dirty):
            answer = QMessageBox.question(
                self,
                "Proyek Baru",
                "Buat proyek baru dan tinggalkan state proyek yang sedang aktif?\n\nGunakan Simpan terlebih dahulu bila perubahan masih diperlukan.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.project = Project()
        self.controller = ProjectController(self.project)
        self.agent = None
        self.invalidate_timeline()
        if getattr(self, "editor_workspace", None) is not None:
            self.editor_workspace.set_document(ProjectDocument.new_empty("Full Album"))
            self._legacy_project_identity = id(self.project)
        self._foundation_project_open = True
        self.foundation_shell.set_workspace("home")
        self.refresh()
        self.foundation_state.set_status(project_context="Proyek baru • 16:9 • 1920×1080")

    def _foundation_open_project(self) -> None:
        before = id(self.project)
        self.load_project_file()
        if id(self.project) != before:
            self._foundation_project_open = True
            self.foundation_shell.set_workspace("home")
        self._sync_foundation_state()

    def _foundation_save_project(self) -> None:
        if not self._foundation_project_open:
            return
        self.foundation_state.set_status(save=("Menyimpan…", "warning"))
        self.save_project_file()
        self._sync_foundation_state()

    def _foundation_undo(self) -> None:
        session = getattr(getattr(self, "editor_workspace", None), "session", None)
        if session is None or not session.can_undo:
            return
        session.undo()
        try:
            self.editor_workspace._after_edit()
        except Exception:
            pass
        self._sync_foundation_state()

    def _foundation_redo(self) -> None:
        session = getattr(getattr(self, "editor_workspace", None), "session", None)
        if session is None or not session.can_redo:
            return
        session.redo()
        try:
            self.editor_workspace._after_edit()
        except Exception:
            pass
        self._sync_foundation_state()

    def _foundation_import_audio(self) -> None:
        if self._foundation_project_open:
            self.add_audio()
            self.foundation_shell.set_workspace("media")
            self._sync_foundation_state()

    def _foundation_import_video(self) -> None:
        if self._foundation_project_open:
            self.add_video()
            self.foundation_shell.set_workspace("media")
            self._sync_foundation_state()

    def _foundation_auto_arrange(self) -> None:
        if self._foundation_project_open:
            self.auto_build_timeline()
            self.foundation_shell.set_workspace("timeline")
            self._sync_foundation_state()

    def _foundation_preview(self) -> None:
        if self._foundation_project_open:
            self.preview_plan()

    def _sync_foundation_state(self) -> None:
        if not getattr(self, "_foundation_ready", False):
            return
        session = getattr(getattr(self, "editor_workspace", None), "session", None)
        dirty = bool(session and session.is_dirty)
        ffmpeg_ready = bool(ffmpeg_path())
        key_summary = self.pool.summary() if getattr(self, "pool", None) is not None else {}
        ai_ready = bool(key_summary.get("ready", 0))
        jobs = 1 if bool(getattr(self, "render_busy", False)) else 0
        if not self._foundation_project_open:
            context = "Belum ada proyek yang dibuka"
        else:
            s = self.project.settings
            context = f"Proyek aktif • {len(self.project.audios)} lagu • {len(self.project.videos)} footage • {s.width}×{s.height}"
        self.foundation_state.set_status(
            save=(("Belum disimpan" if dirty else "Tersimpan"), ("warning" if dirty else "success")),
            ffmpeg=(("FFmpeg Siap" if ffmpeg_ready else "FFmpeg belum tersedia"), ("success" if ffmpeg_ready else "warning")),
            ai=(("Gemini Terhubung" if ai_ready else "AI Opsional"), ("success" if ai_ready else "neutral")),
            jobs=(f"Jobs: {jobs}", "warning" if jobs else "neutral"),
            project_context=context,
        )
        self.foundation_shell.timeline.set_project_context(context)
        self.foundation_shell.refresh_commands()

    def refresh(self, *args, **kwargs):
        result = super().refresh(*args, **kwargs)
        self._sync_foundation_state()
        return result

    def _apply_foundation_preferences(self) -> None:
        prefs = self._foundation_pref_store.load()
        self.resize(prefs.width, prefs.height)
        self.foundation_shell.set_workspace(prefs.workspace)
        self.foundation_shell.inspector.set_expanded_width(prefs.right_dock_width)
        self.foundation_shell.inspector.set_collapsed(prefs.right_dock_collapsed)
        if prefs.timeline_collapsed:
            self.foundation_shell.timeline.set_collapsed(True)
        if prefs.maximized:
            self.showMaximized()

    def _save_foundation_preferences(self) -> None:
        prefs = FoundationPreferences(
            width=self.width(), height=self.height(), maximized=self.isMaximized(),
            workspace=self.foundation_state.workspace,
            nav_compact=self.foundation_shell.navigation._compact,
            right_dock_collapsed=self.foundation_shell.inspector.collapsed,
            right_dock_width=max(TOKENS.right_dock_width, self.foundation_shell.inspector.width()) if not self.foundation_shell.inspector.collapsed else TOKENS.right_dock_width,
            timeline_collapsed=self.foundation_shell.timeline.collapsed,
            timeline_height=self.foundation_shell.timeline.preferred_height,
        )
        try:
            self._foundation_pref_store.save(prefs)
        except OSError:
            pass

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if getattr(self, "_foundation_ready", False):
            self.foundation_shell.set_compact_mode(event.size().width() < TOKENS.compact_breakpoint)

    def closeEvent(self, event) -> None:
        if getattr(self, "_foundation_ready", False):
            self._save_foundation_preferences()
        super().closeEvent(event)
