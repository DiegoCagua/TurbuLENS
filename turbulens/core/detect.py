# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Detección de la imagen doble de la estrella (los dos «spots» del DIMM).

Todo está vectorizado con NumPy: se procesa un bloque de cuadros a la vez,
con forma ``(n, alto, ancho)``, sin recorrer píxeles con bucles de Python.

Para cada cuadro:

1. Se estima el fondo (mediana) y el ruido (MAD) del recorte.
2. El píxel más brillante es el primer spot; se calcula su centroide ponderado
   por intensidad (con umbral) en una ventana pequeña.
3. Se oculta un disco alrededor del primer spot y el máximo restante es el
   segundo spot; se calcula su centroide igual.
4. Se repite el centroide una vez, centrando la ventana en el resultado
   anterior, para precisión por debajo de un píxel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DetectConfig:
    window: int = 4          # semiancho de la ventana del centroide (px)
    exclusion: float = 5.0   # radio del disco que se oculta alrededor del 1.er spot (px)
    snr_min: float = 6.0     # brillo mínimo del pico, en unidades de ruido
    second_min_ratio: float = 0.12  # el 2.º spot debe tener al menos esta fracción del 1.º
    threshold_frac: float = 0.2     # fracción del pico usada como umbral del centroide


def estimate_spot_size(stack: np.ndarray) -> float:
    """Radio aproximado de cada spot (px) a partir de unos cuadros de muestra."""
    stack = np.asarray(stack, dtype=np.float32)
    if stack.ndim == 2:
        stack = stack[None]
    n = stack.shape[0]
    flat = stack.reshape(n, -1)
    bg = np.median(flat, axis=1)
    peak = flat.max(axis=1) - bg
    half = bg + 0.5 * peak
    # Píxeles sobre media altura de los dos spots juntos.
    area = (flat > half[:, None]).sum(axis=1) / 2.0
    r = np.sqrt(np.maximum(area, 1.0) / np.pi)
    return float(np.median(r))


def config_for_radius(r: float) -> DetectConfig:
    r = float(max(r, 0.7))
    return DetectConfig(window=int(max(3, np.ceil(2.5 * r))), exclusion=float(max(4.0, 3.0 * r)))


def _centroid(sub: np.ndarray, py: np.ndarray, px: np.ndarray, rw: int, thr: np.ndarray):
    n, h, w = sub.shape
    d = np.arange(-rw, rw + 1)
    yy = np.clip(py[:, None, None] + d[None, :, None], 0, h - 1)
    xx = np.clip(px[:, None, None] + d[None, None, :], 0, w - 1)
    win = sub[np.arange(n)[:, None, None], yy, xx]
    wgt = np.clip(win - thr[:, None, None], 0.0, None)
    s = wgt.sum(axis=(1, 2))
    ok = s > 0
    s_safe = np.where(ok, s, 1.0)
    cy = (wgt * yy).sum(axis=(1, 2)) / s_safe
    cx = (wgt * xx).sum(axis=(1, 2)) / s_safe
    cy = np.where(ok, cy, py.astype(np.float64))
    cx = np.where(ok, cx, px.astype(np.float64))
    flux = np.clip(win, 0.0, None).sum(axis=(1, 2))
    return cy, cx, flux


def detect_pairs(stack: np.ndarray, cfg: DetectConfig | None = None) -> dict:
    """Detecta los dos spots en cada cuadro de ``stack`` (n, alto, ancho).

    Devuelve un diccionario de arreglos de largo ``n`` con las coordenadas
    (dentro del recorte) ``x1, y1, x2, y2``, los flujos, los picos, el ruido y
    la máscara ``valid``.
    """
    cfg = cfg or DetectConfig()
    a = np.asarray(stack, dtype=np.float32)
    if a.ndim == 2:
        a = a[None]
    n, h, w = a.shape
    flat = a.reshape(n, -1)
    bg = np.median(flat, axis=1)
    mad = np.median(np.abs(flat - bg[:, None]), axis=1) * 1.4826
    noise = np.maximum(mad, 0.5)
    sub = a - bg[:, None, None]
    ar = np.arange(n)

    # Primer spot: el máximo absoluto.
    fs = sub.reshape(n, -1)
    i1 = np.argmax(fs, axis=1)
    p1 = fs[ar, i1]
    y1, x1 = np.divmod(i1, w)

    # Segundo spot: máximo fuera de un disco alrededor del primero.
    Y = np.arange(h)[None, :, None]
    X = np.arange(w)[None, None, :]
    mask = (Y - y1[:, None, None]) ** 2 + (X - x1[:, None, None]) ** 2 <= cfg.exclusion ** 2
    sub2 = np.where(mask, -np.inf, sub).reshape(n, -1)
    i2 = np.argmax(sub2, axis=1)
    p2 = sub2[ar, i2]
    y2, x2 = np.divmod(i2, w)

    thr = np.maximum(cfg.threshold_frac * p1, 3.0 * noise)
    thr2 = np.maximum(cfg.threshold_frac * np.maximum(p2, 0), 3.0 * noise)
    rw = cfg.window
    cy1, cx1, f1 = _centroid(sub, y1, x1, rw, thr)
    cy2, cx2, f2 = _centroid(sub, y2, x2, rw, thr2)
    # Segunda pasada centrada en el centroide.
    cy1, cx1, f1 = _centroid(sub, np.rint(cy1).astype(int), np.rint(cx1).astype(int), rw, thr)
    cy2, cx2, f2 = _centroid(sub, np.rint(cy2).astype(int), np.rint(cx2).astype(int), rw, thr2)

    border = rw
    inside = (
        (y1 >= border) & (y1 < h - border) & (x1 >= border) & (x1 < w - border)
        & (y2 >= border) & (y2 < h - border) & (x2 >= border) & (x2 < w - border)
    )
    valid = (
        (p1 > cfg.snr_min * noise)
        & (p2 > cfg.snr_min * noise)
        & (p2 > cfg.second_min_ratio * p1)
        & np.isfinite(p2)
        & inside
    )
    return {
        "x1": cx1, "y1": cy1, "x2": cx2, "y2": cy2,
        "flux1": f1.astype(np.float32), "flux2": f2.astype(np.float32),
        "peak1": p1.astype(np.float32), "peak2": np.where(np.isfinite(p2), p2, 0).astype(np.float32),
        "noise": noise.astype(np.float32), "valid": valid,
    }
