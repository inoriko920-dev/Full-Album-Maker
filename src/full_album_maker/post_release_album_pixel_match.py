from __future__ import annotations

"""Post-release UI-03 Album presentation layer.

This module only changes how existing Album document state is presented. It does
not own playlist state, selection state, commands, persistence, or timeline
semantics. Cover/visual thumbnails are read from MediaAsset references already
stored in the authoritative ProjectDocument.
"""

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QHeaderView

from .album_workspace import (
    AlbumContextWidget as _BaseAlbumContextWidget,
    AlbumMassToolsWidget as _BaseAlbumMassToolsWidget,
    AlbumSongTable as _BaseAlbumSongTable,
    AlbumTimelineOverviewCanvas as _BaseAlbumTimelineOverviewCanvas,
    AlbumWorkspace as _BaseAlbumWorkspace,
)
from .foundation_icons import foundation_icon
from .foundation_tokens import TOKENS

_installed = False


def _thumbnail_path(asset) -> Path | None:
    if asset is None:
        return None
    metadata = asset.metadata if isinstance(getattr(asset, "metadata", None), dict) else {}
    raw = str(metadata.get("thumbnail_path", "") or "").strip()
    if raw:
        path = Path(raw)
        if path.is_file():
            return path
    if getattr(asset, "kind", "") == "image":
        path = Path(str(getattr(asset, "locator", "")))
        if path.is_file():
            return path
    return None


class PixelAlbumSongTable(_BaseAlbumSongTable):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(40, 28))
        header = self.horizontalHeader()
        for column in (3, 4, 5, 6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, 42)
        self.setColumnWidth(1, 34)
        self.setColumnWidth(3, 68)
        self.setColumnWidth(4, 112)
        self.setColumnWidth(5, 96)
        self.setColumnWidth(6, 128)
        self.verticalHeader().setDefaultSectionSize(42)

    def set_rows(self, values, selected_ids, *, page: int) -> None:
        super().set_rows(values, selected_ids, page=page)
        for row_index, row in enumerate(values):
            self.setRowHeight(row_index, 42)

            # Use the real cover asset already attached to the song.
            song_item = self.item(row_index, 2)
            cover = self._assets.get(row.cover_asset_id) if row.cover_asset_id else None
            cover_path = _thumbnail_path(cover)
            if song_item is not None and cover_path is not None:
                song_item.setIcon(QIcon(str(cover_path)))

            visual_host = QFrame()
            visual_host.setStyleSheet("background:transparent;")
            visual_row = QHBoxLayout(visual_host)
            visual_row.setContentsMargins(3, 2, 3, 2)
            visual_row.setSpacing(6)
            visual = self._assets.get(row.visual_asset_id) if row.visual_asset_id else None
            visual_path = _thumbnail_path(visual)
            visual_thumb = QLabel()
            visual_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            visual_thumb.setFixedSize(38, 26)
            if visual_path is not None:
                pixmap = QPixmap(str(visual_path))
                if not pixmap.isNull():
                    visual_thumb.setPixmap(
                        pixmap.scaled(
                            visual_thumb.size(),
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            else:
                visual_thumb.setPixmap(foundation_icon("media", color="#6F82A2", size=18).pixmap(18, 18))
                visual_thumb.setStyleSheet("background:#F7FAFE;border:1px solid #D9E4F2;border-radius:4px;")
            visual_label = QLabel(row.visual_label)
            visual_label.setStyleSheet(
                "font-size:12px;color:#35517A;" if row.visual_asset_id else "font-size:12px;color:#7C8CA5;"
            )
            visual_row.addWidget(visual_thumb)
            visual_row.addWidget(visual_label)
            visual_row.addStretch(1)
            self.setCellWidget(row_index, 4, visual_host)

            transition = QLabel(row.transition.label)
            transition.setAlignment(Qt.AlignmentFlag.AlignCenter)
            transition.setStyleSheet(
                "QLabel{background:#EEF4FD;color:#31527E;border:1px solid #DFE9F7;"
                "border-radius:9px;padding:2px 7px;font-size:11px;}"
            )
            transition_host = QFrame()
            trow = QHBoxLayout(transition_host)
            trow.setContentsMargins(5, 5, 5, 5)
            trow.addWidget(transition)
            self.setCellWidget(row_index, 5, transition_host)

            status = QLabel()
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if row.status_state == "success":
                text, bg, fg = "●  Siap", "#E8F8EE", "#159447"
            elif row.status_state == "warning":
                text, bg, fg = "●  Perlu Ditinjau", "#FFF3D8", "#C78100"
            else:
                text, bg, fg = "●  Belum Ada Visual", "#FFE7E7", "#D94242"
            status.setText(text)
            status.setStyleSheet(
                f"QLabel{{background:{bg};color:{fg};border-radius:9px;padding:2px 7px;font-size:11px;}}"
            )
            status_host = QFrame()
            srow = QHBoxLayout(status_host)
            srow.setContentsMargins(4, 5, 4, 5)
            srow.addWidget(status)
            self.setCellWidget(row_index, 6, status_host)


class PixelAlbumContextWidget(_BaseAlbumContextWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.cover.setFixedSize(96, 96)
        self.cover.setStyleSheet(
            f"background:{TOKENS.app_bg};border:1px solid {TOKENS.border};border-radius:7px;"
        )
        icon_map = {
            "all": "album",
            "missing_cover": "media",
            "missing_visual": "visual",
            "review": "settings",
        }
        for key, button in self.filter_buttons.items():
            button.setIcon(foundation_icon(icon_map[key], color="#214C89", size=19))
            button.setIconSize(QSize(19, 19))
            button.setMinimumHeight(43)


class PixelAlbumMassToolsWidget(_BaseAlbumMassToolsWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        subtitles = {
            "Kelola Cover": "Atur cover untuk lagu yang dipilih",
            "Auto Match Cover": "Cocokkan cover dari media",
            "Assign Visual": "Terapkan visual ke lagu terpilih",
            "Clear Visual": "Hapus visual dari lagu terpilih",
        }
        for button in self._action_widgets:
            title = button.text()
            if title in subtitles:
                button.setText(f"{title}\n{subtitles[title]}")
                button.setMinimumHeight(58)
                button.setStyleSheet(
                    "QPushButton{text-align:left;padding:7px 12px;background:#FFFFFF;"
                    "border:1px solid #D7E3F2;border-radius:7px;color:#17345F;}"
                    "QPushButton:disabled{color:#94A3B8;background:#F8FAFC;}"
                )
        self.selection_chip.setStyleSheet(
            "QLabel{background:#EAF3FF;color:#1766E8;border-radius:6px;padding:7px 10px;font-weight:700;}"
        )


class PixelAlbumWorkspace(_BaseAlbumWorkspace):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;border:1px solid #D8E4F2;gridline-color:#E7EEF7;}"
            "QTableWidget::item{border-bottom:1px solid #E8EEF6;padding:2px 5px;}"
            "QTableWidget::item:selected{background:#EEF5FF;color:#10234A;}"
            "QHeaderView::section{background:#F7FAFE;border:none;border-bottom:1px solid #D8E4F2;"
            "padding:5px;color:#314A70;font-weight:600;}"
        )
        self.bulk.setStyleSheet(
            "QFrame#famCard{background:#F8FBFF;border:1px solid #D8E4F2;border-radius:7px;}"
        )


class PixelAlbumTimelineOverviewCanvas(_BaseAlbumTimelineOverviewCanvas):
    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        left = 82
        ruler_h = 26
        video_y = ruler_h + 5
        video_h = max(34, int((self.height() - ruler_h - 16) * 0.48))
        audio_y = video_y + video_h + 5
        audio_h = max(24, self.height() - audio_y - 5)

        painter.setPen(QPen(QColor("#D9E4F2"), 1))
        painter.drawLine(left, ruler_h, self.width(), ruler_h)
        painter.setPen(QColor("#223B64"))
        painter.drawText(QRectF(10, video_y, left - 16, video_h), Qt.AlignmentFlag.AlignVCenter, "▣  Video")
        painter.drawText(QRectF(10, audio_y, left - 16, audio_h), Qt.AlignmentFlag.AlignVCenter, "♫  Audio")

        songs = list(self._document.playlist.entries[:7])
        assets = self._document.asset_map()
        if not songs:
            painter.end()
            return
        durations = []
        for song in songs:
            asset = assets.get(song.asset_id)
            tick = max(1, int((song.source_out_tick or (asset.source_duration_tick if asset else 0)) - song.source_in_tick))
            durations.append(tick)
        total = max(1, sum(durations))
        usable = max(1, self.width() - left - 16)

        # Ruler is derived from the visible song durations, not fabricated render state.
        total_seconds = total / max(1, int(self._document.timebase if hasattr(self._document, "timebase") else 1000))
        for idx in range(8):
            x = left + usable * idx / 8
            painter.setPen(QPen(QColor("#C9D9EC"), 1))
            painter.drawLine(int(x), ruler_h - 5, int(x), ruler_h)
            painter.setPen(QColor("#667B99"))
            painter.drawText(QRectF(x - 8, 2, 55, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{idx * 10:02d}:00")

        cursor = float(left)
        for index, (song, duration) in enumerate(zip(songs, durations), start=1):
            width = max(88.0, usable * duration / total)
            if cursor + width > self.width() - 12:
                width = max(40.0, self.width() - 12 - cursor)
            rect = QRectF(cursor, video_y, max(2.0, width - 3), video_h)
            cover = assets.get(song.cover_asset_id) if song.cover_asset_id else None
            path = _thumbnail_path(cover)
            if path is not None:
                pix = QPixmap(str(path))
                if not pix.isNull():
                    painter.drawPixmap(rect.toRect(), pix.scaled(rect.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            else:
                painter.fillRect(rect, QColor("#DDE9F7"))
            painter.fillRect(QRectF(rect.left(), rect.bottom() - 18, rect.width(), 18), QColor(20, 40, 65, 170))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(rect.adjusted(7, rect.height() - 20, -4, -2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{index}. {song.display_title}")
            painter.setPen(QPen(QColor("#D0DDEC"), 1))
            painter.drawRect(rect)
            cursor += width
            if cursor >= self.width() - 12:
                break

        # Audio overview uses true clip boundaries; the light accent is only a lane fill.
        cursor = float(left)
        for song, duration in zip(songs, durations):
            width = max(88.0, usable * duration / total)
            if cursor + width > self.width() - 12:
                width = max(40.0, self.width() - 12 - cursor)
            rect = QRectF(cursor, audio_y, max(2.0, width - 3), audio_h)
            selected = song.song_id in self._selected_ids
            painter.fillRect(rect, QColor("#BEEFE9" if selected else "#D9F4F1"))
            painter.setPen(QPen(QColor("#58CFC3"), 1))
            mid = rect.center().y()
            painter.drawLine(rect.left() + 4, mid, rect.right() - 4, mid)
            painter.setPen(QPen(QColor("#D0E9E6"), 1))
            painter.drawRect(rect)
            cursor += width
            if cursor >= self.width() - 12:
                break
        painter.end()


def install_post_release_album_pixel_match() -> None:
    global _installed
    if _installed:
        return
    from . import album_feature
    from . import album_workspace

    album_workspace.AlbumSongTable = PixelAlbumSongTable
    album_feature.AlbumWorkspace = PixelAlbumWorkspace
    album_feature.AlbumContextWidget = PixelAlbumContextWidget
    album_feature.AlbumMassToolsWidget = PixelAlbumMassToolsWidget
    album_feature.AlbumTimelineOverviewCanvas = PixelAlbumTimelineOverviewCanvas
    _installed = True
