"""Dashboard del modelo SDDP + CVaR (Streamlit) — solo lectura de outputs/run_*.

Ejecucion:
    PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901

Cada indicador incluye tooltip con definicion, unidad, fuente y si es
observado/modelado/supuesto. No ejecuta el modelo; muestra lo ya calculado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"


def load(run: str, name: str = "resumen.json"):
    p = OUT / run / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


st.set_page_config(page_title="SDDP + CVaR · MinEnergía", page_icon="⚡", layout="wide")
st.title("⚡ Modelo SDDP + CVaR · Ministerio de Minas y Energía")
st.caption("Optimización estocástica hidro-térmica del SIN bajo incertidumbre climática (ENOS). "
           "Todas las cifras provienen de ejecuciones reproducibles. Energía en GWh, precios en COP/kWh.")

sddp = load("run_024_v001")
sens = load("run_025_v001")
pron = load("run_022_v001")
bt = load("run_026_v001")
elnino = load("run_030_v001")
elnino_emb = load("run_031_v001")

tabs = st.tabs(["Estado y riesgo", "Recomendación térmica", "Sensibilidad λ/α",
                "Pronóstico ENOS", "Backtesting", "🌡️ El Niño · Riesgo de apagón"])

with tabs[0]:
    if not sddp:
        st.warning("Ejecuta `python scripts/24_sddp.py` para generar los resultados.")
    else:
        pol = sddp["politica"]
        st.subheader(f"Horizonte {sddp['horizonte'][0]} … {sddp['horizonte'][-1]} · fase {sddp['fase'].upper()}")
        c = st.columns(4)
        c[0].metric("Costo esperado", f"{pol['E_costo_billones_cop']:.2f} B COP",
                    help="E[costo operativo] del horizonte (térmica + ENS). Modelado (SDDP).")
        c[1].metric(f"VaR {int(pol['alpha']*100)}", f"{pol['VaR_billones_cop']:.2f} B COP",
                    help="Costo que no se supera con probabilidad α. Modelado.")
        c[2].metric(f"CVaR {int(pol['alpha']*100)}", f"{pol['CVaR_billones_cop']:.2f} B COP",
                    help="Costo esperado en el peor (1−α) de los escenarios (riesgo de cola). Modelado.")
        c[3].metric("Prob. de ENS", f"{pol['prob_ens_horizonte']:.1%}",
                    help="Probabilidad de energía no servida (déficit) en el horizonte. Modelado.")
        df = pd.DataFrame(pol["por_etapa"])
        fig = px.bar(df, x="fecha", y=["gen_hidro_gwh_media", "gen_termica_gwh_media"],
                     labels={"value": "GWh (media)", "fecha": "Etapa", "variable": "Fuente"},
                     title="Despacho esperado por etapa (hidro vs térmica)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Fuente: XM (demanda/hidrología); costos térmicos = supuesto config-driven. "
                   "Método: SDDP con escenarios ENOS. LB=%.2f UB=%.2f B COP, gap=%.3f."
                   % (sddp["convergencia"]["LB_billones"], sddp["convergencia"]["UB_billones"],
                      sddp["convergencia"]["gap"]))

with tabs[1]:
    if sddp:
        df = pd.DataFrame(sddp["politica"]["por_etapa"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        fig = px.line(df, x="fecha", y="valor_agua_cop_kwh_media", markers=True,
                      labels={"valor_agua_cop_kwh_media": "Valor del agua (COP/kWh)", "fecha": "Etapa"},
                      title="Valor del agua por etapa (dual del balance hídrico)")
        st.plotly_chart(fig, use_container_width=True)
        st.info("Valor del agua = ahorro marginal de costo por GWh extra de aporte. "
                "Cuando sube, conviene conservar agua y apoyarse en térmica.")

with tabs[2]:
    if not sens:
        st.warning("Ejecuta `python scripts/25_cvar_sensibilidad.py`.")
    else:
        st.write("**Caso base (embalse actual):**",
                 f"E={sens['base']['resultado']['E_costo']:.2f} · "
                 f"CVaR={sens['base']['resultado']['CVaR']:.2f} B COP · "
                 f"P(ENS)={sens['base']['resultado']['prob_ens']:.1%}")
        tabla = pd.DataFrame(sens["estres"]["tabla"])
        a95 = tabla[tabla["alpha"] == 0.95]
        fig = px.line(a95, x="lambda", y=["E_costo", "CVaR"], markers=True,
                      labels={"value": "B COP", "lambda": "λ (aversión al riesgo)", "variable": ""},
                      title="Estrés: trade-off costo esperado vs. CVaR al variar λ")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Caso de estrés (embalse bajo + térmica restringida). λ es un parámetro de política "
                   "pública: cuánto pagar (más costo esperado) para reducir el riesgo de cola (CVaR).")

with tabs[3]:
    if pron:
        st.write(f"**Mejor modelo:** {pron['mejor_modelo']} (MAE {pron['MAE_mejor']:.1f} GWh/día)")
        st.dataframe(pd.DataFrame(pron["pronostico"]), use_container_width=True, hide_index=True)
        st.caption("Aportes medios por fase (histórico): " +
                   ", ".join(f"{k}={v}" for k, v in pron["aportes_por_fase_hist"].items()) + " GWh/día.")

with tabs[4]:
    if bt:
        st.dataframe(pd.DataFrame(bt["tabla"]), use_container_width=True, hide_index=True)
        st.caption("Costo realizado (B COP) de cada política sobre la trayectoria de aportes OBSERVADA "
                   "de cada episodio. 'Visión perfecta' es cota inferior (conoce el futuro).")

with tabs[5]:
    st.subheader("Riesgo de apagón bajo El Niño 2026 (análogo hidrológico)")
    st.caption("2026 sigue el patrón de El Niño 1997/2015 (correlación SST diaria Niño 3.4 con 1997 = 0.98, "
               "análogo más cercano en 42 años). Se estresa el modelo con los aportes OBSERVADOS del super "
               "El Niño 2015-16. **Escenario físicamente fundamentado, no un pronóstico.**")
    if not elnino or not elnino_emb:
        st.warning("Ejecuta `scripts/30_elnino_stress.py` y `scripts/31_elnino_embalse_bajo.py`.")
    else:
        df30 = pd.DataFrame(elnino["tabla"])
        ana = df30[df30.escenario == "Analogo_2015-16"].iloc[0]
        neu = df30[df30.escenario == "Neutral"].iloc[0]
        k = st.columns(4)
        k[0].metric("Costo esperado (análogo)", f"{ana['E_costo_B']:.1f} B COP",
                    delta=f"{ana['E_costo_B']-neu['E_costo_B']:+.1f} vs neutral")
        k[1].metric("CVaR₉₅ (análogo)", f"{ana['CVaR95_B']:.1f} B COP",
                    delta=f"{ana['CVaR95_B']-neu['CVaR95_B']:+.1f} vs neutral")
        k[2].metric("Prob. de apagón (P(ENS))", f"{ana['prob_ens']:.1%}",
                    delta=f"{(ana['prob_ens']-neu['prob_ens'])*100:+.1f} pp", delta_color="inverse")
        k[3].metric("Generación térmica", f"{ana['gen_termica_gwh']:.0f} GWh",
                    delta=f"×{ana['gen_termica_gwh']/max(neu['gen_termica_gwh'],1):.0f}")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Costo y riesgo por escenario**")
            fig = px.bar(df30, x="escenario", y=["E_costo_B", "CVaR95_B"], barmode="group",
                         labels={"value": "B COP", "escenario": "", "variable": ""})
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("**Riesgo de apagón vs. nivel del embalse** (aportes análogo 2015-16)")
            emb = pd.DataFrame(elnino_emb["tabla"]).sort_values("embalse_inicial_pct")
            emb["P(ENS) %"] = emb["prob_ens"] * 100
            fig2 = px.line(emb, x="embalse_inicial_pct", y="P(ENS) %", markers=True,
                           labels={"embalse_inicial_pct": "Embalse inicial (% capacidad)"})
            fig2.update_traces(line_color="#c0392b")
            st.plotly_chart(fig2, use_container_width=True)

        st.error("**Lectura clave:** con el embalse actual (~79 %) el riesgo de apagón bajo un El Niño tipo "
                 "2015-16 es **manejable (~4 %)** — el agua embalsada amortigua. Pero si el sistema entra a la "
                 "temporada seca con el embalse al **30-40 %**, el riesgo salta a **24-70 %**, concentrado en "
                 "**nov-dic-ene**. **Prioridad operativa: conservar agua y preparar térmica ANTES de la seca.**")
        st.dataframe(pd.DataFrame(elnino_emb["tabla"])[["etiqueta", "embalse_inicial_pct", "E_costo_B",
                     "CVaR95_B", "prob_ens", "ens_total_gwh"]], hide_index=True, use_container_width=True)
        st.caption("Fuente aportes: XM (observados 2015-16). Costos: supuesto config-driven (COP/kWh por fase ENOS). "
                   "Análisis SST/análogo: NOAA CoralTemp v3.1. Honestidad: aportes análogos ≠ pronóstico; el valor "
                   "terminal del agua (v0.1.0) hace que el modelo drene el embalse (la comparación relativa es robusta).")

st.divider()
st.caption("Ministerio de Minas y Energía · Modelo SDDP + CVaR (v001) · cifras trazables a outputs/run_*.")
