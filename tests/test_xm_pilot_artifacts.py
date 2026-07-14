from __future__ import annotations

import json
import unittest
from pathlib import Path

from minenergia_sddp.data.xm_checkpoints import load_checkpoint, versioned_path
from minenergia_sddp.data.xm_pilot import normalize_xm_response


ROOT = Path(__file__).resolve().parents[1]


class XMPilotArtifactsTest(unittest.TestCase):
    def test_pilot_summary_documents_network_block(self) -> None:
        summary = json.loads((ROOT / "outputs/run_007/resumen_piloto.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "PILOT_BLOCKED_NETWORK")
        self.assertEqual(summary["period"], ["2026-06-01", "2026-06-07"])
        self.assertLessEqual(summary["requests_planned"], 100)
        self.assertEqual(summary["requests_ok"], 0)

    def test_no_completed_lots_after_network_block(self) -> None:
        checkpoints = list((ROOT / "data/raw/xm/pilot_20260601_20260607").glob("**/_checkpoint.json"))
        self.assertGreater(len(checkpoints), 0)
        for checkpoint in checkpoints:
            data = load_checkpoint(checkpoint.parent)
            self.assertEqual(data.get("completed", {}), {})
            self.assertGreaterEqual(len(data.get("errors", [])), 1)

    def test_no_normalized_data_created_when_network_blocked(self) -> None:
        normalized = list((ROOT / "data/raw/xm/pilot_20260601_20260607").glob("**/*_normalized.csv"))
        self.assertEqual(normalized, [])

    def test_normalizer_handles_empty_response(self) -> None:
        self.assertTrue(normalize_xm_response([], "DailyEntities").empty)

    def test_versioned_path_does_not_overwrite(self) -> None:
        base = ROOT / "outputs/run_007"
        first = versioned_path(base, "version_test", ".tmp")
        first.write_text("x", encoding="utf-8")
        second = versioned_path(base, "version_test", ".tmp")
        self.assertNotEqual(first, second)
        first.unlink()


if __name__ == "__main__":
    unittest.main()

