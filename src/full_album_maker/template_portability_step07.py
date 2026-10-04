from __future__ import annotations

from typing import Iterable

from .custom_template_builder import (
    CustomTemplate,
    CustomTemplateStore,
    capture_custom_template,
)
from .editor_models import ProjectDocument
from .template_studio_step07 import TemplateStudioDraft, preview_template_document


def portable_template_source(document: ProjectDocument) -> ProjectDocument:
    """Sanitize a clone before CustomTemplate capture.

    Recovered built-ins/projects may use a current-project image/video as a
    background. Reusable Custom Templates intentionally reject project-bound
    asset references. Capture therefore degrades only those background layers
    to a deterministic solid fallback on a clone; it never weakens the
    recovered CustomTemplate validation and never mutates the project.
    """

    clone = document.clone()
    for layer in clone.layers:
        if not layer.asset_refs:
            continue
        if layer.type == "song_cover":
            # Recovered custom builder converts this to a target-project fallback.
            continue
        if layer.type != "background":
            raise ValueError(
                f"Layer '{layer.name}' masih bergantung pada asset project dan tidak dapat disimpan secara portabel."
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


def create_portable_custom_from_document(
    document: ProjectDocument,
    *,
    label: str,
    description: str = "",
    store: CustomTemplateStore | None = None,
) -> CustomTemplate:
    source = portable_template_source(document)
    item = capture_custom_template(source, label=label, description=description)
    (store or CustomTemplateStore()).save(item)
    return item


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
    portable_source = portable_template_source(preview)
    copied = capture_custom_template(
        portable_source,
        label=label,
        description=description,
    )
    (store or CustomTemplateStore()).save(copied)
    return copied


def save_custom_draft(
    document: ProjectDocument,
    draft: TemplateStudioDraft,
    target_song_ids: Iterable[str],
    *,
    existing: CustomTemplate,
    store: CustomTemplateStore | None = None,
) -> CustomTemplate:
    existing.validate()
    preview = preview_template_document(
        document,
        draft,
        target_song_ids,
        custom_template=existing,
    )
    portable_source = portable_template_source(preview)
    updated = capture_custom_template(
        portable_source,
        label=existing.label,
        description=existing.description,
        template_id=existing.template_id,
    )
    (store or CustomTemplateStore()).save(updated)
    return updated
