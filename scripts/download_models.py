from __future__ import annotations

import os
from pathlib import Path

CACHE_DIR = Path(
    os.getenv("DOCUMINT_MODEL_CACHE_DIR", "~/.cache/documint/models")
).expanduser()

MODELS_TO_DOWNLOAD = [
    {
        "name": "ColQwen2 (visual RAG)",
        "id": "vidore/colqwen2-v1.0",
        "required_for": "Agent 7 - Index/RAG adapter",
        "size_gb": 5.5,
    },
    {
        "name": "ColQwen2 base (visual RAG)",
        "id": "vidore/colqwen2-base",
        "required_for": "Agent 7 - Index/RAG base model",
        "size_gb": 15.0,
    },
    {
        "name": "SentenceTransformer (classify/split)",
        "id": "sentence-transformers/all-MiniLM-L6-v2",
        "required_for": "Classify + Split",
        "size_gb": 0.09,
    },
]


def main() -> None:
    from huggingface_hub import snapshot_download

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading models to cache: {CACHE_DIR}\n")
    for model in MODELS_TO_DOWNLOAD:
        print(f"Downloading {model['name']} ({model['size_gb']} GB)")
        print(f"  Model: {model['id']}")
        print(f"  Used by: {model['required_for']}")
        try:
            path = snapshot_download(str(model["id"]), cache_dir=str(CACHE_DIR))
            print(f"  Saved to: {path}")
            print("  Status: OK\n")
        except Exception as exc:
            print(f"  Status: FAILED - {exc}\n")
    print(
        "Download complete. Set DOCUMINT_COLPALI_OFFLINE=true for air-gapped use. "
        "ColQwen2 requires both vidore/colqwen2-v1.0 and vidore/colqwen2-base."
    )


if __name__ == "__main__":
    main()
