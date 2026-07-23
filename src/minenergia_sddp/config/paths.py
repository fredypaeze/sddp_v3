"""Carga de rutas del proyecto sin incrustar fuentes externas en codigo."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Variable de entorno opcional para montar las fuentes externas en este servidor.
# Si se define, external_source_path devuelve <root>/<name> en lugar de la ruta
# absoluta del equipo de origen registrada en config/data_sources.json. Esto hace
# portable el proyecto sin editar el config (unica ubicacion autorizada de rutas).
EXTERNAL_ROOT_ENV = "SDDP_EXTERNAL_SOURCES_ROOT"


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
    root = os.environ.get(EXTERNAL_ROOT_ENV)
    if root:
        return Path(root) / name
    return Path(value)


def external_sources_available(config_path: Path | None = None) -> bool:
    """True si todas las fuentes externas configuradas existen en este servidor.

    En el equipo de origen apuntan a rutas locales (D:/Proyectos/...). En un
    servidor limpio no estan montadas, por lo que las pruebas que dependen de
    catalogos maestros externos deben saltarse (skip) con razon documentada.
    """
    try:
        cfg = load_data_sources(config_path)
    except OSError:
        return False
    names = cfg.get("external_sources", {})
    return bool(names) and all(external_source_path(n, config_path).exists() for n in names)

