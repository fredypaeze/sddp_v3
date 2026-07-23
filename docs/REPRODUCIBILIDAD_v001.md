# Reproducibilidad (v001)

## Entorno

- Python **3.11** (venv `.venv` con `uv`). Instalar: `uv pip install -r requirements.txt -r requirements-model.txt`.
- Parche pydataxm: `python scripts/14_parchear_pydataxm.py --apply`.
- Datos: descomprimir `paquete_datos/transferencia_sddp_v3_20260723.zip` (SHA-256 verificado; manifiesto 3079/3079) y copiar `data/` y `outputs/` a la raíz.

## Ejecuciones reproducibles

Cada script importante crea `outputs/run_XXX_vYYY/` (`src/minenergia_sddp/reporting/run.py`) con:

- `run_meta.json`: commit, fecha, python, plataforma, **semilla**, e **hashes SHA-256 de los insumos**.
- `config_usado.json`: parámetros de la corrida.
- resultados (CSV/JSON), y la evidencia que produjo cada cifra.

Nunca se guarda solo una gráfica sin sus datos, ni un agregado sin trazabilidad.

## Semillas

Todo muestreo (escenarios, SDDP forward, simulación) usa `numpy.random.Generator` con semilla explícita. Misma semilla ⇒ mismo resultado (probado en pronóstico, escenarios y SDDP).

## Pipeline completo (orden)

```
scripts/20_despacho_deterministico.py     # despacho deterministico (validacion)
scripts/22_pronostico_aportes.py          # pronostico ENOS
scripts/23_escenarios_aportes.py          # escenarios estocasticos
scripts/24_sddp.py                        # SDDP + politica
scripts/25_cvar_sensibilidad.py           # sensibilidad lambda/alpha
scripts/26_backtesting.py                 # backtesting historico
scripts/27_actualizar_incremental.py      # plan de actualizacion
```

## Pruebas

`python -m unittest discover -s tests` — 143 pruebas (7 *skip* documentados por catálogos externos). Cubren balances, unidades, cotas, límite determinístico del SDDP, convergencia, reproducibilidad, CVaR, escenarios, pronóstico, topología, API y actualización.
