"""Download the ONNX models used for cascade turn detection.

Usage: python scripts/fetch_turn_models.py [target_dir] [--print-sha]
Stdlib only, so the Docker base stage can run it before dependencies exist.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS = {
    "silero_vad.onnx": (
        "https://raw.githubusercontent.com/snakers4/silero-vad/v5.1.2/src/silero_vad/data/silero_vad.onnx",
        "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f",
    ),
    "smart-turn-v3.onnx": (
        "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/main/smart-turn-v3.0.onnx",
        "07a133aba31e2d0b523f17f8c2e4e65efe6d8f685efd12ca4fe21ebf4e798991",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target = Path(args[0] if args else "models/turn")
    target.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in MODELS.items():
        path = target / name
        if not path.exists():
            urllib.request.urlretrieve(url, path)  # noqa: S310 — fixed https URLs
        digest = _sha256(path)
        if "--print-sha" in sys.argv:
            print(name, digest)
        elif expected and digest != expected:
            path.unlink()
            raise SystemExit(f"Checksum mismatch for {name}: {digest}")


if __name__ == "__main__":
    main()
