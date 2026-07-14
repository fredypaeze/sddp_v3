from __future__ import annotations

import unittest
from pathlib import Path

from minenergia_sddp.config.paths import load_data_sources
from minenergia_sddp.validation.contracts import CONTRACTS


class ConfigAndContractsTest(unittest.TestCase):
    def test_external_paths_only_in_config(self) -> None:
        cfg = load_data_sources()
        for item in cfg["external_sources"].values():
            self.assertEqual(item["mode"], "read_only")
            self.assertTrue(Path(item["path"]).exists())

    def test_required_contract_domains_exist(self) -> None:
        for domain in ["embalses", "aportes", "generacion", "demanda_otras_fuentes", "termicas", "escenarios"]:
            self.assertIn(domain, CONTRACTS)
            self.assertGreater(len(CONTRACTS[domain]), 0)

    def test_thermal_contract_requires_capacity_and_availability(self) -> None:
        self.assertIn("capacidad_mw", CONTRACTS["termicas"])
        self.assertIn("disponibilidad_mw", CONTRACTS["termicas"])
        self.assertIn("precio_oferta_cop_kwh", CONTRACTS["termicas"])


if __name__ == "__main__":
    unittest.main()

