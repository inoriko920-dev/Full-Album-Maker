from __future__ import annotations

"""Presentation-only two-column arrangement for STEP09 plan preview.

The existing PlanCard, scope and impact widgets are reused verbatim. This layer
only moves them into the two-column hierarchy shown by the approved UI-08
reference; AgentPlan content, dry-run commands, permissions and execution are
untouched.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .foundation_components import FAMCard

_installed = False


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionHeading")
    return label


def install_post_release_ai_plan_layout_adjustment() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AITaskCanvas

    original_init = AITaskCanvas.__init__

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)

        body = self.body_layout
        body.removeWidget(self.plan_host)
        body.removeWidget(self.scope_card)
        body.removeWidget(self.impact_card)

        plan_shell = QWidget()
        row = QHBoxLayout(plan_shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        task_card = FAMCard()
        task_layout = QVBoxLayout(task_card)
        task_layout.setContentsMargins(9, 8, 9, 8)
        task_layout.setSpacing(6)
        task_layout.addWidget(_heading("Interpretasi Tugas"))
        task_layout.addWidget(self.plan_host, 1)
        row.addWidget(task_card, 56)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(8)
        side_layout.addWidget(self.scope_card)
        side_layout.addWidget(self.impact_card)
        side_layout.addStretch(1)
        row.addWidget(side, 44)

        # Insert immediately after the AI interpretation bubble.
        body.insertWidget(2, plan_shell)
        self._post_release_plan_shell = plan_shell
        self._post_release_task_card = task_card

    AITaskCanvas.__init__ = adjusted_init
    _installed = True
