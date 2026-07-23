# Entorno Python de sddp_v3

## Version soportada
- Python 3.11.9
- numpy 1.26.4
- pandas 2.2.3
- pydataxm 0.3.17
- openpyxl 3.1.5
- pyarrow 18.1.0

El proyecto debe ejecutarse con .venv y no con el entorno de embalses_manu.

## Instalacion
1. py -3.11 -m venv .venv
2. .\.venv\Scripts\python.exe -m pip install -r requirements.txt
3. .\.venv\Scripts\python.exe .\scripts\14_parchear_pydataxm.py --apply

## Pruebas
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v

## Catalogo XM
src/minenergia_sddp/data/xm_catalog.py es la fuente de verdad.
config/xm_metrics.json y config/xm_download_plan.json se regeneran y no deben editarse manualmente.
