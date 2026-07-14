from __future__ import annotations

import json
import unittest
from pathlib import Path

from minenergia_sddp.validation.availability import (
    AvailabilityCategory,
    GateStatus,
    can_convert_volume_to_gwh,
    evaluate_aggregate_v1,
    evaluate_resource_v2,
    is_metadata_only,
)


ROOT = Path(__file__).resolve().parents[1]


class SecondAuditGatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "outputs/run_005/auditoria_brechas.json"
        cls.audit = json.loads(path.read_text(encoding="utf-8"))
        cls.findings = {row["dato"]: row for row in cls.audit["findings"]}

    def test_demand_metric_is_metadata_only(self) -> None:
        self.assertEqual(self.findings["demanda_oficial_sin"]["category"], AvailabilityCategory.FOUND_METADATA_ONLY)
        self.assertTrue(is_metadata_only(["Date", "ListEntities"], "DemaReal"))

    def test_probabilities_sum_to_one(self) -> None:
        self.assertTrue(all(row["valid"] for row in self.audit["probability_sums"]))

    def test_resource_generation_is_partial_carbon_sample(self) -> None:
        row = self.findings["generacion_por_recurso"]
        self.assertEqual(row["category"], AvailabilityCategory.FOUND_WITH_LIMITATIONS)
        self.assertIn("13 recursos", row["coverage"])
        self.assertIn("2026-06-01", row["coverage"])

    def test_capacity_coverage_is_partial(self) -> None:
        coverage = self.audit["coverage"]
        self.assertEqual(self.findings["capacidad_termica"]["category"], AvailabilityCategory.FOUND_WITH_LIMITATIONS)
        self.assertGreater(coverage["carbon_principal_capacity_mw"], 0)
        self.assertLess(coverage["carbon_coverage_total_thermal_count_pct"], 100)

    def test_v1_and_v2_are_separate_gates(self) -> None:
        categories = {row["dato"]: AvailabilityCategory(row["category"]) for row in self.audit["findings"]}
        self.assertEqual(evaluate_aggregate_v1(categories), GateStatus.BLOCKED_AGGREGATE_V1)
        self.assertEqual(evaluate_resource_v2(categories), GateStatus.BLOCKED_RESOURCE_LEVEL_V2)

    def test_volume_cannot_be_converted_to_gwh_without_factor(self) -> None:
        self.assertFalse(can_convert_volume_to_gwh(["VolumenUtilPorcentaje", "CapacidadUtilMasa"]))
        self.assertFalse(self.audit["hydro_evidence"]["can_convert_volume_to_gwh"])


if __name__ == "__main__":
    unittest.main()

