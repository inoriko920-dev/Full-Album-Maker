from __future__ import annotations

from dataclasses import replace

from .media_feature import install_step03_media
from .media_completion import install_step03_media_completion
from . import media_capture as base


def _golden_fixture_assets():
    values = list(base.fixture_assets_original())
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
        output.append(replace(asset, collections=tuple(memberships)))
    return output


def main(argv: list[str] | None = None) -> int:
    install_step03_media()
    install_step03_media_completion()
    if not hasattr(base, "fixture_assets_original"):
        base.fixture_assets_original = base.fixture_assets
    base.fixture_assets = _golden_fixture_assets
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
