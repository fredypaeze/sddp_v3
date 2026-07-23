from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from minenergia_sddp.data.xm_catalog import (
    build_call_plan,
    build_metric_definitions,
    date_windows,
    output_dir_for,
)
from minenergia_sddp.data.xm_checkpoints import is_completed, mark_completed, sha256_file, versioned_path
from minenergia_sddp.data.xm_client import ExecutionBlocked, XMClient, payload_for_call
from minenergia_sddp.data.xm_validation import (
    kwh_to_gwh,
    preserve_price_unit,
    validate_non_empty_response,
    validate_payload_schema,
)


class XMAcquisitionTest(unittest.TestCase):
    def test_metric_ids_are_found(self) -> None:
        metrics = build_metric_definitions(end_date="2023-01-30")
        ids = {(m.metric_id, m.entity) for m in metrics}
        self.assertIn(("DemaSIN", "Sistema"), ids)
        self.assertIn(("Gene", "Recurso"), ids)
        self.assertIn(("VoluUtilDiarEner", "Embalse"), ids)
        self.assertIn(("PorcVoluUtilDiar", "Sistema"), ids)
        self.assertIn(("PorcVoluUtilDiar", "Embalse"), ids)
        self.assertTrue(all(m.status == "FOUND_EXACT" for m in metrics))

    def test_30_day_windows_do_not_overlap(self) -> None:
        windows = date_windows("2023-01-01", "2023-03-05", 30)
        self.assertEqual(windows[0], ("2023-01-01", "2023-01-30"))
        self.assertEqual(windows[1], ("2023-01-31", "2023-03-01"))
        self.assertEqual(windows[2], ("2023-03-02", "2023-03-05"))

    def test_downloader_is_blocked_without_execute(self) -> None:
        client = XMClient(execute=False)
        with self.assertRaises(ExecutionBlocked):
            client.post_json("https://servapibi.xm.com.co/daily", {"MetricId": "DemaSIN"})

    def test_payload_schema(self) -> None:
        metrics = [m for m in build_metric_definitions(end_date="2023-01-30") if m.target == "generacion_real_por_recurso"]
        call = build_call_plan(metrics, max_resources=2)[0]
        payload = payload_for_call(call)
        validate_payload_schema(payload, call)
        self.assertIn("Filter", payload)

    def test_output_routes(self) -> None:
        metric = [m for m in build_metric_definitions(end_date="2023-01-30") if m.target == "demanda_sin_diaria"][0]
        self.assertEqual(output_dir_for(metric), "data/raw/xm/demanda/demanda_sin_diaria")

    def test_percentage_output_route(self) -> None:
        metrics = build_metric_definitions(end_date="2023-01-30")
        metric = [
            item
            for item in metrics
            if item.target == "porcentaje_volumen_util_embalse"
        ][0]
        self.assertEqual(
            output_dir_for(metric),
            "data/raw/xm/embalses/porcentaje_volumen_util_embalse",
        )

    def test_percentage_metric_configuration(self) -> None:
        metrics = build_metric_definitions(end_date="2026-07-13")
        selected = {
            item.target: item
            for item in metrics
            if item.metric_id == "PorcVoluUtilDiar"
        }
        self.assertEqual(
            set(selected),
            {
                "porcentaje_volumen_util_sin",
                "porcentaje_volumen_util_embalse",
            },
        )
        self.assertEqual(
            selected["porcentaje_volumen_util_sin"].unit,
            "%",
        )
        self.assertEqual(
            selected["porcentaje_volumen_util_embalse"].unit,
            "%",
        )
        self.assertEqual(
            selected["porcentaje_volumen_util_embalse"].periodicity,
            "DailyEntities",
        )
        self.assertEqual(
            selected["porcentaje_volumen_util_embalse"].max_days,
            31,
        )

    def test_percentage_call_counts(self) -> None:
        metrics = build_metric_definitions(end_date="2026-07-13")
        system_metric = [
            item
            for item in metrics
            if item.target == "porcentaje_volumen_util_sin"
        ]
        reservoir_metric = [
            item
            for item in metrics
            if item.target == "porcentaje_volumen_util_embalse"
        ]
        system_calls = build_call_plan(system_metric)
        reservoir_calls = build_call_plan(reservoir_metric)
        combined_calls = build_call_plan(
            system_metric + reservoir_metric
        )
        self.assertEqual(len(system_calls), 202)
        self.assertEqual(len(reservoir_calls), 606)
        self.assertEqual(len(combined_calls), 808)

    def test_units(self) -> None:
        self.assertEqual(kwh_to_gwh(1_000_000), 1.0)
        self.assertEqual(preserve_price_unit("COP/kWh"), "COP/kWh")
        with self.assertRaises(ValueError):
            preserve_price_unit("COP/MWh")

    def test_empty_response_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_non_empty_response([])

    def test_checkpoint_resume_and_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = versioned_path(base, "lote", ".json")
            target.write_text('{"ok": true}', encoding="utf-8")
            mark_completed(base, "call-1", target, rows=1)
            self.assertTrue(is_completed(base, "call-1"))
            self.assertEqual(len(sha256_file(target)), 64)


if __name__ == "__main__":
    unittest.main()

