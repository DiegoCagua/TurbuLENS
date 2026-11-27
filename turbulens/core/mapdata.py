# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Costas, fronteras y divisiones internas (Natural Earth, dominio público) para dibujar sobre los recortes de GOES.

El archivo ``data/mapa_ne.npz`` guarda las líneas en centésimas de grado (int16), separadas por (32767, 32767):

* ``costas``: ne_50m_coastline · ``paises``: ne_50m_admin_0_boundary_lines_land ·
  ``regiones``: ne_10m_admin_1_states_provinces_lines (países de América; departamentos de Colombia, estados, …).

Se simplificaron (un punto cada ≈0,03–0,05°) y se recortaron a la zona que ve GOES-Este.
"""

from __future__ import annotations

import os

import numpy as np

_SEP = 32767
_cache: dict = {}

LAYERS = (("costas", "#FFD54A", 1.4), ("paises", "#FFFFFF", 1.3), ("regiones", "#9AD0FF", 0.8))


def _path() -> str:
    import sys

    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data", "mapa_ne.npz")


def lines(layer: str) -> list[np.ndarray]:
    """Líneas (lon, lat en grados) de una capa."""
    if layer in _cache:
        return _cache[layer]
    out = []
    try:
        with np.load(_path()) as z:
            a = z[layer]
    except (OSError, KeyError):
        _cache[layer] = out
        return out
    cut = np.flatnonzero(a[:, 0] == _SEP)
    start = 0
    for c in cut:
        if c - start >= 2:
            out.append(a[start:c].astype(np.float64) / 100.0)
        start = c + 1
    _cache[layer] = out
    return out


def project(proj, origin: tuple[int, int], shape: tuple[int, int], margin: float = 2.0) -> list:
    """Capas del mapa en píxeles de un recorte de GOES: [(lista de arreglos N×2 (columna, fila)), color, grosor].

    ``proj`` es la :class:`turbulens.core.goes.Projection` del archivo, ``origin`` la (fila, columna) del primer
    píxel del recorte y ``shape`` su (alto, ancho).
    """
    r0, c0 = origin
    h, w = shape
    # Caja en latitud/longitud que cubre el recorte (con margen) para no proyectar todo el mundo.
    corners = [proj.latlon(proj.x0 + (c0 + cc) * proj.dx, proj.y0 + (r0 + rr) * proj.dy)
               for rr in (0, h / 2, h) for cc in (0, w / 2, w)]
    lats = [a for a, _ in corners if np.isfinite(a)]
    lons = [b for _, b in corners if np.isfinite(b)]
    if not lats:
        return []
    pad = 1.0
    la0, la1 = min(lats) - pad, max(lats) + pad
    lo0, lo1 = min(lons) - pad, max(lons) + pad
    out = []
    for layer, color, width in LAYERS:
        segs = []
        for ln in lines(layer):
            if ln[:, 0].max() < lo0 or ln[:, 0].min() > lo1 or ln[:, 1].max() < la0 or ln[:, 1].min() > la1:
                continue
            col, row, vis = proj.pixels(ln[:, 1], ln[:, 0])
            x = col - c0 + 0.5
            y = row - r0 + 0.5
            ok = vis & (x > -margin * w) & (x < (1 + margin) * w) & (y > -margin * h) & (y < (1 + margin) * h)
            # cortar la línea donde deja de verse
            idx = np.flatnonzero(ok)
            if idx.size < 2:
                continue
            breaks = np.flatnonzero(np.diff(idx) > 1)
            for part in np.split(idx, breaks + 1):
                if part.size >= 2:
                    segs.append(np.column_stack([x[part], y[part]]))
        if segs:
            out.append((segs, color, width))
    return out
