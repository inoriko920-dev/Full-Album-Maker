from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


BASELINE_ASPECT = 1672 / 941


def _assert_image_sane(path: Path, *, min_width: int, min_height: int) -> tuple[int, int]:
    size = Image.open(path).size
    assert size[0] >= min_width and size[1] >= min_height, (path.name, size)
    assert abs((size[0] / size[1]) - BASELINE_ASPECT) < 0.08, (path.name, size)
    return size


def validate_linux(root: Path) -> None:
    reports_dir = root / "reports"
    current = root / "current"
    reports = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in reports_dir.glob("*.json")}

    home = reports["home"]["geometry"]
    assert home["window"] == [1672, 941]
    assert 40 <= home["title_bottom"] + 1 <= 42
    assert 92 <= home["command_bottom"] + 1 <= 100
    assert 160 <= home["nav_right"] + 1 <= 180
    assert 330 <= home["right_dock_width"] <= 360
    assert 26 <= home["status_height"] <= 30
    assert home["timeline_height"] <= 40

    ranges = {
        "media": (180, 210),
        "album": (180, 210),
        "timeline": (340, 365),
        "visual": (225, 250),
        "template": (150, 170),
        "spectrum": (240, 265),
        "ai-agent": (170, 190),
        "render": (0, 40),
    }
    for name, (lo, hi) in ranges.items():
        value = reports[name]["geometry"]["timeline_height"]
        assert lo <= value <= hi, (name, value)

    compact = reports["compact-1366"]["geometry"]
    assert compact["window"] == [1366, 768]
    assert compact["nav_right"] + 1 <= 80
    assert reports["dpi-125"]["geometry"]["scale"] == 1.25
    assert reports["dpi-150"]["geometry"]["scale"] == 1.5
    assert {
        reports[key]["geometry"]["workspace"]
        for key in ("home", "media", "album", "timeline", "visual", "template", "spectrum", "ai-agent", "render")
    } == {"home", "media", "album", "timeline", "visual", "template", "spectrum", "ai_agent", "render"}

    assert Image.open(current / "foundation-home.png").size == (1672, 941)
    compact_size = Image.open(current / "foundation-1366.png").size
    assert compact_size[0] == 1366 and compact_size[1] >= 768, compact_size
    _assert_image_sane(current / "foundation-125dpi.png", min_width=1672, min_height=941)
    _assert_image_sane(current / "foundation-150dpi.png", min_width=1672, min_height=941)

    repeat = reports["home-repeat"]["geometry"]
    assert repeat["window"] == home["window"]
    print("LINUX_STEP01_EVIDENCE_PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="ui-golden")
    ns = parser.parse_args(argv)
    validate_linux(Path(ns.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
