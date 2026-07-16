from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from minenergia_sddp.data.xm_checkpoints import mark_completed, mark_error

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/11_ejecutar_piloto_xm2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("xm_pilot_retry_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def fake_call(call_id: str = "demanda_sin_diaria__2026-06-01__2026-06-07__b001", target: str = "demanda_sin_diaria"):
    return {
        "call_id": call_id,
        "target": target,
        "metric_id": "DemaSIN",
        "entity": "Sistema",
        "periodicity": "DailyEntities",
        "url": "https://servapibi.xm.com.co/test",
        "start_date": "2026-06-01",
        "end_date": "2026-06-07",
        "filter_values": [],
        "filter_count": 0,
        "unit": "kWh",
    }


class XMPilotRetryCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.module.ORIGINAL_PILOT_ROOT = self.base / "data/raw/xm/pilot_20260601_20260607"
        self.module.PILOT_ROOT = self.base / "data/raw/xm/pilot_20260601_20260607_retry1"
        self.module.RUN_ROOT = self.base / "outputs/run_008"
        self.calls = [fake_call()]
        self.module.pilot_calls = lambda: list(self.calls)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_help_does_not_execute_pilot(self) -> None:
        parser = self.module.build_parser()
        with self.assertRaises(SystemExit) as raised:
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                parser.parse_args(["--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--execute", stdout.getvalue())
        self.assertFalse(self.module.RUN_ROOT.exists())

    def test_without_execute_does_not_use_http(self) -> None:
        with mock.patch.object(self.module, "XMClient", side_effect=AssertionError("HTTP client should not be built")):
            code = self.module.main(["--max-http-requests", "1"], command_line="python scripts/11_ejecutar_piloto_xm2.py")
        self.assertEqual(code, 0)

    def test_dry_run_does_not_open_network(self) -> None:
        with mock.patch.object(self.module, "XMClient", side_effect=AssertionError("network disabled")):
            code = self.module.main(
                ["--dry-run", "--retry-network-errors", "--max-http-requests", "100"],
                command_line="python scripts/11_ejecutar_piloto_xm2.py --dry-run --retry-network-errors --max-http-requests 100",
            )
        self.assertEqual(code, 0)
        summary = json.loads((self.module.RUN_ROOT / "resumen_piloto_retry.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["mode"], "dry-run")
        self.assertEqual(summary["requests_made"], 0)

    def test_execute_without_retry_network_errors_fails(self) -> None:
        mark_error(
            self.module.ORIGINAL_PILOT_ROOT / "demanda_sin_diaria",
            self.calls[0]["call_id"],
            "<urlopen error [WinError 10013] socket no permitido>",
            {},
        )
        with mock.patch.object(self.module, "XMClient", side_effect=AssertionError("must fail before HTTP")):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = self.module.main(["--execute"], command_line="python scripts/11_ejecutar_piloto_xm2.py --execute")
        self.assertEqual(code, 2)
        self.assertIn("--retry-network-errors", stderr.getvalue())

    def test_retry_network_errors_ignores_only_network_errors(self) -> None:
        other = fake_call("generacion_real_total__2026-06-01__2026-06-07__b001", "generacion_real_total")
        self.calls.append(other)
        mark_error(
            self.module.ORIGINAL_PILOT_ROOT / "demanda_sin_diaria",
            self.calls[0]["call_id"],
            "PermissionError socket local WinError 10013",
            {},
        )
        mark_error(self.module.ORIGINAL_PILOT_ROOT / "generacion_real_total", other["call_id"], "HTTP 400 payload invalido", {})
        plan = self.module.build_execution_plan(
            self.calls,
            retry_network_errors=True,
            resume=False,
            max_http_requests=100,
        )
        self.assertEqual([call["call_id"] for call in plan["planned"]], [self.calls[0]["call_id"]])
        self.assertEqual([call["call_id"] for call in plan["blocked_other"]], [other["call_id"]])

    def test_completed_lots_are_not_repeated(self) -> None:
        raw = self.module.PILOT_ROOT / "demanda_sin_diaria" / "ok.json"
        raw.parent.mkdir(parents=True)
        raw.write_text('{"ok": true}', encoding="utf-8")
        mark_completed(raw.parent, self.calls[0]["call_id"], raw, rows=1)
        plan = self.module.build_execution_plan(
            self.calls,
            retry_network_errors=True,
            resume=True,
            max_http_requests=100,
        )
        self.assertEqual(plan["planned"], [])
        self.assertEqual(len(plan["skipped_completed"]), 1)

    def test_run_007_checkpoint_remains_intact(self) -> None:
        checkpoint_dir = self.module.ORIGINAL_PILOT_ROOT / "demanda_sin_diaria"
        mark_error(checkpoint_dir, self.calls[0]["call_id"], "WinError 10013 socket no permitido", {})
        before = (checkpoint_dir / "_checkpoint.json").read_bytes()
        self.module.main(
            ["--dry-run", "--retry-network-errors"],
            command_line="python scripts/11_ejecutar_piloto_xm2.py --dry-run --retry-network-errors",
        )
        after = (checkpoint_dir / "_checkpoint.json").read_bytes()
        self.assertEqual(before, after)

    def test_retry_destinations_are_run_008_and_pilot_retry1(self) -> None:
        self.assertEqual(self.module.PILOT_ROOT.name, "pilot_20260601_20260607_retry1")
        self.assertEqual(self.module.RUN_ROOT.name, "run_008")

    def test_effective_limit_never_exceeds_100(self) -> None:
        self.assertEqual(self.module.effective_http_limit(500), 100)
        self.assertEqual(self.module.effective_http_limit(7), 7)

    def test_command_is_registered(self) -> None:
        command = "python scripts/11_ejecutar_piloto_xm2.py --dry-run --retry-network-errors --max-http-requests 100"
        self.module.main(["--dry-run", "--retry-network-errors", "--max-http-requests", "100"], command_line=command)
        recorded = (self.module.RUN_ROOT / "comando_ejecutado.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(recorded, command)


if __name__ == "__main__":
    unittest.main()
