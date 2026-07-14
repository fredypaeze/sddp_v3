"""Carga de rutas del proyecto sin incrustar fuentes externas en codigo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_data_sources(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or project_root() / "config" / "data_sources.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def external_source_path(name: str, config_path: Path | None = None) -> Path:
    cfg = load_data_sources(config_path)
    try:
        value = cfg["external_sources"][name]["path"]
    except KeyError as exc:
        raise KeyError(f"Fuente externa no configurada: {name}") from exc
    return Path(value)

