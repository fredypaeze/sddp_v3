"""Modelo estocastico de aportes del SIN (PAR/ARX(1) periodico en espacio log).

Sobre el log de aportes desestacionalizado a'_t = log(a_t) - mu_{mes}:

    a'_t = c + b_oni * ONI_t + phi * a'_{t-1} + eps_t ,   eps_t ~ N(0, sigma^2)

Preserva:
- estacionalidad (mu_m, sigma_m por mes en espacio log),
- persistencia (phi, autocorrelacion de lag 1),
- efecto ENOS (b_oni sobre el ONI del mes).

Provee:
- sample_stage : muestras marginales por etapa (independencia por etapa, supuesto
  estandar del SDDP),
- simulate     : trayectorias completas (preservan phi) para Monte Carlo/validacion,
- stage_scenarios : matriz [T, K] de aportes por etapa + probabilidades,
- validate     : compara simulacion vs historia (media, sd, percentiles, autocorr, sequias).

Semillas reproducibles via numpy.random.Generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

GWH_MIN = 1.0  # piso para evitar log(0)


@dataclass
class InflowModel:
    mu_mes: dict[int, float]        # media de log(aportes) por mes
    sigma_mes: dict[int, float]     # sd de log(aportes) por mes
    c: float
    b_oni: float
    phi: float
    sigma_eps: float
    fase_media_hist: dict[str, float] = field(default_factory=dict)  # GWh/dia por fase (referencia)

    # -------- ajuste --------
    @classmethod
    def fit(cls, monthly: pd.DataFrame) -> "InflowModel":
        df = monthly.copy()
        df["loga"] = np.log(df["aportes_gwh_dia"].clip(lower=GWH_MIN))
        mu = df.groupby(df.index.month)["loga"].mean().to_dict()
        sd = df.groupby(df.index.month)["loga"].std(ddof=0).to_dict()
        df["mu"] = df.index.month.map(mu)
        df["anom"] = df["loga"] - df["mu"]
        df["anom_lag"] = df["anom"].shift(1)
        reg = df.dropna(subset=["anom_lag"])
        X = np.column_stack([np.ones(len(reg)), reg["oni"].to_numpy(), reg["anom_lag"].to_numpy()])
        y = reg["anom"].to_numpy()
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        sigma_eps = float(resid.std(ddof=3))
        fase_media = monthly.groupby("fase_enos")["aportes_gwh_dia"].mean().to_dict()
        return cls(mu_mes=mu, sigma_mes=sd, c=float(beta[0]), b_oni=float(beta[1]),
                   phi=float(beta[2]), sigma_eps=sigma_eps, fase_media_hist=fase_media)

    # -------- utilidades --------
    def _marginal_std(self) -> float:
        denom = max(1.0 - self.phi ** 2, 1e-6)
        return self.sigma_eps / np.sqrt(denom)

    def sample_stage(self, mes: int, oni: float, n: int, rng: np.random.Generator) -> np.ndarray:
        """Muestras marginales de aportes (GWh/dia) para un mes/ONI dados."""
        media_anom = self.c + self.b_oni * oni  # E[a'] estacionario aprox (ignora lag)
        std = self._marginal_std()
        anom = rng.normal(media_anom, std, size=n)
        return np.exp(self.mu_mes[mes] + anom)

    def simulate(self, meses: list[int], oni_path: list[float], n: int,
                 rng: np.random.Generator, anom0: float = 0.0) -> np.ndarray:
        """n trayectorias [n, T] de aportes (GWh/dia) preservando persistencia."""
        T = len(meses)
        out = np.empty((n, T))
        anom_prev = np.full(n, anom0)
        for t in range(T):
            eps = rng.normal(0.0, self.sigma_eps, size=n)
            anom = self.c + self.b_oni * oni_path[t] + self.phi * anom_prev + eps
            out[:, t] = np.exp(self.mu_mes[meses[t]] + anom)
            anom_prev = anom
        return out

    def stage_scenarios(self, meses: list[int], oni_path: list[float], k: int,
                        rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
        """Matriz [T, k] de aportes por etapa (independencia por etapa) + probabilidades uniformes."""
        T = len(meses)
        mat = np.empty((T, k))
        for t in range(T):
            mat[t] = self.sample_stage(meses[t], oni_path[t], k, rng)
        probs = np.full(k, 1.0 / k)
        return mat, probs


def reduce_scenarios(traj: np.ndarray, k: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Reduce n trayectorias a k representativas via k-means; probabilidad = peso del cluster."""
    from sklearn.cluster import KMeans
    km = KMeans(n_clusters=k, n_init=10, random_state=int(rng.integers(0, 2**31 - 1)))
    labels = km.fit_predict(traj)
    reps = km.cluster_centers_
    counts = np.bincount(labels, minlength=k).astype(float)
    probs = counts / counts.sum()
    return reps, probs


def validate(sim_traj: np.ndarray, hist_monthly: pd.DataFrame, meses: list[int]) -> pd.DataFrame:
    """Compara estadisticos de la simulacion por etapa contra la climatologia historica del mes."""
    filas = []
    for t, mes in enumerate(meses):
        col = sim_traj[:, t]
        h = hist_monthly[hist_monthly.index.month == mes]["aportes_gwh_dia"]
        filas.append({
            "etapa": t + 1, "mes": mes,
            "sim_media": float(col.mean()), "hist_media": float(h.mean()),
            "sim_sd": float(col.std()), "hist_sd": float(h.std()),
            "sim_p10": float(np.percentile(col, 10)), "hist_p10": float(np.percentile(h, 10)),
            "sim_p90": float(np.percentile(col, 90)), "hist_p90": float(np.percentile(h, 90)),
        })
    # autocorrelacion lag-1 promedio de las trayectorias
    ac = []
    for i in range(min(sim_traj.shape[0], 500)):
        x = sim_traj[i]
        if x.std() > 0:
            ac.append(np.corrcoef(x[:-1], x[1:])[0, 1])
    df = pd.DataFrame(filas)
    df.attrs["autocorr_lag1_sim"] = float(np.nanmean(ac)) if ac else float("nan")
    return df
