from __future__ import annotations

from copy import deepcopy
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from .editor_commands import AddLayer, DuplicateLayer
from .editor_interaction_commands import SetLayerEnabled, SetLayerLocked
from .spectrum_feature import make_spectrum_layer, normalize_spectrum_properties
from .spectrum_preview_step08 import SpectrumAccuratePreview
from .spectrum_step08 import (
    SetSpectrumLayerState,
    build_apply_to_all_commands,
    build_preset_command,
    build_type_command,
    centered_transform,
    default_transform,
    preset_properties,
    spectrum_geometry,
)
from .spectrum_workspace_step08 import (
    SpectrumInspector,
    SpectrumLayerContext,
    SpectrumTimelineCanvas,
    SpectrumWorkspace,
    inspector_state,
)


_installed = False
_original_init: Any = None


def _install_widgets(self) -> None:
    self._s08_selected_layer_id = ""
    self._s08_preview_token = 0
    self._s08_preview_worker = SpectrumAccuratePreview(parent=self)

    self.spectrum_workspace_s08 = SpectrumWorkspace()
    index = self.foundation_shell.workspace_stack._index["spectrum"]
    old = self.foundation_shell.workspace_stack.widget(index)
    self.foundation_shell.workspace_stack.removeWidget(old)
    old.setParent(None)
    self.foundation_shell.workspace_stack.insertWidget(index, self.spectrum_workspace_s08)

    self.spectrum_context_s08 = SpectrumLayerContext()
    self.spectrum_context_s08.hide()
    self.foundation_shell.context.layout().addWidget(self.spectrum_context_s08, 1)

    self.spectrum_inspector_s08 = SpectrumInspector()
    self._inspector_router.addWidget(self.spectrum_inspector_s08)

    self.spectrum_timeline_s08 = SpectrumTimelineCanvas()
    timeline_layout = self.foundation_shell.timeline.canvas.parentWidget().layout()
    timeline_layout.addWidget(self.spectrum_timeline_s08, 1)
    self.spectrum_timeline_s08.hide()


def _connect_widgets(self) -> None:
    self.spectrum_context_s08.layer_selected.connect(self._s08_select_layer)
    self.spectrum_context_s08.visibility_changed.connect(self._s08_set_visible)
    self.spectrum_context_s08.lock_changed.connect(self._s08_set_locked)
    self.spectrum_context_s08.add_spectrum_requested.connect(self._s08_add_spectrum)
    self.spectrum_context_s08.preset_requested.connect(self._s08_apply_preset)

    self.spectrum_workspace_s08.layer_selected.connect(self._s08_select_layer)
    self.spectrum_workspace_s08.transform_committed.connect(self._s08_transform_committed)

    self.spectrum_inspector_s08.type_changed.connect(self._s08_set_type)
    self.spectrum_inspector_s08.geometry_changed.connect(self._s08_set_geometry)
    self.spectrum_inspector_s08.property_changed.connect(self._s08_set_property)
    self.spectrum_inspector_s08.opacity_changed.connect(self._s08_set_opacity)
    self.spectrum_inspector_s08.center_requested.connect(self._s08_center)
    self.spectrum_inspector_s08.reset_requested.connect(self._s08_reset_transform)
    self.spectrum_inspector_s08.duplicate_requested.connect(self._s08_duplicate)
    self.spectrum_inspector_s08.apply_all_requested.connect(self._s08_apply_all)

    self.spectrum_timeline_s08.playhead_requested.connect(self._s08_seek)
    self._s08_preview_worker.preview_ready.connect(self._s08_preview_ready)
    self.foundation_state.workspace_changed.connect(self._s08_route)
    self.editor_workspace.documentChanged.connect(self._s08_document_changed)
    self.destroyed.connect(lambda *_args: self._s08_preview_worker.close())


def _hide_prior_surfaces(self) -> None:
    for name in (
        "media_context",
        "album_context",
        "timeline_context_s05",
        "visual_context_s06",
        "template_context_s07",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    for name in (
        "media_timeline_canvas",
        "album_timeline_canvas",
        "timeline_precision_s05",
        "visual_timeline_s06",
        "template_timeline_s07",
        "_s03_timeline_old",
    ):
        widget = getattr(self, name, None)
        if widget is not None:
            widget.setVisible(False)
    self.foundation_shell.timeline.canvas.setVisible(False)


def _route(self, route: str) -> None:
    active = route == "spectrum"
    self.spectrum_context_s08.setVisible(active)
    self.spectrum_timeline_s08.setVisible(active)
    if not active:
        self._s08_preview_worker.invalidate()
        if self._inspector_router.currentWidget() is self.spectrum_inspector_s08:
            self._inspector_router.setCurrentIndex(1)
        return
    self._s08_hide_prior_surfaces()
    self._inspector_router.setCurrentWidget(self.spectrum_inspector_s08)
    self.foundation_shell.timeline.set_collapsed(False)
    self._s08_refresh(request_preview=True)


def _current_document(self):
    return self.editor_workspace.document()


def _selected_layer(self):
    return self._s08_current_document().layer_map().get(self._s08_selected_layer_id)


def _choose_selection(self, document) -> None:
    if self._s08_selected_layer_id in document.layer_map():
        return
    spectrum = next((layer for layer in sorted(document.layers, key=lambda item: item.order) if layer.type == "spectrum"), None)
    if spectrum is not None:
        self._s08_selected_layer_id = spectrum.layer_id
    elif document.layers:
        self._s08_selected_layer_id = sorted(document.layers, key=lambda item: item.order)[-1].layer_id
    else:
        self._s08_selected_layer_id = ""


def _refresh(self, *, request_preview: bool = False) -> None:
    if not hasattr(self, "spectrum_workspace_s08"):
        return
    document = self._s08_current_document()
    self._s08_choose_selection(document)
    layer = document.layer_map().get(self._s08_selected_layer_id)
    self.spectrum_context_s08.set_state(document, self._s08_selected_layer_id)
    self.spectrum_workspace_s08.set_document(
        document,
        self._s08_selected_layer_id,
        self.editor_workspace.session.playhead_tick,
    )
    self.spectrum_inspector_s08.set_state(inspector_state(document, layer))
    self.spectrum_timeline_s08.set_state(document, self.editor_workspace.session.playhead_tick)
    self.foundation_shell.refresh_commands()
    if request_preview and self.foundation_state.workspace == "spectrum":
        self._s08_request_preview()


def _document_changed(self, _document) -> None:
    if hasattr(self, "spectrum_workspace_s08") and self.foundation_state.workspace == "spectrum":
        self._s08_refresh(request_preview=True)


def _dispatch(self, commands, message: str) -> bool:
    try:
        self.editor_workspace.dispatch_external(commands, message=message)
        self.foundation_shell.refresh_commands()
        return True
    except Exception as exc:
        QMessageBox.warning(self, "Spectrum", f"Perubahan dibatalkan:\n{exc}")
        return False


def _select_layer(self, layer_id) -> None:
    value = str(layer_id or "")
    document = self._s08_current_document()
    if value not in document.layer_map():
        return
    self._s08_selected_layer_id = value
    self.editor_workspace.session.select_one(value)
    self._s08_refresh(request_preview=False)


def _set_visible(self, layer_id: str, visible: bool) -> None:
    if self._s08_dispatch(SetLayerEnabled(layer_id, bool(visible)), "Visibilitas layer diperbarui."):
        self._s08_selected_layer_id = layer_id


def _set_locked(self, layer_id: str, locked: bool) -> None:
    if self._s08_dispatch(SetLayerLocked(layer_id, bool(locked)), "Status lock layer diperbarui."):
        self._s08_selected_layer_id = layer_id


def _add_spectrum(self) -> None:
    document = self._s08_current_document()
    track = next((item for item in document.tracks if item.kind == "visual" and item.enabled), None)
    if track is None:
        track = next((item for item in document.tracks if item.kind == "visual"), None)
    if track is None:
        QMessageBox.warning(self, "Spectrum", "Track visual tidak tersedia.")
        return
    order = max((layer.order for layer in document.layers), default=-1) + 1
    layer = make_spectrum_layer(track.track_id, order, preset_id="minimal_bars")
    layer.properties = preset_properties("classic", layer.properties)
    layer.transform = default_transform(document, "linear")
    if self._s08_dispatch(AddLayer(layer), "Spectrum baru ditambahkan dengan parameter Classic."):
        self._s08_selected_layer_id = layer.layer_id
        self.editor_workspace.session.select_one(layer.layer_id)


def _require_spectrum(self):
    document = self._s08_current_document()
    layer = document.layer_map().get(self._s08_selected_layer_id)
    if layer is None or layer.type != "spectrum":
        raise ValueError("Pilih layer Spectrum terlebih dahulu.")
    return document, layer


def _apply_preset(self, preset_id: str) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        command = build_preset_command(document, layer.layer_id, preset_id)
    except Exception as exc:
        QMessageBox.information(self, "Preset Spectrum", str(exc))
        return
    self._s08_dispatch(command, f"Preset Spectrum '{preset_id}' diterapkan sebagai satu Undo transaction.")


def _set_type(self, spectrum_type: str) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        command = build_type_command(document, layer.layer_id, spectrum_type)
    except Exception as exc:
        QMessageBox.warning(self, "Spectrum", str(exc))
        return
    self._s08_dispatch(command, f"Tipe Spectrum diubah ke {spectrum_type}.")


def _set_geometry(self, center_x_px: float, center_y_px: float, size_ratio: float) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        props = normalize_spectrum_properties(layer.properties)
        from .spectrum_step08 import transform_from_geometry

        transform = transform_from_geometry(
            document,
            props["spectrum_type"],
            center_x_px=center_x_px,
            center_y_px=center_y_px,
            size_ratio=size_ratio,
            rotation=layer.transform.rotation,
        )
        command = SetSpectrumLayerState(layer.layer_id, {}, transform=transform)
    except Exception as exc:
        QMessageBox.warning(self, "Transform Spectrum", str(exc))
        self._s08_refresh(request_preview=False)
        return
    self._s08_dispatch(command, "Posisi/ukuran Spectrum diperbarui di project coordinates.")


def _set_property(self, key: str, value) -> None:
    try:
        _document, layer = self._s08_require_spectrum()
        payload = {str(key): value, "preset": ""}
        # Keep recovered aliases explicit for two public STEP08 fields.
        if key == "accent_color":
            payload["color"] = value
        elif key == "reactive_scale":
            payload["gain"] = value
        command = SetSpectrumLayerState(layer.layer_id, payload)
    except Exception as exc:
        QMessageBox.warning(self, "Properti Spectrum", str(exc))
        return
    self._s08_dispatch(command, f"Properti Spectrum '{key}' diperbarui.")


def _set_opacity(self, opacity: float) -> None:
    try:
        _document, layer = self._s08_require_spectrum()
        command = SetSpectrumLayerState(layer.layer_id, {}, opacity=float(opacity))
    except Exception as exc:
        QMessageBox.warning(self, "Opacity Spectrum", str(exc))
        return
    self._s08_dispatch(command, "Opacity Spectrum diperbarui.")


def _transform_committed(self, layer_id: str, transform) -> None:
    document = self._s08_current_document()
    layer = document.layer_map().get(str(layer_id))
    if layer is None or layer.type != "spectrum":
        return
    self._s08_selected_layer_id = layer.layer_id
    self._s08_dispatch(
        SetSpectrumLayerState(layer.layer_id, {}, transform=deepcopy(transform)),
        "Transform Spectrum diperbarui dari preview.",
    )


def _center(self) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        props = normalize_spectrum_properties(layer.properties)
        geometry = spectrum_geometry(document, layer)
        transform = centered_transform(
            document,
            props["spectrum_type"],
            size_ratio=geometry.size_ratio,
            rotation=layer.transform.rotation,
        )
        command = SetSpectrumLayerState(layer.layer_id, {}, transform=transform)
    except Exception as exc:
        QMessageBox.warning(self, "Center Spectrum", str(exc))
        return
    self._s08_dispatch(command, "Spectrum dipusatkan ke project frame center.")


def _reset_transform(self) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        props = normalize_spectrum_properties(layer.properties)
        command = SetSpectrumLayerState(
            layer.layer_id,
            {},
            transform=default_transform(document, props["spectrum_type"]),
        )
    except Exception as exc:
        QMessageBox.warning(self, "Reset Spectrum", str(exc))
        return
    self._s08_dispatch(command, "Transform Spectrum direset; style dipertahankan.")


def _duplicate(self) -> None:
    try:
        _document, layer = self._s08_require_spectrum()
        command = DuplicateLayer(layer.layer_id)
    except Exception as exc:
        QMessageBox.warning(self, "Duplicate Spectrum", str(exc))
        return
    if self._s08_dispatch(command, "Spectrum diduplikasi sebagai layer independen."):
        if command.new_layer_id:
            self._s08_selected_layer_id = command.new_layer_id
            self.editor_workspace.session.select_one(command.new_layer_id)
            self._s08_refresh(request_preview=True)


def _apply_all(self) -> None:
    try:
        document, layer = self._s08_require_spectrum()
        commands = build_apply_to_all_commands(document, layer.layer_id, include_position=True)
    except Exception as exc:
        QMessageBox.warning(self, "Apply to All", f"Prevalidation gagal. Tidak ada target yang diubah.\n\n{exc}")
        return
    if not commands:
        QMessageBox.information(self, "Apply to All", "Tidak ada Spectrum lain yang eligible di project ini.")
        return
    answer = QMessageBox.question(
        self,
        "Apply to All",
        f"Salin style + transform ke {len(commands)} Spectrum lain?\nAudio binding tiap target tetap dipertahankan.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    self._s08_dispatch(list(commands), f"Apply to All selesai atomically ke {len(commands)} Spectrum.")


def _seek(self, tick: int) -> None:
    self.editor_workspace.set_playhead(int(tick))
    document = self._s08_current_document()
    self.spectrum_workspace_s08.set_document(
        document,
        self._s08_selected_layer_id,
        self.editor_workspace.session.playhead_tick,
    )
    self.spectrum_timeline_s08.set_state(document, self.editor_workspace.session.playhead_tick)
    self._s08_request_preview()


def _request_preview(self) -> None:
    if self.foundation_state.workspace != "spectrum":
        return
    document = self._s08_current_document()
    active_spectrum = [layer for layer in document.layers if layer.type == "spectrum" and layer.enabled]
    if not active_spectrum:
        self._s08_preview_worker.invalidate()
        self.spectrum_workspace_s08.set_preview_result("", "Tambahkan/aktifkan Spectrum untuk preview audio-reactive.")
        return
    if not any(song.enabled for song in document.playlist.entries):
        self._s08_preview_worker.invalidate()
        self.spectrum_workspace_s08.set_preview_result("", "Playlist belum memiliki audio aktif. Resting geometry digunakan.")
        return
    self.spectrum_workspace_s08.set_preview_pending()
    self._s08_preview_token = self._s08_preview_worker.request(
        document,
        self.editor_workspace.session.playhead_tick,
    )


def _preview_ready(self, token: int, path: str, status: str) -> None:
    if self.foundation_state.workspace != "spectrum" or int(token) != int(self._s08_preview_token):
        return
    self.spectrum_workspace_s08.set_preview_result(path, status)


def install_step08_spectrum() -> None:
    global _installed, _original_init
    if _installed:
        return
    from .foundation_window import FoundationMainWindow as Window

    _original_init = Window.__init__

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        _install_widgets(self)
        _connect_widgets(self)
        self._s08_refresh(request_preview=False)
        self._s08_route(self.foundation_state.workspace)

        def reactivate_current_route() -> None:
            route = self.foundation_state.workspace
            self.foundation_shell._apply_workspace(route)
            self._s08_route(route)

        QTimer.singleShot(0, reactivate_current_route)

    Window.__init__ = wrapped_init
    Window._s08_hide_prior_surfaces = _hide_prior_surfaces
    Window._s08_route = _route
    Window._s08_current_document = _current_document
    Window._s08_selected_layer = _selected_layer
    Window._s08_choose_selection = _choose_selection
    Window._s08_refresh = _refresh
    Window._s08_document_changed = _document_changed
    Window._s08_dispatch = _dispatch
    Window._s08_select_layer = _select_layer
    Window._s08_set_visible = _set_visible
    Window._s08_set_locked = _set_locked
    Window._s08_add_spectrum = _add_spectrum
    Window._s08_require_spectrum = _require_spectrum
    Window._s08_apply_preset = _apply_preset
    Window._s08_set_type = _set_type
    Window._s08_set_geometry = _set_geometry
    Window._s08_set_property = _set_property
    Window._s08_set_opacity = _set_opacity
    Window._s08_transform_committed = _transform_committed
    Window._s08_center = _center
    Window._s08_reset_transform = _reset_transform
    Window._s08_duplicate = _duplicate
    Window._s08_apply_all = _apply_all
    Window._s08_seek = _seek
    Window._s08_request_preview = _request_preview
    Window._s08_preview_ready = _preview_ready
    _installed = True
