from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .editor_commands import CommandError, EditorCommand, ReplaceDocument
from .editor_models import ProjectDocument, new_id
from .timeline_precision import SONG_MIX_KEY, song_mix
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
class ApplySongClipProperties(EditorCommand):
    """Apply the entire Timeline song inspector as one Undo transaction."""

    song_id: str
    start_tick: int
    duration_tick: int
    fade_in_tick: int
    fade_out_tick: int
    crossfade_in_tick: int
    gain: float
    locked: bool

    def apply(self, document: ProjectDocument) -> EditorCommand:
        song = document.song_map().get(self.song_id)
        if song is None:
            raise CommandError("Lagu tidak ditemukan.")
        old = document.clone()
        previous_mix = song_mix(document, self.song_id)
        # A locked clip may be unlocked by the same explicit inspector Apply, but
        # its timing/content may not be changed while remaining locked.
        changing_locked_clip = previous_mix["locked"] and bool(self.locked)

        try:
            start = int(self.start_tick)
            duration = int(self.duration_tick)
            fade_in = int(self.fade_in_tick)
            fade_out = int(self.fade_out_tick)
            crossfade = int(self.crossfade_in_tick)
            gain = float(self.gain)
        except (TypeError, ValueError) as exc:
            raise CommandError("Properti clip lagu tidak valid.") from exc
        if min(start, fade_in, fade_out, crossfade) < 0 or duration <= 0:
            raise CommandError("Timing clip lagu tidak valid.")
        if not 0.0 <= gain <= 4.0:
            raise CommandError("Volume clip lagu di luar rentang.")

        asset = document.asset_map().get(song.asset_id)
        if asset is None:
            raise CommandError("Asset lagu tidak ditemukan.")
        source_out = song.source_in_tick + duration
        if asset.source_duration_tick > 0 and source_out > asset.source_duration_tick:
            raise CommandError("Durasi lagu melewati source audio.")
        if fade_in >= duration or fade_out >= duration:
            raise CommandError("Fade harus lebih pendek dari durasi lagu.")
        if crossfade >= duration:
            raise CommandError("Crossfade harus lebih pendek dari durasi lagu.")

        resolved_before = TimelineResolver().resolve(document)
        event = next((item for item in resolved_before.songs if item.song_id == self.song_id), None)
        if event is None:
            raise CommandError("Clip lagu tidak ditemukan pada timeline.")
        if changing_locked_clip:
            timing_changed = (
                start != event.start_tick
                or duration != (event.end_tick - event.start_tick)
                or fade_in != previous_mix["fade_in_tick"]
                or fade_out != previous_mix["fade_out_tick"]
                or crossfade != song.crossfade_in_tick
                or abs(gain - float(song.gain)) > 1e-9
            )
            if timing_changed:
                raise CommandError("Clip terkunci. Matikan Lock lalu Terapkan untuk mengedit.")

        song.source_out_tick = source_out
        song.gain = gain
        if document.playlist.mode == "free":
            song.free_start_tick = start
            song.crossfade_in_tick = crossfade
        else:
            if start != event.start_tick:
                raise CommandError("Start hanya dapat diubah pada Free Timeline.")
            if crossfade:
                raise CommandError("Crossfade hanya tersedia pada Free Timeline.")
            song.free_start_tick = None
            song.crossfade_in_tick = 0

        raw = deepcopy(document.extensions.get(SONG_MIX_KEY, {}))
        if not isinstance(raw, dict):
            raw = {}
        raw[self.song_id] = {
            "fade_in_tick": fade_in,
            "fade_out_tick": fade_out,
            "locked": bool(self.locked),
        }
        document.extensions[SONG_MIX_KEY] = raw

        document.validate()
        resolved_after = TimelineResolver().resolve(document)
        errors_after = [item for item in resolved_after.errors if item.startswith("Audio: ")]
        if errors_after:
            raise CommandError(" | ".join(errors_after))
        return ReplaceDocument(old)


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
        raw_mix = document.extensions.get(SONG_MIX_KEY, {})
        if isinstance(raw_mix, dict) and self.song_id in raw_mix:
            copied = deepcopy(raw_mix)
            values = deepcopy(copied.get(self.song_id, {}))
            if isinstance(values, dict):
                values["locked"] = False
                copied[second.song_id] = values
                document.extensions[SONG_MIX_KEY] = copied

        document.validate()
        resolved_after = TimelineResolver().resolve(document)
        errors_after = [item for item in resolved_after.errors if item.startswith("Audio: ")]
        if errors_after:
            raise CommandError(" | ".join(errors_after))
        return ReplaceDocument(old)
