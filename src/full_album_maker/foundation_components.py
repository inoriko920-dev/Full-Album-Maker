from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS


def set_dynamic_property(widget: QWidget, name: str, value: object) -> None:
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class FAMButton(QPushButton):
    def __init__(self, text: str = "", *, icon_name: str | None = None, kind: str = "secondary", parent=None) -> None:
        super().__init__(text, parent)
        set_dynamic_property(self, "kind", kind)
        if icon_name:
            self.setIcon(foundation_icon(icon_name, size=TOKENS.icon_inline))
            self.setIconSize(QSize(TOKENS.icon_inline, TOKENS.icon_inline))
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class FAMIconButton(FAMButton):
    def __init__(self, icon_name: str, tooltip: str, *, parent=None) -> None:
        super().__init__("", icon_name=icon_name, kind="ghost", parent=parent)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setFixedWidth(36)


class FAMCard(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("famCard")


class FAMPanel(FAMCard):
    pass


class FAMInput(QLineEdit):
    pass


class FAMCombo(QComboBox):
    pass


class FAMStatusChip(QLabel):
    def __init__(self, text: str = "", status: str = "neutral", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("statusChip")
        self.set_status(status)

    def set_status(self, status: str) -> None:
        set_dynamic_property(self, "status", status)


class FAMSectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TOKENS.space_2)
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("sectionHeading")
        box.addWidget(self.title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("muted")
            box.addWidget(sub)
        row.addLayout(box)
        row.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setContentsMargins(0, 0, 0, 0)
        self.actions.setSpacing(TOKENS.space_1)
        row.addLayout(self.actions)


class FAMEmptyState(QFrame):
    def __init__(self, title: str, description: str, action_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(TOKENS.space_4, TOKENS.space_4, TOKENS.space_4, TOKENS.space_4)
        lay.setSpacing(TOKENS.space_2)
        lay.addStretch(1)
        heading = QLabel(title)
        heading.setObjectName("sectionHeading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(heading)
        body = QLabel(description)
        body.setObjectName("muted")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        lay.addWidget(body)
        self.action = None
        if action_text:
            self.action = FAMButton(action_text)
            lay.addWidget(self.action, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)


class FAMDockHeader(QWidget):
    def __init__(self, title: str, *, collapsible: bool = True, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, TOKENS.space_1, TOKENS.space_2, TOKENS.space_1)
        row.setSpacing(TOKENS.space_2)
        self.title = QLabel(title)
        self.title.setObjectName("sectionHeading")
        row.addWidget(self.title)
        row.addStretch(1)
        self.collapse_button = FAMIconButton("collapse", "Ciutkan panel") if collapsible else None
        if self.collapse_button:
            row.addWidget(self.collapse_button)


class FAMSegmented(QWidget):
    def __init__(self, options: list[tuple[str, str]], parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        for index, (value, label) in enumerate(options):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setObjectName("tabButton")
            button.setChecked(index == 0)
            self._buttons[value] = button
            row.addWidget(button)

    def checked_value(self) -> str:
        return next((value for value, button in self._buttons.items() if button.isChecked()), "")


class FAMToastBanner(QFrame):
    def __init__(self, text: str = "", *, status: str = "neutral", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("famCard")
        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_3, TOKENS.space_2, TOKENS.space_3, TOKENS.space_2)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        row.addWidget(self.label, 1)
        self.status = status


class TabbedEmptyHost(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        tabs = QHBoxLayout()
        tabs.setContentsMargins(TOKENS.space_2, 0, TOKENS.space_2, 0)
        tabs.setSpacing(TOKENS.space_1)
        self.properties = QPushButton("Properti")
        self.properties.setObjectName("tabButton")
        self.properties.setCheckable(True)
        self.properties.setChecked(True)
        self.ai = QPushButton("AI")
        self.ai.setObjectName("tabButton")
        self.ai.setCheckable(True)
        tabs.addWidget(self.properties)
        tabs.addWidget(self.ai)
        tabs.addStretch(1)
        lay.addLayout(tabs)
        self.stack = QStackedWidget()
        self._properties_widget = FAMEmptyState("Belum ada pilihan", "Pilih objek di workspace untuk melihat properti.")
        self._ai_widget = FAMEmptyState("AI opsional", "AI belum dikonfigurasi. Editing manual tetap tersedia.")
        self.stack.addWidget(self._properties_widget)
        self.stack.addWidget(self._ai_widget)
        lay.addWidget(self.stack, 1)
        self.properties.clicked.connect(lambda: self._select(0))
        self.ai.clicked.connect(lambda: self._select(1))

    def _replace_page(self, index: int, widget: QWidget) -> None:
        old = self.stack.widget(index)
        self.stack.removeWidget(old)
        old.setParent(None)
        self.stack.insertWidget(index, widget)
        if index == 0:
            self._properties_widget = widget
        else:
            self._ai_widget = widget

    def set_properties_widget(self, widget: QWidget) -> None:
        self._replace_page(0, widget)
        self._select(0)

    def set_ai_widget(self, widget: QWidget) -> None:
        self._replace_page(1, widget)

    def _select(self, index: int) -> None:
        self.properties.setChecked(index == 0)
        self.ai.setChecked(index == 1)
        self.stack.setCurrentIndex(index)
