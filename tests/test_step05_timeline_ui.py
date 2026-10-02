from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from full_album_maker.editor_models import Layer, MediaAsset, ProjectDocument, SongInstance, TimeBinding, TIMEBASE
from full_album_maker.timeline_precision import AddTimelineMarker, SetSongMix, timeline_gaps, timeline_markers
from full_album_maker.timeline_workspace_step05 import (
    TimelineClipInspector,
    TimelineContextWidget,
    TimelinePrecisionPanel,
    TimelinePreviewWorkspace,
)


def _app():
    return QApplication.instance() or QApplication([])


def _fixture() -> ProjectDocument:
    doc = ProjectDocument.new_empty("Timeline UI")
    doc.playlist.mode = "free"
    starts = (0, 10 * TIMEBASE, 24 * TIMEBASE)
    durations = (12, 12, 12)
    for index, (start, seconds) in enumerate(zip(starts, durations)):
        asset = MediaAsset(
            kind="audio",
            locator=f"/tmp/song-{index + 1}.mp3",
            original_name=f"song-{index + 1}.mp3",
            source_duration_tick=seconds * TIMEBASE,
        )
        doc.media.append(asset)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=asset.asset_id,
                display_title=f"Song {index + 1}",
                source_out_tick=seconds * TIMEBASE,
                free_start_tick=start,
                crossfade_in_tick=2 * TIMEBASE if index == 1 else 0,
            )
        )
    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    doc.layers.append(
        Layer(
            track_id=visual_track.track_id,
            type="text",
            name="Judul Album",
            time_binding=TimeBinding(kind="absolute", start_tick=0, duration_tick=8 * TIMEBASE),
        )
    )
    AddTimelineMarker(0, "Intro").apply(doc)
    AddTimelineMarker(10 * TIMEBASE, "Reff").apply(doc)
    SetSongMix(doc.playlist.entries[0].song_id, 0.9, TIMEBASE, TIMEBASE, False).apply(doc)
    doc.validate()
    return doc


def test_precision_components_render_real_free_state_without_mutating_document():
    _app()
    doc = _fixture()
    signature = doc.content_signature()
    context = TimelineContextWidget()
    preview = TimelinePreviewWorkspace()
    inspector = TimelineClipInspector()
    panel = TimelinePrecisionPanel()

    context.apply_document(doc)
    preview.apply_document(doc)
    panel.apply_document(doc, 5 * TIMEBASE, ripple=False, snap=True)
    inspector.set_song(doc, doc.playlist.entries[0].song_id)

    assert doc.content_signature() == signature
    assert panel.mode.checked_value() == "free"
    assert len(timeline_markers(doc)) == 2
    assert len(timeline_gaps(doc)) == 1
    assert inspector.heading.text() == "Lagu Utama"
    assert inspector.fade_in.value() == 1.0
    assert panel.canvas._document.playlist.mode == "free"


def test_context_lists_markers_and_clips_from_document():
    _app()
    doc = _fixture()
    context = TimelineContextWidget()
    context.apply_document(doc)
    assert context.marker_list.count() == 2
    assert context.clip_list.count() == len(doc.playlist.entries) + len(doc.layers)
    labels = [context.marker_list.item(i).text() for i in range(context.marker_list.count())]
    assert any("Intro" in label for label in labels)
    assert any("Reff" in label for label in labels)
