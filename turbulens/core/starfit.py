# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Ajuste de una gaussiana 2D a una estrella para medir su ancho (σ y FWHM) y, con la escala de placa, el seeing.

Modelo (elíptica, alineada con los ejes)::

    I(x, y) = B + A · exp(−[(x − x₀)² / (2σx²) + (y − y₀)² / (2σy²)])

* σ es el radio en el que el brillo cae al 60,7 % del pico (e^(−1/2)): el «primer sigma».
* FWHM = 2√(2 ln 2) · σ ≈ 2,3548 σ es el ancho a media altura (50 % del pico).
* En una exposición larga, el FWHM de una estrella en segundos de arco (FWHM_px × escala) es el seeing.

El ajuste es de Levenberg–Marquardt con derivadas analíticas, solo con NumPy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

FWHM_FACTOR = 2.0 * math.sqrt(2.0 * math.log(2.0))  # 2,3548


@dataclass
class StarFit:
    ok: bool
    x0: float = float("nan")  # en píxeles de la imagen completa (columna, desde 0)
    y0: float = float("nan")
    amp: float = float("nan")
    bg: float = float("nan")
    sx: float = float("nan")
    sy: float = float("nan")
    rms: float = float("nan")
    iterations: int = 0
    message: str = ""

    @property
    def sigma(self) -> float:
        """σ promedio (media geométrica de σx y σy), en píxeles."""
        return math.sqrt(self.sx * self.sy) if self.ok else float("nan")

    @property
    def fwhm(self) -> float:
        return FWHM_FACTOR * self.sigma

    @property
    def fwhm_x(self) -> float:
        return FWHM_FACTOR * self.sx

    @property
    def fwhm_y(self) -> float:
        return FWHM_FACTOR * self.sy

    @property
    def ellipticity(self) -> float:
        if not self.ok:
            return float("nan")
        a, b = max(self.sx, self.sy), min(self.sx, self.sy)
        return 1.0 - b / a

    def model(self, x, y):
        return self.bg + self.amp * np.exp(-((x - self.x0) ** 2 / (2 * self.sx ** 2) + (y - self.y0) ** 2 / (2 * self.sy ** 2)))


def _model_jac(p, x, y):
    A, x0, y0, sx, sy, B = p
    dx, dy = x - x0, y - y0
    e = np.exp(-(dx * dx / (2 * sx * sx) + dy * dy / (2 * sy * sy)))
    f = B + A * e
    J = np.empty((x.size, 6))
    J[:, 0] = e
    J[:, 1] = A * e * dx / (sx * sx)
    J[:, 2] = A * e * dy / (sy * sy)
    J[:, 3] = A * e * dx * dx / sx ** 3
    J[:, 4] = A * e * dy * dy / sy ** 3
    J[:, 5] = 1.0
    return f, J


def fit_star(img: np.ndarray, x0: int = 0, y0: int = 0, mask: Optional[np.ndarray] = None,
             max_iter: int = 60) -> StarFit:
    """Ajusta la gaussiana a ``img`` (la región recortada); ``x0, y0`` es la esquina de la región en la imagen.

    ``mask`` (booleana, del tamaño de ``img``) limita los píxeles que se usan (regiones circulares o elípticas).
    """
    a = np.asarray(img, dtype=np.float64)
    h, w = a.shape
    if h < 3 or w < 3:
        return StarFit(False, message="la región es demasiado pequeña (al menos 3 × 3 píxeles)")
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    use = np.isfinite(a)
    if mask is not None:
        use &= mask
    if use.sum() < 7:
        return StarFit(False, message="la región tiene muy pocos píxeles válidos")
    x, y, v = xx[use], yy[use], a[use]
    # Arranque con momentos
    B = float(np.percentile(v, 10))
    wv = np.clip(v - B, 0, None)
    S = wv.sum()
    if S <= 0:
        return StarFit(False, message="no hay una estrella en la región (todo es fondo)")
    cx, cy = float((wv * x).sum() / S), float((wv * y).sum() / S)
    sx = math.sqrt(max(0.25, float((wv * (x - cx) ** 2).sum() / S)))
    sy = math.sqrt(max(0.25, float((wv * (y - cy) ** 2).sum() / S)))
    A = float(v.max() - B)
    ipk = int(np.argmax(v))
    cx, cy = 0.5 * (cx + x[ipk]), 0.5 * (cy + y[ipk])
    p = np.array([A, cx, cy, min(sx, w / 2), min(sy, h / 2), B])
    lam = 1e-3
    f, J = _model_jac(p, x, y)
    r = v - f
    cost = float(r @ r)
    it = 0
    for it in range(1, max_iter + 1):
        JTJ = J.T @ J
        g = J.T @ r
        improved = False
        for _ in range(12):
            Hm = JTJ + lam * np.diag(np.diag(JTJ) + 1e-12)
            try:
                step = np.linalg.solve(Hm, g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            q = p + step
            q[3] = max(abs(q[3]), 0.2)
            q[4] = max(abs(q[4]), 0.2)
            f2, J2 = _model_jac(q, x, y)
            r2 = v - f2
            c2 = float(r2 @ r2)
            if c2 < cost:
                p, f, J, r, cost = q, f2, J2, r2, c2
                lam = max(lam / 3, 1e-9)
                improved = True
                break
            lam *= 4
        if not improved or float(np.max(np.abs(step) / (np.abs(p) + 1e-9))) < 1e-7:
            break
    A, cx, cy, sx, sy, B = p
    res = StarFit(True, x0 + cx, y0 + cy, A, B, abs(sx), abs(sy), math.sqrt(cost / max(1, v.size - 6)), it)
    if A <= 0:
        res.ok = False
        res.message = "el ajuste no encontró una estrella (amplitud negativa)"
    elif not (-0.5 <= cx <= w - 0.5 and -0.5 <= cy <= h - 0.5):
        res.ok = False
        res.message = "el centro quedó fuera de la región: encierra mejor la estrella"
    elif max(sx, sy) > max(w, h):
        res.ok = False
        res.message = "la estrella es más grande que la región: dibuja una región más amplia"
    return res


def radial_profile(img: np.ndarray, fit: StarFit, x0: int = 0, y0: int = 0, step: float = 0.5,
                   mask: Optional[np.ndarray] = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Perfil radial alrededor del centro ajustado: (radio de cada píxel, valor) y (radios, promedio por anillo)."""
    a = np.asarray(img, dtype=np.float64)
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(xx + x0 - fit.x0, yy + y0 - fit.y0)
    use = np.isfinite(a) if mask is None else (np.isfinite(a) & mask)
    r, v = rr[use], a[use]
    if r.size == 0:
        return r, v, np.zeros((0, 2))
    edges = np.arange(0, r.max() + step, step)
    idx = np.digitize(r, edges) - 1
    prof = [((edges[i] + edges[i + 1]) / 2, float(np.mean(v[idx == i]))) for i in range(len(edges) - 1) if np.any(idx == i)]
    return r, v, np.array(prof)
