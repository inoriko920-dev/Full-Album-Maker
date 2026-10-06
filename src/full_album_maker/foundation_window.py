from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QListWidget, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout,
)

from .controller import ProjectController
from .editor_models import ProjectDocument
from .foundation_components import FAMEmptyState
from .foundation_preferences import FoundationPreferenceStore, FoundationPreferences
from .foundation_shell import FoundationCommandAdapter, FoundationShellWidget, FoundationUiState
from .foundation_theme import FOUNDATION_STYLE
from .foundation_tokens import TOKENS
from .home_inspector import HomeInspectorWidget
from .home_services import (
    HomeProjectService, QuickDefaultsStore, RecentProjectsService, RecoveryService,
)
from .home_state import (
    CapabilityState, HomeViewState, PortableStatus, RecoveryValidation,
)
from .home_workspace import HomeWorkspace
from . import __version__
from .paths import ffmpeg_path, output_dir
from .project import Project
from .project_io import save_project
from .v14_window import V14EditorMainWindow


class FoundationMainWindow(V14EditorMainWindow):
    """Shared foundation plus the STEP 02 Beranda project hub."""

    def __init__(self) -> None:
        self._foundation_ready = False
        self._foundation_project_open = False
        self._foundation_project_path = ""
        self._foundation_pref_store = FoundationPreferenceStore()
        self._home_recent_service = RecentProjectsService()
        self._home_defaults_store = QuickDefaultsStore()
        self._home_recovery_service = RecoveryService()
        self._home_state = HomeViewState()
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
        self.setWindowTitle(f"Full Album Maker v{__version__}")
        self.setMinimumSize(1180, 720)
        self._install_home_project_hub()
        self._foundation_ready = True
        self._apply_foundation_preferences()
        self.foundation_shell.set_compact_mode(self.width() < TOKENS.compact_breakpoint)
        self._refresh_home_from_services()
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

    def _install_home_project_hub(self) -> None:
        defaults = self._home_defaults_store.load()
        recent = self._home_recent_service.load()
        capabilities = self._portable_status()
        self._home_state = HomeViewState(quick_defaults=defaults).with_recent(recent).with_capabilities(capabilities)
        candidate = self._home_recovery_service.discover()
        if candidate is not None and candidate.validation_state == RecoveryValidation.VALID:
            self._home_state = self._home_state.with_valid_recovery(candidate)
        self.home_workspace = HomeWorkspace(state=self._home_state)
        self.home_workspace.create_project_requested.connect(self._home_create_project)
        self.home_workspace.open_project_requested.connect(self._home_choose_open_project)
        self.home_workspace.restore_recovery_requested.connect(self._home_restore_recovery)
        self.home_workspace.dismiss_recovery_requested.connect(self._home_dismiss_recovery)
        self.home_workspace.recent_open_requested.connect(self._home_open_recent)
        self.home_workspace.recent_remove_requested.connect(self._home_remove_recent)
        self.home_workspace.show_all_recent_requested.connect(self._home_show_all_recent)
        self.home_workspace.quick_route_requested.connect(self._home_quick_route)
        index = self.foundation_shell.workspace_stack._index["home"]
        old_home = self.foundation_shell.workspace_stack.widget(index)
        self.foundation_shell.workspace_stack.removeWidget(old_home)
        old_home.setParent(None)
        self.foundation_shell.workspace_stack.insertWidget(index, self.home_workspace)
        self.home_inspector = HomeInspectorWidget(self._home_state)
        self.home_inspector.defaults_changed.connect(self._home_defaults_changed)
        self.home_inspector.browse_output_requested.connect(self._home_browse_output)
        self._inspector_router = QStackedWidget()
        self._inspector_router.addWidget(self.home_inspector)
        self._inspector_router.addWidget(FAMEmptyState("Belum ada pilihan", "Pilih objek di workspace untuk melihat properti."))
        self.foundation_shell.inspector.content.set_properties_widget(self._inspector_router)
        self.foundation_state.workspace_changed.connect(self._home_workspace_changed)
        self._home_workspace_changed(self.foundation_state.workspace)

    def _portable_status(self) -> PortableStatus:
        ffmpeg_ready = bool(ffmpeg_path())
        key_summary = self.pool.summary() if getattr(self, "pool", None) is not None else {}
        ai_ready = bool(key_summary.get("ready", 0))
        return PortableStatus(
            ffmpeg=CapabilityState.READY if ffmpeg_ready else CapabilityState.WARNING,
            manual_offline=CapabilityState.READY,
            ai_config=CapabilityState.READY if ai_ready else CapabilityState.OPTIONAL,
            ffmpeg_detail=("FFmpeg portable ditemukan dan siap digunakan." if ffmpeg_ready else "FFmpeg portable belum ditemukan."),
            manual_detail="Fungsi editing inti dapat digunakan tanpa AI/network.",
            ai_detail=("Gemini dikonfigurasi dan key siap digunakan." if ai_ready else "AI opsional dan belum dikonfigurasi."),
        )

    def _refresh_home_from_services(self) -> None:
        self._home_state = self._home_state.with_recent(self._home_recent_service.load())
        self._home_state = self._home_state.with_capabilities(self._portable_status())
        if not self._home_state.recovery_dismissed_for_session:
            candidate = self._home_recovery_service.discover()
            if candidate is not None and candidate.validation_state == RecoveryValidation.VALID:
                self._home_state = self._home_state.with_valid_recovery(candidate)
        self._apply_home_state()

    def _apply_home_state(self) -> None:
        if hasattr(self, "home_workspace"):
            self.home_workspace.apply_state(self._home_state)
        if hasattr(self, "home_inspector"):
            self.home_inspector.apply_state(self._home_state)
            valid = self._home_defaults_store.output_is_writable(self._home_state.quick_defaults)
            self.home_inspector.set_output_warning("" if valid else "Pilih lokasi output yang dapat ditulis.")

    def _home_workspace_changed(self, route: str) -> None:
        if hasattr(self, "_inspector_router"):
            self._inspector_router.setCurrentIndex(0 if route == "home" else 1)

    def _confirm_replace_project(self) -> bool:
        session = getattr(getattr(self, "editor_workspace", None), "session", None)
        if not self._foundation_project_open and not bool(session and session.is_dirty):
            return True
        answer = QMessageBox.question(
            self,
            "Ganti Proyek",
            "Buka atau buat proyek lain?\n\nGunakan Simpan terlebih dahulu bila perubahan sekarang masih diperlukan.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        try:
            self._home_recovery_service.write_snapshot(self.project)
        except Exception:
            pass
        return True

    def _adopt_home_project(self, project: Project, result, *, route: str = "media", add_recent: bool = True) -> None:
        self.project = project
        self.controller = ProjectController(self.project)
        self.agent = None
        self.invalidate_timeline()
        self._foundation_project_open = True
        self._foundation_project_path = result.project_path if add_recent else ""
        if getattr(self, "editor_workspace", None) is not None:
            self.editor_workspace.set_document(ProjectDocument.new_empty(result.project_context or "Full Album"))
            self._legacy_project_identity = id(self.project)
        if add_recent and result.project_path:
            try:
                self._home_recent_service.touch(result.project_path, project)
            except OSError:
                pass
        self._home_state = self._home_state.project_opened(result).with_recent(self._home_recent_service.load())
        self.refresh()
        self._apply_home_state()
        self.foundation_shell.set_workspace(route)

    def _home_create_project(self) -> None:
        if not self._confirm_replace_project():
            return
        default = str(output_dir() / "Full_Album_Project.json")
        path, _ = QFileDialog.getSaveFileName(self, "Proyek Baru", default, "Full Album Project (*.json)")
        if not path:
            return
        self._home_state = self._home_state.begin("create_project")
        self._apply_home_state()
        result, project = HomeProjectService.create(path, self._home_state.quick_defaults)
        if not result.success or project is None:
            self._home_state = self._home_state.project_opened(result)
            self._apply_home_state()
            return
        self._adopt_home_project(project, result, route="media")

    def _home_choose_open_project(self) -> None:
        if not self._confirm_replace_project():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Buka Proyek", "", "Full Album Project (*.json)")
        if path:
            self._home_open_path(path)

    def _home_open_path(self, path: str) -> None:
        self._home_state = self._home_state.begin("open_project")
        self._apply_home_state()
        result, project = HomeProjectService.open(path)
        if not result.success or project is None:
            self._home_state = self._home_state.project_opened(result)
            self._apply_home_state()
            return
        self._adopt_home_project(project, result, route="media")

    def _home_open_recent(self, path: str) -> None:
        source = Path(path)
        if not source.exists():
            located, _ = QFileDialog.getOpenFileName(self, "Cari Lokasi Proyek", str(source.parent), "Full Album Project (*.json)")
            if not located:
                return
            path = located
        if not self._confirm_replace_project():
            return
        self._home_open_path(path)

    def _home_remove_recent(self, project_id: str) -> None:
        try:
            self._home_recent_service.remove(project_id)
        except OSError as exc:
            QMessageBox.warning(self, "Proyek Terakhir", f"Daftar proyek tidak dapat diperbarui:\n{exc}")
            return
        self._home_state = self._home_state.with_recent(self._home_recent_service.load())
        self._apply_home_state()

    def _home_show_all_recent(self) -> None:
        projects = self._home_recent_service.load()
        dialog = QDialog(self)
        dialog.setWindowTitle("Proyek Terakhir")
        dialog.resize(620, 420)
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        for project in projects:
            item_text = project.display_name
            if not Path(project.path).exists():
                item_text += " — Tidak ditemukan"
            listing.addItem(item_text)
            listing.item(listing.count() - 1).setData(Qt.ItemDataRole.UserRole, project.path)
        layout.addWidget(listing, 1)
        row = QHBoxLayout()
        open_button = QPushButton("Buka")
        close_button = QPushButton("Tutup")
        row.addStretch(1)
        row.addWidget(open_button)
        row.addWidget(close_button)
        layout.addLayout(row)

        def open_selected() -> None:
            current = listing.currentItem()
            if current is None:
                return
            path = str(current.data(Qt.ItemDataRole.UserRole) or "")
            dialog.accept()
            self._home_open_recent(path)

        open_button.clicked.connect(open_selected)
        listing.itemDoubleClicked.connect(lambda _item: open_selected())
        close_button.clicked.connect(dialog.reject)
        dialog.exec()

    def _home_restore_recovery(self) -> None:
        candidate = self._home_state.recovery
        if candidate is None:
            return
        self._home_state = self._home_state.begin("restore_recovery")
        self._apply_home_state()
        result, project = self._home_recovery_service.restore(candidate)
        if not result.success or project is None:
            self._home_state = self._home_state.project_opened(result)
            self._apply_home_state()
            return
        self._adopt_home_project(project, result, route="media", add_recent=False)

    def _home_dismiss_recovery(self) -> None:
        self._home_state = self._home_state.dismiss_recovery()
        self._apply_home_state()

    def _home_quick_route(self, route: str) -> None:
        if route == "media":
            if not self._foundation_project_open:
                self._home_create_project()
                return
            self.foundation_shell.set_workspace("media")
            return
        if route == "album":
            if not self._foundation_project_open:
                self._home_create_project()
                return
            self.foundation_shell.set_workspace("album" if self.project.audios else "media")
            return
        if route == "render":
            self.foundation_shell.set_workspace("render")

    def _home_defaults_changed(self, defaults) -> None:
        valid = self._home_defaults_store.output_is_writable(defaults)
        self._home_state = self._home_state.with_quick_defaults(defaults, output_valid=valid)
        if valid:
            try:
                self._home_defaults_store.save(defaults)
            except OSError:
                pass
        if self._foundation_project_open:
            self.project.settings.width = defaults.width
            self.project.settings.height = defaults.height
        self._apply_home_state()
        self._sync_foundation_state()

    def _home_browse_output(self) -> None:
        start = self._home_state.quick_defaults.output_folder or str(output_dir())
        selected = QFileDialog.getExistingDirectory(self, "Pilih Folder Output", start)
        if selected:
            self.home_inspector.set_output_folder(selected)

    def _foundation_new_project(self) -> None:
        self._home_create_project()

    def _foundation_open_project(self) -> None:
        before = id(self.project)
        self.load_project_file()
        if id(self.project) != before:
            self._foundation_project_open = True
            self._foundation_project_path = ""
            self.foundation_shell.set_workspace("home")
            self._home_state = self._home_state.with_recent(self._home_recent_service.load())
            self._apply_home_state()
        self._sync_foundation_state()

    def _foundation_save_project(self) -> None:
        if not self._foundation_project_open:
            return
        if not self._foundation_project_path:
            self.foundation_state.set_status(save=("Menyimpan…", "warning"))
            self.save_project_file()
            self._sync_foundation_state()
            return
        self.foundation_state.set_status(save=("Menyimpan…", "warning"))
        try:
            saved = save_project(self._foundation_project_path, self.project)
            self._foundation_project_path = saved
            self._home_recent_service.touch(saved, self.project)
            self._home_state = self._home_state.with_recent(self._home_recent_service.load())
        except Exception as exc:
            QMessageBox.critical(self, "Simpan Proyek", f"Gagal menyimpan proyek:\n{exc}")
        self._apply_home_state()
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
        caps = self._portable_status()
        ffmpeg_ready = caps.ffmpeg == CapabilityState.READY
        ai_ready = caps.ai_config == CapabilityState.READY
        jobs = 1 if bool(getattr(self, "render_busy", False)) else 0
        if not self._foundation_project_open:
            context = "Belum ada proyek yang dibuka"
        else:
            s = self.project.settings
            name = Path(self._foundation_project_path).stem if self._foundation_project_path else "Proyek aktif"
            context = f"{name} • {len(self.project.audios)} lagu • {len(self.project.videos)} footage • {s.width}×{s.height}"
        self.foundation_state.set_status(
            save=(("Belum disimpan" if dirty else "Tersimpan"), ("warning" if dirty else "success")),
            ffmpeg=(("FFmpeg Siap" if ffmpeg_ready else "FFmpeg belum tersedia"), ("success" if ffmpeg_ready else "warning")),
            ai=(("Gemini Terhubung" if ai_ready else "AI Opsional"), ("success" if ai_ready else "neutral")),
            jobs=(f"Jobs: {jobs}", "warning" if jobs else "neutral"),
            project_context=context,
        )
        self.foundation_shell.timeline.set_project_context(context)
        self.foundation_shell.refresh_commands()
        self._home_state = self._home_state.with_capabilities(caps)
        self._apply_home_state()

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
