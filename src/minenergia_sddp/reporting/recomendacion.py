"""Capa de interpretacion operativa del resultado del SDDP.

Traduce la simulacion de la politica en una recomendacion accionable de despacho y
priorizacion termica por etapa. TODOS los valores provienen de la ejecucion (no se
inventan): generacion termica esperada, agua conservada, valor del agua, riesgo de
ENS. Responde "cuando/cuanto/por que" aumentar la termica (encargo, seccion 20).
"""

from __future__ import annotations

import numpy as np


def recomendacion_por_etapa(sim: dict, meta, umbral_valor_agua: float = 250.0) -> list[dict]:
    """Construye la recomendacion por etapa a partir de la simulacion de la politica.

    umbral_valor_agua (COP/kWh): por encima, el agua es escasa/valiosa => senal de
    aumentar termica y conservar agua.
    """
    det = sim["detalle"]
    T = det["gt"].shape[1]
    filas = []
    for s in range(T):
        dias = _dias(meta.fechas[s])
        gt = det["gt"][:, s]
        gh = det["gh"][:, s]
        ens = det["ens"][:, s]
        vfin = det["v_next"][:, s]
        va = det["valor_agua_cop_kwh"][:, s]
        prob_ens = float((ens > 1e-6).mean())
        va_med = float(np.mean(va))
        gt_dia = float(gt.mean()) / dias
        gh_dia = float(gh.mean()) / dias
        vol_pct = 100.0 * float(vfin.mean()) / meta.capacidad_gwh
        if prob_ens > 0.05 or va_med > umbral_valor_agua:
            senal = "aumentar_termica_conservar_agua"
        elif va_med < umbral_valor_agua * 0.6:
            senal = "priorizar_hidro"
        else:
            senal = "equilibrado"
        filas.append({
            "etapa": s + 1, "fecha": meta.fechas[s], "fase_oni": round(meta.oni_path[s], 2),
            "gen_termica_gwh_dia": round(gt_dia, 1),
            "gen_hidro_gwh_dia": round(gh_dia, 1),
            "valor_agua_cop_kwh": round(va_med, 1),
            "volumen_esperado_pct": round(vol_pct, 1),
            "prob_ens": round(prob_ens, 3),
            "senal": senal,
        })
    return filas


def _dias(fecha_ym: str) -> int:
    import calendar
    y, m = int(fecha_ym[:4]), int(fecha_ym[5:7])
    return calendar.monthrange(y, m)[1]


def frase_recomendacion(por_etapa: list[dict], resumen: dict) -> str:
    """Frase de recomendacion en lenguaje natural, con valores trazables del run."""
    n_term = [e for e in por_etapa if e["senal"] == "aumentar_termica_conservar_agua"]
    if n_term:
        e0 = n_term[0]
        cuerpo = (f"En {e0['fecha']} conviene aumentar la generacion termica a ~"
                  f"{e0['gen_termica_gwh_dia']:.0f} GWh/dia (valor del agua "
                  f"{e0['valor_agua_cop_kwh']:.0f} COP/kWh, volumen esperado "
                  f"{e0['volumen_esperado_pct']:.0f}%): conservar agua reduce el riesgo de "
                  f"deficit en la cola seca.")
    else:
        cuerpo = ("El sistema no requiere aumentar la termica de forma anticipada en el horizonte: "
                  "la hidraulica cubre la demanda con bajo riesgo de deficit.")
    return (f"{cuerpo} Costo esperado del horizonte: {resumen['E_costo_billones_cop']:.2f} "
            f"billones COP; CVaR_{int(resumen['alpha']*100)} "
            f"{resumen['CVaR_billones_cop']:.2f} billones; probabilidad de ENS "
            f"{resumen['prob_ens_horizonte']:.1%}.")
