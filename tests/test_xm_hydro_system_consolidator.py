from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/13_consolidar_hidrologia_sin.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xm_hydro_system_consolidator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def daily_response(date: str, value: float, metric_id: str = "AporEner"):
    return {
        "Metric": {"Id": metric_id},
        "Items": [
            {
                "Date": date,
                "DailyEntities": [
                    {
                        "Id": "Sistema",
                        "Values": {"code": "Sistema", "Value": str(value)},
                    }
                ],
            }
        ],
    }


class XMHydroSystemConsolidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.module.ROOT = self.base

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def make_raw(self, target: str, domain: str, date: str, value: float, metric_id: str):
        path = self.base / "data/raw/xm" / domain / target / f"{target}__{date}__{date}__b001.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(daily_response(date, value, metric_id)), encoding="utf-8")
        return path

    def test_normalization_conversion_hash_and_source_preservation(self):
        spec = self.module.TARGETS["aportes"]
        raw = self.make_raw(spec["target"], spec["domain"], "2020-01-01", 1_000_000, spec["metric_id"])
        before = self.module.file_sha256(raw)
        frame, source = self.module.normalize_source_file("aportes", spec, raw)
        after = self.module.file_sha256(raw)
        self.assertEqual(before, after)
        self.assertEqual(source["source_sha256"], before)
        self.assertEqual(float(frame.loc[0, "Value"]), 1_000_000.0)
        self.assertEqual(float(frame.loc[0, "Value_GWh"]), 1.0)
        self.assertEqual(frame.loc[0, "source_file"], str(raw.relative_to(self.base)))

    def test_join_percentage_daily_differences_and_model_ready(self):
        target_frames = {
            "aportes": pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-01-02", "2020-01-03"],
                    "Value": [1_000_000.0, 2_000_000.0, 3_000_000.0],
                    "Value_GWh": [1.0, 2.0, 3.0],
                    "source_file": ["a1.json", "a2.json", "a3.json"],
                }
            ),
            "volumen": pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-01-02", "2020-01-03"],
                    "Value": [50_000_000.0, 55_000_000.0, 52_000_000.0],
                    "Value_GWh": [50.0, 55.0, 52.0],
                    "source_file": ["v1.json", "v2.json", "v3.json"],
                }
            ),
            "capacidad": pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-01-02", "2020-01-03"],
                    "Value": [100_000_000.0, 110_000_000.0, 104_000_000.0],
                    "Value_GWh": [100.0, 110.0, 104.0],
                    "source_file": ["c1.json", "c2.json", "c3.json"],
                }
            ),
        }
        daily, duplicates = self.module.build_daily_dataset(target_frames, "2020-01-01", "2020-01-03")
        self.assertTrue(duplicates.empty)
        self.assertEqual(len(daily), 3)
        self.assertEqual(daily["date"].nunique(), 3)
        self.assertTrue(daily["model_ready"].all())
        self.assertTrue(daily["quality_status"].eq("OK").all())
        self.assertAlmostEqual(float(daily.loc[1, "porcentaje_volumen_util_calculado"]), 50.0)
        self.assertTrue(pd.isna(daily.loc[0, "cambio_diario_volumen_gwh"]))
        self.assertTrue(pd.isna(daily.loc[0, "cambio_diario_capacidad_gwh"]))
        self.assertAlmostEqual(float(daily.loc[1, "cambio_diario_volumen_gwh"]), 5.0)
        self.assertAlmostEqual(float(daily.loc[2, "cambio_diario_capacidad_gwh"]), -6.0)

    def test_physical_rules_block_model_ready(self):
        frame = pd.DataFrame(
            {
                "date": ["2020-01-01"],
                "aportes_energia_kwh": [1_000_000.0],
                "aportes_energia_gwh": [1.0],
                "volumen_util_energia_kwh": [120_000_000.0],
                "volumen_util_energia_gwh": [120.0],
                "capacidad_util_energia_kwh": [100_000_000.0],
                "capacidad_util_energia_gwh": [100.0],
                "porcentaje_volumen_util_calculado": [120.0],
                "cambio_diario_volumen_gwh": [pd.NA],
                "cambio_diario_capacidad_gwh": [pd.NA],
                "source_file_aportes": ["a.json"],
                "source_file_volumen": ["v.json"],
                "source_file_capacidad": ["c.json"],
            }
        )
        checked = self.module.apply_quality_rules(frame)
        self.assertEqual(checked.loc[0, "quality_status"], "ERROR")
        self.assertFalse(bool(checked.loc[0, "model_ready"]))
        self.assertIn("volumen_mayor_que_capacidad", checked.loc[0, "quality_issues"])
        self.assertIn("porcentaje_fuera_de_rango", checked.loc[0, "quality_issues"])

    def test_versioning_without_overwrite(self):
        (self.base / "data/processed/xm/hydro_system_historical_v1").mkdir(parents=True)
        (self.base / "outputs/run_013").mkdir(parents=True)
        self.assertEqual(
            self.module.versioned_dataset_path("data/processed/xm/hydro_system_historical").name,
            "hydro_system_historical_v2",
        )
        self.assertEqual(self.module.versioned_run_path("outputs/run_013").name, "run_013_v002")

    def test_csv_parquet_generation_and_reproducible_digest(self):
        frame = pd.DataFrame(
            {
                "date": ["2020-01-01"],
                "aportes_energia_kwh": [1_000_000.0],
                "aportes_energia_gwh": [1.0],
                "volumen_util_energia_kwh": [50_000_000.0],
                "volumen_util_energia_gwh": [50.0],
                "capacidad_util_energia_kwh": [100_000_000.0],
                "capacidad_util_energia_gwh": [100.0],
                "porcentaje_volumen_util_calculado": [50.0],
                "cambio_diario_volumen_gwh": [pd.NA],
                "cambio_diario_capacidad_gwh": [pd.NA],
                "source_file_aportes": ["a.json"],
                "source_file_volumen": ["v.json"],
                "source_file_capacidad": ["c.json"],
                "quality_status": ["OK"],
                "quality_issues": [""],
                "model_ready": [True],
            }
        )
        out = self.base / "out"
        csv_path = out / "data.csv"
        parquet_path = out / "data.parquet"
        self.module.safe_write_csv(csv_path, frame, self.module.DAILY_COLUMNS)
        self.module.safe_write_parquet(parquet_path, frame[self.module.DAILY_COLUMNS])
        self.assertTrue(csv_path.exists())
        self.assertTrue(parquet_path.exists())
        self.assertEqual(len(pd.read_csv(csv_path)), len(pd.read_parquet(parquet_path)))
        self.assertEqual(self.module.dataframe_digest(frame[self.module.DAILY_COLUMNS]), self.module.dataframe_digest(frame[self.module.DAILY_COLUMNS]))
        with self.assertRaises(FileExistsError):
            self.module.safe_write_csv(csv_path, frame)


if __name__ == "__main__":
    unittest.main()
