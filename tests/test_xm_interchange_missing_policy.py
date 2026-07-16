from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/12_auditar_intercambios_xm.py"
spec = importlib.util.spec_from_file_location("xm_interchange_audit", SCRIPT)
xm = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(xm)


def response(metric_id="ImpoEner", value="0", date="2023-01-01"):
    values = {"code": "Sistema", **{f"Hour{i:02d}": "" for i in range(1, 25)}}
    values["Hour01"] = value
    return {
        "Metric": {"Id": metric_id},
        "Items": [{"Date": date, "HourlyEntities": [{"Id": "Sistema", "Values": values}]}],
    }


class XMInterchangeMissingPolicyTest(unittest.TestCase):
    def make_raw(self, payload, target="importaciones_energia_sistema", start="2023-01-01", end="2023-01-01"):
        tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / f"{target}__{start}__{end}__b001.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_identifies_empty_window(self):
        path = self.make_raw({"Metric": {"Id": "ImpoEner"}, "Items": []})
        rows, summary, missing, zeros = xm.classify_window("importaciones_energia_sistema", path)
        self.assertTrue(summary["empty_window"])
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(row["status"] == "UNKNOWN_EMPTY_WINDOW" for row in rows))
        self.assertEqual(len(zeros), 0)

    def test_detects_explicit_zero(self):
        path = self.make_raw(response(value="0"))
        rows, _, _, zeros = xm.classify_window("importaciones_energia_sistema", path)
        self.assertEqual(rows[0]["status"], "EXPLICIT_ZERO")
        self.assertEqual(rows[0]["value_gwh"], 0.0)
        self.assertEqual(len(zeros), 1)

    def test_blank_hour_inside_valid_response_is_structural_candidate(self):
        path = self.make_raw(response(value="1250000"))
        rows, _, missing, _ = xm.classify_window("importaciones_energia_sistema", path)
        by_hour = {row["hora_xm"]: row for row in rows}
        self.assertEqual(by_hour["Hour01"]["status"], "REPORTED_VALUE")
        self.assertEqual(by_hour["Hour02"]["status"], "STRUCTURAL_ZERO_INFERRED")
        self.assertTrue(by_hour["Hour02"]["imputed"])
        self.assertGreaterEqual(len(missing), 23)

    def test_unknown_empty_window_is_not_zero(self):
        path = self.make_raw({"Metric": {"Id": "ImpoEner"}, "Items": []})
        rows, _, _, _ = xm.classify_window("importaciones_energia_sistema", path)
        self.assertEqual(rows[0]["status"], "UNKNOWN_EMPTY_WINDOW")
        self.assertTrue(pd.isna(rows[0]["value_gwh"]))
        self.assertFalse(rows[0]["imputed"])

    def test_policy_has_separate_import_and_export_rules(self):
        policy = xm.build_policy_file("STRUCTURAL_ZERO_POLICY_VALIDATED_WITH_WARNINGS")
        targets = {rule["target"] for rule in policy["policies"]}
        self.assertEqual(targets, {"importaciones_energia_sistema", "exportaciones_energia_sistema"})
        for rule in policy["policies"]:
            self.assertEqual(rule["empty_window_policy"], "UNKNOWN_EMPTY_WINDOW")

    def test_preserves_reported_value_conversion(self):
        path = self.make_raw(response(value="3500000"))
        rows, _, _, _ = xm.classify_window("importaciones_energia_sistema", path)
        self.assertEqual(rows[0]["status"], "REPORTED_VALUE")
        self.assertAlmostEqual(rows[0]["value_gwh"], 3.5)

    def test_balance_and_model_ready_construction(self):
        hourly = pd.DataFrame(
            {
                "fecha": ["2023-01-01"] * 24,
                "hora_xm": [f"Hour{i:02d}" for i in range(1, 25)],
                "demanda_real_gwh": [1.0] * 24,
                "generacion_total_gwh": [1.0] * 24,
                "importaciones_gwh": [0.0] * 24,
                "importaciones_status": ["STRUCTURAL_ZERO_INFERRED"] * 24,
                "exportaciones_gwh": [0.0] * 24,
                "exportaciones_status": ["REPORTED_VALUE"] * 24,
                "demanda_real_reportada": [True] * 24,
                "generacion_reportada": [True] * 24,
            }
        )
        frames = {"demanda_sin_diaria": pd.DataFrame({"Date": ["2023-01-01"], "Value_GWh": [24.0]})}
        daily, ready, excluded = xm.build_daily_v2(frames, hourly, "2023-01-01", "2023-01-01")
        self.assertEqual(len(daily), 1)
        self.assertEqual(len(ready), 1)
        self.assertEqual(len(excluded), 0)
        self.assertAlmostEqual(float(daily.loc[0, "diferencia_balance_gwh"]), 0.0)

    def test_excludes_unknown_days_from_model_ready(self):
        hourly = pd.DataFrame(
            {
                "fecha": ["2023-01-01"] * 24,
                "hora_xm": [f"Hour{i:02d}" for i in range(1, 25)],
                "demanda_real_gwh": [1.0] * 24,
                "generacion_total_gwh": [1.0] * 24,
                "importaciones_gwh": [pd.NA] * 24,
                "importaciones_status": ["UNKNOWN_EMPTY_WINDOW"] * 24,
                "exportaciones_gwh": [0.0] * 24,
                "exportaciones_status": ["STRUCTURAL_ZERO_INFERRED"] * 24,
                "demanda_real_reportada": [True] * 24,
                "generacion_reportada": [True] * 24,
            }
        )
        frames = {"demanda_sin_diaria": pd.DataFrame({"Date": ["2023-01-01"], "Value_GWh": [24.0]})}
        _, ready, excluded = xm.build_daily_v2(frames, hourly, "2023-01-01", "2023-01-01")
        self.assertEqual(len(ready), 0)
        self.assertIn("importaciones_unknown_empty_window", excluded.loc[0, "motivo_exclusion"])

    def test_versioning_and_no_overwrite(self):
        tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name) / "system_historical_v2"
        base.mkdir()
        candidate = xm.versioned_path(str(base.relative_to(ROOT)), dataset=True)
        self.assertTrue(candidate.name.endswith("_v3"))
        (base / "x.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            xm.write_json(base / "x.json", {"a": 1})

    def test_sha256_traceability(self):
        path = self.make_raw(response(value="1000000"))
        rows, _, _, _ = xm.classify_window("importaciones_energia_sistema", path)
        self.assertRegex(rows[0]["source_sha256"], r"^[0-9a-f]{64}$")

    def test_no_network_in_dry_run(self):
        with patch("urllib.request.urlopen") as urlopen:
            code = xm.dry_run(xm.build_parser().parse_args(["--dry-run"]))
        self.assertEqual(code, 0)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
