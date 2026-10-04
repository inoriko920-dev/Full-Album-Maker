from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .foundation_tokens import TOKENS


def _prepare_qt(scale: float) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["QT_SCALE_FACTOR"] = str(scale)
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")


def _difference(current: Path, golden: Path, out_dir: Path) -> dict[str, object]:
    from PIL import Image, ImageChops, ImageEnhance

    a = Image.open(current).convert("RGBA")
    b = Image.open(golden).convert("RGBA")
    if a.size != b.size:
        raise ValueError(
            f"Golden size {b.size} tidak sama dengan current {a.size}; "
            "golden tidak boleh di-resize untuk membuat hasil terlihat cocok."
        )
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


def _logical_viewport_image(client_pixmap, width: int, height: int, scale: float):
    """Return an exact logical viewport at 100% without rescaling pixels."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor, QImage, QPainter

    source = client_pixmap.toImage()
    source.setDevicePixelRatio(1.0)
    if abs(float(scale) - 1.0) > 1e-9:
        return source
    target = QImage(
        int(width),
        int(height),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    target.setDevicePixelRatio(1.0)
    target.fill(QColor(TOKENS.app_bg))
    painter = QPainter(target)
    painter.drawImage(QPoint(0, 0), source)
    painter.end()
    return target


def _compose_native_title_preview(client_source, title_height_logical: int, scale: float):
    """Add deterministic native-title evidence above the captured Qt client."""
    from PySide6.QtCore import QRect, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
    from PySide6.QtWidgets import QApplication

    client = client_source.toImage() if hasattr(client_source, "toImage") else client_source
    client.setDevicePixelRatio(1.0)
    title_px = max(1, int(round(title_height_logical * scale)))
    width_px = client.width()
    canvas = QImage(
        width_px,
        client.height() + title_px,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    canvas.setDevicePixelRatio(1.0)
    canvas.fill(QColor("#F8FBFF"))

    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.fillRect(QRect(0, 0, width_px, title_px), QColor("#F8FBFF"))
    p.setPen(QPen(QColor(TOKENS.border), max(1, int(round(scale)))))
    p.drawLine(0, title_px - 1, width_px, title_px - 1)

    base_font = QApplication.instance().font() if QApplication.instance() is not None else QFont()
    family = base_font.family()
    pad = max(8, int(round(13 * scale)))
    logo = max(14, int(round(18 * scale)))
    logo_y = max(4, (title_px - logo) // 2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(TOKENS.primary_600))
    p.drawRoundedRect(QRectF(pad, logo_y, logo, logo), 3 * scale, 3 * scale)
    p.setPen(QColor("#FFFFFF"))
    icon_font = QFont(family)
    icon_font.setPixelSize(max(8, int(round(10 * scale))))
    icon_font.setBold(True)
    p.setFont(icon_font)
    p.drawText(QRectF(pad, logo_y, logo, logo), Qt.AlignmentFlag.AlignCenter, "▶")

    title_font = QFont(family)
    title_font.setPixelSize(max(10, int(round(12 * scale))))
    title_font.setWeight(QFont.Weight.DemiBold)
    p.setFont(title_font)
    p.setPen(QColor(TOKENS.text_primary))
    title_x = pad + logo + max(7, int(round(8 * scale)))
    p.drawText(
        QRectF(title_x, 0, max(160, int(round(240 * scale))), title_px),
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
        "Full Album Maker",
    )

    control_w = max(34, int(round(42 * scale)))
    control_font = QFont(family)
    control_font.setPixelSize(max(9, int(round(11 * scale))))
    p.setFont(control_font)
    p.setPen(QColor("#53627A"))
    for offset, symbol in enumerate(("−", "□", "×")):
        x = width_px - control_w * (3 - offset)
        p.drawText(QRectF(x, 0, control_w, title_px), Qt.AlignmentFlag.AlignCenter, symbol)

    p.drawImage(QRect(0, title_px, client.width(), client.height()), client)
    p.end()
    return canvas


def capture(workspace: str, output: Path, width: int, height: int, scale: float) -> dict[str, object]:
    _prepare_qt(scale)
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication

    from .foundation_font import install_foundation_font
    from .foundation_shell import FoundationFixtureWindow

    app = QApplication.instance() or QApplication([])
    font_family = install_foundation_font(app)
    client_height = max(320, height - TOKENS.title_height)
    window = FoundationFixtureWindow(workspace)
    window.resize(width, client_height)
    window.shell.set_compact_mode(width < TOKENS.compact_breakpoint)
    window.show()
    loop = QEventLoop()
    QTimer.singleShot(180, loop.quit)
    loop.exec()
    app.processEvents()

    raw = window.grab()
    client = _logical_viewport_image(raw, width, client_height, scale)
    framed = _compose_native_title_preview(client, TOKENS.title_height, scale)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not framed.save(str(output), "PNG"):
        raise RuntimeError(f"Gagal menyimpan screenshot: {output}")

    geometry = {
        "window": [width, height],
        "title_bottom": TOKENS.title_height - 1,
        "command_bottom": TOKENS.title_height + window.shell.command_bar.geometry().bottom(),
        "nav_right": window.shell.navigation.geometry().right(),
        "right_dock_width": window.shell.inspector.width(),
        "timeline_height": window.shell.timeline.height(),
        "status_height": window.shell.status_bar.height(),
        "workspace": workspace,
        "scale": scale,
        "font_family": font_family,
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
