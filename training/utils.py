"""Small training utilities for reproducibility and provenance."""

from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path
from typing import Any

import numpy as np


def seed_everything(seed: int) -> None:
    """Seed Python, NumPy, and PyTorch when available."""

    if seed < 0:
        raise ValueError("seed must be non-negative")

    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch
    except ImportError:
        return

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def git_commit() -> str:
    """Return the current Git commit without making training depend on Git."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else "unknown"


def device_summary() -> dict[str, Any]:
    """Describe the selected compute capability without assuming CUDA."""

    try:
        import torch
    except ImportError:
        return {"device": "unavailable", "cuda_available": False}

    cuda_available = bool(torch.cuda.is_available())
    result: dict[str, Any] = {
        "device": "cuda" if cuda_available else "cpu",
        "cuda_available": cuda_available,
    }
    if cuda_available:
        result["cuda_device_name"] = torch.cuda.get_device_name(0)
    return result


def json_safe(value: Any) -> Any:
    """Convert common NumPy/PyTorch scalar values to JSON-compatible types."""

    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def write_json(path: str | Path, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
