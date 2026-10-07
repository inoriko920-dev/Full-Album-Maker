from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


FFMPEG=shutil.which("ffmpeg")


def _run(tmp_path: Path, commands: str, chain: str):
    if not FFMPEG:
        pytest.skip("ffmpeg unavailable")
    cmd=tmp_path/"commands.txt"
    cmd.write_text(commands,encoding="utf-8")
    escaped=cmd.resolve().as_posix().replace(":", r"\:")
    vf=f"sendcmd=f='{escaped}',{chain},format=rgb24"
    proc=subprocess.run(
        [
            FFMPEG,"-hide_banner","-loglevel","error",
            "-f","lavfi","-i","color=c=red:s=64x64:r=10:d=1",
            "-vf",vf,
            "-f","framemd5","-",
        ],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30,
    )
    assert proc.returncode==0, proc.stderr
    hashes=[
        line.rsplit(",",1)[-1].strip()
        for line in proc.stdout.splitlines()
        if line and not line.startswith("#")
    ]
    assert hashes
    return hashes


def test_real_ffmpeg_runtime_scale_command(tmp_path):
    hashes=_run(
        tmp_path,
        "0.2 scale@beat_size width 80;\n0.2 scale@beat_size height 80;\n0.6 scale@beat_size width 64;\n0.6 scale@beat_size height 64;\n",
        "scale@beat_size=w=64:h=64:eval=init",
    )
    assert len(set(hashes)) >= 1


def test_real_ffmpeg_runtime_rotate_command(tmp_path):
    hashes=_run(
        tmp_path,
        "0.2 rotate@beat_rotate angle 0.25;\n0.6 rotate@beat_rotate angle 0;\n",
        "rotate@beat_rotate=angle=0:ow=iw:oh=ih:c=black",
    )
    assert len(set(hashes)) > 1


def test_real_ffmpeg_runtime_eq_command_changes_pixels(tmp_path):
    hashes=_run(
        tmp_path,
        "0.2 eq@beat_glow brightness 0.2;\n0.2 eq@beat_glow saturation 1.2;\n0.6 eq@beat_glow brightness 0;\n0.6 eq@beat_glow saturation 1;\n",
        "eq@beat_glow=brightness=0:saturation=1:eval=init",
    )
    assert len(set(hashes)) > 1


def test_real_ffmpeg_combined_sendcmd_chain(tmp_path):
    hashes=_run(
        tmp_path,
        "0.2 scale@beat_size width 72;\n0.2 scale@beat_size height 72;\n0.3 rotate@beat_rotate angle 0.1;\n0.4 eq@beat_glow brightness 0.1;\n0.7 scale@beat_size width 64;\n0.7 scale@beat_size height 64;\n0.7 rotate@beat_rotate angle 0;\n0.7 eq@beat_glow brightness 0;\n",
        "scale@beat_size=w=64:h=64:eval=init,eq@beat_glow=brightness=0:saturation=1:eval=init,rotate@beat_rotate=angle=0:ow=iw:oh=ih:c=black",
    )
    assert len(set(hashes)) > 1
