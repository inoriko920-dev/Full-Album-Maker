from __future__ import annotations

from pathlib import Path

from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.s11_render_graph import S11FFmpegCompiler
from full_album_maker.timeline_precision import SetSongMix


def _doc(mode: str) -> ProjectDocument:
    doc = ProjectDocument.new_empty("Mix Render")
    doc.playlist.mode = mode
    starts = (0, 8 * TIMEBASE)
    for index in range(2):
        asset = MediaAsset(
            kind="audio",
            locator=f"/tmp/mix-{index}.mp3",
            original_name=f"mix-{index}.mp3",
            source_duration_tick=10 * TIMEBASE,
        )
        doc.media.append(asset)
        song = SongInstance(
            asset_id=asset.asset_id,
            display_title=f"Mix {index}",
            source_out_tick=10 * TIMEBASE,
        )
        if mode == "free":
            song.free_start_tick = starts[index]
            song.crossfade_in_tick = 2 * TIMEBASE if index == 1 else 0
        doc.playlist.entries.append(song)
    SetSongMix(doc.playlist.entries[0].song_id, 0.5, TIMEBASE, 2 * TIMEBASE, False).apply(doc)
    doc.validate()
    return doc


def _graph(compiled) -> str:
    args = list(compiled.args)
    if "-filter_complex" in args:
        return args[args.index("-filter_complex") + 1]
    path = Path(args[args.index("-/filter_complex") + 1])
    return path.read_text(encoding="utf-8")


def test_packed_render_graph_applies_gain_and_explicit_fades(tmp_path):
    compiled = S11FFmpegCompiler("ffmpeg").compile_video(
        _doc("packed"),
        tmp_path / "packed.mp4",
        tmp_path,
    )
    graph = _graph(compiled)
    assert "volume=0.50000000" in graph
    assert "afade=t=in:st=0:d=1.000000:curve=tri" in graph
    assert "afade=t=out:st=8.000000:d=2.000000:curve=tri" in graph


def test_free_render_graph_combines_explicit_fade_with_crossfade(tmp_path):
    compiled = S11FFmpegCompiler("ffmpeg").compile_video(
        _doc("free"),
        tmp_path / "free.mp4",
        tmp_path,
    )
    graph = _graph(compiled)
    assert "volume=0.50000000" in graph
    assert "afade=t=in:st=0:d=1.000000:curve=tri" in graph
    # First song has explicit 2s fade out and incoming song has a 2s crossfade.
    assert "afade=t=out:st=8.000000:d=2.000000:curve=tri" in graph
    assert "anullsrc=r=48000:cl=stereo" in graph
