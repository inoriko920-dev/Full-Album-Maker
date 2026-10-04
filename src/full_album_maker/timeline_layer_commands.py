from __future__ import annotations

from dataclasses import dataclass

from .editor_commands import CommandError, EditorCommand, ReplaceDocument
from .editor_models import ProjectDocument
from .timeline_resolver import TimelineResolver


@dataclass
class ApplyLayerClipProperties(EditorCommand):
    """Apply Timeline layer start/duration/lock as one undoable edit."""

    layer_id: str
    start_tick: int
    duration_tick: int
    locked: bool

    def apply(self, document: ProjectDocument) -> EditorCommand:
        layer = document.layer_map().get(self.layer_id)
        if layer is None:
            raise CommandError("Layer tidak ditemukan.")
        old = document.clone()
        resolved = TimelineResolver().resolve(document)
        item = next((entry for entry in resolved.layers if entry.layer_id == self.layer_id), None)
        if item is None or len(item.intervals) != 1:
            raise CommandError("Inspector Timeline membutuhkan layer dengan satu interval aktif.")
        interval = item.intervals[0]
        try:
            start = int(self.start_tick)
            duration = int(self.duration_tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Timing layer tidak valid.") from exc
        if start < 0 or duration <= 0:
            raise CommandError("Timing layer tidak valid.")

        if layer.locked and bool(self.locked):
            if start != interval.start_tick or duration != (interval.end_tick - interval.start_tick):
                raise CommandError("Layer terkunci. Matikan Lock lalu Terapkan untuk mengedit.")

        binding = layer.time_binding
        if binding.kind == "absolute":
            binding.start_tick = start
        elif binding.kind == "album":
            binding.start_offset_tick = start
        elif binding.kind == "song":
            anchor = next(
                (song for song in resolved.songs if song.song_id == (binding.song_id or "")),
                None,
            )
            if anchor is None:
                raise CommandError("Anchor lagu layer tidak ditemukan.")
            position = start - anchor.start_tick
            if position < 0:
                raise CommandError("Start layer tidak boleh mendahului anchor lagu.")
            binding.offset_tick = position
        else:
            raise CommandError("Inspector Timeline belum mendukung edit start untuk song_range.")
        binding.duration_tick = duration
        layer.locked = bool(self.locked)
        document.validate()
        after = TimelineResolver().resolve(document)
        errors = [error for error in after.errors if layer.name in error]
        if errors:
            raise CommandError(" | ".join(errors))
        return ReplaceDocument(old)
