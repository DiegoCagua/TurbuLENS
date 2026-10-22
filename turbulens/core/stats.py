"""Estadística básica con NumPy, usada por el análisis y por el modo educativo."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Summary:
    n: int
    mean: float
    median: float
    std: float      # desviación estándar muestral (ddof=1)
    var: float
    sem: float      # error estándar de la media = std / sqrt(n)
    min: float
    max: float
    q1: float
    q3: float
    mad: float      # desviación absoluta mediana escalada (≈ σ para datos normales)

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def summarize(x) -> Summary:
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    n = int(a.size)
    if n == 0:
        nan = float("nan")
        return Summary(0, nan, nan, nan, nan, nan, nan, nan, nan, nan, nan)
    mean = float(a.mean())
    std = float(a.std(ddof=1)) if n > 1 else 0.0
    q1, med, q3 = (float(v) for v in np.percentile(a, [25, 50, 75]))
    mad = float(np.median(np.abs(a - med)) * 1.4826)
    return Summary(n, mean, med, std, std * std, std / math.sqrt(n) if n > 0 else float("nan"),
                   float(a.min()), float(a.max()), q1, q3, mad)


def sigma_clip_mask(x, k: float = 5.0, iters: int = 3) -> np.ndarray:
    """Máscara de datos que quedan tras descartar los que se alejan más de ``k`` σ robustas."""
    a = np.asarray(x, dtype=np.float64)
    keep = np.isfinite(a)
    for _ in range(iters):
        if keep.sum() < 3:
            break
        med = np.median(a[keep])
        mad = np.median(np.abs(a[keep] - med)) * 1.4826
        if mad <= 0:
            break
        new = keep & (np.abs(a - med) <= k * mad)
        if new.sum() == keep.sum():
            break
        keep = new
    return keep


def nice_bins(x, nbins: int | None = None, lo: float | None = None, hi: float | None = None):
    """Bordes del histograma (regla de Freedman–Diaconis si no se da ``nbins``)."""
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return np.linspace(0, 1, 11)
    lo = float(a.min()) if lo is None else lo
    hi = float(a.max()) if hi is None else hi
    if hi <= lo:
        hi = lo + 1.0
    if nbins is None:
        q1, q3 = np.percentile(a, [25, 75])
        h = 2 * (q3 - q1) / max(a.size, 1) ** (1 / 3)
        nbins = int(np.clip(np.ceil((hi - lo) / h) if h > 0 else 20, 8, 60))
    return np.linspace(lo, hi, int(nbins) + 1)


def normal_pdf(x, mu: float, sigma: float):
    x = np.asarray(x, dtype=np.float64)
    if sigma <= 0:
        return np.zeros_like(x)
    return np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))


def fraction_within(x, mu: float, sigma: float, k: float) -> float:
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return float("nan")
    return float(np.mean(np.abs(a - mu) <= k * sigma))


def sample_means(x, size: int, repeats: int = 2000, seed: int = 0) -> np.ndarray:
    """Medias de ``repeats`` muestras aleatorias de tamaño ``size`` (teorema del límite central)."""
    a = np.asarray(x, dtype=np.float64)
    a = a[np.isfinite(a)]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(repeats, int(size)))
    return a[idx].mean(axis=1)


def pearson_r(x, y) -> float:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 3:
        return float("nan")
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def running_std(t, x, window_s: float):
    """Desviación estándar de ``x`` en ventanas consecutivas de ``window_s`` segundos."""
    t = np.asarray(t, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    if t.size == 0:
        return np.array([]), np.array([]), np.array([], dtype=int)
    t0, t1 = float(t.min()), float(t.max())
    nseg = max(1, int(np.ceil((t1 - t0 + 1e-9) / window_s)))
    seg = np.minimum(((t - t0) / window_s).astype(int), nseg - 1)
    mids = t0 + (np.arange(nseg) + 0.5) * window_s
    sd = np.full(nseg, np.nan)
    cnt = np.bincount(seg, minlength=nseg)
    s1 = np.bincount(seg, weights=x, minlength=nseg)
    s2 = np.bincount(seg, weights=x * x, minlength=nseg)
    ok = cnt > 1
    var = np.where(ok, (s2 - s1 * s1 / np.maximum(cnt, 1)) / np.maximum(cnt - 1, 1), np.nan)
    sd[ok] = np.sqrt(np.maximum(var[ok], 0))
    return mids, sd, cnt
