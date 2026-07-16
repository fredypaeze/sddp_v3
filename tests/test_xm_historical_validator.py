from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/09_validar_descargas_xm2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xm_historical_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_response(metric_id: str = "DemaSIN", entity_col: str = "DailyEntities", start: str = "2023-01-01", end: str = "2023-01-30"):
    values = {"code": "Sistema", "Value": "1000000"}
    if entity_col == "HourlyEntities":
        values = {"code": "Sistema", **{f"Hour{i:02d}": "1000000" for i in range(1, 25)}}
    return {
        "Metric": {"Id": metric_id, "Name": metric_id, "StartDate": f"{start}T00:00:00", "EndDate": f"{end}T00:00:00"},
        "Items": [{"Date": start, entity_col: [{"Id": "Sistema", "Values": values}]}],
    }


class HistoricalXMValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.module.ROOT = self.base
        self.spec = self.module.TargetSpec(
            target="demanda_sin_diaria",
            metric_id="DemaSIN",
            entity="Sistema",
            periodicity="DailyEntities",
            unit="kWh",
            output_domain="demanda",
        )
        self.raw_dir = self.base / "data/raw/xm/demanda/demanda_sin_diaria"
        self.raw_dir.mkdir(parents=True)
        self.run_dir = self.base / "outputs/run_010"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_raw(self, name: str, data) -> Path:
        path = self.raw_dir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_help_does_not_validate(self) -> None:
        parser = self.module.build_parser()
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--dry-run", stdout.getvalue())
        self.assertFalse(self.run_dir.exists())

    def test_dry_run_does_not_write(self) -> None:
        self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", sample_response())
        args = self.module.build_parser().parse_args(["--dry-run", "--target", "demanda_sin_diaria", "--run-dir", "outputs/run_010"])
        with contextlib.redirect_stdout(io.StringIO()):
            code = self.module.dry_run(args, {"demanda_sin_diaria": self.spec})
        self.assertEqual(code, 0)
        self.assertFalse(self.run_dir.exists())

    def test_selection_exclusive_targets(self) -> None:
        args = self.module.build_parser().parse_args(["--target", "demanda_sin_diaria"])
        self.assertEqual(self.module.selected_targets(args), ["demanda_sin_diaria"])

    def test_excludes_pilot_by_authorized_paths(self) -> None:
        pilot = self.base / "data/raw/xm/pilot_20260601_20260607_retry1/demanda_sin_diaria"
        pilot.mkdir(parents=True)
        (pilot / "demanda_sin_diaria__2026-06-01__2026-06-07__b001.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.module.list_target_files(self.spec), [])

    def test_reconstruct_windows(self) -> None:
        windows = self.module.date_windows("2023-01-01", "2026-07-13")
        self.assertEqual(len(windows), 43)
        self.assertEqual(windows[0], ("2023-01-01", "2023-01-30"))
        self.assertEqual(windows[-1], ("2026-06-14", "2026-07-13"))

    def test_detect_missing_windows(self) -> None:
        expected = self.module.date_windows("2023-01-01", "2023-03-01")
        self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", sample_response())
        coverage, missing, _ = self.module.coverage_for_target(self.spec, self.module.list_target_files(self.spec), expected, [])
        self.assertEqual(coverage["windows_expected"], 2)
        self.assertEqual(len(missing), 1)

    def test_detect_overlaps(self) -> None:
        expected = [("2023-01-01", "2023-01-30"), ("2023-01-30", "2023-02-28")]
        coverage, _, _ = self.module.coverage_for_target(self.spec, [], expected, [])
        self.assertEqual(coverage["overlaps"], 1)

    def test_empty_json(self) -> None:
        path = self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", {})
        errors = []
        row, _ = self.module.validate_file(path, self.spec, errors)
        self.assertFalse(row["non_empty"])
        self.assertEqual(errors[0]["code"], "EMPTY_JSON")

    def test_invalid_json(self) -> None:
        path = self.raw_dir / "demanda_sin_diaria__2023-01-01__2023-01-30__b001.json"
        path.write_text("{bad", encoding="utf-8")
        errors = []
        row, _ = self.module.validate_file(path, self.spec, errors)
        self.assertFalse(row["json_valid"])
        self.assertEqual(errors[0]["code"], "INVALID_JSON")

    def test_wrong_schema(self) -> None:
        data = sample_response()
        data["Items"][0].pop("DailyEntities")
        path = self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", data)
        errors = []
        self.module.validate_file(path, self.spec, errors)
        self.assertTrue(any(err["code"] == "SCHEMA_MISSING_ENTITY_COLUMN" for err in errors))

    def test_date_out_of_range(self) -> None:
        path = self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", sample_response(start="2023-02-01"))
        errors = []
        row, _ = self.module.validate_file(path, self.spec, errors)
        self.assertFalse(row["dates_inside_window"])
        self.assertTrue(any(err["code"] == "DATE_OUT_OF_WINDOW" for err in errors))

    def test_sha256_and_kwh_conversion(self) -> None:
        path = self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", sample_response())
        errors = []
        row, frame = self.module.validate_file(path, self.spec, errors)
        self.assertEqual(len(row["sha256"]), 64)
        normalized = self.module.derive_units_contextual(frame, target=self.spec.target, metric_id=self.spec.metric_id, entity=self.spec.entity, catalog_unit=self.spec.unit)
        self.assertEqual(float(normalized.loc[0, "Value_GWh"]), 1.0)
        self.assertEqual(row["unit_effective"], "kWh")

    def test_no_overwrite_uses_versioned_run_dir(self) -> None:
        self.run_dir.mkdir(parents=True)
        resolved = self.module.resolve_run_dir("outputs/run_010")
        self.assertEqual(resolved.name, "run_010_v002")

    def test_writes_only_run_010(self) -> None:
        self.write_raw("demanda_sin_diaria__2023-01-01__2023-01-30__b001.json", sample_response())
        args = self.module.build_parser().parse_args([
            "--target", "demanda_sin_diaria",
            "--start-date", "2023-01-01",
            "--end-date", "2023-01-30",
            "--run-dir", "outputs/run_010",
        ])
        summary = self.module.validate(args, {"demanda_sin_diaria": self.spec}, "python scripts/09_validar_descargas_xm2.py")
        self.assertEqual(summary["run_dir"], "outputs\\run_010" if "\\" in summary["run_dir"] else "outputs/run_010")
        self.assertTrue((self.run_dir / "resumen_validacion.json").exists())
        self.assertFalse((self.base / "outputs/run_008").exists())


if __name__ == "__main__":
    unittest.main()




