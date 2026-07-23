"""Despacho hidro-termico deterministico sobre las ultimas 26 semanas observadas.

Ejecucion de validacion con "vision perfecta" (los aportes observados actuan como
un escenario deterministico). Compara fase neutral vs. El Nino y guarda una
carpeta reproducible en outputs/run_020_v001/.

Uso:
    PYTHONPATH=src python scripts/20_despacho_deterministico.py [--semanas 26] [--fase neutral|nino|nina]
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from minenergia_sddp.config.paths import project_root
from minenergia_sddp.dispatch.datasets import load_daily, to_stages
from minenergia_sddp.dispatch.deterministic import CONFIG_DEFAULT, load_config, solve_deterministic
from minenergia_sddp.reporting.run import new_run

SYS = "data/processed/xm/system_historical_v3/system_daily_model_ready.csv"
HYD = "data/processed/xm/hydro_system_historical_v1/hydro_system_daily_model_ready.csv"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semanas", type=int, default=26)
    ap.add_argument("--dias", type=int, default=7)
    args = ap.parse_args()

    root = project_root()
    cfg = load_config()
    daily = load_daily()
    ventana = daily.tail(args.semanas * args.dias)
    sd = to_stages(ventana, dias_por_etapa=args.dias, n_etapas=args.semanas)

    carpeta = new_run("run_020_v001", config=cfg,
                      inputs=[root / SYS, root / HYD, root / CONFIG_DEFAULT],
                      descripcion="Despacho deterministico (vision perfecta) sobre las ultimas "
                                  f"{args.semanas} semanas. Neutral vs El Nino.")

    resumenes = {}
    for fase in ("neutral", "nino"):
        res = solve_deterministic(sd, cfg, fase_enos=fase)
        res.tabla.to_csv(carpeta / f"despacho_{fase}.csv", index=False)
        resumenes[fase] = res.resumen
        r = res.resumen
        print(f"[{fase}] factible={res.factible} costo={r['costo_total_billones_cop']:.4f} B COP "
              f"| termica {r['gen_termica_total_gwh']:.0f} GWh ({r['participacion_termica_pct']:.1f}%) "
              f"| ENS {r['ens_total_gwh']:.2f} GWh | vol_fin {r['volumen_final_gwh']:.0f} GWh")

    (carpeta / "resumen.json").write_text(
        json.dumps({"ventana": {"ini": str(sd.etapas.fecha_ini.iloc[0].date()),
                                "fin": str(sd.etapas.fecha_fin.iloc[-1].date()),
                                "n_etapas": sd.n_etapas,
                                "volumen_inicial_gwh": sd.volumen_inicial_gwh},
                    "resultados": resumenes}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("Salida:", carpeta.relative_to(root))


if __name__ == "__main__":
    main()
