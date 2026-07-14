from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class QualityGateArtifactsTest(unittest.TestCase):
    def test_quality_gate_file_exists_after_audit(self) -> None:
        path = ROOT / "outputs/run_001/reporte_calidad_datos.json"
        self.assertTrue(path.exists(), "Ejecute scripts/01_auditar_fuentes.py antes de las pruebas completas")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn(data["status"], {"GO_FULL_MODEL", "GO_BACKTEST_ONLY", "GO_AGGREGATE_PROSPECTIVE", "BLOCKED_CRITICAL_DATA"})

    def test_required_docs_exist_after_prepare(self) -> None:
        for rel in [
            "docs/CONTRATO_DATOS.md",
            "docs/MATRIZ_UNIDADES.md",
            "docs/BRECHAS_DATOS.md",
            "docs/SOLICITUD_DATOS_USUARIO.md",
        ]:
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()

