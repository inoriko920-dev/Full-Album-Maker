from __future__ import annotations

from pathlib import Path

from full_album_maker.ffmpeg_filter_path import escape_filter_option_path


def test_filter_path_escapes_space_apostrophe_and_filter_separators(tmp_path: Path):
    folder = tmp_path / "RC smoke – O'Brien,semi;[x]"
    folder.mkdir()
    target = folder / "beat.sendcmd"
    target.write_text("0.0 eq@x brightness 0;\n", encoding="utf-8")

    escaped = escape_filter_option_path(target)

    assert "\\ " in escaped
    assert "\\\\\\'" in escaped
    assert "\\," in escaped
    assert "\\;" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    assert "'" in escaped
    assert not escaped.startswith("'")
    assert not escaped.endswith("'")


def test_filter_path_rejects_control_characters(tmp_path: Path):
    try:
        escape_filter_option_path(str(tmp_path / "bad\nname"))
    except ValueError as exc:
        assert "control" in str(exc).lower()
    else:
        raise AssertionError("control-character path must fail closed")
