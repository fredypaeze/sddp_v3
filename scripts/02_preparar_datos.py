from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minenergia_sddp.validation.contracts import CONTRACTS, VARIABLE_STATUS


def read_gate_status() -> str:
    path = ROOT / "outputs/run_001/reporte_calidad_datos.json"
    if not path.exists():
        return "NO_EVALUADO"
    return json.loads(path.read_text(encoding="utf-8")).get("status", "NO_EVALUADO")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")


def contracts_md() -> str:
    lines = ["# Contrato de datos", "", "Los contratos definen campos requeridos; no implican que todos esten disponibles actualmente."]
    for domain, cols in CONTRACTS.items():
        lines.extend(["", f"## {domain}", "", "| Campo | Obligatorio |", "|---|---|"])
        lines.extend(f"| `{col}` | si |" for col in cols)
    return "\n".join(lines)


def dictionary_md() -> str:
    rows = [
        ("fecha", "Fecha del periodo", "fecha ISO", "disponible con limitaciones"),
        ("escenario_id", "Identificador de escenario", "texto", "disponible con limitaciones"),
        ("probabilidad", "Probabilidad del escenario por fecha", "0-1", "disponible con limitaciones"),
        ("codigo_embalse", "Codigo de embalse", "texto XM/local", "disponible con limitaciones"),
        ("volumen_util", "Volumen util observado o proyectado", "masa/porcentaje segun fuente", "disponible con limitaciones"),
        ("energia_almacenada_gwh", "Energia almacenada equivalente", "GWh", "prohibido estimarla sin informacion adicional"),
        ("aporte", "Aporte hidrico", "unidad no validada / indice", "disponible con limitaciones"),
        ("generacion_gwh", "Generacion por recurso o agregado", "GWh", "proxy admisible solo para backtesting"),
        ("demanda_gwh", "Demanda electrica total", "GWh", "no disponible"),
        ("solar_gwh", "Generacion solar", "GWh", "no disponible"),
        ("eolica_gwh", "Generacion eolica", "GWh", "no disponible"),
        ("cogeneracion_gwh", "Cogeneracion", "GWh", "no disponible"),
        ("importacion_neta_gwh", "Importacion neta", "GWh", "no disponible"),
        ("capacidad_mw", "Capacidad efectiva por recurso", "MW", "no disponible"),
        ("disponibilidad_mw", "Disponibilidad temporal por recurso", "MW", "no disponible"),
        ("precio_oferta_cop_kwh", "Precio de oferta auditado", "COP/kWh", "disponible con limitaciones"),
    ]
    lines = ["# Diccionario de datos", "", "| Variable | Definicion | Unidad | Estado |", "|---|---|---|---|"]
    lines.extend(f"| `{v}` | {d} | {u} | {s} |" for v, d, u, s in rows)
    return "\n".join(lines)


def units_md() -> str:
    return """# Matriz de unidades

| Dominio | Variable | Unidad auditada | Conversion permitida | Estado |
|---|---|---|---|---|
| Precios | precio_oferta_cop_kwh | COP/kWh | ninguna; no usar COP/MWh en salidas | disponible con limitaciones |
| Precios | precio_bolsa | COP/kWh segun archivo heredado | ninguna; requiere confirmacion por metrica XM | disponible con limitaciones |
| Generacion | hidro_gwh, termo_gwh | GWh/dia agregado Sistema | suma temporal permitida | proxy admisible solo para backtesting |
| Generacion | hidro_kwh, termo_kwh | kWh/dia agregado Sistema | kWh / 1e6 = GWh | proxy admisible solo para backtesting |
| Termicas | capacidad_mw | MW | MW * horas / 1000 = GWh si existe capacidad validada | no disponible |
| Termicas | disponibilidad_mw | MW | MW * horas / 1000 = GWh si existe disponibilidad temporal validada | no disponible |
| Embalses | VolumenUtilPorcentaje | fraccion o porcentaje segun archivo | no convertir a GWh sin curva volumen-energia | disponible con limitaciones |
| Embalses | CapacidadUtilMasa, VolumenUtilDiarioMasa | masa/volumen local | no convertir a energia sin relacion tecnica | disponible con limitaciones |
| Aportes | Value, AportesPorc, AportesHidricosMasa | indice/masa/porcentaje segun fuente | no convertir a GWh sin factor tecnico | disponible con limitaciones |
| Costos | GWh x COP/kWh | miles de millones COP | GWh * 1e6 * COP/kWh / 1e9 | formula validada |
"""


def gaps_md() -> str:
    return """# Brechas de datos

## Brechas criticas

- Demanda oficial horaria/diaria agregada y sus componentes para no asumir que hidro + termica = demanda.
- Generacion por recurso y tipo para reconstruir despacho historico y priorizacion termica.
- Capacidad efectiva o maxima por recurso termico en MW.
- Disponibilidad temporal por recurso termico en MW.
- Relacion tecnica embalse-recurso: volumen util, energia almacenada GWh, factor de conversion o curva volumen-energia.
- Aportes hidricos prospectivos en unidad util para balance hidrico, no trayectoria de almacenamiento operativo.
- Condiciones iniciales y terminales verificables para almacenamiento en unidad comun con generacion hidraulica.

## Brechas metodologicas

- `embalses_manu` entrega trayectoria indicativa/envolvente de volumen util, no aportes exogenos.
- La generacion local heredada esta agregada a Sistema; sirve como referencia historica, no para decidir recursos.
- La disponibilidad de `listado_plantas.csv` indica si el recurso es despachado centralmente, no disponibilidad operativa temporal.
"""


def data_request_md() -> str:
    return """# Solicitud de datos al usuario

| Dato requerido | Columnas requeridas | Periodo | Granularidad | Unidad | Formato aceptado | Razon | Fase bloqueada | Alternativa |
|---|---|---|---|---|---|---|---|---|
| Demanda oficial SIN | fecha, demanda_kwh o demanda_gwh | 2023-actual y prospectivo 26 semanas | horaria o diaria | kWh/GWh | CSV/Parquet/XLSX | Reconstruir balance electrico sin proxy hidro+termica | backtest/prospectivo | metrica XM `DemaReal` ya descargada localmente |
| Generacion por recurso | fecha, codigo_recurso, tipo_recurso, generacion_kwh/gwh | 2023-actual | horaria o diaria | kWh/GWh | CSV/Parquet/XLSX | Validar generacion termica e hidraulica por recurso | backtest/recomendacion | bloques agregados por combustible si conservan energia total |
| Capacidad termica | fecha, codigo_recurso, capacidad_mw | vigente para el horizonte | recurso | MW | CSV/Parquet/XLSX | Limitar energia maxima por periodo | backtest/prospectivo | capacidad efectiva por bloque termico |
| Disponibilidad termica | fecha, codigo_recurso, disponibilidad_mw | historico y 26 semanas futuras | diaria/semanal | MW | CSV/Parquet/XLSX | Evitar recomendar energia no disponible | backtest/prospectivo | escenarios de disponibilidad por bloque |
| Relacion volumen-energia | codigo_embalse, capacidad_util, energia_almacenada_gwh o factor/cota | vigente | embalse | GWh y unidad de volumen | CSV/Parquet/XLSX/documento tecnico | Convertir almacenamiento a balance hidrico energetico | valor del agua/prospectivo | curvas regionales auditadas |
| Aportes hidricos utiles para despacho | fecha, escenario_id, codigo_embalse/sistema, aporte_gwh o caudal convertible | historico y 26 semanas futuras | diaria/semanal/mensual | GWh o caudal con factor | CSV/Parquet/XLSX | Balance hidrico prospectivo exogeno | prospectivo/CVaR | escenarios de energia afluente por sistema |
| Probabilidades de escenarios | fecha, escenario_id, probabilidad | 26 semanas futuras | por escenario | 0-1 | CSV/Parquet/XLSX | CVaR y valor esperado coherentes | prospectivo/CVaR | probabilidades ENOS oficiales por trimestre mapeadas a escenarios |
"""


def formulation_md(status: str) -> str:
    return f"""# Formulacion matematica

Estado de puerta usado para esta formulacion: **{status}**.

Esta especificacion no declara un SDDP completo. Un SDDP formal requeriria forward pass, backward pass, cortes y funcion de costo futuro aproximada. Tampoco declara Unit Commitment, porque no hay variables binarias, rampas, minimos tecnicos ni costos de arranque.

## Usos tecnicamente consistentes de `embalses_manu`

1. Estado inicial y condicion terminal indicativa si se valida conversion a unidad comun.
2. Envolvente o banda prospectiva de almacenamiento.
3. Trayectoria de validacion contra resultados simulados.

Seleccion actual: **trayectoria indicativa/envolvente y validacion**, no almacenamiento fijo endogeno ni aporte hidrico.

## Backtest deterministico condicionado

Indices: periodo `t`, recurso termico `r`, escenario `s`.

Decisiones: generacion hidraulica, generacion termica por recurso o bloque, almacenamiento, vertimiento, ENS e incumplimientos separados.

Objetivo: minimizar costo termico mas penalizaciones separadas por ENS e incumplimientos. Las penalizaciones no son valor economico del agua.

Restricciones requeridas: balance electrico, balance hidrico en unidad energetica comun, limites de generacion, disponibilidad, almacenamiento minimo/maximo, condicion inicial, condicion terminal y no negatividad.

## CVaR condicionado

Objetivo: minimizar `E[costo operativo] + lambda * CVaR_alpha[costo critico]`.

`lambda` pondera riesgo de cola; no es precio. Solo puede declararse optimizacion con CVaR si se resuelve conjuntamente con las variables de decision, no si se calcula la metrica ex post.
"""


def differences_md() -> str:
    return """# Diferencia entre despacho, CVaR, SDDP y Unit Commitment

- Despacho deterministico: optimiza una trayectoria con datos conocidos o supuestos fijos.
- Simulacion prospectiva: evalua escenarios futuros; no es prediccion si las entradas son supuestos.
- Optimizacion con CVaR: incorpora riesgo de cola en la funcion objetivo mediante `lambda` y `alpha`.
- SDDP: metodo de programacion dinamica estocastica con forward pass, backward pass, cortes y funcion de costo futuro.
- Unit Commitment: problema con decisiones binarias de encendido, rampas, minimos tecnicos y costos de arranque.

Esta base tecnica no debe usar "orden de encendido" ni "prender planta". La salida admisible es "Recomendacion de despacho y priorizacion termica" solo cuando existan datos suficientes.
"""


def readme_md(status: str) -> str:
    return f"""# Modelo multiperiodo de despacho hidrotermico bajo escenarios ENOS

Base tecnica para una futura **Recomendacion de despacho y priorizacion termica**.

Estado actual de puerta de calidad: **{status}**.

La version actual organiza fuentes, contratos, trazabilidad, matriz de unidades, brechas y validaciones. No construye un SDDP completo ni un Unit Commitment.

## Ejecucion

```powershell
python scripts/01_auditar_fuentes.py
python scripts/02_preparar_datos.py
python -m unittest discover -s tests
```

Los scripts `03` a `05` verifican la puerta de calidad y se bloquean si los datos criticos siguen ausentes.
"""


def simple_doc(title: str, body: str) -> str:
    return f"# {title}\n\n{body}"


def main() -> int:
    status = read_gate_status()
    write("docs/CONTRATO_DATOS.md", contracts_md())
    write("docs/DICCIONARIO_DATOS.md", dictionary_md())
    write("docs/MATRIZ_UNIDADES.md", units_md())
    write("docs/BRECHAS_DATOS.md", gaps_md())
    write("docs/SOLICITUD_DATOS_USUARIO.md", data_request_md())
    write("docs/FORMULACION_MATEMATICA.md", formulation_md(status))
    write("docs/DIFERENCIA_DESPACHO_CVAR_SDDP_UC.md", differences_md())
    write("README.md", readme_md(status))
    write("docs/LIMITACIONES.md", simple_doc("Limitaciones", "No hay recomendacion operativa valida mientras falten demanda oficial, capacidad/disponibilidad termica y conversion volumen-energia. Todos los precios electricos deben reportarse en COP/kWh."))
    write("docs/BLOQUEOS.md", simple_doc("Bloqueos", f"La puerta actual es {status}. El optimizador, prospectivo, valor del agua y CVaR quedan bloqueados hasta recibir los datos listados en `docs/SOLICITUD_DATOS_USUARIO.md`."))
    write("docs/COMO_EJECUTAR.md", simple_doc("Como ejecutar", "Ejecutar los scripts en orden desde la raiz del proyecto con Python 3.11.9. No requieren internet ni descargan datos."))
    write("docs/PLAN_COMMITS.md", simple_doc("Plan de commits", "Git requirio usar `-c safe.directory=D:/Proyectos/minenergia/sddp_v3` por diferencia de usuario sandbox. Los commits locales se intentan por fase usando `git add` selectivo; no se hace push."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

