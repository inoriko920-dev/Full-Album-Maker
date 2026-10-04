from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .render_center_model_step10 import RenderJob, RenderJobState
from .render_preflight_step10 import PreflightLevel, PreflightReport

_installed = False
_original_init = None
_original_apply_queue = None


def install_step10_queue_presentation() -> None:
    """Align Render Center presentation with the STEP10 golden contract.

    This layer changes presentation only:
    - engine preflight still evaluates snapshot/timeline/media/ffmpeg/encoder/output/disk;
    - the golden card surface exposes Timeline, Media, FFmpeg, Output, Disk;
    - encoder capability remains enforced by preflight and inspector settings;
    - the newest VERIFIED completion is shown next to active/queued jobs without
      being reclassified as queued work.
    """

    global _installed, _original_init, _original_apply_queue
    if _installed:
        return

    from .render_workspace_step10 import RenderCenterWorkspace

    _original_init = RenderCenterWorkspace.__init__
    _original_apply_queue = RenderCenterWorkspace.apply_queue

    def wrapped_init(self, *args, **kwargs) -> None:
        _original_init(self, *args, **kwargs)
        timeline_card = self.preflight_cards.get("snapshot")
        if timeline_card is not None:
            timeline_card.title.setText("Timeline Valid")
        encoder_card = self.preflight_cards.get("encoder")
        if encoder_card is not None:
            encoder_card.hide()

    def apply_preflight_golden(self, report: PreflightReport) -> None:
        by_key = {check.key: check for check in report.checks}
        mapping = {
            "snapshot": "timeline",
            "media": "media",
            "ffmpeg": "ffmpeg",
            "disk": "disk",
        }
        for card_key, check_key in mapping.items():
            card = self.preflight_cards.get(card_key)
            check = by_key.get(check_key)
            if card is not None and check is not None:
                card.set_check(check.level, check.message)

        output_card = self.preflight_cards.get("output")
        output_values = [
            item
            for name, item in by_key.items()
            if name in {"output", "output_source"}
        ]
        if output_card is not None and output_values:
            level = (
                PreflightLevel.BLOCK
                if any(item.level == PreflightLevel.BLOCK for item in output_values)
                else PreflightLevel.WARN
                if any(item.level == PreflightLevel.WARN for item in output_values)
                else PreflightLevel.PASS
            )
            output_card.set_check(
                level,
                " • ".join(item.message for item in output_values),
            )

        self.snapshot_label.setText(
            "Snapshot: " + (report.snapshot.snapshot_hash[:12] if report.snapshot else "BLOCKED")
        )

    def apply_queue_with_recent(self, jobs: Iterable[RenderJob]) -> None:
        items = tuple(jobs)
        _original_apply_queue(self, items)
        completed = [
            job
            for job in items
            if job.state == RenderJobState.COMPLETED and bool(job.verified_output)
        ]
        if completed:
            job = completed[-1]
            self.queue_list.addItem(
                f"{Path(job.settings.final_output).name}  •  COMPLETED VERIFIED  •  100%"
            )

    RenderCenterWorkspace.__init__ = wrapped_init
    RenderCenterWorkspace.apply_preflight = apply_preflight_golden
    RenderCenterWorkspace.apply_queue = apply_queue_with_recent
    _installed = True
