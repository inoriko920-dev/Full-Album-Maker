from __future__ import annotations

"""Presentation-only UI-08 refinement for the central AI Agent task surface.

The AgentPlan, preview commands, permissions and execution state remain authoritative.
This module only reorganizes existing widgets so the plan/scope/impact area reads as
one compact task card instead of several stacked cards.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .foundation_components import FAMCard

_installed = False


def install_post_release_ai_task_surface() -> None:
    global _installed
    if _installed:
        return

    from .ai_workspace_step09 import AITaskCanvas

    original_init = AITaskCanvas.__init__
    original_render_plan = AITaskCanvas._render_plan
    original_render_impact = AITaskCanvas._render_impact

    def adjusted_init(self, *args, **kwargs) -> None:
        original_init(self, *args, **kwargs)

        # Re-use the production widgets; only move them into a denser two-column
        # presentation matching the approved AI Agent reference.
        for widget in (self.plan_host, self.scope_card, self.impact_card):
            self.body_layout.removeWidget(widget)

        details = QWidget(self.body)
        details.setObjectName("postReleaseAiTaskDetails")
        details_row = QHBoxLayout(details)
        details_row.setContentsMargins(0, 0, 0, 0)
        details_row.setSpacing(10)

        plan_card = FAMCard(details)
        plan_box = QVBoxLayout(plan_card)
        plan_box.setContentsMargins(10, 8, 10, 8)
        plan_box.setSpacing(5)
        plan_header = QHBoxLayout()
        plan_title = QLabel("✓  Interpretasi Tugas")
        plan_title.setObjectName("sectionHeading")
        plan_header.addWidget(plan_title)
        plan_header.addStretch(1)
        self._post_release_plan_state = QLabel("Siap Dijalankan")
        self._post_release_plan_state.setObjectName("statusChip")
        self._post_release_plan_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._post_release_plan_state.setContentsMargins(8, 2, 8, 2)
        plan_header.addWidget(self._post_release_plan_state)
        plan_box.addLayout(plan_header)
        plan_box.addWidget(self.plan_host, 1)
        details_row.addWidget(plan_card, 3)

        right = QWidget(details)
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(8)
        right_box.addWidget(self.scope_card, 3)
        right_box.addWidget(self.impact_card, 2)
        details_row.addWidget(right, 2)

        self.body_layout.insertWidget(2, details)
        self._post_release_task_details = details

        # Compact the old stacked-card visuals inside the new parent card.
        self.plan_host.layout().setSpacing(2)
        self.user_card.setStyleSheet(
            "QFrame#famCard{background:#FFFFFF;border:1px solid #D9E4F2;border-radius:9px;}"
        )
        self.ai_card.setStyleSheet(
            "QFrame#famCard{background:#FFFFFF;border:1px solid #D9E4F2;border-radius:9px;}"
        )
        self.scope_card.setStyleSheet(
            "QFrame#famCard{background:#F8FBFF;border:1px solid #D9E7F7;border-radius:8px;}"
        )
        self.impact_card.setStyleSheet(
            "QFrame#famCard{background:#F1FBF7;border:1px solid #CFEFE2;border-radius:8px;}"
        )

        for label in self.scope_card.findChildren(QLabel):
            if label.text().strip() == "Ruang Lingkup":
                label.setText("Ruang Lingkup yang Digunakan")
        self.impact_text.hide()

        stats = QWidget(self.impact_card)
        stats_row = QHBoxLayout(stats)
        stats_row.setContentsMargins(0, 2, 0, 0)
        stats_row.setSpacing(4)
        self._post_release_impact_stats = []
        for text in ("0\nLagu", "0\nVisual", "—\nTimeline"):
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                "font-weight:700;color:#10234A;padding:4px 2px;"
                "border-right:1px solid #D7EAE2;"
            )
            stats_row.addWidget(label, 1)
            self._post_release_impact_stats.append(label)
        self.impact_card.layout().addWidget(stats)

        # The compact task card now fits without a persistent scrollbar.
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def render_plan(self, plan) -> None:
        original_render_plan(self, plan)
        if hasattr(self, "_post_release_plan_state"):
            self._post_release_plan_state.setVisible(plan is not None)

        if plan is None:
            return

        # Flatten the individual production plan rows inside the enclosing card.
        for frame in self.plan_host.findChildren(QFrame, options=Qt.FindChildOption.FindDirectChildrenOnly):
            frame.setStyleSheet("QFrame#famCard{background:transparent;border:none;border-radius:0px;}")
            layout = frame.layout()
            if layout is not None:
                layout.setContentsMargins(4, 3, 4, 3)

        visual_count = sum(1 for action in plan.actions if action.name == "set_song_visual")
        speed_action = next((action for action in plan.actions if action.name == "set_song_video_speed"), None)
        auto_arrange = any(action.name == "auto_arrange_timeline" for action in plan.actions)
        scope_lines = [
            f"🎵  {len(plan.scope_song_ids)} lagu dipilih",
            f"▣  {visual_count} visual disiapkan" if visual_count else "▣  Visual dari media project",
        ]
        if speed_action is not None:
            scope_lines.append(f"◴  Slowmo {speed_action.args.get('speed')}x")
        if auto_arrange:
            scope_lines.append("☷  Auto Susun timeline")
        self.scope_text.setText("\n".join(scope_lines))
        self.scope_text.setStyleSheet("color:#2468C8;line-height:1.35;")

    def render_impact(self, preview) -> None:
        original_render_impact(self, preview)
        labels = getattr(self, "_post_release_impact_stats", ())
        if len(labels) != 3:
            return
        if preview is None:
            labels[0].setText("0\nLagu")
            labels[1].setText("0\nVisual")
            labels[2].setText("—\nTimeline")
            return
        impact = preview.impact
        labels[0].setText(f"{len(impact.changed_song_ids)}\nLagu dipilih")
        labels[1].setText(f"{len(impact.changed_layer_ids)}\nLayer berubah")
        labels[2].setText("Siap\nTimeline" if preview.has_changes else "Tetap\nTimeline")

    AITaskCanvas.__init__ = adjusted_init
    AITaskCanvas._render_plan = render_plan
    AITaskCanvas._render_impact = render_impact
    _installed = True
