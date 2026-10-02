from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _prepare_qt(scale: float) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def _difference(current: Path, golden: Path, out_dir: Path) -> dict[str, object]:
    from PIL import Image, ImageChops, ImageEnhance

    a = Image.open(current).convert("RGBA")
    b = Image.open(golden).convert("RGBA")
    if a.size != b.size:
        b = b.resize(a.size)
    overlay = Image.blend(b, a, 0.5)
    overlay_path = out_dir / f"{current.stem}-overlay.png"
    overlay.save(overlay_path)
    diff = ImageChops.difference(a, b).convert("RGB")
    heat_path = out_dir / f"{current.stem}-diff.png"
    ImageEnhance.Contrast(diff).enhance(3.0).save(heat_path)
    hist = diff.histogram()
    total = a.size[0] * a.size[1] * 3 * 255
    absolute = sum((index % 256) * count for index, count in enumerate(hist))
    return {
        "overlay": str(overlay_path),
        "diff": str(heat_path),
        "normalized_absolute_difference": absolute / total if total else 0.0,
    }


def capture(workspace: str, output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    _prepare_qt(scale)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_shell import FoundationFixtureWindow

    app = QApplication.instance() or QApplication([])
    window = FoundationFixtureWindow(workspace)
    window.resize(width, height)
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(180, loop.quit)
    loop.exec()
    app.processEvents()
    pix = window.grab()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not pix.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot: {output}")
    geometry = {
        "window": [window.width(), window.height()],
        "command_bottom": window.shell.command_bar.geometry().bottom(),
        "nav_right": window.shell.navigation.geometry().right(),
        "right_dock_width": window.shell.inspector.width(),
        "timeline_height": window.shell.timeline.height(),
        "status_height": window.shell.status_bar.height(),
        "workspace": workspace,
        "scale": scale,
    }
    window.close()
    return geometry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture deterministic STEP 01 foundation screenshot")
    parser.add_argument("--workspace", default="home")
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1672)
    parser.add_argument("--height", type=int, default=941)
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--golden")
    parser.add_argument("--report")
    ns = parser.parse_args(argv)
    output = Path(ns.output)
    geometry = capture(ns.workspace, output, ns.width, ns.height, ns.scale)
    result: dict[str, object] = {"current": str(output), "geometry": geometry}
    if ns.golden:
        result.update(_difference(output, Path(ns.golden), output.parent))
    if ns.report:
        path = Path(ns.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
