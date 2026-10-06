from __future__ import annotations

from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap


@lru_cache(maxsize=1)
def _close_matrix() -> dict:
    script = textwrap.dedent(
        r"""
        import json
        import os
        import tempfile
        from pathlib import Path

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ["FAM_STEP11_NO_RECOVERY_PROMPT"] = "1"
        os.environ["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
        os.environ["FAM_STEP09_PROVIDER"] = "mock"

        from PySide6.QtWidgets import QApplication, QMessageBox
        import full_album_maker.main
        from full_album_maker.v14_window import create_main_window

        app = QApplication.instance() or QApplication([])
        results = {}
        with tempfile.TemporaryDirectory(prefix="s11-close-") as folder:
            root = Path(folder)
            for choice in ("Save", "Discard", "Cancel"):
                window = create_main_window()
                window._foundation_project_open = True
                canonical = root / f"{choice.lower()}-project.json"
                window._foundation_project_path = str(canonical)

                window.editor_workspace.session.add_text_layer()
                window.editor_workspace._after_edit()
                app.processEvents()
                assert window.editor_workspace.session.is_dirty is True

                calls = []
                answer = getattr(QMessageBox.StandardButton, choice)

                def fake_question(*args, **kwargs):
                    calls.append(1)
                    return answer

                QMessageBox.question = fake_question
                closed = bool(window.close())
                app.processEvents()

                results[choice] = {
                    "calls": len(calls),
                    "closed": closed,
                    "session_dirty": bool(window.editor_workspace.session.is_dirty),
                    "legacy_dirty": bool(window.is_project_dirty()),
                    "save_state": str(window.foundation_state.save_state),
                    "current_path": str(getattr(window, "_current_project_path", "") or ""),
                    "canonical": str(canonical),
                    "file_exists": canonical.is_file(),
                }

                if choice == "Cancel":
                    window._s11_quiesce_autosave(restart=False)
                    window.hide()
                    window.deleteLater()
                    app.processEvents()

        print("CLOSE_MATRIX_JSON=" + json.dumps(results, sort_keys=True), flush=True)
        os._exit(0)
        """
    )
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["FAM_STEP11_NO_RECOVERY_PROMPT"] = "1"
    env["FAM_DISABLE_TEMPLATE_THUMBNAIL_RENDER"] = "1"
    env["FAM_STEP09_PROVIDER"] = "mock"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    line = next(
        item for item in result.stdout.splitlines() if item.startswith("CLOSE_MATRIX_JSON=")
    )
    return json.loads(line.split("=", 1)[1])


def test_step11_close_dirty_save_prompts_once() -> None:
    case = _close_matrix()["Save"]
    assert case["calls"] == 1
    assert case["closed"] is True
    assert case["file_exists"] is True


def test_step11_close_dirty_discard_prompts_once() -> None:
    case = _close_matrix()["Discard"]
    assert case["calls"] == 1
    assert case["closed"] is True
    assert case["file_exists"] is False


def test_step11_close_cancel_keeps_window_open_without_legacy_prompt() -> None:
    case = _close_matrix()["Cancel"]
    assert case["calls"] == 1
    assert case["closed"] is False
    assert case["session_dirty"] is True


def test_step11_successful_save_clears_both_visible_dirty_indicators() -> None:
    case = _close_matrix()["Save"]
    assert case["session_dirty"] is False
    assert case["legacy_dirty"] is False
    assert case["save_state"] == "success"


def test_step11_save_keeps_current_project_path() -> None:
    case = _close_matrix()["Save"]
    assert Path(case["current_path"]).resolve() == Path(case["canonical"]).resolve()
