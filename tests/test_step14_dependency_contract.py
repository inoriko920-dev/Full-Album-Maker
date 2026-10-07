from __future__ import annotations

from pathlib import Path
import re
import tomllib

ROOT=Path(__file__).resolve().parents[1]


def _lock():
    lines=[]
    for raw in (ROOT/"build"/"requirements-windows.lock").read_text(encoding="utf-8").splitlines():
        text=raw.strip()
        if text and not text.startswith("#"):
            lines.append(text)
    return lines


def test_pyproject_requires_python_312_and_scientific_runtime():
    data=tomllib.loads((ROOT/"pyproject.toml").read_text(encoding="utf-8"))
    project=data["project"]
    assert project["requires-python"]==">=3.12"
    deps=set(project["dependencies"])
    assert "librosa==1.0.0" in deps
    assert "numpy>=2.5,<3" in deps
    assert "scipy>=1.18,<2" in deps


def test_windows_lock_has_required_exact_scientific_pins():
    lines=set(_lock())
    required={
        "numpy==2.5.3","scipy==1.18.1","librosa==1.0.0","numba==0.68.0",
        "llvmlite==0.50.0","scikit-learn==1.9.1","soundfile==0.14.0",
        "soxr==1.1.0","pooch==1.9.0","cffi==2.1.1","platformdirs==4.11.14",
    }
    assert required.issubset(lines)


def test_windows_lock_has_no_duplicate_distribution_names():
    names=[]
    for line in _lock():
        match=re.match(r"([A-Za-z0-9_.-]+)==",line)
        if match:
            names.append(match.group(1).lower().replace("_","-").replace(".","-"))
    assert len(names)==len(set(names))


def test_capability_report_source_declares_beat_scientific_runtime():
    text=(ROOT/"build"/"write_release_capabilities.py").read_text(encoding="utf-8")
    assert '"librosa": "1.0.0"' in text
    assert '"scientific_runtime_bundled": True' in text
    assert '"beat_animation_v2"' in text


def test_main_has_frozen_beat_runtime_smoke_switch():
    text=(ROOT/"src"/"full_album_maker"/"main.py").read_text(encoding="utf-8")
    assert '"--beat-runtime-smoke"' in text
    assert "run_beat_runtime_smoke" in text


def test_third_party_notice_matches_current_ffmpeg_and_scientific_runtime():
    text=(ROOT/"THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "autobuild-2026-10-03-18-14" in text
    assert "librosa 1.0.0" in text
    assert "NumPy 2.5.3" in text
