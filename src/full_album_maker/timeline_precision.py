from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .editor_commands import CommandError, EditorCommand, ReplaceDocument
from .editor_models import ProjectDocument, new_id
from .timeline_resolver import TimelineResolver

MARKERS_KEY = "timeline_markers_v1"
SONG_MIX_KEY = "timeline_song_mix_v1"
DEFAULT_MARKER_COLOR = "#1766E8"


@dataclass(frozen=True)
class TimelineMarker:
    marker_id: str
    tick: int
    label: str
    color: str = DEFAULT_MARKER_COLOR

    def to_dict(self) -> dict[str, Any]:
        return {
            "marker_id": self.marker_id,
            "tick": int(self.tick),
            "label": self.label,
            "color": self.color,
        }


@dataclass(frozen=True)
class TimelineGap:
    start_tick: int
    end_tick: int
    previous_song_id: str
    next_song_id: str

    @property
    def duration_tick(self) -> int:
        return self.end_tick - self.start_tick


def _valid_color(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) != 7 or not text.startswith("#"):
        raise CommandError("Warna marker harus format #RRGGBB.")
    try:
        int(text[1:], 16)
    except ValueError as exc:
        raise CommandError("Warna marker harus format #RRGGBB.") from exc
    return text.upper()


def timeline_markers(document: ProjectDocument) -> tuple[TimelineMarker, ...]:
    raw = document.extensions.get(MARKERS_KEY, [])
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CommandError("Data marker timeline tidak valid.")
    seen: set[str] = set()
    result: list[TimelineMarker] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CommandError("Data marker timeline tidak valid.")
        marker_id = str(item.get("marker_id") or "").strip()
        label = str(item.get("label") or "").strip()
        try:
            tick = int(item.get("tick", -1))
        except (TypeError, ValueError) as exc:
            raise CommandError("Posisi marker tidak valid.") from exc
        if not marker_id or marker_id in seen or tick < 0 or not label:
            raise CommandError("Data marker timeline tidak valid.")
        seen.add(marker_id)
        result.append(
            TimelineMarker(marker_id, tick, label, _valid_color(item.get("color", DEFAULT_MARKER_COLOR)))
        )
    result.sort(key=lambda marker: (marker.tick, marker.label.casefold(), marker.marker_id))
    return tuple(result)


def _write_markers(document: ProjectDocument, markers: list[TimelineMarker] | tuple[TimelineMarker, ...]) -> None:
    document.extensions[MARKERS_KEY] = [marker.to_dict() for marker in markers]


@dataclass
class SetTimelineMarkers(EditorCommand):
    markers: tuple[TimelineMarker, ...]

    def apply(self, document: ProjectDocument) -> EditorCommand:
        old = timeline_markers(document)
        normalized: list[TimelineMarker] = []
        seen: set[str] = set()
        for marker in self.markers:
            if marker.marker_id in seen or not marker.marker_id.strip() or int(marker.tick) < 0 or not marker.label.strip():
                raise CommandError("Marker timeline tidak valid.")
            seen.add(marker.marker_id)
            normalized.append(
                TimelineMarker(
                    marker.marker_id,
                    int(marker.tick),
                    marker.label.strip(),
                    _valid_color(marker.color),
                )
            )
        normalized.sort(key=lambda marker: (marker.tick, marker.label.casefold(), marker.marker_id))
        _write_markers(document, normalized)
        return SetTimelineMarkers(old)


@dataclass
class AddTimelineMarker(EditorCommand):
    tick: int
    label: str = "Marker"
    color: str = DEFAULT_MARKER_COLOR
    marker_id: str | None = None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        try:
            tick = int(self.tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Posisi marker tidak valid.") from exc
        label = str(self.label or "").strip()
        if tick < 0 or not label:
            raise CommandError("Marker membutuhkan posisi dan nama yang valid.")
        marker_id = self.marker_id or new_id()
        self.marker_id = marker_id
        current = list(timeline_markers(document))
        if any(item.marker_id == marker_id for item in current):
            raise CommandError("marker_id sudah ada.")
        old = tuple(current)
        current.append(TimelineMarker(marker_id, tick, label, _valid_color(self.color)))
        _write_markers(document, sorted(current, key=lambda marker: (marker.tick, marker.label.casefold(), marker.marker_id)))
        return SetTimelineMarkers(old)


@dataclass
class UpdateTimelineMarker(EditorCommand):
    marker_id: str
    tick: int
    label: str
    color: str = DEFAULT_MARKER_COLOR

    def apply(self, document: ProjectDocument) -> EditorCommand:
        current = list(timeline_markers(document))
        old = tuple(current)
        found = False
        replacement: list[TimelineMarker] = []
        for marker in current:
            if marker.marker_id != self.marker_id:
                replacement.append(marker)
                continue
            found = True
            try:
                tick = int(self.tick)
            except (TypeError, ValueError) as exc:
                raise CommandError("Posisi marker tidak valid.") from exc
            label = str(self.label or "").strip()
            if tick < 0 or not label:
                raise CommandError("Marker membutuhkan posisi dan nama yang valid.")
            replacement.append(TimelineMarker(marker.marker_id, tick, label, _valid_color(self.color)))
        if not found:
            raise CommandError("Marker tidak ditemukan.")
        _write_markers(document, sorted(replacement, key=lambda marker: (marker.tick, marker.label.casefold(), marker.marker_id)))
        return SetTimelineMarkers(old)


@dataclass
class DeleteTimelineMarker(EditorCommand):
    marker_id: str

    def apply(self, document: ProjectDocument) -> EditorCommand:
        current = list(timeline_markers(document))
        if not any(marker.marker_id == self.marker_id for marker in current):
            raise CommandError("Marker tidak ditemukan.")
        old = tuple(current)
        _write_markers(document, [marker for marker in current if marker.marker_id != self.marker_id])
        return SetTimelineMarkers(old)


def song_mix(document: ProjectDocument, song_id: str) -> dict[str, Any]:
    raw = document.extensions.get(SONG_MIX_KEY, {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise CommandError("Data mix lagu timeline tidak valid.")
    item = raw.get(song_id, {})
    if not isinstance(item, dict):
        raise CommandError("Data mix lagu timeline tidak valid.")
    try:
        fade_in = max(0, int(item.get("fade_in_tick", 0)))
        fade_out = max(0, int(item.get("fade_out_tick", 0)))
    except (TypeError, ValueError) as exc:
        raise CommandError("Fade lagu tidak valid.") from exc
    return {
        "fade_in_tick": fade_in,
        "fade_out_tick": fade_out,
        "locked": bool(item.get("locked", False)),
    }


@dataclass
class SetSongMix(EditorCommand):
    song_id: str
    gain: float
    fade_in_tick: int = 0
    fade_out_tick: int = 0
    locked: bool = False

    def apply(self, document: ProjectDocument) -> EditorCommand:
        song = document.song_map().get(self.song_id)
        if song is None:
            raise CommandError("Lagu tidak ditemukan.")
        old_mix = song_mix(document, self.song_id)
        old_gain = float(song.gain)
        try:
            gain = float(self.gain)
            fade_in = int(self.fade_in_tick)
            fade_out = int(self.fade_out_tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Properti audio lagu tidak valid.") from exc
        if gain < 0 or gain > 4 or fade_in < 0 or fade_out < 0:
            raise CommandError("Properti audio lagu di luar rentang.")
        assets = document.asset_map()
        asset = assets.get(song.asset_id)
        source_out = song.source_out_tick if song.source_out_tick is not None else (asset.source_duration_tick if asset else 0)
        duration = max(0, source_out - song.source_in_tick)
        if duration and (fade_in >= duration or fade_out >= duration):
            raise CommandError("Fade harus lebih pendek dari durasi lagu.")
        song.gain = gain
        raw = deepcopy(document.extensions.get(SONG_MIX_KEY, {}))
        if not isinstance(raw, dict):
            raw = {}
        raw[self.song_id] = {
            "fade_in_tick": fade_in,
            "fade_out_tick": fade_out,
            "locked": bool(self.locked),
        }
        document.extensions[SONG_MIX_KEY] = raw
        return SetSongMix(
            self.song_id,
            old_gain,
            old_mix["fade_in_tick"],
            old_mix["fade_out_tick"],
            old_mix["locked"],
        )


def timeline_gaps(document: ProjectDocument) -> tuple[TimelineGap, ...]:
    resolved = TimelineResolver().resolve(document)
    if resolved.errors:
        audio_errors = [item for item in resolved.errors if item.startswith("Audio: ")]
        if audio_errors:
            raise CommandError(" | ".join(audio_errors))
    songs = sorted(resolved.songs, key=lambda item: (item.start_tick, item.end_tick, item.song_id))
    result: list[TimelineGap] = []
    for previous, current in zip(songs, songs[1:]):
        if current.start_tick > previous.end_tick:
            result.append(
                TimelineGap(previous.end_tick, current.start_tick, previous.song_id, current.song_id)
            )
    return tuple(result)


@dataclass
class DeleteGapAtTick(EditorCommand):
    tick: int

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if document.playlist.mode != "free":
            raise CommandError("Delete Gap hanya tersedia pada Free Timeline.")
        try:
            tick = int(self.tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Posisi gap tidak valid.") from exc
        gap = next((item for item in timeline_gaps(document) if item.start_tick <= tick <= item.end_tick), None)
        if gap is None:
            raise CommandError("Tidak ada gap pada playhead.")
        old = document.clone()
        shift = gap.duration_tick
        for song in document.playlist.entries:
            if song.free_start_tick is not None and song.free_start_tick >= gap.end_tick:
                song.free_start_tick -= shift
        resolved = TimelineResolver().resolve(document)
        audio_errors = [item for item in resolved.errors if item.startswith("Audio: ")]
        if audio_errors:
            raise CommandError(" | ".join(audio_errors))
        return ReplaceDocument(old)


@dataclass
class RippleMoveSong(EditorCommand):
    song_id: str
    target_tick: int

    def apply(self, document: ProjectDocument) -> EditorCommand:
        if document.playlist.mode != "free":
            raise CommandError("Ripple move hanya tersedia pada Free Timeline.")
        song = document.song_map().get(self.song_id)
        if song is None or song.free_start_tick is None:
            raise CommandError("Lagu tidak memiliki timing Free yang valid.")
        if song_mix(document, self.song_id)["locked"]:
            raise CommandError("Clip lagu terkunci.")
        try:
            target = int(self.target_tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Target ripple tidak valid.") from exc
        if target < 0:
            raise CommandError("Target ripple tidak boleh negatif.")
        old = document.clone()
        current = int(song.free_start_tick)
        delta = target - current
        for item in document.playlist.entries:
            if item.free_start_tick is None:
                continue
            if item.song_id == self.song_id or item.free_start_tick >= current:
                shifted = int(item.free_start_tick) + delta
                if shifted < 0:
                    raise CommandError("Ripple akan memindahkan clip sebelum 00:00.")
                item.free_start_tick = shifted
        resolved = TimelineResolver().resolve(document)
        audio_errors = [item for item in resolved.errors if item.startswith("Audio: ")]
        if audio_errors:
            raise CommandError(" | ".join(audio_errors))
        return ReplaceDocument(old)


@dataclass
class SplitLayerAtTick(EditorCommand):
    layer_id: str
    tick: int
    new_layer_id: str | None = None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        layer = document.layer_map().get(self.layer_id)
        if layer is None:
            raise CommandError("Layer tidak ditemukan.")
        if layer.locked:
            raise CommandError("Layer terkunci tidak dapat di-split.")
        if layer.time_binding.kind == "song_range":
            raise CommandError("Split song-range ambigu; ubah menjadi clip tunggal terlebih dahulu.")
        resolved = TimelineResolver().resolve(document)
        item = next((entry for entry in resolved.layers if entry.layer_id == self.layer_id), None)
        if item is None or len(item.intervals) != 1:
            raise CommandError("Layer harus memiliki satu interval aktif untuk Split.")
        interval = item.intervals[0]
        try:
            tick = int(self.tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Playhead Split tidak valid.") from exc
        if not interval.start_tick < tick < interval.end_tick:
            raise CommandError("Playhead harus berada di dalam clip untuk Split.")
        old = document.clone()
        first_duration = tick - interval.start_tick
        second_duration = interval.end_tick - tick
        layer.time_binding.duration_tick = first_duration
        second = deepcopy(layer)
        second.layer_id = self.new_layer_id or new_id()
        self.new_layer_id = second.layer_id
        second.name = f"{layer.name} B"
        second.time_binding.duration_tick = second_duration
        binding = second.time_binding
        if binding.kind == "absolute":
            binding.start_tick = tick
        elif binding.kind == "album":
            binding.start_offset_tick += first_duration
        elif binding.kind == "song":
            binding.offset_tick += first_duration
        else:
            raise CommandError("Binding layer belum mendukung Split.")
        insert_at = document.layers.index(layer) + 1
        document.layers.insert(insert_at, second)
        document.validate()
        return ReplaceDocument(old)
