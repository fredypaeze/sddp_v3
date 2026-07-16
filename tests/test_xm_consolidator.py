from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/10_consolidar_xm2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xm_consolidator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def response(metric_id="DemaReal", entity_col="HourlyEntities", date="2023-01-01", value="1000000"):
    values = {"code": "Sistema", "Value": value}
    if entity_col == "HourlyEntities":
        values = {"code": "Sistema", "Hour01": value, "Hour02": value}
    return {"Metric": {"Id": metric_id}, "Items": [{"Date": date, entity_col: [{"Id": "Sistema", "Values": values}]}]}


class XMConsolidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.module.ROOT = self.base
        self.module.VALIDATION_RUN = self.base / "outputs/run_010_v002"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_help(self):
        parser = self.module.build_parser()
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--execute", out.getvalue())

    def test_dry_run(self):
        args = self.module.build_parser().parse_args(["--dry-run"])
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = self.module.dry_run(args)
        self.assertEqual(code, 0)
        self.assertIn("No se escribieron", out.getvalue())

    def test_block_without_execute(self):
        code = self.module.main([])
        self.assertEqual(code, 2)

    def test_selection_exclusive_five_targets_and_excludes_pilot(self):
        self.assertEqual(set(self.module.TARGETS), {
            "demanda_real_sistema_horaria", "demanda_sin_diaria", "generacion_real_total", "importaciones_energia_sistema", "exportaciones_energia_sistema"
        })
        pilot = self.base / "data/raw/xm/pilot_20260601_20260607_retry1/demanda_real_sistema_horaria"
        pilot.mkdir(parents=True)
        (pilot / "x.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.module.list_raw_files("demanda_real_sistema_horaria"), [])

    def test_normalization_kwh_to_gwh_and_preserves_value(self):
        raw = self.base / "data/raw/xm/demanda/demanda_real_sistema_horaria/demanda_real_sistema_horaria__2023-01-01__2023-01-30__b001.json"
        raw.parent.mkdir(parents=True)
        raw.write_text(json.dumps(response()), encoding="utf-8")
        frame, source, empty = self.module.normalize_file("demanda_real_sistema_horaria", raw)
        self.assertIsNone(empty)
        self.assertIn("Value", frame.columns)
        self.assertEqual(float(frame.loc[0, "Value_GWh"]), 1.0)
        self.assertEqual(len(source["source_sha256"]), 64)

    def test_hourly_and_daily_keys(self):
        self.assertEqual(self.module.key_columns("demanda_real_sistema_horaria"), ["Date", "Hour", "code"])
        self.assertEqual(self.module.key_columns("demanda_sin_diaria"), ["Date", "code"])

    def test_exact_dedup_and_conflict_block(self):
        frame = pd.DataFrame([
            {"Date": "2023-01-01", "Hour": "Hour01", "code": "Sistema", "Value": 1, "Value_GWh": 0.1, "target": "t", "metric_id": "m", "entity": "Sistema", "periodicity": "HourlyEntities", "unit_catalog": "kWh", "unit_effective": "kWh"},
            {"Date": "2023-01-01", "Hour": "Hour01", "code": "Sistema", "Value": 1, "Value_GWh": 0.1, "target": "t", "metric_id": "m", "entity": "Sistema", "periodicity": "HourlyEntities", "unit_catalog": "kWh", "unit_effective": "kWh"},
        ])
        clean, exact, conflicts = self.module.split_duplicates("demanda_real_sistema_horaria", frame)
        self.assertEqual(len(clean), 1)
        self.assertEqual(len(exact), 2)
        self.assertTrue(conflicts.empty)
        conflict = frame.copy()
        conflict.loc[1, "Value"] = 2
        _, _, conflicts = self.module.split_duplicates("demanda_real_sistema_horaria", conflict)
        self.assertFalse(conflicts.empty)

    def test_hourly_aggregation_and_no_nan_zero_fill(self):
        hourly = pd.DataFrame([
            {"fecha": "2023-01-01", "hora_xm": "Hour01", "demanda_real_gwh": 1.0, "generacion_total_gwh": 2.0, "importaciones_gwh": pd.NA, "exportaciones_gwh": 0.5, "demanda_real_reportada": True, "generacion_reportada": True, "importaciones_reportadas": False, "exportaciones_reportadas": True},
            {"fecha": "2023-01-01", "hora_xm": "Hour02", "demanda_real_gwh": 1.0, "generacion_total_gwh": 2.0, "importaciones_gwh": pd.NA, "exportaciones_gwh": 0.5, "demanda_real_reportada": True, "generacion_reportada": True, "importaciones_reportadas": False, "exportaciones_reportadas": True},
        ])
        daily = self.module.aggregate_daily_from_hourly(hourly)
        self.assertTrue(pd.isna(daily.loc[0, "importaciones_gwh"]))
        self.assertEqual(float(daily.loc[0, "demanda_real_gwh"]), 2.0)

    def test_empty_import_window(self):
        raw = self.base / "data/raw/xm/intercambios/importaciones_energia_sistema/importaciones_energia_sistema__2023-01-01__2023-01-30__b001.json"
        raw.parent.mkdir(parents=True)
        raw.write_text(json.dumps({"Metric": {"Id": "ImpoEner"}, "Items": []}), encoding="utf-8")
        frame, source, empty = self.module.normalize_file("importaciones_energia_sistema", raw)
        self.assertTrue(frame.empty)
        self.assertTrue(source["empty_items"])
        self.assertEqual(empty["classification"], "NO_REPORTED_VALUES")

    def test_exclusions_and_model_ready(self):
        daily = pd.DataFrame([
            {"fecha": "2023-01-01", "demanda_sin_reportada": True, "generacion_completa": True, "importaciones_completas": True, "exportaciones_completas": True, "datos_completos_balance": True},
            {"fecha": "2023-01-02", "demanda_sin_reportada": True, "generacion_completa": True, "importaciones_completas": False, "exportaciones_completas": True, "datos_completos_balance": False},
        ])
        excluded = self.module.exclusions(daily)
        ready = daily.loc[daily["datos_completos_balance"]]
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(excluded), 1)
        self.assertIn("importaciones", excluded.loc[0, "motivo_exclusion"])

    def test_versioning_and_no_overwrite(self):
        (self.base / "outputs/run_011").mkdir(parents=True)
        (self.base / "data/processed/xm/system_historical_v1").mkdir(parents=True)
        self.assertEqual(self.module.versioned_path("outputs/run_011").name, "run_011_v002")
        self.assertEqual(self.module.versioned_path("data/processed/xm/system_historical_v1", dataset=True).name, "system_historical_v2")

    def test_absence_of_network(self):
        with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network disabled")):
            plan = self.module.inspect_plan("2023-01-01", "2023-01-01")
        self.assertIn("targets", plan)


if __name__ == "__main__":
    unittest.main()
