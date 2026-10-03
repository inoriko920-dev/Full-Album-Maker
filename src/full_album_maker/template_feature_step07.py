from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog, QMessageBox

from .custom_template_builder import CustomTemplate, CustomTemplateStore
from .template_portability_step07 import (
    create_portable_custom_from_document,
    duplicate_portable_template,
    save_custom_draft,
)
from .template_studio_step07 import (
    ORIGIN_CUSTOM,
    TemplateFavoriteStore,
    TemplateStudioDescriptor,
    TemplateStudioDraft,
    build_template_apply_commands,
    builtin_descriptors,
    custom_descriptors,
    filter_templates,
    preview_template_document,
    stable_scope_song_ids,
)
from .template_thumbnail_cache_step07 import TemplateThumbnailCache
from .template_workspace_step07 import (
    TemplateFilterContext,
    TemplateGalleryWorkspace,
    TemplateInspector,
)
from .visual_workspace_step06 import VisualAlignmentCanvas


_installed = False
_original_init: Any = None


def _install_widgets(self) -> None:
    self._s07_store = CustomTemplateStore()
    self._s07_favorites_store = TemplateFavoriteStore()
    self._s07_thumbnail_cache = TemplateThumbnailCache(parent=self)
    self._s07_selected_template_id = ""
    self._s07_drafts: dict[str, TemplateStudioDraft] = {}
    self._s07_catalog: tuple[TemplateStudioDescriptor, ...] = ()
    self._s07_custom_errors: tuple[str, ...] = ()

    self.template_workspace_s07 = TemplateGalleryWorkspace()
    index = self.foundation_shell.workspace_stack._index["template"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.template_workspace_s07)

    context_layout = self.foundation_shell.context.layout()
    self.template_context_s07 = TemplateFilterContext()
    self.template_context_s07.hide()
    context_layout.addWidget(self.template_context_s07, 1)

    self.template_inspector_s07 = TemplateInspector()
    self._inspector_router.addWidget(self.template_inspector_s07)

    self.template_timeline_s07 = VisualAlignmentCanvas()
    timeline_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    timeline_layout.addWidget(self.template_timeline_s07, 1)
    self.template_timeline_s07.hide()


def _connect_widgets(self) -> None:
    self.template_context_s07.filters_changed.connect(self._s07_refresh)
    self.template_workspace_s07.template_selected.connect(self._s07_select_template)
    self.template_workspace_s07.preview_requested.connect(self._s07_preview_template)
    self.template_workspace_s07.use_requested.connect(self._s07_use_template)
    self.template_workspace_s07.favorite_requested.connect(self._s07_set_favorite)
    self.template_inspector_s07.draft_changed.connect(self._s07_draft_changed)
    self.template_inspector_s07.preview_requested.connect(self._s07_preview)
    self.template_inspector_s07.use_requested.connect(self._s07_apply)
    self.template_inspector_s07.create_requested.connect(self._s07_create_custom)
    self.template_inspector_s07.duplicate_requested.connect(self._s07_duplicate)
    self.template_inspector_s07.save_custom_requested.connect(self._s07_save_custom)
    self.template_inspector_s07.reset_requested.connect(self._s07_reset)
    self._s07_thumbnail_cache.thumbnail_ready.connect(self._s07_thumbnail_ready)
    self.foundation_state.workspace_changed.connect(self._s07_route)
    self.editor_workspace.documentChanged.connect(self._s07_document_changed)
    self.destroyed.connect(lambda *_args: self._s07_thumbnail_cache.close())


def _hide_prior_surfaces(self) -> None:
    for widget in getattr(self, "_s06_context_old", ()):
        if widget is not None:
            widget.setVisible(False)
    for name in (
        "media_context",
        "album_context",
        "timeline_context_s05",
        "visual_context_s06",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    for name in (
        "media_timeline_canvas",
        "album_timeline_canvas",
        "timeline_precision_s05",
        "visual_timeline_s06",
        "_s03_timeline_old",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    self.foundation_shell.timeline.canvas.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "template"
    self.template_context_s07.setVisible(active)
    self.template_timeline_s07.setVisible(active)
    if not active:
        if self._inspector_router.currentWidget() is self.template_inspector_s07:
            self._inspector_router.setCurrentIndex(1)
        return
    _hide_prior_surfaces(self)
    self._inspector_router.setCurrentWidget(self.template_inspector_s07)
    self.foundation_shell.timeline.set_collapsed(False)
    self._s07_refresh()


def _document_changed(self, _document) -> None:
    if hasattr(self, "template_workspace_s07") and self.foundation_state.workspace == "template":
        self._s07_refresh()


def _load_catalog(self) -> None:
    customs, errors = self._s07_store.scan()
    self._s07_custom_errors = tuple(errors)
    self._s07_catalog = (*builtin_descriptors(), *custom_descriptors(customs))


def _descriptor_map(self) -> dict[str, TemplateStudioDescriptor]:
    return {item.template_id: item for item in self._s07_catalog}


def _draft_for_descriptor(self, descriptor: TemplateStudioDescriptor) -> TemplateStudioDraft:
    ratio = self.template_context_s07.ratio_key
    draft = self._s07_drafts.get(descriptor.template_id)
    if draft is None:
        draft = TemplateStudioDraft(template_id=descriptor.template_id, ratio=ratio)
        self._s07_drafts[descriptor.template_id] = draft
    else:
        draft.ratio = ratio
    draft.validate()
    return draft


def _inspector_draft(self) -> TemplateStudioDraft:
    draft = self.template_inspector_s07.draft()
    draft.ratio = self.template_context_s07.ratio_key
    draft.validate()
    return draft


def _refresh(self) -> None:
    if not hasattr(self, "template_workspace_s07"):
        return
    self._s07_load_catalog()
    favorites = self._s07_favorites_store.load()
    visible = filter_templates(
        self._s07_catalog,
        search=self.template_context_s07.search.text(),
        origin=self.template_context_s07.origin_key,
        category=self.template_context_s07.category_key,
        ratio=self.template_context_s07.ratio_key,
        favorites=favorites,
        sort=self.template_context_s07.sort_key,
    )
    visible_ids = {item.template_id for item in visible}
    if self._s07_selected_template_id not in visible_ids:
        self._s07_selected_template_id = visible[0].template_id if visible else ""
    self.template_context_s07.set_counts(len(visible), custom_errors=self._s07_custom_errors)
    self.template_workspace_s07.set_templates(
        visible,
        selected_id=self._s07_selected_template_id,
        favorites=favorites,
    )
    if self._s07_selected_template_id:
        descriptor = self._s07_descriptor_map().get(self._s07_selected_template_id)
        if descriptor is not None:
            self.template_inspector_s07.set_template(
                descriptor,
                self._s07_draft_for_descriptor(descriptor),
            )
    self._s07_refresh_timeline()
    self._s07_request_thumbnails(visible)
    self.foundation_shell.refresh_commands()


def _request_thumbnails(self, descriptors) -> None:
    if not self.isVisible():
        return
    if os.environ.get("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "").strip() == "1":
        return
    document = self.editor_workspace.document()
    if not document.playlist.entries:
        return
    for descriptor in descriptors:
        try:
            draft = self._s07_draft_for_descriptor(descriptor)
            custom = self._s07_custom_for_descriptor(descriptor)
            cached = self._s07_thumbnail_cache.request(
                document,
                descriptor,
                draft,
                custom_template=custom,
            )
            if cached:
                self.template_workspace_s07.set_thumbnail(
                    descriptor.template_id,
                    cached,
                    "CACHE_HIT",
                )
        except Exception:
            self.template_workspace_s07.set_thumbnail(
                descriptor.template_id,
                "",
                "FALLBACK",
            )


def _thumbnail_ready(self, template_id: str, path: str, status: str) -> None:
    self.template_workspace_s07.set_thumbnail(template_id, path, status)


def _refresh_timeline(self) -> None:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    selected = {
        str(value)
        for value in getattr(self, "_s06_selected_ids", set())
        if str(value) in valid
    }
    primary = str(getattr(self, "_s06_primary_song_id", ""))
    if primary not in valid:
        primary = document.playlist.entries[0].song_id if document.playlist.entries else ""
    if primary:
        selected.add(primary)
    self.template_timeline_s07.set_state(
        document,
        selected,
        self.editor_workspace.session.playhead_tick,
    )


def _select_template(self, template_id: str) -> None:
    descriptor = self._s07_descriptor_map().get(str(template_id))
    if descriptor is None:
        return
    self._s07_selected_template_id = descriptor.template_id
    self.template_inspector_s07.set_template(
        descriptor,
        self._s07_draft_for_descriptor(descriptor),
    )
    self._s07_refresh()


def _current_descriptor(self) -> TemplateStudioDescriptor:
    descriptor = self._s07_descriptor_map().get(self._s07_selected_template_id)
    if descriptor is None:
        raise ValueError("Pilih template terlebih dahulu.")
    return descriptor


def _custom_for_descriptor(self, descriptor: TemplateStudioDescriptor) -> CustomTemplate | None:
    if descriptor.origin != ORIGIN_CUSTOM:
        return None
    return self._s07_store.load(descriptor.template_id)


def _current_song_id(self) -> str:
    document = self.editor_workspace.document()
    valid = set(document.song_map())
    current = str(getattr(self, "_s06_primary_song_id", ""))
    if current in valid:
        return current
    return document.playlist.entries[0].song_id if document.playlist.entries else ""


def _scope_targets(self, scope: str | None = None) -> tuple[str, ...]:
    document = self.editor_workspace.document()
    current = self._s07_current_song_id()
    selected = {
        str(value)
        for value in getattr(self, "_s06_selected_ids", set())
    }
    if current:
        selected.add(current)
    return stable_scope_song_ids(
        document,
        scope or self.template_inspector_s07.scope_key,
        current_song_id=current,
        selected_song_ids=selected,
    )


def _draft_changed(self) -> None:
    if not self._s07_selected_template_id:
        return
    try:
        draft = self._s07_inspector_draft()
        self._s07_drafts[draft.template_id] = draft
        self._s07_preview()
    except Exception as exc:
        self.template_workspace_s07.preview_state.setText(f"Draft belum valid: {exc}")


def _preview(self) -> None:
    try:
        descriptor = self._s07_current_descriptor()
        draft = self._s07_inspector_draft()
        self._s07_drafts[draft.template_id] = draft
        targets = self._s07_scope_targets()
        custom = self._s07_custom_for_descriptor(descriptor)
        preview = preview_template_document(
            self.editor_workspace.document(),
            draft,
            targets,
            custom_template=custom,
        )
        self.template_workspace_s07.set_preview_summary(
            descriptor,
            preview,
            len(targets),
        )
    except Exception as exc:
        self.template_workspace_s07.preview_state.setText(f"Preview gagal: {exc}")


def _preview_template(self, template_id: str) -> None:
    self._s07_select_template(template_id)
    self._s07_preview()


def _dispatch(self, commands, message: str) -> bool:
    try:
        self.editor_workspace.dispatch_external(commands, message=message)
        self.foundation_shell.refresh_commands()
        return True
    except Exception as exc:
        QMessageBox.warning(self, "Template", f"Template tidak dapat diterapkan:\n{exc}")
        return False


def _apply(self) -> None:
    try:
        descriptor = self._s07_current_descriptor()
        draft = self._s07_inspector_draft()
        targets = self._s07_scope_targets()
        custom = self._s07_custom_for_descriptor(descriptor)
        commands = build_template_apply_commands(
            self.editor_workspace.document(),
            draft,
            targets,
            custom_template=custom,
        )
    except Exception as exc:
        QMessageBox.warning(self, "Template", f"Apply dibatalkan sebelum mutation:\n{exc}")
        return
    if self._s07_dispatch(
        commands,
        f"Template '{descriptor.name}' diterapkan atomically ke {len(targets)} lagu.",
    ):
        self._s07_drafts[draft.template_id] = draft
        self._s07_refresh()


def _use_template(self, template_id: str) -> None:
    self._s07_select_template(template_id)
    self._s07_apply()


def _set_favorite(self, template_id: str, favorite: bool) -> None:
    try:
        self._s07_favorites_store.set_favorite(template_id, favorite)
    except Exception as exc:
        QMessageBox.warning(self, "Favorit Template", f"Preferensi favorit tidak dapat disimpan:\n{exc}")
        return
    self._s07_refresh()


def _create_custom(self) -> None:
    label, ok = QInputDialog.getText(self, "Buat Template", "Nama template:")
    if not ok or not str(label).strip():
        return
    try:
        item = create_portable_custom_from_document(
            self.editor_workspace.document(),
            label=str(label).strip(),
            description="Dibuat dari desain project aktif di Template Studio.",
            store=self._s07_store,
        )
    except Exception as exc:
        QMessageBox.warning(self, "Buat Template", f"Template belum dapat disimpan secara portabel:\n{exc}")
        return
    self.template_context_s07.origin._buttons[ORIGIN_CUSTOM].setChecked(True)
    self._s07_selected_template_id = item.template_id
    self._s07_refresh()


def _duplicate(self) -> None:
    try:
        descriptor = self._s07_current_descriptor()
        draft = self._s07_inspector_draft()
        targets = self._s07_scope_targets()
        source_custom = self._s07_custom_for_descriptor(descriptor)
        item = duplicate_portable_template(
            self.editor_workspace.document(),
            draft,
            targets,
            label=f"Salinan {descriptor.name}",
            description=f"Duplikat portabel dari {descriptor.name}.",
            store=self._s07_store,
            source_custom=source_custom,
        )
    except Exception as exc:
        QMessageBox.warning(self, "Duplikat Template", f"Duplikat gagal:\n{exc}")
        return
    self.template_context_s07.origin._buttons[ORIGIN_CUSTOM].setChecked(True)
    self._s07_selected_template_id = item.template_id
    self._s07_refresh()


def _save_custom(self) -> None:
    try:
        descriptor = self._s07_current_descriptor()
        if descriptor.origin != ORIGIN_CUSTOM:
            raise ValueError("Built-in immutable. Duplikat terlebih dahulu untuk mengedit sebagai Custom.")
        existing = self._s07_store.load(descriptor.template_id)
        draft = self._s07_inspector_draft()
        targets = self._s07_scope_targets()
        save_custom_draft(
            self.editor_workspace.document(),
            draft,
            targets,
            existing=existing,
            store=self._s07_store,
        )
    except Exception as exc:
        QMessageBox.warning(self, "Simpan Custom", f"Template Custom tidak dapat disimpan:\n{exc}")
        return
    self._s07_refresh()
    self.template_workspace_s07.preview_state.setText("Template Custom tersimpan secara atomic.")


def _reset(self) -> None:
    try:
        descriptor = self._s07_current_descriptor()
    except Exception:
        return
    draft = TemplateStudioDraft(
        template_id=descriptor.template_id,
        ratio=self.template_context_s07.ratio_key,
    )
    self._s07_drafts[descriptor.template_id] = draft
    self.template_inspector_s07.set_template(descriptor, draft)
    self.template_workspace_s07.clear_preview()


def install_step07_template() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s07_refresh()
        self._s07_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s07_route(route)

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s07_route = _route
    Window._s07_document_changed = _document_changed
    Window._s07_load_catalog = _load_catalog
    Window._s07_descriptor_map = _descriptor_map
    Window._s07_draft_for_descriptor = _draft_for_descriptor
    Window._s07_inspector_draft = _inspector_draft
    Window._s07_refresh = _refresh
    Window._s07_request_thumbnails = _request_thumbnails
    Window._s07_thumbnail_ready = _thumbnail_ready
    Window._s07_refresh_timeline = _refresh_timeline
    Window._s07_select_template = _select_template
    Window._s07_current_descriptor = _current_descriptor
    Window._s07_custom_for_descriptor = _custom_for_descriptor
    Window._s07_current_song_id = _current_song_id
    Window._s07_scope_targets = _scope_targets
    Window._s07_draft_changed = _draft_changed
    Window._s07_preview = _preview
    Window._s07_preview_template = _preview_template
    Window._s07_dispatch = _dispatch
    Window._s07_apply = _apply
    Window._s07_use_template = _use_template
    Window._s07_set_favorite = _set_favorite
    Window._s07_create_custom = _create_custom
    Window._s07_duplicate = _duplicate
    Window._s07_save_custom = _save_custom
    Window._s07_reset = _reset
    _installed = True
