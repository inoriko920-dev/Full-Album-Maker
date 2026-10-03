from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .render_center_model_step10 import RenderJob, RenderJobState

_installed = False
_original_apply_queue = None


def install_step10_queue_presentation() -> None:
    """Extend the recovered queue list with recent terminal evidence.

    Queue scheduling/state ownership remains in RenderQueue. This presentation
    layer only adds the newest VERIFIED completed attempt to the central list so
    the Render Center can show Running + Queued + Completed together, matching
    the STEP10 golden contract without treating terminal history as queued work.
    """

    global _installed, _original_apply_queue
    if _installed:
        return

    from .render_workspace_step10 import RenderCenterWorkspace

    _original_apply_queue = RenderCenterWorkspace.apply_queue

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

    RenderCenterWorkspace.apply_queue = apply_queue_with_recent
    _installed = True
