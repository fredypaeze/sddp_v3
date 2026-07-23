# Diccionario de datos (v001)

Unidades: energía en **GWh**; precios/valor del agua en **COP/kWh**; costos totales en **COP** (o billones = 10¹²).

## Datasets model-ready

`system_daily_model_ready.csv` (diario, SIN)
| Campo | Definición | Unidad |
|---|---|---|
| fecha | Día | fecha |
| demanda_sin_gwh | Demanda del SIN | GWh |
| generacion_total_gwh | Generación total | GWh |
| importaciones_gwh / exportaciones_gwh | Intercambios | GWh |
| datos_completos_balance | Bandera de completitud | bool |

`hydro_system_daily_model_ready.csv` (diario, SIN)
| Campo | Definición | Unidad |
|---|---|---|
| aportes_energia_gwh | Aportes hídricos en energía | GWh |
| volumen_util_energia_gwh | Volumen útil almacenado | GWh |
| capacidad_util_energia_gwh | Capacidad útil | GWh |
| porcentaje_volumen_util_calculado | Volumen / capacidad | % |

`hydro_reservoir_daily_model_ready.csv` (diario, 24 embalses): idem por `reservoir_code`.

`data/reference/oni_noaa.csv`: `anio, mes, temporada, oni` (°C), `fase_enos` (nino/nina/neutral).

## Salidas del modelo (outputs/run_*)

| Campo | Definición | Unidad |
|---|---|---|
| gen_hidro_gwh / gen_termica_gwh | Despacho por etapa | GWh |
| ens_gwh | Energía no servida (déficit) | GWh |
| vertimiento_gwh | Agua vertida (no turbinada) | GWh |
| volumen_fin_gwh / volumen_pct | Estado del embalse al cierre | GWh / % |
| valor_agua_cop_kwh | Ahorro marginal por GWh de aporte (−dual balance hídrico) | COP/kWh |
| E_costo / VaR / CVaR (billones_cop) | Esperado / cuantil α / cola α del costo | 10¹² COP |
| prob_ens | Probabilidad de déficit en el horizonte | — |
| lambda / alpha | Aversión al riesgo / nivel de cola | — |

## Parámetros (config/model/parametros_base.json)

Costo térmico por fase ENOS, capacidad térmica, costo de ENS, valor del agua terminal, otras fuentes, turbina máx. Cada uno con `fuente`, `confianza` y `nota`. Los marcados `supuesto` **no** son dato oficial.

## Etiquetado de procedencia

Toda cifra en dashboard/reportes se marca como: **oficial** (XM/NOAA), **cálculo**, **modelo** (SDDP/pronóstico), **supuesto** (config) o **dato con rezago**.
