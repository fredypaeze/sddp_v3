"""Carpetas de ejecucion reproducibles: outputs/run_XXX_vYYY/.

Cada ejecucion importante crea una carpeta con metadatos (commit, entorno,
fecha, semilla), copia del config usado, hashes de insumos, resultados y logs.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from minenergia_sddp.config.paths import project_root


def _git_commit(root: Path) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "desconocido"
    except Exception:
        return "desconocido"


def sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def new_run(nombre: str, *, config: dict[str, Any] | None = None,
            inputs: list[str | Path] | None = None, semilla: int | None = None,
            descripcion: str = "") -> Path:
    """Crea outputs/<nombre>/ con metadatos y devuelve su ruta.

    nombre por convencion: 'run_020_v001'. No sobrescribe silenciosamente: si ya
    existe, agrega/actualiza metadatos pero conserva resultados previos.
    """
    root = project_root()
    carpeta = root / "outputs" / nombre
    carpeta.mkdir(parents=True, exist_ok=True)

    meta = {
        "nombre": nombre,
        "descripcion": descripcion,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(root),
        "python": sys.version.split()[0],
        "plataforma": platform.platform(),
        "semilla": semilla,
        "inputs": [],
    }
    for ipath in inputs or []:
        ip = Path(ipath)
        if ip.exists():
            meta["inputs"].append({"ruta": str(ip.relative_to(root) if ip.is_absolute() and str(ip).startswith(str(root)) else ip),
                                    "bytes": ip.stat().st_size, "sha256": sha256(ip)})
    (carpeta / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if config is not None:
        (carpeta / "config_usado.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return carpeta
