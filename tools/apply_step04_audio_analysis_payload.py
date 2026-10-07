from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = ROOT / "docs" / "beat-animation" / "_step04_source_payload"
PARTS = [PAYLOAD_ROOT / f"part{i}.txt" for i in range(1, 4)]
EXPECTED_PART_SHA256 = {
    1: "bf9d63c3945211ef511da8b1628f6771bd45a13dccc920fe708573d7461dee77",
    2: "80e6cd382bacc5eaab48728a5309c57858df9a622bb9977e923b2c7a1ffc61af",
    3: "56b24c05ea2b71bf4748fc4368e4fa58309d8b8155ddd1927cede0b9d2e2e640",
}
EXPECTED_BUNDLE_SHA256 = "af58c93835d15533b659b95c3315ef980b8e6ad62135561b0b825c6eb4528f29"


def load_bundle() -> dict[str, str]:
    encoded: list[str] = []
    for index, path in enumerate(PARTS, start=1):
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        expected = EXPECTED_PART_SHA256[index]
        if actual != expected:
            raise RuntimeError(f"STEP04 payload part {index} checksum mismatch: {actual} != {expected}")
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
