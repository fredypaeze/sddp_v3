from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    gate = ROOT / "outputs/run_001/reporte_calidad_datos.json"
    status = json.loads(gate.read_text(encoding="utf-8")).get("status") if gate.exists() else "NO_EVALUADO"
    if status == "BLOCKED_CRITICAL_DATA":
        raise SystemExit("Backtest bloqueado: faltan datos criticos documentados en docs/SOLICITUD_DATOS_USUARIO.md")
    raise SystemExit("Backtest no implementado hasta que la puerta permita avanzar.")


if __name__ == "__main__":
    main()

