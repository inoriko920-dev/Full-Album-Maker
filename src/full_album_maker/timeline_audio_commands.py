from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .editor_commands import CommandError, EditorCommand, ReplaceDocument
from .editor_models import ProjectDocument, new_id
from .timeline_precision import song_mix
from .timeline_resolver import TimelineResolver


@dataclass
class SetSongDuration(EditorCommand):
    song_id: str
    duration_tick: int

    def apply(self, document: ProjectDocument) -> EditorCommand:
        song = document.song_map().get(self.song_id)
        if song is None:
            raise CommandError("Lagu tidak ditemukan.")
        if song_mix(document, self.song_id)["locked"]:
            raise CommandError("Clip lagu terkunci.")
        try:
            duration = int(self.duration_tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Durasi lagu tidak valid.") from exc
        if duration <= 0:
            raise CommandError("Durasi lagu harus lebih dari 0.")
        asset = document.asset_map().get(song.asset_id)
        if asset is None:
            raise CommandError("Asset lagu tidak ditemukan.")
        old_out = song.source_out_tick if song.source_out_tick is not None else asset.source_duration_tick
        old_duration = old_out - song.source_in_tick
        requested_out = song.source_in_tick + duration
        if asset.source_duration_tick > 0 and requested_out > asset.source_duration_tick:
            raise CommandError("Durasi lagu melewati source audio.")
        song.source_out_tick = requested_out
        resolved = TimelineResolver().resolve(document)
        audio_errors = [item for item in resolved.errors if item.startswith("Audio: ")]
        if audio_errors:
            song.source_out_tick = old_out
            raise CommandError(" | ".join(audio_errors))
        return SetSongDuration(self.song_id, old_duration)


@dataclass
class SplitSongAtTick(EditorCommand):
    song_id: str
    tick: int
    new_song_id: str | None = None

    def apply(self, document: ProjectDocument) -> EditorCommand:
        song = document.song_map().get(self.song_id)
        if song is None or not song.enabled:
            raise CommandError("Lagu aktif tidak ditemukan.")
        if song_mix(document, self.song_id)["locked"]:
            raise CommandError("Clip lagu terkunci.")
        resolved = TimelineResolver().resolve(document)
        audio_errors = [item for item in resolved.errors if item.startswith("Audio: ")]
        if audio_errors:
            raise CommandError(" | ".join(audio_errors))
        event = next((item for item in resolved.songs if item.song_id == self.song_id), None)
        if event is None:
            raise CommandError("Clip audio tidak ditemukan pada timeline.")
        try:
            tick = int(self.tick)
        except (TypeError, ValueError) as exc:
            raise CommandError("Playhead Split tidak valid.") from exc
        if not event.start_tick < tick < event.end_tick:
            raise CommandError("Playhead harus berada di dalam clip audio untuk Split.")

        old = document.clone()
        asset = document.asset_map()[song.asset_id]
        original_out = song.source_out_tick if song.source_out_tick is not None else asset.source_duration_tick
        elapsed = tick - event.start_tick
        split_source_tick = song.source_in_tick + elapsed
        if not song.source_in_tick < split_source_tick < original_out:
            raise CommandError("Titik Split source audio tidak valid.")

        second = deepcopy(song)
        second.song_id = self.new_song_id or new_id()
        self.new_song_id = second.song_id
        second.source_in_tick = split_source_tick
        second.source_out_tick = original_out
        second.crossfade_in_tick = 0
        second.display_title = (song.display_title.strip() or "Lagu") + " B"

        song.source_out_tick = split_source_tick
        if document.playlist.mode == "free":
            if song.free_start_tick is None:
                raise CommandError("Free Timeline membutuhkan start lagu yang valid.")
            second.free_start_tick = tick
        else:
            second.free_start_tick = None

        index = document.playlist.entries.index(song)
        document.playlist.entries.insert(index + 1, second)

        # Copy persisted mix values, but do not inherit lock so the new clip can be edited.
        raw_mix = document.extensions.get("timeline_song_mix_v1", {})
        if isinstance(raw_mix, dict) and self.song_id in raw_mix:
            copied = deepcopy(raw_mix)
            values = deepcopy(copied.get(self.song_id, {}))
            if isinstance(values, dict):
                values["locked"] = False
                copied[second.song_id] = values
                document.extensions["timeline_song_mix_v1"] = copied

        document.validate()
        resolved_after = TimelineResolver().resolve(document)
        errors_after = [item for item in resolved_after.errors if item.startswith("Audio: ")]
        if errors_after:
            raise CommandError(" | ".join(errors_after))
        return ReplaceDocument(old)
