from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    gate = ROOT / "outputs/run_001/reporte_calidad_datos.json"
    status = json.loads(gate.read_text(encoding="utf-8")).get("status") if gate.exists() else "NO_EVALUADO"
    if status in {"BLOCKED_CRITICAL_DATA", "GO_BACKTEST_ONLY"}:
        raise SystemExit("Prospectivo bloqueado por puerta de calidad. No se generan fechas futuras ni recomendaciones.")
    raise SystemExit("Prospectivo pendiente de implementacion posterior a una base deterministica valida.")


if __name__ == "__main__":
    main()

