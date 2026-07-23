# Validación y backtesting (v001)

Código: `scripts/26_backtesting.py` → `outputs/run_026_v001/`. Cada política se evalúa sobre la **trayectoria de aportes OBSERVADA** de cada episodio; el modelo de escenarios se ajusta **solo con datos anteriores** al episodio (sin fuga temporal).

## Políticas comparadas

- **Visión perfecta determinística** (conoce los aportes; cota inferior de costo).
- **SDDP neutral** (λ=0) y **SDDP + CVaR** (λ=0.6).
- **Regla miope "hidro-primero"** (turbina lo disponible; térmica cubre el faltante).

## Episodios (dentro del rango de demanda 2023+)

| Episodio | Fase | Visión perfecta | SDDP neutral | SDDP+CVaR | Miope |
|---|---|---|---|---|---|
| Niño 2023-24 | niño | 6.44 | 6.44 | 6.44 | 6.44 |
| Reciente 2025 | neutral | ~0 | ~0 | ~0 | ~0 |

Con el **embalse en niveles sanos** (situación real de esos episodios) **todas las políticas coinciden**: la hidráulica cubre la demanda y el tradeoff intertemporal del agua no es vinculante. El SDDP no pierde frente a las alternativas, pero tampoco aporta ventaja cuando no hay escasez.

*(“Transición 2024-25” se omite por un hueco real en la demanda observada: 2024-09 tiene solo 9 días.)*

## Backtesting bajo estrés (embalse bajo, 25 % de capacidad)

Aquí el manejo del agua sí es vinculante:

| Episodio (V0=25 %) | SDDP neutral | Miope | ENS SDDP | ENS miope | Ventaja SDDP |
|---|---|---|---|---|---|
| **Niño 2023-24** | **6.44** | **8.81** | **0 GWh** | **2 205 GWh** | **+2.38 B COP** |
| Reciente 2025 (neutral) | 1.15 | 0.20 | 0 | 0 | −0.96 B COP |

- **Bajo El Niño con embalse bajo**, la regla miope **agota el agua y cae en déficit (2 205 GWh de ENS)**; el SDDP **conserva agua y evita el déficit**, ahorrando **2.38 billones COP**. Ventaja demostrable del modelo estocástico.
- En un período **benigno**, la precaución del SDDP **cuesta ~0.96 B COP** (conservó agua que no hizo falta). Honestidad: la cobertura tiene precio cuando la sequía no se materializa.

## Conclusión

El valor del SDDP+CVaR aparece **cuando el agua escasea y el momento del despacho importa** (evita déficit costoso). En condiciones holgadas equivale a reglas simples. La decisión de cuánta precaución tomar (λ) es de política pública y se cuantifica en `docs/CVAR_v001.md`.
