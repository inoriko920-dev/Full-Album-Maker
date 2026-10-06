from __future__ import annotations

from dataclasses import replace

from .media_feature import install_step03_media
from .media_completion import install_step03_media_completion
from .media_layout_fix import install_step03_media_layout_fix
from . import media_capture as base


def _golden_fixture_assets():
    source = getattr(base, "fixture_assets_original", base.fixture_assets)
    values = list(source())

    # Deterministic visual fixture order from the canonical Media reference.
    # Runtime sorting remains metadata-driven; only screenshot fixture timestamps
    # are shaped so the "Terbaru" view exercises the same mixed-media rhythm.
    golden_order = [
        "Senja di Kota Ini.mp3",
        "Jalan Pulang.mp3",
        "Pantai Bali.jpg",
        "Gunung Bromo.jpg",
        "Perjalanan.jpg",
        "Senja di Kota Ini.mp4",
        "Jalan Pulang.mp4",
        "Perjalanan Kita.mp4",
        "Cerita Baru.mp4",
        "Danau.jpg",
        "Inspirasi.mp3",
        "Hutan.jpg",
        "Pelangi.mp3",
        "Timelapse.mp4",
        "Kota Malam.jpg",
        "Studio.jpg",
        "Jembatan.jpg",
        "Sawah.jpg",
        "Harmoni.mp3",
        "Langit.mp3",
        "Cerita.mp3",
        "Outro.mp3",
        "B-Roll Kota.mp4",
        "Missing Shot.mp4",
    ]
    rank = {name: len(golden_order) - index for index, name in enumerate(golden_order)}

    output = []
    for index, asset in enumerate(values):
        memberships = []
        if index < 12:
            memberships.append("Aset Utama")
        if index < 6:
            memberships.append("B-Roll")
        if index < 4:
            memberships.append("Musik")
        if index < 2:
            memberships.append("Narasi")
        if index == len(values) - 1:
            memberships.append("Outro")
        output.append(
            replace(
                asset,
                collections=tuple(memberships),
                imported_at=float(rank.get(asset.display_name, 0)),
            )
        )
    return output


def main(argv: list[str] | None = None) -> int:
    install_step03_media()
    install_step03_media_completion()
    install_step03_media_layout_fix()
    if not hasattr(base, "fixture_assets_original"):
        base.fixture_assets_original = base.fixture_assets
    base.fixture_assets = _golden_fixture_assets
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())