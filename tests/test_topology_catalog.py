"""Pruebas del catalogo de topologia hidraulica."""

from __future__ import annotations

import unittest

from minenergia_sddp.topology.catalog import build_catalog, check_consistency, relations


class TopologyCatalogTest(unittest.TestCase):
    def test_todos_los_embalses_estan_en_datos(self) -> None:
        chk = check_consistency()
        self.assertEqual(chk["n_embalses_config"], 24)
        self.assertEqual(chk["n_embalses_en_datos"], 24, chk["faltantes_en_datos"])

    def test_cascadas_apuntan_a_embalses_existentes(self) -> None:
        chk = check_consistency()
        self.assertTrue(chk["destinos_de_cascada_validos"])
        self.assertGreaterEqual(chk["n_relaciones_cascada"], 3)

    def test_capacidades_positivas(self) -> None:
        cat = build_catalog()
        self.assertTrue((cat["capacidad_media_gwh"].dropna() > 0).all())

    def test_relaciones_tienen_metadato(self) -> None:
        rel = relations()
        for col in ["origen", "destino", "tipo_relacion", "fuente", "confianza", "validacion"]:
            self.assertIn(col, rel.columns)
        # cascadas bien establecidas presentes
        pares = set(zip(rel["origen"], rel["destino"]))
        self.assertIn(("EL QUIMBO", "BETANIA"), pares)
        self.assertIn(("PORCE II", "PORCE III"), pares)


if __name__ == "__main__":
    unittest.main()
