from __future__ import annotations

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from .paths import asset_path


def install_foundation_font(app: QApplication | None = None) -> str:
    """Install the portable Noto Sans font when present, else use Qt system font.

    The Windows portable build already supplies ``assets/fonts/NotoSans.ttf``.
    Source/dev runs remain functional without that optional file, while visual QA
    can stage the same pinned build asset before capture for deterministic glyphs.
    """

    app = app or QApplication.instance()
    if app is None:
        return ""

    family = ""
    font_path = asset_path("fonts/NotoSans.ttf")
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                family = families[0]

    if not family:
        family = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()

    if family:
        font = QFont(family)
        font.setPointSizeF(9.75)
        app.setFont(font)
    return family
