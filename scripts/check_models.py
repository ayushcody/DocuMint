from __future__ import annotations

import json
import os
from pathlib import Path

CACHE_DIR = Path(os.getenv("DOCUMINT_MODEL_CACHE_DIR", "~/.cache/documint/models")).expanduser()


def main() -> None:
    checks = [
        ("vidore--colqwen2-v1.0", ["adapter_config.json", "adapter_model.safetensors"]),
        ("vidore--colqwen2-base", ["config.json", "model.safetensors.index.json"]),
        (
            "sentence-transformers--all-MiniLM-L6-v2",
            ["modules.json", "config.json", "model.safetensors"],
        ),
    ]
    print(f"Model cache: {CACHE_DIR}")
    for model_cache_name, required_files in checks:
        snapshot = _latest_snapshot(model_cache_name)
        if snapshot is None:
            print(f"{model_cache_name}: NOT CACHED")
            continue
        missing = [name for name in required_files if not (snapshot / name).exists()]
        if model_cache_name == "vidore--colqwen2-base" and not missing:
            missing.extend(_missing_shards(snapshot))
        if missing:
            print(f"{model_cache_name}: INCOMPLETE missing {', '.join(missing)}")
        else:
            print(f"{model_cache_name}: CACHED")


def _latest_snapshot(model_cache_name: str) -> Path | None:
    snapshots = CACHE_DIR / f"models--{model_cache_name}" / "snapshots"
    if not snapshots.exists():
        return None
    candidates = [path for path in snapshots.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _missing_shards(snapshot: Path) -> list[str]:
    index_path = snapshot / "model.safetensors.index.json"
    try:
        weight_map = json.loads(index_path.read_text())["weight_map"]
    except (OSError, KeyError, json.JSONDecodeError):
        return ["model shards listed in model.safetensors.index.json"]
    shard_names = sorted(set(str(name) for name in weight_map.values()))
    return [name for name in shard_names if not (snapshot / name).exists()]


if __name__ == "__main__":
    main()
