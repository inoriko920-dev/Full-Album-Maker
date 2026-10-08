"""Verify native Windows-hosted Qt offscreen Render Center capture evidence.

This does NOT claim a native Windows titlebar screenshot or golden pixel match:
render_capture_step10 draws the title frame synthetically, intentionally.
No original golden binary is shipped into CI; use the owner's immutable golden
outside this repository for subsequent overlay/delta analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from PIL import Image, ImageStat


CAPTURES = (
    ("render-g09-final", 1672, 941),
    ("render-1366-final", 1366, 768),
)


def verify_capture_evidence(root: Path, *, require_windows: bool = True) -> dict:
    if require_windows and sys.platform != "win32":
        raise RuntimeError("Capture Windows must be verified on a Windows runner")
    if os.getenv("QT_QPA_PLATFORM", "").lower() != "offscreen":
        raise RuntimeError("Capture must be Qt offscreen, not a visible desktop capture")

    cases = {}
    for name, width, height in CAPTURES:
        png = root / "current" / (name + ".png")
        report = root / "reports" / (name + ".json")
        if not png.is_file() or not report.is_file():
            raise FileNotFoundError(f"Screenshot/JSON evidence missing: {name}")

        data = json.loads(report.read_text(encoding="utf-8"))
        geometry = data["geometry"]
        digest = hashlib.sha256(png.read_bytes()).hexdigest()
        if digest != geometry["screenshot_sha256"]:
            raise AssertionError(f"PNG digest differs from capture report: {name}")
        if geometry["window"] != [width, height]:
            raise AssertionError(f"Unexpected screenshot dimensions in report: {name}")

        with Image.open(png) as image:
            if image.format != "PNG" or image.size != (width, height):
                raise AssertionError(f"Invalid PNG or dimensions for {name}")
            stats = ImageStat.Stat(image.convert("RGB"))
            if max(stats.stddev) < 4:
                raise AssertionError(f"Rendered screenshot appears blank: {name}")

        invariants = {
            "route_active": (
                geometry["workspace"] == "render"
                and geometry["render_active"] is True
                and geometry["inspector_active"] is True
            ),
            "project_unchanged": geometry["project_signature_unchanged_by_route_and_fixture"] is True,
            "queue_count": geometry["queue_row_count"] == 3
                and geometry["ui09_queue_card_count"] == 3,
            "all_queue_rows_visible": geometry["ui09_all_queue_rows_visible"] is True,
            "queue_progress": geometry["ui09_queue_progress"] == [630, 0, 1000],
            "inspector_scroll": geometry["ui09_inspector_scroll_layout_pass"] is True
                and geometry["ui09_inspector_debug"]["horizontal_range"] == 0,
            "verified_completion": geometry["completed_verified"] is True,
            "telemetry": geometry["performance_points"] == 5,
            "cannot_pause": geometry["pause_enabled"] is False,
        }
        problems = [key for key, valid in invariants.items() if not valid]
        if problems:
            raise AssertionError(f"{name} screenshot geometry rejected: {problems}")

        cases[name] = {
            "size": [width, height],
            "sha256": digest,
            "queue_count": geometry["ui09_queue_card_count"],
            "all_rows_visible": geometry["ui09_all_queue_rows_visible"],
            "inspector_scroll_pass": geometry["ui09_inspector_scroll_layout_pass"],
            "font_family": geometry["font_family"],
        }

    result = {
        "status": "PASS",
        "platform": sys.platform,
        "qt_platform": "offscreen",
        "evidence_type": "Windows-hosted Qt offscreen with synthetic title frame",
        "golden_reference": "external, never modified",
        "golden_pixel_match": "NOT_EVALUATED",
        "snapshots": cases,
    }
    (root / "reports" / "windows-evidence-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_capture_evidence(args.root), ensure_ascii=True, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
