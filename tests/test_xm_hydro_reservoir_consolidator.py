from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/15_consolidar_hidrologia_embalse.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "xm_hydro_reservoir_consolidator",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def daily_response(
    date: str,
    values: dict[str, float],
    metric_id: str,
):
    return {
        "Metric": {"Id": metric_id},
        "Items": [
            {
                "Date": date,
                "DailyEntities": [
                    {
                        "Id": code,
                        "Values": {
                            "code": code,
                            "name": code,
                            "Value": str(value),
                        },
                    }
                    for code, value in values.items()
                ],
            }
        ],
    }


class XMHydroReservoirConsolidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.module.ROOT = self.base

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def make_raw(
        self,
        label: str,
        date: str,
        values: dict[str, float],
        *,
        suffix: str = "",
    ) -> Path:
        spec = self.module.TARGETS[label]
        filename = (
            f"{spec['target']}__{date}__{date}__b001"
            f"{suffix}.json"
        )
        path = (
            self.base
            / "data/raw/xm"
            / spec["domain"]
            / spec["target"]
            / filename
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                daily_response(
                    date,
                    values,
                    spec["metric_id"],
                )
            ),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def target_frame(
        dates: list[str],
        codes: list[str],
        values: list[float],
        sources: list[str],
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Date": dates,
                "code": codes,
                "name": codes,
                "Value": values,
                "source_file": sources,
            }
        )

    def test_normalization_energy_percentage_and_source_preservation(self):
        raw_volume = self.make_raw(
            "volumen",
            "2020-01-01",
            {"PLAYAS": 50_000_000},
        )
        before = self.module.file_sha256(raw_volume)
        frame, source = self.module.normalize_source_file(
            "volumen",
            self.module.TARGETS["volumen"],
            raw_volume,
        )
        after = self.module.file_sha256(raw_volume)

        self.assertEqual(before, after)
        self.assertEqual(source["source_sha256"], before)
        self.assertTrue(source["metric_id_match"])
        self.assertEqual(float(frame.loc[0, "Value"]), 50_000_000.0)

        pair = self.module.target_pair_frame(
            "volumen",
            self.module.TARGETS["volumen"],
            frame,
        )
        self.assertEqual(
            float(pair.loc[0, "volumen_util_energia_gwh"]),
            50.0,
        )

        raw_pct = self.make_raw(
            "porcentaje",
            "2020-01-01",
            {"PLAYAS": 0.5},
        )
        pct_frame, _ = self.module.normalize_source_file(
            "porcentaje",
            self.module.TARGETS["porcentaje"],
            raw_pct,
        )
        pct_pair = self.module.target_pair_frame(
            "porcentaje",
            self.module.TARGETS["porcentaje"],
            pct_frame,
        )
        self.assertAlmostEqual(
            float(
                pct_pair.loc[
                    0,
                    "porcentaje_volumen_util_oficial_raw",
                ]
            ),
            0.5,
        )
        self.assertAlmostEqual(
            float(
                pct_pair.loc[
                    0,
                    "porcentaje_volumen_util_oficial",
                ]
            ),
            50.0,
        )

    def test_canonical_listing_excludes_control_versions(self):
        canonical = self.make_raw(
            "volumen",
            "2020-01-01",
            {"PLAYAS": 50_000_000},
        )
        self.make_raw(
            "volumen",
            "2020-01-01",
            {"PLAYAS": 50_000_000},
            suffix="_v002",
        )
        files = self.module.list_raw_files(
            self.module.TARGETS["volumen"]
        )
        self.assertEqual(files, [canonical])

    def test_union_percentage_difference_daily_changes_and_model_ready(self):
        target_frames = {
            "volumen": self.target_frame(
                [
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-03",
                ],
                ["PLAYAS", "PLAYAS", "PLAYAS"],
                [50_000_000.0, 55_000_000.0, 52_000_000.0],
                ["v1.json", "v2.json", "v3.json"],
            ),
            "capacidad": self.target_frame(
                [
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-03",
                    "2020-01-01",
                ],
                ["PLAYAS", "PLAYAS", "PLAYAS", "PRADO"],
                [
                    100_000_000.0,
                    110_000_000.0,
                    104_000_000.0,
                    60_000_000.0,
                ],
                ["c1.json", "c2.json", "c3.json", "cp.json"],
            ),
            "porcentaje": self.target_frame(
                [
                    "2020-01-01",
                    "2020-01-02",
                    "2020-01-03",
                ],
                ["PLAYAS", "PLAYAS", "PLAYAS"],
                [0.5, 0.5, 0.5],
                ["p1.json", "p2.json", "p3.json"],
            ),
        }

        daily, duplicates = self.module.build_daily_dataset(
            target_frames,
            "2020-01-01",
            "2020-01-03",
        )

        self.assertTrue(duplicates.empty)
        self.assertEqual(len(daily), 4)
        self.assertEqual(
            daily[["date", "reservoir_code"]]
            .drop_duplicates()
            .shape[0],
            4,
        )

        playas = (
            daily.loc[daily["reservoir_code"] == "PLAYAS"]
            .sort_values("date")
            .reset_index(drop=True)
        )
        self.assertTrue(playas["model_ready"].all())
        self.assertAlmostEqual(
            float(
                playas.loc[
                    1,
                    "porcentaje_volumen_util_calculado",
                ]
            ),
            50.0,
        )
        self.assertAlmostEqual(
            float(playas.loc[1, "diferencia_porcentajes_pp"]),
            0.0,
        )
        self.assertTrue(
            pd.isna(
                playas.loc[0, "cambio_diario_volumen_gwh"]
            )
        )
        self.assertAlmostEqual(
            float(
                playas.loc[1, "cambio_diario_volumen_gwh"]
            ),
            5.0,
        )
        self.assertAlmostEqual(
            float(
                playas.loc[2, "cambio_diario_capacidad_gwh"]
            ),
            -6.0,
        )

        prado = daily.loc[
            daily["reservoir_code"] == "PRADO"
        ].iloc[0]
        self.assertFalse(bool(prado["model_ready"]))
        self.assertEqual(prado["quality_status"], "ERROR")
        self.assertIn(
            "INCOMPLETO_METRICAS_REQUERIDAS",
            prado["quality_issues"],
        )

    def test_quality_policy_warning_over_100_and_negative_exclusion(self):
        frame = pd.DataFrame(
            {
                "date": ["2020-01-01", "2020-01-02"],
                "reservoir_code": [
                    "PLAYAS",
                    "ALTOANCHICAYA",
                ],
                "reservoir_name": [
                    "PLAYAS",
                    "ALTOANCHICAYA",
                ],
                "volumen_util_energia_kwh": [
                    120_000_000.0,
                    -100_000.0,
                ],
                "volumen_util_energia_gwh": [120.0, -0.1],
                "capacidad_util_energia_kwh": [
                    100_000_000.0,
                    10_000_000.0,
                ],
                "capacidad_util_energia_gwh": [100.0, 10.0],
                "porcentaje_volumen_util_oficial_raw": [
                    1.2,
                    -0.01,
                ],
                "porcentaje_volumen_util_oficial": [
                    120.0,
                    -1.0,
                ],
                "porcentaje_volumen_util_calculado": [
                    120.0,
                    -1.0,
                ],
                "diferencia_porcentajes_pp": [0.0, 0.0],
                "cambio_diario_volumen_gwh": [pd.NA, pd.NA],
                "cambio_diario_capacidad_gwh": [
                    pd.NA,
                    pd.NA,
                ],
                "source_file_volumen": ["v1.json", "v2.json"],
                "source_file_capacidad": [
                    "c1.json",
                    "c2.json",
                ],
                "source_file_porcentaje": [
                    "p1.json",
                    "p2.json",
                ],
            }
        )

        checked = self.module.apply_quality_rules(frame)

        self.assertEqual(
            checked.loc[0, "quality_status"],
            "WARNING",
        )
        self.assertTrue(bool(checked.loc[0, "model_ready"]))
        self.assertIn(
            "INCONSISTENCIA_RELACION_VOLUMEN_CAPACIDAD",
            checked.loc[0, "quality_issues"],
        )

        self.assertEqual(
            checked.loc[1, "quality_status"],
            "ERROR",
        )
        self.assertFalse(bool(checked.loc[1, "model_ready"]))
        self.assertIn(
            "VOLUMEN_NEGATIVO",
            checked.loc[1, "quality_issues"],
        )
        self.assertIn(
            "PORCENTAJE_OFICIAL_NEGATIVO",
            checked.loc[1, "quality_issues"],
        )

    def test_reservoir_coverage_records_catalog_entity_without_data(self):
        frame = pd.DataFrame(
            {
                "date": ["2020-01-01"],
                "reservoir_code": ["PLAYAS"],
                "reservoir_name": ["PLAYAS"],
                "volumen_util_energia_gwh": [50.0],
                "capacidad_util_energia_gwh": [100.0],
                "porcentaje_volumen_util_oficial": [50.0],
                "model_ready": [True],
            }
        )
        coverage = self.module.reservoir_coverage(frame)
        florida = coverage.loc[
            coverage["reservoir_code"] == "FLORIDA II"
        ].iloc[0]
        self.assertFalse(bool(florida["observed"]))
        self.assertEqual(
            florida["status"],
            "ENTIDAD_CATALOGO_SIN_REPORTE_METRICA",
        )

    def test_versioning_without_overwrite(self):
        (
            self.base
            / "data/processed/xm/hydro_reservoir_historical_v1"
        ).mkdir(parents=True)
        (self.base / "outputs/run_015").mkdir(parents=True)

        self.assertEqual(
            self.module.versioned_dataset_path(
                "data/processed/xm/hydro_reservoir_historical"
            ).name,
            "hydro_reservoir_historical_v2",
        )
        self.assertEqual(
            self.module.versioned_run_path(
                "outputs/run_015"
            ).name,
            "run_015_v002",
        )

    def test_csv_parquet_generation_and_reproducible_digest(self):
        row = {
            column: pd.NA
            for column in self.module.DAILY_COLUMNS
        }
        row.update(
            {
                "date": "2020-01-01",
                "reservoir_code": "PLAYAS",
                "reservoir_name": "PLAYAS",
                "volumen_util_energia_kwh": 50_000_000.0,
                "volumen_util_energia_gwh": 50.0,
                "capacidad_util_energia_kwh": 100_000_000.0,
                "capacidad_util_energia_gwh": 100.0,
                "porcentaje_volumen_util_oficial_raw": 0.5,
                "porcentaje_volumen_util_oficial": 50.0,
                "porcentaje_volumen_util_calculado": 50.0,
                "diferencia_porcentajes_pp": 0.0,
                "source_file_volumen": "v.json",
                "source_file_capacidad": "c.json",
                "source_file_porcentaje": "p.json",
                "quality_status": "OK",
                "quality_issues": "",
                "model_ready": True,
            }
        )
        frame = pd.DataFrame([row]).reindex(
            columns=self.module.DAILY_COLUMNS
        )
        out = self.base / "out"
        csv_path = out / "data.csv"
        parquet_path = out / "data.parquet"

        self.module.safe_write_csv(
            csv_path,
            frame,
            self.module.DAILY_COLUMNS,
        )
        self.module.safe_write_parquet(
            parquet_path,
            frame[self.module.DAILY_COLUMNS],
        )

        self.assertTrue(csv_path.exists())
        self.assertTrue(parquet_path.exists())
        self.assertEqual(
            len(pd.read_csv(csv_path)),
            len(pd.read_parquet(parquet_path)),
        )
        self.assertEqual(
            self.module.dataframe_digest(
                frame[self.module.DAILY_COLUMNS]
            ),
            self.module.dataframe_digest(
                frame[self.module.DAILY_COLUMNS]
            ),
        )
        with self.assertRaises(FileExistsError):
            self.module.safe_write_csv(csv_path, frame)


if __name__ == "__main__":
    unittest.main()
