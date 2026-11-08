# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Calibración de imágenes astronómicas con bias, darks y flats.

* **Bias**: lectura del sensor con exposición nula. Se combinan por mediana.
* **Dark**: misma exposición y temperatura que las imágenes, con la tapa puesta.
  El dark maestro ya contiene el bias (se usa tal cual si tiene la misma exposición).
* **Flat**: imagen de una fuente uniforme (cielo del crepúsculo, pantalla). Se le
  resta su dark (o el bias), se combina por mediana y se normaliza a mediana 1.

Imagen calibrada = (imagen − dark) / flat normalizado.
"""

from __future__ import annotations

from typing import Iterable, Optional

import numpy as np


def combine(frames: Iterable[np.ndarray], method: str = "mediana", sigma: float = 3.0) -> np.ndarray:
    """Combina una serie de imágenes del mismo tamaño en una maestra (float32).

    ``method``: "mediana", "media" o "sigma" (media tras descartar valores a más de ``sigma`` desviaciones
    robustas de la mediana de cada píxel).
    """
    stack = np.stack([np.asarray(f, dtype=np.float32) for f in frames])
    if stack.ndim != 3 or stack.shape[0] == 0:
        raise ValueError("se necesita al menos una imagen")
    if stack.shape[0] == 1:
        return stack[0].copy()
    if method == "media":
        return stack.mean(axis=0, dtype=np.float32)
    med = np.median(stack, axis=0)
    if method == "mediana":
        return med.astype(np.float32)
    mad = np.median(np.abs(stack - med), axis=0) * 1.4826
    ok = np.abs(stack - med) <= sigma * np.maximum(mad, 1e-6)
    s = np.where(ok, stack, 0).sum(axis=0)
    c = ok.sum(axis=0)
    return np.where(c > 0, s / np.maximum(c, 1), med).astype(np.float32)


def master_flat(flats: Iterable[np.ndarray], dark_for_flats: Optional[np.ndarray] = None,
                bias: Optional[np.ndarray] = None, method: str = "mediana") -> np.ndarray:
    """Flat maestro normalizado a mediana 1 (sin ceros: los píxeles muertos quedan en 1)."""
    corr = []
    for f in flats:
        f = np.asarray(f, dtype=np.float32)
        if dark_for_flats is not None:
            f = f - dark_for_flats
        elif bias is not None:
            f = f - bias
        corr.append(f)
    m = combine(corr, method)
    med = float(np.median(m[m > 0])) if np.any(m > 0) else 1.0
    norm = m / (med if med > 0 else 1.0)
    bad = ~np.isfinite(norm) | (norm < 0.05)
    norm[bad] = 1.0
    return norm.astype(np.float32)


def apply_calibration(img: np.ndarray, dark: Optional[np.ndarray] = None, flat: Optional[np.ndarray] = None,
                      bias: Optional[np.ndarray] = None) -> np.ndarray:
    """(imagen − dark) / flat. Si no hay dark pero sí bias, resta el bias. Devuelve float32."""
    out = np.asarray(img, dtype=np.float32)
    if dark is not None:
        if dark.shape != out.shape:
            raise ValueError(f"el dark mide {dark.shape[1]}×{dark.shape[0]} y la imagen {out.shape[1]}×{out.shape[0]}")
        out = out - dark
    elif bias is not None:
        if bias.shape != out.shape:
            raise ValueError("el bias no tiene el tamaño de la imagen")
        out = out - bias
    if flat is not None:
        if flat.shape != out.shape:
            raise ValueError(f"el flat mide {flat.shape[1]}×{flat.shape[0]} y la imagen {out.shape[1]}×{out.shape[0]}")
        out = out / flat
    return out


def stats(a: np.ndarray) -> dict:
    """Estadística de una región: como la de DS9."""
    a = np.asarray(a, dtype=np.float64)
    if a.size == 0:
        return {}
    med = float(np.median(a))
    return {
        "n": int(a.size), "suma": float(a.sum()), "media": float(a.mean()), "mediana": med,
        "sigma": float(a.std()), "mad": float(np.median(np.abs(a - med)) * 1.4826),
        "min": float(a.min()), "max": float(a.max()),
    }
