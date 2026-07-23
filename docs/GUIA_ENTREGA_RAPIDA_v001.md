# Guía de entrega rápida — SDDP + CVaR v0.1.0

## Qué es

Prototipo analítico **funcional y reproducible** de optimización estocástica hidro-térmica del SIN colombiano (SDDP + CVaR) para apoyar decisiones operativas a 6 meses bajo incertidumbre climática (ENOS). Decide cuánto apoyarse en térmica vs. conservar agua, y cuantifica costo esperado y riesgo de cola. **No** es una instrucción operativa oficial por planta/embalse (ver `ALCANCE_ENTREGA_v001.md`).

## Requisitos

- Linux, **Python 3.11**, ~2 GB de disco. Sin GPU (no se requiere).
- `uv` (o `venv` + `pip`). Solver **HiGHS** (se instala vía pip).

## Clonar

```bash
git clone https://github.com/fredypaeze/sddp_v3.git
cd sddp_v3
git checkout trabajo/modelo-hidrotermico-v3
```

## Instalar

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-model.txt
uv pip check --python .venv/bin/python                # verificar consistencia de dependencias
.venv/bin/python scripts/14_parchear_pydataxm.py --apply
# datos: descomprimir paquete_datos/transferencia_sddp_v3_20260723.zip y copiar data/ y outputs/ a la raiz
.venv/bin/python -m unittest discover -s tests        # 143 pruebas (136 ok, 7 skip)
```

> **Importante:** el modelo, las pruebas, la API y el dashboard requieren **ambos** archivos: `requirements.txt` **y** `requirements-model.txt`.

## Ejecutar el modelo

```bash
PYTHONPATH=src .venv/bin/python scripts/24_sddp.py
```

## Abrir la API

```bash
PYTHONPATH=src .venv/bin/uvicorn minenergia_sddp.api.app:app --host 127.0.0.1 --port 8900
# http://127.0.0.1:8900/docs  ·  /estado  ·  /riesgo  ·  /recomendacion
```

## Abrir el dashboard

```bash
PYTHONPATH=src .venv/bin/streamlit run app/dashboard.py --server.port 8901
```

## Dónde están los resultados

`outputs/run_XXX_vYYY/` (config, commit, semilla, hashes y resultados). La corrida demostrativa es **`outputs/run_024_v001/`**.

## Cómo cambiar λ (aversión al riesgo) y α (nivel de cola)

```bash
PYTHONPATH=src .venv/bin/python scripts/24_sddp.py --lam 0.5 --alpha 0.95
```

- `--lam` ∈ [0,1] (0 = neutral al riesgo; recomendado ≤ 0.5). `--alpha` ∈ [0.80, 0.99].
- Sensibilidad completa: `scripts/25_cvar_sensibilidad.py`. Los supuestos base están en `config/model/parametros_base.json`.

## Errores frecuentes

- `ModuleNotFoundError: minenergia_sddp` → falta `PYTHONPATH=src`.
- `ModuleNotFoundError: highspy/scipy/fastapi` → falta instalar `requirements-model.txt`.
- `pydataxm` con pandas moderno → ejecutar el parche `scripts/14_parchear_pydataxm.py --apply`.
- API/dashboard sin datos (404) → ejecutar antes `scripts/24_sddp.py`.

## Limitaciones principales

Embalse-equivalente **agregado**; split hidro/térmico **endógeno**; costos/capacidad térmica y precios son **supuestos configurables** (no oficiales); demanda determinística; datos hasta **2026-07-13**; actualización incremental pendiente del catálogo externo; **validación institucional pendiente**. Detalle en `docs/LIMITACIONES_v001.md` y `docs/ALCANCE_ENTREGA_v001.md`.
