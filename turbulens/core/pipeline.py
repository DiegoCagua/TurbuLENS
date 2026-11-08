# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Procesamiento completo de un video: separar en imágenes y medir.

Recorre el tramo elegido una sola vez:

* recorta cada cuadro alrededor de la estrella, siguiéndola si se mueve;
* guarda los recortes (si el usuario lo pide) en el formato elegido;
* detecta los dos spots en bloques de cuadros (NumPy vectorizado);
* guarda las mediciones en un arreglo estructurado reservado de antemano.

El resultado queda listo para analizar: imágenes, ``mediciones.csv`` y
``resumen.json`` en la carpeta de salida.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from dataclasses import dataclass, field, asdict, replace
from typing import Callable, Optional

import numpy as np

from .detect import DetectConfig, config_for_radius, detect_pairs, estimate_spot_size
from .dimm import DimmParams, DimmResult, analyze
from .video import VideoReader
from .writers import FrameSink

MEAS_DTYPE = np.dtype([
    ("frame", "i4"), ("t", "f8"),
    ("x1", "f8"), ("y1", "f8"), ("x2", "f8"), ("y2", "f8"),
    ("flux1", "f4"), ("flux2", "f4"), ("peak1", "f4"), ("peak2", "f4"), ("noise", "f4"),
    ("roi_x", "i4"), ("roi_y", "i4"), ("valid", "?"),
])


@dataclass
class ProcessOptions:
    roi: tuple  # (x, y, ancho, alto) en el cuadro de referencia
    start: int
    stop: int
    track: bool = True
    save_images: bool = True
    fmt: str = "PNG"
    every_n: int = 1
    out_dir: str = ""
    base_name: str = "cuadro"
    chunk: int = 32
    auto_size: bool = True      # ajustar el tamaño de la región al tamaño real de la imagen doble
    calibration: Optional[dict] = None  # {"dark": arreglo, "flat": arreglo} (cuadro completo), opcional

    def to_dict(self) -> dict:
        d = asdict(self)
        d["roi"] = list(self.roi)
        d.pop("calibration", None)
        d["calibrated"] = bool(self.calibration)
        return d


@dataclass
class ProcessResult:
    meas: np.ndarray
    options: ProcessOptions
    video: dict
    n_saved: int
    elapsed_s: float
    cancelled: bool
    out_dir: str
    detect_cfg: dict
    track_lost: int = 0
    notes: list = field(default_factory=list)
    # Muestra de recortes para la animación de centroides (k, alto, ancho) y su fila en ``meas``.
    preview_frames: Optional[np.ndarray] = None
    preview_rows: Optional[np.ndarray] = None


MIN_ROI = 16  # px: más pequeño no caben dos spots con margen


def _smooth(a: np.ndarray, k: int) -> np.ndarray:
    from .detect import _box

    return _box(np.asarray(a, dtype=np.float32)[None], k)[0]


def light_center(crop: np.ndarray) -> tuple[float, float, bool]:
    """Centro de luz (x, y) de un recorte, rápido: sirve para seguir a la estrella cuadro a cuadro.

    Devuelve ``ok=False`` si no hay nada claramente más brillante que el fondo.
    """
    a = np.asarray(crop, dtype=np.float32)
    h, w = a.shape
    if h < 4 or w < 4:
        return w / 2.0, h / 2.0, False
    border = np.concatenate([a[0], a[-1], a[1:-1, 0], a[1:-1, -1]])
    bg = float(np.median(border))
    noise = max(1.4826 * float(np.median(np.abs(border - bg))), 0.5)
    m = float(a.max())
    if m - bg < 8.0 * noise:
        return w / 2.0, h / 2.0, False
    wgt = np.clip(a - (bg + 0.25 * (m - bg)), 0.0, None)
    s = float(wgt.sum())
    if s <= 0:
        return w / 2.0, h / 2.0, False
    ys = np.arange(h, dtype=np.float32)
    xs = np.arange(w, dtype=np.float32)
    return float((wgt.sum(axis=0) * xs).sum() / s), float((wgt.sum(axis=1) * ys).sum() / s), True


def locate_pair(frame: np.ndarray, near: Optional[tuple] = None, radius: Optional[int] = None) -> Optional[dict]:
    """Busca la imagen doble y la mide con una ventana que crece hasta contener los dos spots.

    Devuelve ``{"cx", "cy", "sep", "dx", "dy", "r", "valid"}`` en coordenadas del cuadro, o ``None``.
    """
    a = np.asarray(frame, dtype=np.float32)
    H, W = a.shape
    x0 = y0 = 0
    if near is not None and radius:
        cx, cy = near
        x0 = int(max(0, cx - radius)); y0 = int(max(0, cy - radius))
        xe = int(min(W, cx + radius)); ye = int(min(H, cy + radius))
        if xe - x0 > 8 and ye - y0 > 8:
            a = a[y0:ye, x0:xe]
    h, w = a.shape
    # Búsqueda gruesa: en cuadros grandes se reduce a la mitad (rápido) y se suaviza para no caer en un píxel caliente.
    f = 2 if h * w > 1_500_000 else 1
    small = a[: h - h % f, : w - w % f].reshape(h // f, f, w // f, f).mean(axis=(1, 3)) if f > 1 else a
    s = _smooth(small, 5)
    iy, ix = np.unravel_index(int(np.argmax(s)), s.shape)
    iy, ix = iy * f + f // 2, ix * f + f // 2
    best = None
    for win in (24, 48, 96, 192):
        ya, yb = max(0, iy - win), min(h, iy + win + 1)
        xa, xb = max(0, ix - win), min(w, ix + win + 1)
        sub = a[ya:yb, xa:xb]
        d = detect_pairs(sub[None])
        cx = (d["x1"][0] + d["x2"][0]) / 2 + xa
        cy = (d["y1"][0] + d["y2"][0]) / 2 + ya
        r = float(max(d["r1"][0], d["r2"][0]))
        res = {"cx": float(cx + x0), "cy": float(cy + y0), "dx": float(abs(d["x2"][0] - d["x1"][0])),
               "dy": float(abs(d["y2"][0] - d["y1"][0])), "r": r, "valid": bool(d["valid"][0])}
        res["sep"] = float(math.hypot(res["dx"], res["dy"]))
        if res["valid"]:
            # Válido y lejos del borde de la ventana: listo. Si toca el borde, se prueba una ventana mayor.
            m = min(d["x1"][0], d["x2"][0], d["y1"][0], d["y2"][0],
                    sub.shape[1] - 1 - max(d["x1"][0], d["x2"][0]), sub.shape[0] - 1 - max(d["y1"][0], d["y2"][0]))
            best = res
            if m > 2.0 * r + 2 or (xa == 0 and ya == 0 and xb == w and yb == h):
                return res
        elif best is None and win == 24:
            best = res
    if best is None:
        return None
    if not best["valid"]:
        best["cx"], best["cy"] = float(ix + x0), float(iy + y0)
    return best


def find_star(frame: np.ndarray, near: Optional[tuple] = None, radius: Optional[int] = None) -> tuple[float, float]:
    """Centro (x, y) de la imagen doble: punto medio de los dos spots."""
    r = locate_pair(frame, near=near, radius=radius)
    if r is None:
        H, W = np.asarray(frame).shape
        return W / 2.0, H / 2.0
    return r["cx"], r["cy"]


def roi_size_for(sep_dx: float, sep_dy: float, r_spot: float, jitter: float = 0.0, frame_shape=None) -> int:
    """Lado de una región cuadrada que contiene la pareja con margen para el fondo y el movimiento."""
    margin = max(12.0, 3.0 * r_spot + 4.0 * jitter + 6.0)
    side = int(math.ceil((max(sep_dx, sep_dy) + 2 * margin) / 8.0) * 8)
    side = max(side, MIN_ROI + 8)
    if frame_shape is not None:
        side = min(side, min(frame_shape))
    return side


def fit_roi(frame: np.ndarray, margin: int = 24, near: Optional[tuple] = None) -> tuple[int, int, int, int]:
    """Región ajustada a la imagen doble, con margen."""
    a = np.asarray(frame, dtype=np.float32)
    H, W = a.shape
    r = locate_pair(a, near=near, radius=400 if near else None)
    if r is None or not r["valid"]:
        cx, cy = (r["cx"], r["cy"]) if r else (W / 2, H / 2)
        side = 64
    else:
        cx, cy = r["cx"], r["cy"]
        side = roi_size_for(r["dx"], r["dy"], r["r"], 1.0, (H, W))
    x = int(round(cx - side / 2)); y = int(round(cy - side / 2))
    x = min(max(x, 0), W - side); y = min(max(y, 0), H - side)
    return x, y, side, side


def _calibrate(frame: np.ndarray, cal: Optional[dict]) -> np.ndarray:
    if not cal:
        return frame
    from .calibration import apply_calibration

    return apply_calibration(frame, cal.get("dark"), cal.get("flat"), cal.get("bias"))


def run(reader: VideoReader, opts: ProcessOptions,
        progress: Optional[Callable[[int, int, float], None]] = None,
        cancel: Optional[threading.Event] = None) -> ProcessResult:
    info = reader.info
    W, H = info.width, info.height
    rx, ry, rw, rh = (int(v) for v in opts.roi)
    rw = max(MIN_ROI, min(rw, W)); rh = max(MIN_ROI, min(rh, H))
    start = int(max(0, opts.start))
    stop = int(min(info.n_frames - 1, max(opts.stop, start)))
    total = stop - start + 1
    every = max(1, int(opts.every_n))
    n_save_expected = (total + every - 1) // every
    notes = []
    cal = opts.calibration
    cx, cy = rx + rw / 2.0, ry + rh / 2.0

    # 1) Búsqueda inicial: se ubica la estrella en los primeros cuadros, aunque la región quede lejos,
    #    y se mide su tamaño para ajustar la región.
    if opts.track or opts.auto_size:
        sample = []
        for idx, frame in reader.iter_frames(start, min(stop, start + 23)):
            sample.append(_calibrate(frame, cal))
        if sample:
            first = sample[0]
            r_near = locate_pair(first, near=(cx, cy), radius=int(max(64, 1.5 * max(rw, rh))))
            if r_near is None or not r_near["valid"]:
                r_near = locate_pair(first)  # en todo el cuadro
                if r_near is not None and r_near["valid"] and opts.track:
                    notes.append("La estrella estaba lejos de la región elegida: se ubicó en todo el cuadro antes de empezar.")
            if r_near is not None and r_near["valid"]:
                if opts.track:
                    cx, cy = r_near["cx"], r_near["cy"]
                if opts.auto_size:
                    # Tamaño con varios cuadros: separación, tamaño de los spots y cuánto se mueve la pareja.
                    win = int(max(rw, rh, 2 * roi_size_for(r_near["dx"], r_near["dy"], r_near["r"], 0.0)))
                    xa = int(min(max(r_near["cx"] - win / 2, 0), max(0, W - win)))
                    ya = int(min(max(r_near["cy"] - win / 2, 0), max(0, H - win)))
                    stack = np.stack([f[ya:ya + win, xa:xa + win] for f in sample]).astype(np.float32)
                    d = detect_pairs(stack)
                    if d["valid"].any():
                        v = d["valid"]
                        dx = float(np.percentile(np.abs(d["x2"][v] - d["x1"][v]), 90))
                        dy = float(np.percentile(np.abs(d["y2"][v] - d["y1"][v]), 90))
                        r_spot = float(np.median(np.maximum(d["r1"][v], d["r2"][v])))
                        mx = (d["x1"][v] + d["x2"][v]) / 2
                        my = (d["y1"][v] + d["y2"][v]) / 2
                        jit = float(max(np.std(mx), np.std(my))) if v.sum() > 2 else 1.0
                        if not opts.track:
                            jit += float(max(np.ptp(mx), np.ptp(my)))  # sin seguimiento, la región debe cubrir la deriva
                        side = roi_size_for(dx, dy, r_spot, jit, (H, W))
                        if side != rw or side != rh:
                            notes.append(f"La región se ajustó a {side} × {side} px para que quepan los dos spots con margen.")
                        if not opts.track:
                            cx, cy = rx + rw / 2.0, ry + rh / 2.0
                        rw = rh = side
    rx = int(round(cx - rw / 2)); ry = int(round(cy - rh / 2))
    rx = min(max(rx, 0), W - rw); ry = min(max(ry, 0), H - rh)
    if not opts.track:
        cx, cy = rx + rw / 2.0, ry + rh / 2.0
    used_opts = replace(opts, roi=(rx, ry, rw, rh))

    meas = np.zeros(total + 16, dtype=MEAS_DTYPE)
    dtype = np.uint16 if info.bit_depth > 8 else np.uint8
    sink = None
    if opts.save_images and opts.out_dir:
        sink = FrameSink(opts.fmt, opts.out_dir, opts.base_name, n_save_expected, rh, rw, dtype,
                         extra={"VIDEO": info.name[:60], "FPS": round(info.fps, 6), "ROIW": rw, "ROIH": rh})

    cfg: Optional[DetectConfig] = None
    buf = np.empty((opts.chunk, rh, rw), dtype=np.float32 if cal else dtype)
    buf_meta = []  # (fila, cuadro, t, rx, ry)
    # Muestra para la animación: hasta ~900 recortes y como máximo ~48 MB.
    prev_max = int(max(60, min(900, 48e6 / max(1, rw * rh * np.dtype(dtype).itemsize))))
    prev_step = max(1, int(np.ceil(total / prev_max)))
    prev_frames: list = []
    prev_rows: list = []
    n = 0
    n_saved = 0
    lost_chunks = 0
    misses = 0
    reacquired = 0
    t0 = time.time()
    cancelled = False

    def flush():
        nonlocal cfg, lost_chunks
        k = len(buf_meta)
        if k == 0:
            return
        block = buf[:k]
        if cfg is None:
            cfg = config_for_radius(estimate_spot_size(block))
        d = detect_pairs(block, cfg)
        rows = np.array([m[0] for m in buf_meta])
        offx = np.array([m[3] for m in buf_meta], dtype=np.float64)
        offy = np.array([m[4] for m in buf_meta], dtype=np.float64)
        meas["frame"][rows] = [m[1] for m in buf_meta]
        meas["t"][rows] = [m[2] for m in buf_meta]
        meas["x1"][rows] = d["x1"] + offx
        meas["y1"][rows] = d["y1"] + offy
        meas["x2"][rows] = d["x2"] + offx
        meas["y2"][rows] = d["y2"] + offy
        for key in ("flux1", "flux2", "peak1", "peak2", "noise"):
            meas[key][rows] = d[key]
        meas["roi_x"][rows] = offx.astype(int)
        meas["roi_y"][rows] = offy.astype(int)
        meas["valid"][rows] = d["valid"]
        if d["valid"].sum() < max(2, k // 10):
            lost_chunks += 1
        buf_meta.clear()

    for idx, frame in reader.iter_frames(start, stop):
        if cancel is not None and cancel.is_set():
            cancelled = True
            break
        frame = _calibrate(frame, cal)
        x0 = int(round(cx - rw / 2)) if opts.track else rx
        y0 = int(round(cy - rh / 2)) if opts.track else ry
        x0 = min(max(x0, 0), W - rw); y0 = min(max(y0, 0), H - rh)
        crop = frame[y0:y0 + rh, x0:x0 + rw]
        if opts.track:
            # 2) Seguimiento cuadro a cuadro: la región se mueve hacia el centro de luz (amortiguado para
            #    no copiar el temblor de la turbulencia). Si se pierde varios cuadros, se busca en todo el cuadro.
            lx, ly, ok = light_center(crop)
            if ok:
                misses = 0
                cx += 0.5 * (x0 + lx - cx)
                cy += 0.5 * (y0 + ly - cy)
            else:
                misses += 1
                if misses >= 5:
                    r_far = locate_pair(frame)
                    if r_far is not None and r_far["valid"]:
                        cx, cy = r_far["cx"], r_far["cy"]
                        reacquired += 1
                    misses = 0
        if n >= meas.size:
            meas = np.concatenate([meas, np.zeros(1024, dtype=MEAS_DTYPE)])
        buf[len(buf_meta)] = crop
        buf_meta.append((n, idx, idx / info.fps, x0, y0))
        if (idx - start) % prev_step == 0 and len(prev_frames) < prev_max:
            prev_frames.append(np.clip(crop, 0, np.iinfo(dtype).max).astype(dtype) if cal else crop.copy())
            prev_rows.append(n)
        if sink is not None and (idx - start) % every == 0:
            sink.write(idx, np.clip(crop, 0, np.iinfo(dtype).max).astype(dtype) if cal else crop)
            n_saved += 1
        n += 1
        if len(buf_meta) == opts.chunk:
            flush()
        if progress is not None and (n % 16 == 0 or n == total):
            el = time.time() - t0
            progress(n, total, n / el if el > 0 else 0.0)
    flush()
    if sink is not None:
        sink.close()
    meas = meas[:n]
    if reacquired:
        notes.append(f"Se perdió la estrella {reacquired} vez/veces y se volvió a encontrar en todo el cuadro.")
    if lost_chunks:
        notes.append(f"En {lost_chunks} bloque(s) de {opts.chunk} cuadros casi no se vieron los dos spots.")
    return ProcessResult(
        meas=meas, options=used_opts, video=info.to_dict(), n_saved=n_saved,
        elapsed_s=time.time() - t0, cancelled=cancelled, out_dir=opts.out_dir,
        detect_cfg=asdict(cfg) if cfg else {}, track_lost=lost_chunks + reacquired, notes=notes,
        preview_frames=np.stack(prev_frames) if prev_frames else None,
        preview_rows=np.array(prev_rows, dtype=np.int32) if prev_rows else None,
    )


def write_outputs(res: ProcessResult, dimm: DimmResult, params: DimmParams) -> None:
    """Escribe ``mediciones.csv`` y ``resumen.json`` junto a las imágenes."""
    if not res.out_dir:
        return
    os.makedirs(res.out_dir, exist_ok=True)
    from .export import write_measurements_csv, summary_record

    write_measurements_csv(os.path.join(res.out_dir, "mediciones.csv"), res.meas, dimm)
    with open(os.path.join(res.out_dir, "resumen.json"), "w", encoding="utf-8") as f:
        json.dump(summary_record(res, dimm, params), f, ensure_ascii=False, indent=2, default=float)
