# Reporte de calidad de datos

Estado: **BLOCKED_CRITICAL_DATA**

## Cobertura

- generation_rows: 1278
- generation_range: ['2023-01-01', '2026-05-31']
- aportes_rows: 6027
- aportes_range: ['2010-01-01', '2026-06-01']
- bolsa_rows: 6026
- bolsa_range: ['2010-01-01', '2026-05-31']
- offer_resource_codes: 95
- offer_range: ['2010-01-01', '2026-06-30']
- thermal_resources: 77
- central_thermal_resources: 41
- xm_metric_presence: {'DemaReal': True, 'catalogo_metricas_disponible': True}
- scenario_dates: 12
- scenario_names: ['Debil', 'Fuerte', 'Moderado', 'MuyFuerte', 'Neutro']

## Indicadores

| Metrica | Valor | Detalle |
|---|---:|---|
| catalogo_vs_generacion_por_recurso | 0.000000 | generacion_2023_2026.csv esta agregada a Sistema; no trae codigo_recurso. |
| termicas_con_precio_oferta | 0.519481 | 40/77 recursos termicos. |
| termicas_centrales_con_precio_oferta | 0.975610 | 40/41 termicas despachadas centralmente. |
| termicas_con_capacidad_mw | 0.000000 | Listado de plantas no contiene capacidad_mw. |
| termicas_con_disponibilidad_mw | 0.000000 | Values_Disp es clasificacion de despacho central, no disponibilidad_mw temporal. |
| escenarios_probabilidades_validas_por_fecha | 1.000000 | 12/12 fechas suman 1. |

## Razones de bloqueo

- No hay demanda oficial local ni desagregacion de solar, eolica, cogeneracion, importaciones u otras fuentes para reconstruir balance electrico.
- La generacion historica disponible esta agregada a Sistema en hidro_gwh y termo_gwh; no permite recomendacion por recurso.
- No hay capacidad_mw ni disponibilidad_mw temporal por recurso termico en los archivos auditados.
- embalses_manu proyecta volumen util/porcentaje mensual; no existe relacion tecnica auditada para convertir volumen util o masa a energia almacenada GWh.
- Las trayectorias proyectadas de volumen no son aportes hidricos exogenos ni pueden fijarse como almacenamiento endogeno del despacho.