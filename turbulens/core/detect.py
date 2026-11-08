# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Detección de la imagen doble de la estrella (los dos «spots» del DIMM).

Todo está vectorizado con NumPy: se procesa un bloque de cuadros a la vez,
con forma ``(n, alto, ancho)``, sin recorrer píxeles con bucles de Python.

Para cada cuadro:

1. Se estima el fondo (mediana) y el ruido (MAD) del recorte.
2. Se suaviza un poco (caja de 3 × 3) para que un píxel caliente aislado no
   cuente como estrella, y se toman los píxeles sobre un umbral (fracción del
   pico y varias veces el ruido).
3. Esos píxeles se reparten en **dos grupos** (k-medias con k = 2, ponderado por
   el brillo). El primer grupo empieza en el píxel más brillante y el segundo en
   el píxel brillante más lejano. Así funciona con spots de cualquier tamaño,
   con spots desenfocados en forma de anillo y con spots moteados por la
   turbulencia, que se parten en varios pedazos.
4. El centro de cada spot es el centroide ponderado por intensidad de su grupo
   (precisión de centésimas de píxel). Los píxeles muy alejados del grupo se
   descartan y se recalcula.
5. El cuadro es válido si los dos grupos son dos spots de verdad: los dos sobre
   el ruido, de brillo comparable, separados por más de 2,2 veces su tamaño y
   con un «valle» oscuro entre ellos. Si solo se ve un spot, no se parte en dos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class DetectConfig:
    window: int = 4          # (compatibilidad) semiancho típico de un spot (px)
    exclusion: float = 5.0   # (compatibilidad)
    snr_min: float = 6.0     # brillo mínimo del pico, en unidades de ruido
    second_min_ratio: float = 0.12  # el spot más débil debe tener al menos esta fracción del flujo del otro
    threshold_frac: float = 0.15    # fracción del pico usada como umbral
    iterations: int = 8

MAX_ELEMENTS = 3_000_000  # tamaño de cada sub-bloque (n · alto · ancho) para no gastar mucha memoria


def _box(a: np.ndarray, k: int) -> np.ndarray:
    """Promedio móvil k × k (separable, con sumas acumuladas)."""
    if k <= 1:
        return a
    r = k // 2
    p = np.pad(a, ((0, 0), (r, r), (r, r)), mode="edge")
    c = np.cumsum(p, axis=1, dtype=np.float32)
    c = np.concatenate([np.zeros_like(c[:, :1]), c], axis=1)
    v = c[:, k:] - c[:, :-k]
    c = np.cumsum(v, axis=2, dtype=np.float32)
    c = np.concatenate([np.zeros_like(c[:, :, :1]), c], axis=2)
    return (c[:, :, k:] - c[:, :, :-k]) / float(k * k)


def estimate_spot_size(stack: np.ndarray) -> float:
    """Radio aproximado de cada spot (px) a partir de unos cuadros de muestra."""
    a = np.asarray(stack, dtype=np.float32)
    if a.ndim == 2:
        a = a[None]
    a = a[: min(len(a), 32)]
    n = a.shape[0]
    bg = np.median(a.reshape(n, -1), axis=1)
    s = _box(a - bg[:, None, None], 3)
    peak = s.reshape(n, -1).max(axis=1)
    area = (s.reshape(n, -1) > (0.25 * peak)[:, None]).sum(axis=1) / 2.0
    r = np.sqrt(np.maximum(area, 1.0) / np.pi)
    return float(np.median(r))


def config_for_radius(r: float) -> DetectConfig:
    r = float(max(r, 0.7))
    return DetectConfig(window=int(max(3, np.ceil(2.5 * r))), exclusion=float(max(4.0, 3.0 * r)))


def detect_pairs(stack: np.ndarray, cfg: DetectConfig | None = None) -> dict:
    """Detecta los dos spots en cada cuadro de ``stack`` (n, alto, ancho).

    Devuelve un diccionario de arreglos de largo ``n`` con las coordenadas
    (dentro del recorte) ``x1, y1, x2, y2``, los flujos, los picos, el ruido,
    el tamaño de cada spot (``r1``, ``r2``) y la máscara ``valid``.
    """
    cfg = cfg or DetectConfig()
    a = np.asarray(stack)
    if a.ndim == 2:
        a = a[None]
    n, h, w = a.shape
    step = max(1, MAX_ELEMENTS // max(1, h * w))
    if n > step:
        parts = [detect_pairs(a[i:i + step], cfg) for i in range(0, n, step)]
        return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    return _detect(a.astype(np.float32, copy=False), cfg)


def _detect(a: np.ndarray, cfg: DetectConfig) -> dict:
    n, h, w = a.shape
    ar = np.arange(n)
    flat = a.reshape(n, -1)
    bg = np.median(flat, axis=1)
    mad = np.median(np.abs(flat - bg[:, None]), axis=1) * 1.4826
    noise = np.maximum(mad, 0.5).astype(np.float32)
    sub = a - bg[:, None, None]
    s3 = _box(sub, 3)
    Y = np.arange(h, dtype=np.float32)[None, :, None]
    X = np.arange(w, dtype=np.float32)[None, None, :]

    s3f = s3.reshape(n, -1)
    i_pk = np.argmax(s3f, axis=1)
    peak3 = s3f[ar, i_pk]
    thr = np.maximum(cfg.threshold_frac * peak3, 4.0 * noise / 3.0)
    fg = (s3 > thr[:, None, None]) & (sub > thr[:, None, None])
    wgt = np.where(fg, sub - thr[:, None, None], 0.0).astype(np.float32)

    # Arranque: primer grupo en el píxel más brillante; segundo en el píxel brillante más lejano.
    y1, x1 = np.divmod(i_pk, w)
    c1y, c1x = y1.astype(np.float32), x1.astype(np.float32)
    bright = s3 > (0.35 * peak3)[:, None, None]
    d1 = (Y - c1y[:, None, None]) ** 2 + (X - c1x[:, None, None]) ** 2
    i_far = np.argmax(np.where(bright, d1, -1.0).reshape(n, -1), axis=1)
    y2, x2 = np.divmod(i_far, w)
    c2y, c2x = y2.astype(np.float32), x2.astype(np.float32)
    same = (c2y == c1y) & (c2x == c1x)
    c2x = np.where(same, c1x + 1.0, c2x)

    def centroids(c1y, c1x, c2y, c2x, lim1=None, lim2=None):
        d1 = (Y - c1y[:, None, None]) ** 2 + (X - c1x[:, None, None]) ** 2
        d2 = (Y - c2y[:, None, None]) ** 2 + (X - c2x[:, None, None]) ** 2
        A = d1 <= d2
        wA = np.where(A, wgt, 0.0)
        wB = wgt - wA
        if lim1 is not None:
            wA = np.where(d1 <= lim1[:, None, None], wA, 0.0)
            wB = np.where(d2 <= lim2[:, None, None], wB, 0.0)
        S1 = wA.sum(axis=(1, 2))
        S2 = wB.sum(axis=(1, 2))
        s1 = np.where(S1 > 0, S1, 1.0)
        s2 = np.where(S2 > 0, S2, 1.0)
        n1y = np.where(S1 > 0, (wA * Y).sum(axis=(1, 2)) / s1, c1y)
        n1x = np.where(S1 > 0, (wA * X).sum(axis=(1, 2)) / s1, c1x)
        n2y = np.where(S2 > 0, (wB * Y).sum(axis=(1, 2)) / s2, c2y)
        n2x = np.where(S2 > 0, (wB * X).sum(axis=(1, 2)) / s2, c2x)
        return n1y, n1x, n2y, n2x, A, wA, wB, S1, S2

    for _ in range(max(1, cfg.iterations)):
        n1y, n1x, n2y, n2x, A, wA, wB, S1, S2 = centroids(c1y, c1x, c2y, c2x)
        moved = np.maximum(np.abs(n1y - c1y) + np.abs(n1x - c1x), np.abs(n2y - c2y) + np.abs(n2x - c2x))
        c1y, c1x, c2y, c2x = n1y, n1x, n2y, n2x
        if float(moved.max(initial=0.0)) < 1e-3:
            break

    def gyration(wX, cy, cx, S):
        r2 = ((Y - cy[:, None, None]) ** 2 + (X - cx[:, None, None]) ** 2) * wX
        return np.sqrt(r2.sum(axis=(1, 2)) / np.where(S > 0, S, 1.0))

    # Recorte: fuera los píxeles muy lejos de su grupo (otra estrella, un reflejo) y se recalcula.
    rg1 = gyration(wA, c1y, c1x, S1)
    rg2 = gyration(wB, c2y, c2x, S2)
    lim1 = (3.0 * rg1 + 3.0) ** 2
    lim2 = (3.0 * rg2 + 3.0) ** 2
    c1y, c1x, c2y, c2x, A, wA, wB, S1, S2 = centroids(c1y, c1x, c2y, c2x, lim1, lim2)
    rg1 = gyration(wA, c1y, c1x, S1)
    rg2 = gyration(wB, c2y, c2x, S2)

    inA = (wA > 0)
    inB = (wB > 0)
    p1 = np.where(inA, sub, -np.inf).reshape(n, -1).max(axis=1)
    p2 = np.where(inB, sub, -np.inf).reshape(n, -1).max(axis=1)
    q1 = np.where(inA, s3, -np.inf).reshape(n, -1).max(axis=1)
    q2 = np.where(inB, s3, -np.inf).reshape(n, -1).max(axis=1)
    my = np.clip(np.rint((c1y + c2y) / 2).astype(int), 0, h - 1)
    mx = np.clip(np.rint((c1x + c2x) / 2).astype(int), 0, w - 1)
    dip = s3[ar, my, mx]
    sep = np.hypot(c1y - c2y, c1x - c2x)
    flux1 = np.clip(np.where(inA, sub, 0.0), 0, None).sum(axis=(1, 2))
    flux2 = np.clip(np.where(inB, sub, 0.0), 0, None).sum(axis=(1, 2))
    fmin, fmax = np.minimum(flux1, flux2), np.maximum(flux1, flux2)
    inside = (c1y >= 1) & (c1y <= h - 2) & (c1x >= 1) & (c1x <= w - 2) & (c2y >= 1) & (c2y <= h - 2) & (c2x >= 1) & (c2x <= w - 2)
    with np.errstate(invalid="ignore"):
        valid = (
            (S1 > 0) & (S2 > 0)
            & (p1 > cfg.snr_min * noise) & (p2 > cfg.snr_min * noise)
            & (fmin > cfg.second_min_ratio * np.maximum(fmax, 1e-9))
            & (sep > 2.2 * np.maximum(np.maximum(rg1, rg2), 0.5))
            & (dip < 0.6 * np.minimum(q1, q2))
            & np.isfinite(p1) & np.isfinite(p2)
            & inside
        )
    # El «primer» spot es el más brillante (el orden se reordena después con el eje principal).
    swap = p2 > p1
    X1 = np.where(swap, c2x, c1x); Y1 = np.where(swap, c2y, c1y)
    X2 = np.where(swap, c1x, c2x); Y2 = np.where(swap, c1y, c2y)
    F1 = np.where(swap, flux2, flux1); F2 = np.where(swap, flux1, flux2)
    P1 = np.where(swap, p2, p1); P2 = np.where(swap, p1, p2)
    R1 = np.where(swap, rg2, rg1); R2 = np.where(swap, rg1, rg2)
    return {
        "x1": X1.astype(np.float64), "y1": Y1.astype(np.float64), "x2": X2.astype(np.float64), "y2": Y2.astype(np.float64),
        "flux1": F1.astype(np.float32), "flux2": F2.astype(np.float32),
        "peak1": np.where(np.isfinite(P1), P1, 0).astype(np.float32),
        "peak2": np.where(np.isfinite(P2), P2, 0).astype(np.float32),
        "noise": noise, "r1": R1.astype(np.float32), "r2": R2.astype(np.float32), "valid": valid,
    }


def pair_extent(d: dict, valid_only: bool = True) -> tuple[float, float, float]:
    """Separación típica, tamaño típico de un spot y movimiento del centro de la pareja (px), a partir de ``detect_pairs``."""
    v = d["valid"] if valid_only else np.ones_like(d["valid"])
    if not v.any():
        return 0.0, 0.0, 0.0
    sep = np.hypot(d["x1"][v] - d["x2"][v], d["y1"][v] - d["y2"][v])
    r = np.maximum(d["r1"][v], d["r2"][v])
    mx = (d["x1"][v] + d["x2"][v]) / 2
    my = (d["y1"][v] + d["y2"][v]) / 2
    jit = float(np.hypot(np.std(mx), np.std(my))) if v.sum() > 1 else 0.0
    return float(np.median(sep)), float(np.median(r)), jit
