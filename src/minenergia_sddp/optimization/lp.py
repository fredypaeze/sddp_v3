"""Helper minimo de programacion lineal sobre HiGHS.

Envuelve highspy con una API declarativa (variables con costo, restricciones por
diccionario de coeficientes) y expone valores primales y **duales** por
restriccion. Los duales son necesarios para el valor del agua (dual del balance
hidrico) y para los cortes de Benders del SDDP (ETAPA 7).

Convencion: minimizacion por defecto. Todos los costos y RHS en las unidades que
elija el modelo llamador (este proyecto usa COP para costos y GWh para energia).
"""

from __future__ import annotations

from typing import Mapping

import highspy
import numpy as np

INF = highspy.kHighsInf


class LpModel:
    """Modelo LP incremental con acceso a duales."""

    def __init__(self, sense: str = "min") -> None:
        self.h = highspy.Highs()
        self.h.setOptionValue("output_flag", False)
        self.h.setOptionValue("presolve", "on")
        obj = highspy.ObjSense.kMinimize if sense == "min" else highspy.ObjSense.kMaximize
        self.h.changeObjectiveSense(obj)
        self._ncol = 0
        self._nrow = 0
        self.var_names: list[str | None] = []
        self.row_names: list[str | None] = []

    def add_var(self, lb: float = 0.0, ub: float = INF, cost: float = 0.0,
                name: str | None = None) -> int:
        idx = self._ncol
        self.h.addCol(float(cost), float(lb), float(ub), 0,
                      np.array([], dtype=np.int32), np.array([], dtype=float))
        self._ncol += 1
        self.var_names.append(name)
        return idx

    def add_constraint(self, coeffs: Mapping[int, float], lb: float = -INF,
                       ub: float = INF, name: str | None = None) -> int:
        """Agrega sum(coeffs[i]*x_i) en [lb, ub]. Igualdad: lb == ub."""
        idx = np.fromiter(coeffs.keys(), dtype=np.int32, count=len(coeffs))
        val = np.fromiter((float(v) for v in coeffs.values()), dtype=float, count=len(coeffs))
        row = self._nrow
        self.h.addRow(float(lb), float(ub), len(idx), idx, val)
        self._nrow += 1
        self.row_names.append(name)
        return row

    def add_eq(self, coeffs: Mapping[int, float], rhs: float, name: str | None = None) -> int:
        return self.add_constraint(coeffs, lb=rhs, ub=rhs, name=name)

    def add_le(self, coeffs: Mapping[int, float], rhs: float, name: str | None = None) -> int:
        return self.add_constraint(coeffs, lb=-INF, ub=rhs, name=name)

    def add_ge(self, coeffs: Mapping[int, float], rhs: float, name: str | None = None) -> int:
        return self.add_constraint(coeffs, lb=rhs, ub=INF, name=name)

    def solve(self) -> bool:
        self.h.run()
        return self.h.getModelStatus() == highspy.HighsModelStatus.kOptimal

    def status(self) -> str:
        return self.h.modelStatusToString(self.h.getModelStatus())

    def objective(self) -> float:
        return float(self.h.getObjectiveValue())

    def primal(self, idx: int) -> float:
        return float(self.h.getSolution().col_value[idx])

    def primal_all(self) -> np.ndarray:
        return np.asarray(self.h.getSolution().col_value, dtype=float)

    def dual(self, row: int) -> float:
        """Precio sombra de la restriccion (marginal del RHS)."""
        return float(self.h.getSolution().row_dual[row])
