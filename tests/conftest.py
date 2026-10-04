from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The repository uses a src/ layout without installing the package before the
# regression suite. Pytest adds src for the parent process, but subprocess-based
# production smoke tests invoke a fresh `python -c` and therefore need the same
# source root explicitly inherited through PYTHONPATH.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = str(_REPO_ROOT / "src")
_existing_pythonpath = os.environ.get("PYTHONPATH", "")
_pythonpath_entries = [entry for entry in _existing_pythonpath.split(os.pathsep) if entry]
if _SRC_ROOT not in _pythonpath_entries:
    os.environ["PYTHONPATH"] = os.pathsep.join([_SRC_ROOT, *_pythonpath_entries])


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
