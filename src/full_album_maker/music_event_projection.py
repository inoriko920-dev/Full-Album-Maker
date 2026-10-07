from __future__ import annotations

from collections.abc import Mapping

from .editor_models import ProjectDocument
from .music_event_contract import (
    MusicEventTimeline,
    ProjectedMusicEvent,
    projected_event_sort_key,
)
from .timeline_resolver import ResolvedTimeline, TimelineResolver


def project_song_events(
    document: ProjectDocument,
    resolved: ResolvedTimeline,
    song_id: str,
    source_timeline: MusicEventTimeline,
) -> tuple[ProjectedMusicEvent, ...]:
    document.validate()
    source_timeline.validate()

    song = document.song_map().get(song_id)
    if song is None or not song.enabled:
        return ()
    if song.asset_id != source_timeline.asset_id:
        raise ValueError("source timeline asset_id does not match song asset_id")

    resolved_song = next((value for value in resolved.songs if value.song_id == song_id), None)
    if resolved_song is None:
        return ()

    asset = document.asset_map()[song.asset_id]
    source_in = int(song.source_in_tick)
    source_out = int(song.source_out_tick if song.source_out_tick is not None else asset.source_duration_tick)
    if source_out <= source_in:
        return ()

    result: list[ProjectedMusicEvent] = []
    for event in source_timeline.events:
        if event.tick < source_in:
            continue
        if event.tick >= source_out:
            break
        projected = ProjectedMusicEvent(
            project_tick=int(resolved_song.start_tick + (event.tick - source_in)),
            source_tick=event.tick,
            song_id=song.song_id,
            asset_id=song.asset_id,
            event_type=event.event_type,
            strength=event.strength,
            confidence=event.confidence,
            source=event.source,
        )
        projected.validate()
        result.append(projected)
    return tuple(sorted(result, key=projected_event_sort_key))


def project_album_events(
    document: ProjectDocument,
    timelines_by_asset: Mapping[str, MusicEventTimeline],
    *,
    resolved: ResolvedTimeline | None = None,
) -> tuple[ProjectedMusicEvent, ...]:
    document.validate()
    resolved_timeline = resolved or TimelineResolver().resolve(document)
    result: list[ProjectedMusicEvent] = []
    for resolved_song in resolved_timeline.songs:
        song = document.song_map()[resolved_song.song_id]
        timeline = timelines_by_asset.get(song.asset_id)
        if timeline is None:
            continue
        result.extend(project_song_events(document, resolved_timeline, song.song_id, timeline))
    return tuple(sorted(result, key=projected_event_sort_key))
