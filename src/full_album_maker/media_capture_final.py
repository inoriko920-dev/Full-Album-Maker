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

    metadata_overrides = {
        "Senja di Kota Ini.mp3": dict(duration=204.0, size_bytes=3_400_000),
        "Jalan Pulang.mp3": dict(duration=252.0, size_bytes=4_100_000),
        "Pantai Bali.jpg": dict(size_bytes=2_800_000),
        "Gunung Bromo.jpg": dict(size_bytes=3_100_000),
        "Perjalanan.jpg": dict(size_bytes=2_400_000),
        "Senja di Kota Ini.mp4": dict(
            duration=42.0, width=3840, height=2160, fps=24.0,
            size_bytes=1_200_000_000, created_at=1736519520.0,
            container="MP4 (H.264, AAC)",
        ),
        "Jalan Pulang.mp4": dict(duration=75.0, width=1920, height=1080, fps=30.0, size_bytes=512_000_000),
        "Perjalanan Kita.mp4": dict(duration=156.0, width=3840, height=2160, fps=30.0, size_bytes=1_400_000_000),
        "Cerita Baru.mp4": dict(duration=58.0, width=1920, height=1080, fps=30.0, size_bytes=420_000_000),
        "Danau.jpg": dict(size_bytes=2_900_000),
        "Inspirasi.mp3": dict(duration=138.0, size_bytes=2_100_000),
        "Hutan.jpg": dict(size_bytes=3_500_000),
        "Pelangi.mp3": dict(duration=190.0, size_bytes=3_000_000),
        "Timelapse.mp4": dict(duration=20.0, width=3840, height=2160, fps=60.0, size_bytes=720_000_000),
        "Kota Malam.jpg": dict(size_bytes=2_600_000),
    }

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
        metadata = replace(asset.metadata, **metadata_overrides.get(asset.display_name, {}))
        path = asset.path
        tags = asset.tags
        description = asset.description
        if asset.display_name == "Senja di Kota Ini.mp4":
            path = r"D:\Proyek\Aset Utama\Senja di Kota Ini.mp4"
            tags = ("senja", "perjalanan", "vlog")
            description = "Momen senja di kota, pemandangan kota dari ketinggian."

        output.append(
            replace(
                asset,
                path=path,
                tags=tags,
                description=description,
                metadata=metadata,
                collections=tuple(memberships),
                imported_at=float(rank.get(asset.display_name, 0)),
            )
        )

    output.sort(key=lambda asset: rank.get(asset.display_name, 0), reverse=True)
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