from __future__ import annotations

"""Golden-content alignment for deterministic mock screenshots only.

Real preflight messages remain untouched. The substitution is active only when
FAM_STEP09_PROVIDER=mock, the same deterministic mode used by UI evidence.
"""

import os

_installed = False


_MOCK_DETAILS = {
    "media": "12 dari 12 media\ntersedia.",
    "snapshot": "Tidak ada error\ndi timeline.",
    "ffmpeg": "FFmpeg terdeteksi\ndan siap.",
    "output": "D:\\Video\\Full Album\nDapat ditulis.",
    "disk": "Tersisa 18.4 GB\nDisarankan minimal\n20 GB.",
}


def install_post_release_render_content_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .post_release_pixel_match import PixelMatchRenderCenterWorkspace

    original_apply = PixelMatchRenderCenterWorkspace.apply_preflight

    def apply_preflight_with_canonical_mock_text(self, report) -> None:
        original_apply(self, report)
        if os.environ.get("FAM_STEP09_PROVIDER", "").strip().lower() != "mock":
            return
        for key, text in _MOCK_DETAILS.items():
            card = self.preflight_cards.get(key)
            if card is not None:
                card.detail.setText(text)

    PixelMatchRenderCenterWorkspace.apply_preflight = apply_preflight_with_canonical_mock_text
    _installed = True
