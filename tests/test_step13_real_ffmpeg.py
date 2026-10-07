from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from full_album_maker.ffmpeg_command_batch import CommandBatchWriter

FFMPEG=shutil.which("ffmpeg")


def ffmpeg():
    if not FFMPEG:
        pytest.skip("ffmpeg unavailable")
    return FFMPEG


def run_graph(tmp_path: Path, graph: str, inputs: list[str], name: str):
    out=tmp_path/f"{name}.mp4"
    args=[ffmpeg(),"-y","-hide_banner","-loglevel","error"]
    for inp in inputs:
        args += ["-f","lavfi","-i",inp]
    args += ["-filter_complex",graph,"-map","[out]","-t","0.5","-c:v","libx264","-pix_fmt","yuv420p",str(out)]
    proc=subprocess.run(args,capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr
    assert out.exists() and out.stat().st_size>0


def test_real_ffmpeg_accepts_batched_scale_and_glow(tmp_path):
    cmd=tmp_path/"scale.sendcmd"; w=CommandBatchWriter()
    w.add(.10,"scale@beat_size","width",80)
    w.add(.10,"scale@beat_size","height",80)
    w.add(.10,"eq@beat_glow","brightness","0.08")
    w.add(.10,"eq@beat_glow","saturation","1.10")
    w.write(cmd)
    path=cmd.resolve().as_posix().replace(":","\\:")
    graph=f"[0:v]sendcmd=f='{path}',scale@beat_size=w=64:h=64:eval=init,eq@beat_glow=brightness=0:saturation=1:eval=init[out]"
    run_graph(tmp_path,graph,["testsrc2=size=64x64:rate=30"],"scale-glow")


def test_real_ffmpeg_accepts_batched_overlay_xy(tmp_path):
    cmd=tmp_path/"overlay.sendcmd"; w=CommandBatchWriter()
    w.add(.10,"overlay@beat_overlay","x","10")
    w.add(.10,"overlay@beat_overlay","y","12")
    w.write(cmd)
    path=cmd.resolve().as_posix().replace(":","\\:")
    graph=f"[1:v]sendcmd=f='{path}'[fg];[0:v][fg]overlay@beat_overlay=x=0:y=0[out]"
    run_graph(tmp_path,graph,[
        "color=c=black:s=96x96:r=30",
        "color=c=white:s=24x24:r=30",
    ],"overlay")


def test_real_ffmpeg_accepts_batched_spark_drawbox(tmp_path):
    cmd=tmp_path/"spark.sendcmd"; w=CommandBatchWriter()
    w.add(.10,"drawbox@beat_spark_0","x",20)
    w.add(.10,"drawbox@beat_spark_0","y",18)
    w.add(.10,"drawbox@beat_spark_0","color","white@0.9")
    w.write(cmd)
    path=cmd.resolve().as_posix().replace(":","\\:")
    graph=f"[0:v]sendcmd=f='{path}',drawbox@beat_spark_0=x=0:y=0:w=6:h=6:color=white@0:t=fill[out]"
    run_graph(tmp_path,graph,["color=c=black:s=64x64:r=30"],"spark")
