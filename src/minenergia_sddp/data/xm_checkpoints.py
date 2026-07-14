"""Checkpoints y versionamiento de lotes XM."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def checkpoint_path(base_dir: Path) -> Path:
    return base_dir / "_checkpoint.json"


def load_checkpoint(base_dir: Path) -> dict[str, Any]:
    path = checkpoint_path(base_dir)
    if not path.exists():
        return {"completed": {}, "errors": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_checkpoint(base_dir: Path, data: dict[str, Any]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path(base_dir).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def is_completed(base_dir: Path, call_id: str) -> bool:
    return call_id in load_checkpoint(base_dir).get("completed", {})


def mark_completed(base_dir: Path, call_id: str, file_path: Path, rows: int | None = None) -> None:
    data = load_checkpoint(base_dir)
    data.setdefault("completed", {})[call_id] = {
        "file": str(file_path),
        "sha256": sha256_file(file_path),
        "rows": rows,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_checkpoint(base_dir, data)


def mark_error(base_dir: Path, call_id: str, error: str, context: dict[str, Any]) -> None:
    data = load_checkpoint(base_dir)
    data.setdefault("errors", []).append(
        {
            "call_id": call_id,
            "error": error,
            "context": context,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    save_checkpoint(base_dir, data)


def versioned_path(base_dir: Path, stem: str, suffix: str = ".json") -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    candidate = base_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = base_dir / f"{stem}_v{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1

