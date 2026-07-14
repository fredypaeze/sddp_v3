# Brechas de datos

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
