"""Configuration-driven Hugging Face tokenizer loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_tokenizer(
    model_name: str,
    *,
    revision: str | None = None,
    cache_dir: str | Path | None = None,
    local_files_only: bool = False,
) -> Any:
    """Load an AutoTokenizer without hard-coding a model architecture.

    ``revision`` should be pinned for repeatable training and deployment. A
    ``None`` revision is useful only for an explicitly configured development
    workflow and should not be used for production releases.
    """

    if not model_name.strip():
        raise ValueError("model_name must not be empty")

    try:
        from transformers import AutoTokenizer
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "The 'transformers' package is required to load a tokenizer."
        ) from exc

    kwargs: dict[str, Any] = {
        "cache_dir": str(cache_dir) if cache_dir else None,
        "local_files_only": local_files_only,
    }
    if revision:
        kwargs["revision"] = revision

    return AutoTokenizer.from_pretrained(model_name, **kwargs)
