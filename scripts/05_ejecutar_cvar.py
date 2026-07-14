from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    gate = ROOT / "outputs/run_001/reporte_calidad_datos.json"
    status = json.loads(gate.read_text(encoding="utf-8")).get("status") if gate.exists() else "NO_EVALUADO"
    if status != "GO_FULL_MODEL":
        raise SystemExit("CVaR bloqueado: requiere backtest y prospectivo deterministico validos.")
    raise SystemExit("CVaR pendiente de implementacion conjunta despues del modelo deterministico.")


if __name__ == "__main__":
    main()

