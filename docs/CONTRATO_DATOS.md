# Contrato de datos

Los contratos definen campos requeridos; no implican que todos esten disponibles actualmente.

## embalses

| Campo | Obligatorio |
|---|---|
| `fecha` | si |
| `escenario_id` | si |
| `probabilidad` | si |
| `codigo_embalse` | si |
| `nombre_embalse` | si |
| `region` | si |
| `volumen_util` | si |
| `unidad_volumen` | si |
| `volumen_util_pct` | si |
| `capacidad_util` | si |
| `unidad_capacidad` | si |
| `energia_almacenada_gwh` | si |
| `dato_observado_o_proyectado` | si |
| `fecha_actualizacion` | si |
| `fuente` | si |

## aportes

| Campo | Obligatorio |
|---|---|
| `fecha` | si |
| `escenario_id` | si |
| `codigo_embalse_o_sistema` | si |
| `aporte` | si |
| `unidad_aporte` | si |
| `indice_aporte` | si |
| `fase_enos` | si |
| `oni` | si |
| `dato_observado_o_proyectado` | si |
| `fuente` | si |

## generacion

| Campo | Obligatorio |
|---|---|
| `fecha` | si |
| `codigo_recurso` | si |
| `tipo_recurso` | si |
| `generacion_gwh` | si |
| `granularidad` | si |
| `fuente` | si |

## demanda_otras_fuentes

| Campo | Obligatorio |
|---|---|
| `fecha` | si |
| `demanda_gwh` | si |
| `solar_gwh` | si |
| `eolica_gwh` | si |
| `cogeneracion_gwh` | si |
| `importacion_neta_gwh` | si |
| `otras_gwh` | si |
| `demanda_residual_gwh` | si |
| `fuente` | si |

## termicas

| Campo | Obligatorio |
|---|---|
| `fecha` | si |
| `codigo_recurso` | si |
| `nombre_recurso` | si |
| `combustible` | si |
| `despacho_central` | si |
| `capacidad_mw` | si |
| `disponibilidad_mw` | si |
| `energia_maxima_periodo_gwh` | si |
| `precio_oferta_cop_kwh` | si |
| `estado` | si |
| `fuente` | si |

## escenarios

| Campo | Obligatorio |
|---|---|
| `escenario_id` | si |
| `nombre_escenario` | si |
| `fecha` | si |
| `probabilidad` | si |
| `aporte` | si |
| `almacenamiento` | si |
| `fase_enos` | si |
| `oni` | si |
| `fuente` | si |
