# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Videos y cuadros sintéticos de un DIMM con valores conocidos (para pruebas)."""

from __future__ import annotations

import numpy as np


def render_pair(h, w, p1, p2, sigma_psf=1.3, peak=200.0, bg=4.0, noise=1.0, rng=None):
    """Imagen con dos spots gaussianos en ``p1`` y ``p2`` (x, y)."""
    rng = rng or np.random.default_rng(0)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    img = bg + noise * rng.standard_normal((h, w))
    for (x, y), amp in ((p1, peak), (p2, peak * 0.85)):
        img += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma_psf ** 2))
    return np.clip(img, 0, 255)


def dimm_track(n, sep=13.0, angle_deg=114.0, sigma_l=0.7, sigma_t=0.65, start=(300.0, 200.0), drift=(-0.8, -1.0), seed=1):
    """Posiciones (x1, y1, x2, y2) de los dos spots con temblor diferencial conocido."""
    rng = np.random.default_rng(seed)
    a = np.radians(angle_deg)
    u = np.array([np.cos(a), np.sin(a)])
    v = np.array([-u[1], u[0]])
    lon = sep + sigma_l * rng.standard_normal(n)
    tra = sigma_t * rng.standard_normal(n)
    common = 0.8 * rng.standard_normal((n, 2))  # vibración del telescopio (se cancela)
    centers = np.array(start)[None, :] + np.outer(np.arange(n), drift) / 10 + common
    d = lon[:, None] * u[None, :] + tra[:, None] * v[None, :]
    p1 = centers - d / 2
    p2 = centers + d / 2
    return p1, p2


def make_video(path: str, n=600, fps=60, w=640, h=400, codec="ffv1", **kw):
    """Escribe un video sintético con PyAV y devuelve las posiciones verdaderas."""
    import av

    p1, p2 = dimm_track(n, **kw)
    rng = np.random.default_rng(3)
    with av.open(path, "w") as out:
        st = out.add_stream(codec, rate=fps)
        st.width, st.height = w, h
        st.pix_fmt = "gray" if codec == "ffv1" else "yuv420p"
        if codec != "ffv1":
            st.options = {"qscale": "2"}
        for i in range(n):
            img = render_pair(h, w, p1[i], p2[i], rng=rng).astype(np.uint8)
            if codec == "ffv1":
                fr = av.VideoFrame.from_ndarray(img, format="gray")
            else:
                fr = av.VideoFrame.from_ndarray(np.stack([img] * 3, axis=-1), format="rgb24")
            for pkt in st.encode(fr):
                out.mux(pkt)
        for pkt in st.encode():
            out.mux(pkt)
    return p1, p2
