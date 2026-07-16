from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from minenergia_sddp.data.xm_checkpoints import sha256_file
from minenergia_sddp.data.xm_pilot import (
    derive_units_contextual,
    load_unit_overrides,
    resolve_effective_unit,
)

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "config/xm_unit_overrides.json"
REPROCESS_SCRIPT = ROOT / "scripts/12_reprocesar_piloto_xm_unidades.py"


class XMUnitOverridesTest(unittest.TestCase):
    def sample_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{"Date": "2026-06-01", "Hour": "Hour01", "code": "2QEK", "Value": 35000.0}])

    def test_load_overrides(self) -> None:
        rules = load_unit_overrides(OVERRIDES)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["target"], "disponibilidad_declarada_recurso")

    def test_exact_match_resolves_override(self) -> None:
        resolved = resolve_effective_unit("disponibilidad_declarada_recurso", "DispoDeclarada", "Recurso", "kWh", OVERRIDES)
        self.assertTrue(resolved["unit_override_applied"])
        self.assertEqual(resolved["unit_effective"], "kW")

    def test_catalog_unit_is_preserved(self) -> None:
        resolved = resolve_effective_unit("disponibilidad_declarada_recurso", "DispoDeclarada", "Recurso", "kWh", OVERRIDES)
        self.assertEqual(resolved["unit_catalog"], "kWh")

    def test_dispo_declarada_generates_value_mw_only(self) -> None:
        frame = derive_units_contextual(
            self.sample_frame(),
            target="disponibilidad_declarada_recurso",
            metric_id="DispoDeclarada",
            entity="Recurso",
            catalog_unit="kWh",
            override_path=OVERRIDES,
        )
        self.assertIn("Value_MW", frame.columns)
        self.assertNotIn("Value_GWh", frame.columns)
        self.assertEqual(float(frame.loc[0, "Value_MW"]), 35.0)
        self.assertEqual(frame.loc[0, "unit_catalog"], "kWh")
        self.assertEqual(frame.loc[0, "unit_effective"], "kW")
        self.assertTrue(bool(frame.loc[0, "unit_override_applied"]))

    def test_energy_kwh_still_generates_gwh(self) -> None:
        frame = derive_units_contextual(
            pd.DataFrame([{"Value": 1_000_000.0}]),
            target="demanda_sin_diaria",
            metric_id="DemaSIN",
            entity="Sistema",
            catalog_unit="kWh",
            override_path=OVERRIDES,
        )
        self.assertEqual(float(frame.loc[0, "Value_GWh"]), 1.0)
        self.assertNotIn("Value_MW", frame.columns)

    def test_normal_kw_still_generates_mw(self) -> None:
        frame = derive_units_contextual(
            pd.DataFrame([{"Value": 35_000.0}]),
            target="disponibilidad_real_recurso",
            metric_id="DispoReal",
            entity="Recurso",
            catalog_unit="kW",
            override_path=OVERRIDES,
        )
        self.assertEqual(float(frame.loc[0, "Value_MW"]), 35.0)
        self.assertFalse(bool(frame.loc[0, "unit_override_applied"]))

    def test_override_does_not_affect_other_kwh_metrics(self) -> None:
        resolved = resolve_effective_unit("generacion_real_total", "Gene", "Sistema", "kWh", OVERRIDES)
        self.assertFalse(resolved["unit_override_applied"])
        self.assertEqual(resolved["unit_effective"], "kWh")

    def test_invalid_config_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"overrides": [{"target": "x"}]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incompleto"):
                load_unit_overrides(path)

    def test_contradictory_catalog_unit_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "contradictorio"):
            resolve_effective_unit("disponibilidad_declarada_recurso", "DispoDeclarada", "Recurso", "MW", OVERRIDES)


class XMUnitReprocessTest(unittest.TestCase):
    def load_reprocess_module(self):
        spec = importlib.util.spec_from_file_location("xm_reprocess_units", REPROCESS_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_reprocess_from_raw_json_without_network_and_trace_sha(self) -> None:
        module = self.load_reprocess_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            module.ROOT = base
            module.RAW_ROOT = base / "raw"
            module.NORMALIZED_ROOT = base / "normalized_v2"
            target_dir = module.RAW_ROOT / "disponibilidad_declarada_recurso"
            target_dir.mkdir(parents=True)
            raw_path = target_dir / "disponibilidad_declarada_recurso__2026-06-01__2026-06-07__b001.json"
            raw_path.write_text(
                json.dumps(
                    [
                        {
                            "Date": "2026-06-01",
                            "HourlyEntities": [
                                {"Id": "2QEK", "Values": {"code": "2QEK", "Hour01": 35000.0}}
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            module.pilot_calls = lambda: [
                {
                    "call_id": raw_path.stem,
                    "target": "disponibilidad_declarada_recurso",
                    "metric_id": "DispoDeclarada",
                    "entity": "Recurso",
                    "periodicity": "HourlyEntities",
                    "unit": "kWh",
                }
            ]
            with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
                manifest, frames = module.normalize_raw_files()
            self.assertEqual(manifest[0]["raw_sha256"], sha256_file(raw_path))
            self.assertTrue((base / manifest[0]["normalized_path"]).exists())
            frame = frames["disponibilidad_declarada_recurso"][0]
            self.assertIn("Value_MW", frame.columns)
            self.assertNotIn("Value_GWh", frame.columns)
            self.assertEqual(float(frame.loc[0, "Value_MW"]), 35.0)
            with self.assertRaises(FileExistsError):
                module.normalize_raw_files()


if __name__ == "__main__":
    unittest.main()


