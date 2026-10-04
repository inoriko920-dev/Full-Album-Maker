from __future__ import annotations

from collections import namedtuple
from pathlib import Path
import os
import subprocess
import sys
import textwrap

import pytest

from full_album_maker.ai_action_registry_step09 import (
    Step09TransactionEngine,
    required_permissions_for_actions,
)
from full_album_maker.ai_agent_core_step09 import (
    AgentActionCall,
    AgentPlan,
    PermissionGrant,
    build_agent_context_snapshot,
    deterministic_plan_id,
)
from full_album_maker.editor_controller import EditorController
from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
from full_album_maker.integration_core_step11 import normalized_project_hash
from full_album_maker.integration_lifecycle_step11 import (
    extract_project_document_from_saved_json,
    verify_persisted_document,
)
from full_album_maker.playlist_commands import MoveSong, SetSongVisual
from full_album_maker.project_repository import save_project_document
from full_album_maker.render_center_model_step10 import RenderSettings
from full_album_maker.render_preflight_step10 import (
    FFmpegCapability,
    run_preflight,
)
from full_album_maker.spectrum_feature import make_spectrum_layer
from full_album_maker.spectrum_step08 import build_preset_command
from full_album_maker.template_studio_step07 import (
    TemplateStudioDraft,
    build_template_apply_commands,
)
from full_album_maker.timeline_audio_commands import SplitSongAtTick
from full_album_maker.timeline_resolver import TimelineResolver
from full_album_maker.visual_precision import (
    SetSongVisualSettings,
    visual_settings_for_song,
)


DiskUsage = namedtuple("DiskUsage", "total used free")


def _fixture(tmp_path: Path) -> tuple[ProjectDocument, str, str]:
    doc = ProjectDocument.new_empty("STEP11 E2E")
    image_path = tmp_path / "cover.png"
    video_path = tmp_path / "visual.mp4"
    image_path.write_bytes(b"image-fixture")
    video_path.write_bytes(b"video-fixture")
    image = MediaAsset(kind="image", locator=str(image_path), original_name=image_path.name)
    video = MediaAsset(
        kind="video",
        locator=str(video_path),
        original_name=video_path.name,
        source_duration_tick=12 * TIMEBASE,
    )
    doc.media.extend([image, video])

    for index in range(3):
        audio_path = tmp_path / f"song-{index + 1}.wav"
        audio_path.write_bytes(b"audio-fixture")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=20 * TIMEBASE,
        )
        doc.media.append(audio)
        doc.playlist.entries.append(
            SongInstance(
                asset_id=audio.asset_id,
                display_title=f"Lagu {index + 1}",
                display_artist="Perjalanan Kita",
                source_out_tick=20 * TIMEBASE,
                cover_asset_id=image.asset_id,
            )
        )

    visual_track = next(track for track in doc.tracks if track.kind == "visual")
    doc.layers.append(make_spectrum_layer(visual_track.track_id, 0, preset_id="minimal_bars"))
    doc.validate()
    return doc, image.asset_id, video.asset_id


def _ai_plan(doc: ProjectDocument, song_id: str, video_id: str):
    context = build_agent_context_snapshot(
        doc,
        selected_song_ids=(song_id,),
        allowed_media_ids=(video_id,),
        enabled_contexts=("media", "timeline", "visual", "spectrum"),
        user_text="pasang video ke lagu ini lalu slowmo 0.5x",
    )
    actions = (
        AgentActionCall("set_song_visual", {"song_ids": [song_id], "asset_id": video_id}),
        AgentActionCall("set_song_video_speed", {"song_ids": [song_id], "speed": 0.5}),
    )
    plan = AgentPlan(
        plan_id=deterministic_plan_id(
            project_id=doc.project_id,
            revision=doc.revision,
            context_fingerprint=context.fingerprint,
            prompt="pasang video ke lagu ini lalu slowmo 0.5x",
            actions=actions,
        ),
        project_id=doc.project_id,
        expected_revision=doc.revision,
        context_fingerprint=context.fingerprint,
        prompt_summary="pasang video ke lagu ini lalu slowmo 0.5x",
        scope_song_ids=(song_id,),
        actions=actions,
        required_permissions=required_permissions_for_actions(actions),
        provider="mock",
    )
    plan.validate()
    return context, plan


def test_full_cross_workspace_edit_undo_redo_save_reopen_and_render_snapshot(tmp_path: Path) -> None:
    doc, image_id, video_id = _fixture(tmp_path)
    baseline_hash = normalized_project_hash(doc)
    baseline_signature = doc.content_signature()
    baseline_order = tuple(song.song_id for song in doc.playlist.entries)
    first, second, third = baseline_order
    spectrum_id = doc.layers[0].layer_id
    controller = EditorController(doc)

    # C — Album reorder through the recovered owner. Playlist positions are 1-based.
    controller.dispatch(MoveSong(third, target_position=1))
    assert tuple(song.song_id for song in controller.snapshot().playlist.entries)[:3] == (third, first, second)

    # D — Timeline manual split through the recovered Timeline command.
    resolved_before_split = controller.snapshot()
    first_event = next(
        item
        for item in TimelineResolver().resolve(resolved_before_split).songs
        if item.song_id == first
    )
    controller.dispatch(SplitSongAtTick(first, first_event.start_tick + 8 * TIMEBASE))
    assert len(controller.snapshot().playlist.entries) == 4

    # E — Visual assignment + motion as one global Undo entry.
    visual_settings = visual_settings_for_song(controller.snapshot(), first)
    visual_settings.update({
        "image_motion": "ken_burns",
        "pan_zoom": True,
        "transition": "fade",
        "transition_seconds": 0.8,
    })
    controller.dispatch([
        SetSongVisual(first, image_id),
        SetSongVisualSettings(first, visual_settings),
    ])
    assert controller.snapshot().song_map()[first].visual_asset_id == image_id

    # F — Template apply uses the same ProjectDocument and command history.
    template_targets = tuple(song.song_id for song in controller.snapshot().playlist.entries)
    template_commands = build_template_apply_commands(
        controller.snapshot(),
        TemplateStudioDraft(template_id="spotify_clean", overlay_opacity=0.55),
        template_targets,
    )
    controller.dispatch(template_commands)
    assert any(layer.origin == "template" for layer in controller.snapshot().layers)

    # G — Spectrum edit through STEP08 owner.
    controller.dispatch(build_preset_command(controller.snapshot(), spectrum_id, "classic"))
    assert controller.snapshot().layer_map()[spectrum_id].properties["preset"] == "classic"

    # H — AI Preview -> Execute, committed as one global Undo transaction.
    ai_context, ai_plan = _ai_plan(controller.snapshot(), first, video_id)
    engine = Step09TransactionEngine(controller)
    before_ai = normalized_project_hash(controller.snapshot())
    preview = engine.dry_run(ai_plan, ai_context, PermissionGrant.all_editor_writes())
    assert preview.has_changes is True
    assert normalized_project_hash(controller.snapshot()) == before_ai
    record = engine.execute(ai_plan, ai_context, PermissionGrant.all_editor_writes())
    assert record.duplicate is False
    assert controller.snapshot().song_map()[first].visual_asset_id == video_id
    assert visual_settings_for_song(controller.snapshot(), first)["video_speed"] == pytest.approx(0.5)

    final_document = controller.snapshot()
    final_signature = final_document.content_signature()
    assert normalized_project_hash(final_document) != baseline_hash
    assert final_signature != baseline_signature

    # Global Undo/Redo compares semantic domain content. Revision is deliberately
    # monotonic and therefore not part of ProjectDocument.content_signature().
    undo_count = 0
    while controller.can_undo:
        controller.undo()
        undo_count += 1
    assert undo_count == 6
    assert controller.snapshot().content_signature() == baseline_signature

    redo_count = 0
    while controller.can_redo:
        controller.redo()
        redo_count += 1
    assert redo_count == 6
    assert controller.snapshot().content_signature() == final_signature

    # I-K — Canonical save/reopen compares persisted normalized state at the
    # final post-Redo revision, including revision/schema metadata.
    final_hash = normalized_project_hash(controller.snapshot())
    project_path = tmp_path / "step11-final.json"
    save_project_document(str(project_path), controller.snapshot())
    assert verify_persisted_document(project_path, controller.snapshot()) is True
    reopened = extract_project_document_from_saved_json(project_path)
    assert normalized_project_hash(reopened) == final_hash
    assert reopened.content_signature() == controller.snapshot().content_signature()

    # N — Render preflight creates an immutable authoritative snapshot.
    settings = RenderSettings(
        filename="STEP11_E2E.mp4",
        output_folder=str(tmp_path / "output"),
        hardware_mode="software",
    )
    (tmp_path / "output").mkdir()
    capability = FFmpegCapability(
        ffmpeg="ffmpeg",
        ffprobe="ffprobe",
        version="ffmpeg fixture",
        encoders=frozenset({"libx264"}),
        runtime_verified_encoders=frozenset(),
        source="fixture",
    )
    preflight = run_preflight(
        reopened,
        settings,
        capability=capability,
        disk_usage=lambda _path: DiskUsage(100 * 1024**3, 10 * 1024**3, 90 * 1024**3),
    )
    assert preflight.ready is True
    assert preflight.snapshot is not None
    snapshot_hash = preflight.snapshot.snapshot_hash
    frozen_signature = preflight.snapshot.content_signature

    # Mutating the live controller after queue/preflight cannot mutate the frozen snapshot.
    controller.dispatch(MoveSong(second, target_position=1))
    assert preflight.snapshot.snapshot_hash == snapshot_hash
    assert preflight.snapshot.content_signature == frozen_signature
    assert preflight.snapshot.document().content_signature() == reopened.content_signature()
    assert controller.snapshot().content_signature() != preflight.snapshot.document().content_signature()


def test_nine_workspace_navigation_is_read_only_in_production_subprocess(tmp_path: Path) -> None:
    script = textwrap.dedent(
        r'''
        import os
        from pathlib import Path
        import tempfile
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER", "1")
        from PySide6.QtWidgets import QApplication
        import full_album_maker.main  # installs production layers through STEP11
        from full_album_maker.editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE
        from full_album_maker.foundation_window import FoundationMainWindow
        from full_album_maker.integration_core_step11 import normalized_project_hash

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix="step11-nav-") as root:
            root = Path(root)
            doc = ProjectDocument.new_empty("STEP11 navigation")
            path = root / "song.wav"
            path.write_bytes(b"fixture")
            audio = MediaAsset(kind="audio", locator=str(path), original_name=path.name, source_duration_tick=10 * TIMEBASE)
            doc.media.append(audio)
            doc.playlist.entries.append(SongInstance(asset_id=audio.asset_id, display_title="Lagu", source_out_tick=10 * TIMEBASE))
            doc.validate()

            window = FoundationMainWindow()
            window._foundation_project_open = True
            window.editor_workspace.set_document(doc)
            # Let all zero-delay activation guards from STEP03-STEP11 settle
            # before navigation becomes the behavior under measurement.
            app.processEvents()
            app.processEvents()
            before = normalized_project_hash(window.editor_workspace.document())
            routes = ("home", "media", "album", "timeline", "visual", "template", "spectrum", "ai_agent", "render")
            for route in routes:
                window.foundation_shell.set_workspace(route)
                app.processEvents()
                app.processEvents()
                assert window.foundation_state.workspace == route, (route, window.foundation_state.workspace)
                current = normalized_project_hash(window.editor_workspace.document())
                assert current == before, (route, before, current)
            window.hide()
            shutdown = getattr(window, "_s11_shutdown", None)
            if callable(shutdown):
                shutdown()
            window.deleteLater()
            app.processEvents()
        '''
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr