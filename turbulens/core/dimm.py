# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Del movimiento diferencial de la imagen al seeing.

Modelo de Tokovinin (2002, PASP 114, 1156; arXiv:astro-ph/0111022) para el
centroide (inclinación G) de dos subaperturas de diámetro ``D`` separadas ``B``::

    σ²_l = K_l · λ² · r0^(-5/3) · D^(-1/3)      (dirección de la línea de base)
    σ²_t = K_t · λ² · r0^(-5/3) · D^(-1/3)      (dirección perpendicular)

    K_l = 0.364 · (1 − 0.532 b^(-1/3) − 0.024 b^(-7/3))
    K_t = 0.364 · (1 − 0.798 b^(-1/3) + 0.018 b^(-7/3)),   b = B / D

    seeing ε = 0.98 · λ / r0   (FWHM, en radianes)

Las varianzas se miden en píxeles² y se convierten a radianes² con la escala
de placa. Si se conoce la altura de la estrella, el seeing se lleva al cenit
con ε_cenit = ε · (cos z)^(3/5).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np

from . import stats

ARCSEC_PER_RAD = 206264.80624709636


def k_coefficients(b: float) -> tuple[float, float]:
    kl = 0.364 * (1 - 0.532 * b ** (-1 / 3) - 0.024 * b ** (-7 / 3))
    kt = 0.364 * (1 - 0.798 * b ** (-1 / 3) + 0.018 * b ** (-7 / 3))
    return kl, kt


def r0_from_variance(var_rad2: float, K: float, lam_m: float, D_m: float) -> float:
    if not (var_rad2 > 0 and K > 0 and lam_m > 0 and D_m > 0):
        return float("nan")
    return (K * lam_m ** 2 * D_m ** (-1 / 3) / var_rad2) ** (3 / 5)


def seeing_from_r0(r0_m: float, lam_m: float) -> float:
    if not (r0_m > 0):
        return float("nan")
    return 0.98 * lam_m / r0_m * ARCSEC_PER_RAD


@dataclass
class DimmParams:
    D_cm: float = 2.5            # diámetro de cada orificio
    B_cm: float = 14.0           # separación entre centros de los orificios
    lambda_nm: float = 550.0     # longitud de onda efectiva
    scale_arcsec_px: Optional[float] = None  # escala de placa (″/px)
    altitude_deg: Optional[float] = None     # altura de la estrella sobre el horizonte

    def valid_geometry(self) -> bool:
        return self.D_cm > 0 and self.B_cm > self.D_cm and self.lambda_nm > 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DimmResult:
    n_frames: int
    n_detected: int
    n_used: int
    mean_sep_px: float
    median_sep_px: float
    std_sep_px: float
    sigma_l_px: float
    sigma_t_px: float
    baseline_angle_deg: float
    eps_l: float = float("nan")
    eps_t: float = float("nan")
    eps: float = float("nan")
    r0_cm: float = float("nan")
    eps_zenith: float = float("nan")
    airmass: float = float("nan")
    corr_lt: float = float("nan")
    # Arreglos por cuadro (no se guardan en la tabla del historial)
    arrays: dict = field(default_factory=dict, repr=False)

    def summary_dict(self) -> dict:
        d = asdict(self)
        d.pop("arrays", None)
        return d


def quality_label(eps: float) -> str:
    if not math.isfinite(eps):
        return "Sin escala de placa"
    if eps <= 1.5:
        return "Excelente"
    if eps <= 3.0:
        return "Aceptable"
    return "Muy turbulento"


def analyze(meas: np.ndarray, params: DimmParams, clip_k: float = 5.0) -> DimmResult:
    """Analiza las mediciones por cuadro (arreglo estructurado de ``pipeline``)."""
    n = int(meas.size)
    det = meas["valid"].astype(bool)
    dx = (meas["x2"] - meas["x1"]).astype(np.float64)
    dy = (meas["y2"] - meas["y1"]).astype(np.float64)
    # Los spots pueden intercambiarse entre cuadros (cambia cuál es el más
    # brillante). Se orienta cada vector según el eje principal de la nube.
    if det.sum() >= 2:
        m = np.array([[np.mean(dx[det] ** 2), np.mean(dx[det] * dy[det])],
                      [np.mean(dx[det] * dy[det]), np.mean(dy[det] ** 2)]])
        w, v = np.linalg.eigh(m)
        ax, ay = v[:, int(np.argmax(w))]
        sgn = np.where(dx * ax + dy * ay < 0, -1.0, 1.0)
        dx, dy = dx * sgn, dy * sgn
    sep = np.hypot(dx, dy)
    sep = np.where(det, sep, np.nan)

    used = det & stats.sigma_clip_mask(sep, k=clip_k)
    if used.sum() < 3:
        used = det.copy()

    # Dirección media de la línea de base y proyecciones.
    mdx = float(np.nanmean(dx[used])) if used.any() else 1.0
    mdy = float(np.nanmean(dy[used])) if used.any() else 0.0
    norm = math.hypot(mdx, mdy) or 1.0
    ux, uy = mdx / norm, mdy / norm
    lon = dx * ux + dy * uy
    tra = -dx * uy + dy * ux

    s_sep = stats.summarize(sep[used])
    sl = float(np.std(lon[used], ddof=1)) if used.sum() > 1 else float("nan")
    st = float(np.std(tra[used], ddof=1)) if used.sum() > 1 else float("nan")

    res = DimmResult(
        n_frames=n,
        n_detected=int(det.sum()),
        n_used=int(used.sum()),
        mean_sep_px=s_sep.mean,
        median_sep_px=s_sep.median,
        std_sep_px=s_sep.std,
        sigma_l_px=sl,
        sigma_t_px=st,
        baseline_angle_deg=math.degrees(math.atan2(uy, ux)),
        corr_lt=stats.pearson_r(lon[used], tra[used]),
    )
    res.arrays = {"sep": sep, "dx": dx, "dy": dy, "lon": lon, "tra": tra, "used": used, "detected": det}

    scale = params.scale_arcsec_px
    if scale and scale > 0 and params.valid_geometry():
        D = params.D_cm / 100.0
        B = params.B_cm / 100.0
        lam = params.lambda_nm * 1e-9
        kl, kt = k_coefficients(B / D)
        conv = (scale / ARCSEC_PER_RAD) ** 2
        r0l = r0_from_variance(sl ** 2 * conv, kl, lam, D)
        r0t = r0_from_variance(st ** 2 * conv, kt, lam, D)
        res.eps_l = seeing_from_r0(r0l, lam)
        res.eps_t = seeing_from_r0(r0t, lam)
        vals = [v for v in (res.eps_l, res.eps_t) if math.isfinite(v)]
        res.eps = float(np.mean(vals)) if vals else float("nan")
        r0s = [v for v in (r0l, r0t) if math.isfinite(v)]
        res.r0_cm = float(np.mean(r0s)) * 100 if r0s else float("nan")
        alt = params.altitude_deg
        if alt is not None and 5 <= alt <= 90:
            z = math.radians(90 - alt)
            res.airmass = 1.0 / math.cos(z)
            res.eps_zenith = res.eps * math.cos(z) ** (3 / 5)
    return res
