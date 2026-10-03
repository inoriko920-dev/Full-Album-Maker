from __future__ import annotations

import sys

from full_album_maker.gemini_schema_compat import install_gemini_schema_compat
from full_album_maker.playlist_feature import install_feature
from full_album_maker.playlist_hardening import install_playlist_hardening
from full_album_maker.visual_feature import install_visual_feature
from full_album_maker.engine_hardening import install_engine_hardening
from full_album_maker.source_integrity import install_source_integrity
from full_album_maker.ui_hardening import install_ui_hardening
from full_album_maker.atomic_bundle import install_atomic_bundle
from full_album_maker.render_lifecycle import install_render_lifecycle
from full_album_maker.project_dirty import install_project_dirty_state
from full_album_maker.async_import import install_async_import
from full_album_maker.media_feature import install_step03_media
from full_album_maker.media_feature_activation import install_step03_media_activation_guard
from full_album_maker.media_completion import install_step03_media_completion
from full_album_maker.media_layout_fix import install_step03_media_layout_fix
from full_album_maker.album_feature import install_step04_album
from full_album_maker.album_restore_fix import install_step04_album_restore_fix
from full_album_maker.timeline_feature_step05 import install_step05_timeline
from full_album_maker.timeline_route_fix import install_step05_timeline_route_fix
from full_album_maker.timeline_completion_step05 import install_step05_timeline_completion
from full_album_maker.visual_feature_step06 import install_step06_visual
from full_album_maker.visual_preview_decode_step06 import install_step06_visual_preview_decode
from full_album_maker.visual_timeline_completion_step06 import install_step06_visual_timeline_completion
from full_album_maker.template_feature_step07 import install_step07_template
from full_album_maker.spectrum_feature_step08 import install_step08_spectrum
from full_album_maker.ai_feature_step09 import install_step09_ai_agent
from full_album_maker.render_queue_presentation_step10 import install_step10_queue_presentation
from full_album_maker.render_feature_step10 import install_step10_render
from full_album_maker.integration_feature_step11 import install_step11_integration
from full_album_maker.integration_completion_step11 import install_step11_integration_completion


install_feature()
install_gemini_schema_compat()
install_playlist_hardening()
install_visual_feature()
install_engine_hardening()
install_source_integrity()
install_ui_hardening()
install_atomic_bundle()
install_render_lifecycle()
install_project_dirty_state()
install_async_import()
install_step03_media()
install_step03_media_activation_guard()
install_step03_media_completion()
install_step03_media_layout_fix()
install_step04_album()
install_step04_album_restore_fix()
install_step05_timeline()
install_step05_timeline_route_fix()
install_step05_timeline_completion()
install_step06_visual()
install_step06_visual_preview_decode()
install_step06_visual_timeline_completion()
install_step07_template()
install_step08_spectrum()
install_step09_ai_agent()
install_step10_queue_presentation()
install_step10_render()
install_step11_integration()
install_step11_integration_completion()


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--portable-smoke" in args:
        from full_album_maker.release_smoke import run_portable_smoke

        return run_portable_smoke()

    # Import after installing the compatibility/presentation layers so the recovered
    # v1.4 window keeps its proven engine while the integrated workspaces extend it.
    from full_album_maker.v14_window import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())