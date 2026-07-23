"""Pruebas de actualizacion incremental y API."""

from __future__ import annotations

import unittest

from minenergia_sddp.data.incremental import build_update_plan, plan_missing_windows


class IncrementalTest(unittest.TestCase):
    def test_ventanas_cubren_y_no_exceden(self) -> None:
        v = plan_missing_windows("2026-01-01", "2026-05-15", max_dias=60)
        self.assertGreater(len(v), 0)
        self.assertEqual(v[0][0], "2026-01-02")
        self.assertEqual(v[-1][1], "2026-05-15")
        for ini, fin in v:
            self.assertLessEqual(fin, "2026-05-15")

    def test_sin_faltantes_si_objetivo_es_pasado(self) -> None:
        v = plan_missing_windows("2026-05-15", "2026-05-15")
        self.assertEqual(v, [])

    def test_plan_detecta_ultima_fecha(self) -> None:
        plan = build_update_plan(hasta="2026-07-23")
        self.assertIn("sistema", plan.ultima_fecha)
        self.assertIn("hidrologia", plan.ultima_fecha)
        self.assertIsInstance(plan.puede_descargar, bool)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from fastapi.testclient import TestClient
        from minenergia_sddp.api.app import app
        cls.client = TestClient(app)

    def test_estado(self) -> None:
        r = self.client.get("/estado")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ultima_fecha_datos", r.json())

    def test_embalses(self) -> None:
        r = self.client.get("/embalses")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["n"], 24)

    def test_ultima_actualizacion(self) -> None:
        r = self.client.get("/ultima_actualizacion")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
