from __future__ import annotations

from pathlib import Path


def escape_filter_option_path(value: str | Path) -> str:
    """Escape a filesystem path for an unquoted FFmpeg filter option value.

    FFmpeg filtergraph parsing has multiple escaping layers. A literal apostrophe
    in a filename cannot be represented safely by placing the path inside single
    quotes with a simple backslash. Keep the value unquoted and escape the
    filter-option/filtergraph separators explicitly.

    The returned string is intended for constructs such as:
        sendcmd=f=<escaped>
        drawtext=textfile=<escaped>
        drawtext=fontfile=<escaped>
    """

    text = Path(value).resolve().as_posix()
    if any(ch in text for ch in ("\x00", "\n", "\r", "\t")):
        raise ValueError("FFmpeg filter path contains unsupported control characters.")

    # Escape existing backslashes first; replacements below intentionally add
    # parser escapes and must not be doubled again.
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\" * 2 + ":")
    text = text.replace("'", "\\" * 3 + "'")
    text = text.replace(" ", "\\ ")
    for char in (",", ";", "[", "]"):
        text = text.replace(char, "\\" + char)
    return text
