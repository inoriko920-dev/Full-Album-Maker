"""Reproducible owner-golden UI09 visual acceptance (no reference image bundled).

The rendering fixture uses a randomly named temporary directory in the output
folder input. Only its variable *text pixels* are masked, in both baseline and
candidate. All other pixels, including the input border, stay in the MAE gate.
Never use this mask to claim pixel-perfect parity; raw MAE is always reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

GOLDEN_SHA256 = "8739b225d83089772b19f05b133b98b3ea8e448d1fb905ba613751f46d988618"
WIDTH, HEIGHT = 1672, 941
REGIONS = {
    "full": (0, 0, WIDTH, HEIGHT),
    "queue": (467, 430, 1291, 742),
    "queued_row": (478, 568, 1306, 649),
    "queue_status": (1090, 480, 1275, 715),
    "history": (179, 450, 451, 824),
}
# Clipped contents of "Folder Output" carry a fresh tempfile slug per run.
# Coordinates inspected against historical Windows CI evidence, not a guess.
VOLATILE_OUTPUT_FOLDER_TEXT = (1335, 315, 1470, 339)


def _read(path: Path) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        raise ValueError(f"{path}: expected {WIDTH}x{HEIGHT}, got {image.size}")
    return np.asarray(image, dtype=np.int16)


def _mae(reference: np.ndarray, candidate: np.ndarray, crop: tuple) -> float:
    x0, y0, x1, y1 = crop
    return float(np.abs(reference[y0:y1, x0:x1] -
                        candidate[y0:y1, x0:x1]).mean())


def check(golden: Path, baseline: Path, candidate: Path) -> tuple[bool, dict]:
    actual_sha = hashlib.sha256(golden.read_bytes()).hexdigest()
    if actual_sha != GOLDEN_SHA256:
        raise ValueError(f"Owner golden SHA mismatch: {actual_sha}")
    reference, old, new = _read(golden), _read(baseline), _read(candidate)
    metrics = {}
    for name, crop in REGIONS.items():
        a, b = _mae(reference, old, crop), _mae(reference, new, crop)
        metrics[name] = {"wave13": a, "candidate": b, "delta": b - a}
    # The raw full screenshot remains part of the report for audit.
    # Mask only the inherently random temporary-path characters, symmetrically.
    left, top, right, bottom = VOLATILE_OUTPUT_FOLDER_TEXT
    ref_n = reference.copy()
    old_n, new_n = old.copy(), new.copy()
    for arr in (ref_n, old_n, new_n):
        arr[top:bottom, left:right] = 0
    a, b = _mae(ref_n, old_n, REGIONS["full"]), _mae(ref_n, new_n, REGIONS["full"])
    metrics["full_normalized_temp_path"] = {
        "wave13": a, "candidate": b, "delta": b - a,
        "mask": [left, top, right, bottom],
    }
    passed = (metrics["queue"]["delta"] <= 0 and
              metrics["full_normalized_temp_path"]["delta"] <= 0)
    result = {
        "status": "PASS" if passed else "FAIL",
        "note": "Normalizes only random folder text, never the render queue",
        "golden_sha256": actual_sha,
        "metrics": metrics,
        "strict_pixel_perfect": False,
    }
    return passed, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    passed, report = check(args.golden, args.baseline, args.candidate)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
