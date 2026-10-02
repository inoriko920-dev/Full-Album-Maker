from __future__ import annotations

from copy import deepcopy
from typing import Iterable

from .custom_template_builder import (
    CustomTemplate,
    CustomTemplateStore,
    capture_custom_template,
)
from .editor_models import ProjectDocument
from .template_studio_step07 import TemplateStudioDraft, preview_template_document


def _portable_duplicate_source(document: ProjectDocument) -> ProjectDocument:
    """Sanitize a disposable preview before CustomTemplate capture.

    Recovered built-ins are allowed to use a current-project image/video as a
    dynamic album background. Reusable Custom Templates intentionally reject
    such project-bound asset references. Duplication therefore degrades only
    those background layers to a deterministic solid fallback on the clone;
    it never weakens CustomTemplate validation and never mutates the project.
    """

    clone = document.clone()
    for layer in clone.layers:
        if not layer.asset_refs:
            continue
        if layer.type == "song_cover":
            # Recovered custom builder already converts this to a target-project
            # fallback image, so the semantic cover layer is portable.
            continue
        if layer.type != "background":
            raise ValueError(
                f"Layer '{layer.name}' masih bergantung pada asset project dan tidak dapat diduplikat secara portabel."
            )
        props = dict(layer.properties)
        color = str(props.get("color") or clone.canvas.background_color or "#101114")
        layer.properties = {
            "mode": "solid",
            "color": color,
            "playback": "loop",
            "motion": "static",
            "template_id": str(props.get("template_id", "")),
        }
        layer.asset_refs = []
    clone.validate()
    return clone


def duplicate_portable_template(
    document: ProjectDocument,
    draft: TemplateStudioDraft,
    target_song_ids: Iterable[str],
    *,
    label: str,
    description: str = "",
    store: CustomTemplateStore | None = None,
    source_custom: CustomTemplate | None = None,
) -> CustomTemplate:
    preview = preview_template_document(
        document,
        draft,
        target_song_ids,
        custom_template=source_custom,
    )
    portable_source = _portable_duplicate_source(preview)
    copied = capture_custom_template(
        portable_source,
        label=label,
        description=description,
    )
    (store or CustomTemplateStore()).save(copied)
    return copied
