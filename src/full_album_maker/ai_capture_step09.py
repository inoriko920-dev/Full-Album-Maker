from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .foundation_capture import (
    _compose_native_title_preview,
    _logical_viewport_image,
    _prepare_qt,
)
from .foundation_tokens import TOKENS


GOLDEN_PROMPT = (
    "Pilih 20 lagu, pasangkan visual yang cocok, slowmo footage 0,5x, "
    "lalu susun timeline."
)


def _fixture_document(root: Path):
    from .editor_models import MediaAsset, ProjectDocument, SongInstance, TIMEBASE

    document = ProjectDocument.new_empty("AI Agent Golden Project")
    document.album_title = "Perjalanan Kita — Full Album"
    document.canvas.width = 1920
    document.canvas.height = 1080

    song_ids: list[str] = []
    video_ids: list[str] = []
    for index in range(1, 21):
        title = f"Lagu {index:02d}"
        audio_path = root / f"audio-{index:02d}.wav"
        video_path = root / f"{title}.mp4"
        audio_path.write_bytes(b"fixture-audio")
        video_path.write_bytes(b"fixture-video")
        audio = MediaAsset(
            kind="audio",
            locator=str(audio_path),
            original_name=audio_path.name,
            source_duration_tick=30 * TIMEBASE,
            metadata={"title": title, "artist": "Perjalanan Kita"},
        )
        video = MediaAsset(
            kind="video",
            locator=str(video_path),
            original_name=video_path.name,
            source_duration_tick=18 * TIMEBASE,
        )
        document.media.extend([audio, video])
        song = SongInstance(
            asset_id=audio.asset_id,
            display_title=title,
            display_artist="Perjalanan Kita",
            source_out_tick=30 * TIMEBASE,
        )
        document.playlist.entries.append(song)
        song_ids.append(song.song_id)
        video_ids.append(video.asset_id)
    document.validate()
    return document, tuple(song_ids), tuple(video_ids)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    os.environ["FAM_STEP09_PROVIDER"] = "mock"
    os.environ["FAM_STEP09_GOLDEN"] = "1"
    os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    _prepare_qt(scale)
    import full_album_maker.main  # noqa: F401 - installs production layers through STEP09

    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .ai_agent_core_step09 import AgentState
    from .ai_provider_step09 import MockStep09Provider
    from .foundation_font import install_foundation_font
    from .foundation_window import FoundationMainWindow
    from .visual_precision import visual_settings_for_song

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    root = Path(tempfile.mkdtemp(prefix="fam-step09-ai-"))
    document, song_ids, video_ids = _fixture_document(root)
    signature_before = document.content_signature()
    revision_before = document.revision

    window = FoundationMainWindow()
    window.resize(width, client_height)
    window.foundation_shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window._foundation_project_open = True
    window.editor_workspace.set_document(document)
    window._s06_selected_ids = set(song_ids)
    window._s06_primary_song_id = song_ids[0]
    window.foundation_shell.set_workspace("ai_agent")
    window.ai_workspace_s09.set_prompt(GOLDEN_PROMPT)

    context = window._s09_build_context(GOLDEN_PROMPT)
    session = window._s09_ensure_session()
    session.grant = window._s09_grant()
    session.begin_interpretation(GOLDEN_PROMPT, context)
    interpretation = MockStep09Provider().interpret(GOLDEN_PROMPT, context)
    session.receive_interpretation(interpretation)
    plan_snapshot = session.snapshot()
    if plan_snapshot.state != AgentState.PLAN_READY or plan_snapshot.plan is None:
        raise RuntimeError("Mock STEP09 golden fixture tidak menghasilkan PLAN_READY.")
    session.preview()
    preview_snapshot = session.snapshot()
    if preview_snapshot.state != AgentState.PREVIEW_READY or preview_snapshot.preview is None:
        raise RuntimeError("Mock STEP09 golden fixture tidak menghasilkan PREVIEW_READY.")
    window._s09_context_snapshot = context
    window._s09_refresh()
    window.show()

    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    app.processEvents()

    live = window.editor_workspace.document()
    signature_after_preview = live.content_signature()
    revision_after_preview = live.revision
    plan = preview_snapshot.plan
    preview = preview_snapshot.preview
    assert plan is not None and preview is not None

    visual_actions = [action for action in plan.actions if action.name == "set_song_visual"]
    speed_action = next((action for action in plan.actions if action.name == "set_song_video_speed"), None)
    auto_action = next((action for action in plan.actions if action.name == "auto_arrange_timeline"), None)
    if len(visual_actions) != 20 or speed_action is None or auto_action is None:
        raise RuntimeError("Golden AgentPlan tidak memuat kontrak 20 visual + slowmo + Auto Susun.")

    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot STEP09 AI Agent: {output}")

    shell = window.foundation_shell
    report = {
        "window": [width, height],
        "workspace": window.foundation_state.workspace,
        "ai_active": shell.workspace_stack.currentWidget() is window.ai_workspace_s09,
        "conversation_visible": not window.ai_conversations_s09.isHidden(),
        "context_dock_active": window._inspector_router.currentWidget() is window.ai_context_s09,
        "timeline_visible": not window.ai_timeline_s09.isHidden(),
        "context_width": shell.context.width(),
        "right_dock_width": shell.inspector.width(),
        "timeline_height": shell.timeline.height(),
        "status_height": shell.status_bar.height(),
        "state": preview_snapshot.state.value,
        "provider": plan.provider,
        "plan_action_count": len(plan.actions),
        "visual_action_count": len(visual_actions),
        "slowmo_speed": float(speed_action.args.get("speed", 0.0)),
        "auto_arrange_present": auto_action is not None,
        "scope_song_count": len(plan.scope_song_ids),
        "allowed_media_count": len(context.allowed_media_ids),
        "permission_count": len(plan.required_permissions),
        "preview_command_count": preview.command_count,
        "preview_change_count": preview.impact.change_count,
        "project_signature_unchanged_by_send_and_preview": signature_before == signature_after_preview,
        "project_revision_unchanged_by_send_and_preview": revision_before == revision_after_preview,
        "send_and_preview_did_not_apply_visual": all(
            live.song_map()[song_id].visual_asset_id is None for song_id in song_ids
        ),
        "send_and_preview_did_not_apply_slowmo": all(
            visual_settings_for_song(live, song_id)["video_speed"] == 1.0 for song_id in song_ids
        ),
        "prompt": GOLDEN_PROMPT,
        "screenshot_sha256": _sha(output),
        "scale": scale,
        "font_family": font_family,
    }

    window.hide()
    if getattr(window, "_s09_async", None) is not None:
        window._s09_async.close()
    window.deleteLater()
    app.processEvents()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP09 AI Agent evidence")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    ns = parser.parse_args(argv)

    output = Path(ns.output)
    geometry = capture(output, ns.width, ns.height, ns.scale)
    result = {"current": str(output), "geometry": geometry}
    if ns.report:
        report = Path(ns.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
