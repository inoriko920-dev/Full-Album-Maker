from __future__ import annotations

"""Presentation-only metadata labels for UI-06 Template cards.

Filter/search semantics continue to use TemplateStudioDescriptor.categories and
ratios. This layer only replaces the small subtitle shown under cards, matching
the approved UI language while avoiding the duplicate 16:9 label that is already
rendered as a thumbnail badge. Custom templates surface their real saved
description when available instead of collapsing every custom card to the generic
"Modern" category.
"""

from PySide6.QtWidgets import QLabel

from .template_studio_step07 import ORIGIN_CUSTOM

_installed = False

_PRESENTATION_SUBTITLE = {
    "spotify_clean": "Cinematic • Emosional",
    "cafe_acoustic": "Travel • Modern",
    "viral_full_album": "Travel • Cerita",
    "vinyl_nostalgia": "Romantis • Hangat",
    "neon_spectrum": "Romantis • Minimalis",
    "romantic_bokeh": "Keluarga • Klasik",
    "dark_cinematic": "Cinematic • Dramatis",
    "photo_album": "Minimalis • Modern",
    "cassette_retro": "Klasik • Retro",
    "music_channel_pro": "Modern • Profesional",
}


def _display_subtitle(descriptor) -> str:
    if descriptor.origin == ORIGIN_CUSTOM:
        description = " ".join(str(descriptor.description or "").split()).strip()
        if description:
            return description
    return _PRESENTATION_SUBTITLE.get(
        descriptor.template_id,
        " • ".join(descriptor.categories[:2]),
    )


def _replace_subtitle(card, descriptor) -> None:
    target = None
    old_prefix = " • ".join(descriptor.categories[:2])
    for label in card.findChildren(QLabel):
        text = label.text().strip()
        if text.startswith(old_prefix) and descriptor.ratios[0] in text:
            target = label
            break
    if target is None:
        # Fallback: metadata label containing the ratio but not the overlay ratio
        # badge (which is parented under the thumbnail).
        for label in card.findChildren(QLabel):
            if label.parentWidget() is card and descriptor.ratios[0] in label.text():
                target = label
                break
    if target is not None:
        target.setText(_display_subtitle(descriptor))


def install_post_release_template_card_metadata() -> None:
    global _installed
    if _installed:
        return

    from .template_workspace_step07 import TemplateCard

    previous_init = TemplateCard.__init__

    def wrapped_init(self, descriptor, *args, **kwargs) -> None:
        previous_init(self, descriptor, *args, **kwargs)
        _replace_subtitle(self, descriptor)

    TemplateCard.__init__ = wrapped_init
    _installed = True
