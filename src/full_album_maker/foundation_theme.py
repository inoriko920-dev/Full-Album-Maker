from __future__ import annotations

from .foundation_tokens import TOKENS


def foundation_stylesheet() -> str:
    t = TOKENS
    return f"""
* {{
    /* Do not force a missing font family here. Qt/Windows must use the
       framework/system general font unless a bundled application font is
       explicitly registered by the portable build. This prevents tofu boxes
       on Windows offscreen/native font backends. */
    font-size: 13px;
    color: {t.text_primary};
}}
QMainWindow, QDialog, QWidget#foundationRoot {{
    background: {t.app_bg};
}}
QToolTip {{
    background: {t.text_primary};
    color: {t.surface};
    border: 1px solid {t.text_primary};
    padding: 5px 7px;
}}
QFrame#globalCommandBar, QFrame#workspaceNavigation, QFrame#contextHost,
QFrame#workspaceHost, QFrame#inspectorDock, QFrame#timelineDock, QFrame#appStatusBar {{
    background: {t.surface};
    border: 1px solid {t.border};
}}
QFrame#globalCommandBar {{ border-left: none; border-right: none; border-top: none; }}
QFrame#workspaceNavigation {{ border-left: none; border-top: none; border-bottom: none; background: #F8FBFF; }}
QFrame#contextHost, QFrame#workspaceHost, QFrame#inspectorDock {{ border-top: none; border-bottom: none; }}
QFrame#timelineDock {{ border-left: none; border-right: none; }}
QFrame#appStatusBar {{ border-left: none; border-right: none; border-bottom: none; }}
/* Production uses the native Windows title bar for the app name. Keep this
   spacer so the first global command aligns with the golden references, but
   do not render a duplicate title inside the command row. */
QLabel#appName {{
    min-width: 168px;
    max-width: 168px;
    font-size: 16px;
    font-weight: 650;
    color: transparent;
}}
QLabel#workspaceHeading {{ font-size: 26px; font-weight: 750; color: {t.text_primary}; }}
QLabel#sectionHeading {{ font-size: 16px; font-weight: 650; color: {t.text_primary}; }}
QLabel#muted, QLabel#metadata {{ color: {t.text_muted}; }}
QLabel#metadata {{ font-size: 12px; }}
QPushButton, QToolButton {{
    min-height: 34px;
    padding: 3px 10px;
    border: 1px solid {t.border};
    border-radius: {t.radius_control}px;
    background: {t.surface};
    color: {t.text_primary};
}}
QPushButton:hover, QToolButton:hover {{ background: #F1F7FF; border-color: #B9D2F2; }}
QPushButton:pressed, QToolButton:pressed {{ background: #E4EFFC; }}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus {{ border: 2px solid {t.accent_500}; }}
QPushButton:disabled, QToolButton:disabled {{ color: #97A2B2; background: #F4F6F9; border-color: #E3E9F1; }}
QPushButton[kind="primary"] {{
    min-height: 36px;
    background: {t.primary_600};
    border-color: {t.primary_600};
    color: {t.surface};
    font-weight: 650;
}}
QPushButton[kind="primary"]:hover {{ background: #0F59CE; border-color: #0F59CE; }}
QPushButton[kind="primary"]:pressed {{ background: #0D4FB6; }}
QPushButton[kind="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton#navButton {{
    min-height: 48px;
    text-align: left;
    padding: 3px 11px;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: {t.text_primary};
    font-weight: 520;
}}
QPushButton#navButton:hover {{ background: #F3F8FF; }}
QPushButton#navButton:checked {{
    background: {t.selection_soft};
    color: {t.primary_600};
    border-left: 3px solid {t.primary_600};
    font-weight: 650;
}}
QPushButton#tabButton {{
    min-height: 37px;
    min-width: 78px;
    padding-left: 12px;
    padding-right: 12px;
    border-radius: 0px;
    border: none;
    border-bottom: 2px solid transparent;
    background: transparent;
}}
QPushButton#tabButton:checked {{ color: {t.primary_600}; border-bottom: 2px solid {t.primary_600}; font-weight: 650; }}
QFrame#famCard {{ background: {t.surface}; border: 1px solid {t.border}; border-radius: {t.radius_card}px; }}
QFrame#emptyState {{ background: #FBFDFF; border: 1px dashed #C7D8EC; border-radius: {t.radius_card}px; }}
QLabel#statusChip {{
    padding: 3px 7px;
    border: 1px solid {t.border};
    border-radius: 8px;
    background: #F8FBFF;
    color: {t.text_muted};
}}
QLabel#statusChip[status="success"] {{ color: #187A43; background: #EEFAF3; border-color: #BCE8CE; }}
QLabel#statusChip[status="warning"] {{ color: #966A00; background: #FFF8E6; border-color: #F2D58C; }}
QLabel#statusChip[status="error"] {{ color: #A93232; background: #FFF0F0; border-color: #EDB8B8; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    min-height: 34px;
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: {t.radius_control}px;
    padding: 3px 8px;
    selection-background-color: {t.selection_soft};
    selection-color: {t.text_primary};
}}
QSplitter::handle {{ background: #EDF3FA; }}
QSplitter::handle:hover {{ background: #C9DDF5; }}
QScrollBar:vertical {{ width: 9px; background: transparent; }}
QScrollBar::handle:vertical {{ min-height: 28px; border-radius: 4px; background: #C9D7E8; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ height: 9px; background: transparent; }}
QScrollBar::handle:horizontal {{ min-width: 28px; border-radius: 4px; background: #C9D7E8; }}
"""


FOUNDATION_STYLE = foundation_stylesheet()
