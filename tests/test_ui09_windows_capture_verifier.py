"""Pure QA contract tests; these images are test fixtures, not UI goldens."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy

from PIL import Image, ImageDraw
import pytest


def _verifier():
    script = Path(__file__).resolve().parents[1] / "build" / "verify_ui09_windows_evidence.py"
    return runpy.run_path(str(script))["verify_capture_evidence"]


def _write_example(root: Path):
    for name, width, height in (
        ("render-g09-final", 1672, 941),
        ("render-1366-final", 1366, 768),
    ):
        png = root / "current" / f"{name}.png"
        report = root / "reports" / f"{name}.json"
        png.parent.mkdir(parents=True, exist_ok=True)
        report.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (width, height), "#F5F8FE")
        draw = ImageDraw.Draw(image)
        draw.rectangle((150, 80, width - 200, height - 130), fill="#1A71E8")
        image.save(png)
        digest = hashlib.sha256(png.read_bytes()).hexdigest()
        geometry = {
            "window": [width, height],
            "screenshot_sha256": digest,
            "workspace": "render",
            "render_active": True,
            "inspector_active": True,
            "project_signature_unchanged_by_route_and_fixture": True,
            "queue_row_count": 3,
            "ui09_queue_card_count": 3,
            "ui09_all_queue_rows_visible": True,
            "ui09_queue_progress": [630, 0, 1000],
            "ui09_inspector_scroll_layout_pass": True,
            "ui09_inspector_debug": {"horizontal_range": 0},
            "completed_verified": True,
            "performance_points": 5,
            "pause_enabled": False,
            "font_family": "Test",
        }
        report.write_text(json.dumps({"geometry": geometry}), encoding="utf-8")


def test_capture_validator_checks_both_views_without_claiming_golden(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_example(tmp_path)
    result = _verifier()(tmp_path, require_windows=False)
    assert result["status"] == "PASS"
    assert result["golden_pixel_match"] == "NOT_EVALUATED"
    assert "synthetic title" in result["evidence_type"]
    assert set(result["snapshots"]) == {"render-g09-final", "render-1366-final"}


def test_capture_validator_rejects_clipped_and_corrupt_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    _write_example(tmp_path)
    verify = _verifier()
    compact = tmp_path / "reports" / "render-1366-final.json"
    data = json.loads(compact.read_text(encoding="utf-8"))
    data["geometry"]["ui09_all_queue_rows_visible"] = False
    compact.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(AssertionError, match="all_queue_rows_visible"):
        verify(tmp_path, require_windows=False)

    data["geometry"]["ui09_all_queue_rows_visible"] = True
    compact.write_text(json.dumps(data), encoding="utf-8")
    png = tmp_path / "current" / "render-1366-final.png"
    png.write_bytes(png.read_bytes() + b"corrupt-after-report")
    with pytest.raises(AssertionError, match="digest differs"):
        verify(tmp_path, require_windows=False)
