from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = ROOT / "docs" / "beat-animation" / "_step04_source_payload"
PARTS = [
    ("part1.txt", "bf9d63c3945211ef511da8b1628f6771bd45a13dccc920fe708573d7461dee77"),
    ("part2a.txt", "f82274b7d367f1b981b493739806c6df2a81aee48fae87f13d8b7103895fb80f"),
    ("part2b.txt", "b746be77b707a094385d78a2acb961590d0b6cb087c498904df14c2a50f21ddf"),
    ("part2c.txt", "52090fad01af42c481b865d4f5748372aec810aa2e92753cd0cfa6c79d426a5b"),
    ("part3_exact.txt", "56b24c05ea2b71bf4748fc4368e4fa58309d8b8155ddd1927cede0b9d2e2e640"),
]
EXPECTED_BUNDLE_SHA256 = "af58c93835d15533b659b95c3315ef980b8e6ad62135561b0b825c6eb4528f29"


def load_bundle() -> dict[str, str]:
    encoded: list[str] = []
    for filename, expected in PARTS:
        path = PAYLOAD_ROOT / filename
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise RuntimeError(f"STEP04 payload {filename} checksum mismatch: {actual} != {expected}")
        encoded.append(raw.decode("ascii"))
    packed = base64.b64decode("".join(encoded), validate=True)
    decoded = zlib.decompress(packed)
    actual_bundle = hashlib.sha256(decoded).hexdigest()
    if actual_bundle != EXPECTED_BUNDLE_SHA256:
        raise RuntimeError(f"STEP04 bundle checksum mismatch: {actual_bundle} != {EXPECTED_BUNDLE_SHA256}")
    data = json.loads(decoded.decode("utf-8"))
    if not isinstance(data, dict) or not data:
        raise RuntimeError("STEP04 source payload is empty or invalid")
    return {str(path): str(content) for path, content in data.items()}


def main() -> None:
    bundle = load_bundle()
    for relative, content in sorted(bundle.items()):
        target = (ROOT / relative).resolve()
        if ROOT.resolve() not in target.parents:
            raise RuntimeError(f"Refusing path outside repository: {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        print(relative)
    print(f"Applied {len(bundle)} STEP04 source files.")


if __name__ == "__main__":
    main()
