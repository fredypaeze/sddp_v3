from __future__ import annotations

import unittest
from pathlib import Path

from minenergia_sddp.config.paths import (
    external_sources_available,
    load_data_sources,
)
from minenergia_sddp.validation.contracts import CONTRACTS


class ConfigAndContractsTest(unittest.TestCase):
    def test_external_paths_only_in_config(self) -> None:
        cfg = load_data_sources()
        for item in cfg["external_sources"].values():
            self.assertEqual(item["mode"], "read_only")
        # La existencia fisica solo se verifica cuando las fuentes externas estan
        # montadas en este servidor (equipo de origen o SDDP_EXTERNAL_SOURCES_ROOT).
        if not external_sources_available():
            self.skipTest("Fuentes externas XM no montadas en este servidor "
                          "(config/data_sources.json apunta al equipo de origen)")
        for item in cfg["external_sources"].values():
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

