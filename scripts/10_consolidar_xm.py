from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.data.xm_pilot import derive_units_contextual, normalize_xm_response


def normalize_downloaded_response(data: Any, call: dict[str, Any]):
    return derive_units_contextual(
        normalize_xm_response(data, call["periodicity"]),
        target=call["target"],
        metric_id=call["metric_id"],
        entity=call["entity"],
        catalog_unit=call["unit"],
    )


def normalize_downloaded_file(raw_path: Path, call: dict[str, Any]):
    data = json.loads(raw_path.read_text(encoding="utf-8"))
    return normalize_downloaded_response(data, call)


def main() -> int:
    raw_root = ROOT / "data/raw/xm"
    files = sorted(path for path in raw_root.glob("**/*.json") if not path.name.startswith("_checkpoint"))
    if not files:
        print("No hay descargas XM para consolidar. Ejecute primero scripts/08_descargar_xm_controlado.py con autorizacion explicita.")
        return 0
    raise SystemExit(
        "Consolidacion historica pendiente: las futuras transformaciones deben usar "
        "normalize_downloaded_response(), que aplica overrides de unidades desde config/xm_unit_overrides.json."
    )


if __name__ == "__main__":
    raise SystemExit(main())
