from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    gate_path = ROOT / "outputs/run_001/reporte_calidad_datos.json"
    status = "NO_EVALUADO"
    if gate_path.exists():
        status = json.loads(gate_path.read_text(encoding="utf-8")).get("status", status)
    report = f"""# Reporte final

Salida objetivo: Recomendacion de despacho y priorizacion termica.

Estado de puerta: **{status}**.

No hay resultados operativos validos si la puerta esta bloqueada. Consulte `docs/SOLICITUD_DATOS_USUARIO.md` para los datos requeridos.
"""
    (ROOT / "outputs/latest/reporte_final.md").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

