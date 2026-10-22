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
from dataclasses import dataclass, field, asdict
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

    def to_dict(self) -> dict:
        d = asdict(self)
        d["roi"] = list(self.roi)
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


def find_star(frame: np.ndarray, near: Optional[tuple] = None, radius: Optional[int] = None) -> tuple[float, float]:
    """Centro (x, y) de la imagen doble: punto medio de los dos picos más brillantes."""
    a = np.asarray(frame, dtype=np.float32)
    H, W = a.shape
    x0 = y0 = 0
    if near is not None and radius:
        cx, cy = near
        x0 = int(max(0, cx - radius)); y0 = int(max(0, cy - radius))
        x1 = int(min(W, cx + radius)); y1 = int(min(H, cy + radius))
        if x1 - x0 > 8 and y1 - y0 > 8:
            a = a[y0:y1, x0:x1]
    # Suavizado ligero (caja 3×3) para no caer en un píxel caliente.
    p = np.pad(a, 1, mode="edge")
    s = sum(p[dy:dy + a.shape[0], dx:dx + a.shape[1]] for dy in range(3) for dx in range(3)) / 9.0
    iy, ix = np.unravel_index(int(np.argmax(s)), s.shape)
    win = 24
    ya, yb = max(0, iy - win), min(a.shape[0], iy + win + 1)
    xa, xb = max(0, ix - win), min(a.shape[1], ix + win + 1)
    sub = a[ya:yb, xa:xb]
    d = detect_pairs(sub[None], config_for_radius(estimate_spot_size(sub[None])))
    if bool(d["valid"][0]):
        mx = (d["x1"][0] + d["x2"][0]) / 2 + xa + x0
        my = (d["y1"][0] + d["y2"][0]) / 2 + ya + y0
        return float(mx), float(my)
    return float(ix + x0), float(iy + y0)


def fit_roi(frame: np.ndarray, margin: int = 24, near: Optional[tuple] = None) -> tuple[int, int, int, int]:
    """Región ajustada a la imagen doble, con margen, en múltiplos de 16 px."""
    a = np.asarray(frame, dtype=np.float32)
    H, W = a.shape
    cx, cy = find_star(a, near=near, radius=200 if near else None)
    win = 40
    xa, xb = int(max(0, cx - win)), int(min(W, cx + win))
    ya, yb = int(max(0, cy - win)), int(min(H, cy + win))
    sub = a[ya:yb, xa:xb]
    d = detect_pairs(sub[None], config_for_radius(estimate_spot_size(sub[None])))
    if bool(d["valid"][0]):
        span_x = abs(d["x2"][0] - d["x1"][0])
        span_y = abs(d["y2"][0] - d["y1"][0])
    else:
        span_x = span_y = 16.0
    w = int(math.ceil((span_x + 2 * margin) / 16.0) * 16)
    h = int(math.ceil((span_y + 2 * margin) / 16.0) * 16)
    w = max(w, h)
    h = w
    x = int(round(cx - w / 2)); y = int(round(cy - h / 2))
    x = min(max(x, 0), W - w); y = min(max(y, 0), H - h)
    return x, y, w, h


def run(reader: VideoReader, opts: ProcessOptions,
        progress: Optional[Callable[[int, int, float], None]] = None,
        cancel: Optional[threading.Event] = None) -> ProcessResult:
    info = reader.info
    W, H = info.width, info.height
    rx, ry, rw, rh = (int(v) for v in opts.roi)
    rw = max(8, min(rw, W)); rh = max(8, min(rh, H))
    start = int(max(0, opts.start))
    stop = int(min(info.n_frames - 1, max(opts.stop, start)))
    total = stop - start + 1
    every = max(1, int(opts.every_n))
    n_save_expected = (total + every - 1) // every

    meas = np.zeros(total + 16, dtype=MEAS_DTYPE)
    cx, cy = rx + rw / 2.0, ry + rh / 2.0
    dtype = np.uint16 if info.bit_depth > 8 else np.uint8
    sink = None
    if opts.save_images and opts.out_dir:
        sink = FrameSink(opts.fmt, opts.out_dir, opts.base_name, n_save_expected, rh, rw, dtype,
                         extra={"VIDEO": info.name[:60], "FPS": round(info.fps, 6), "ROIW": rw, "ROIH": rh})

    cfg: Optional[DetectConfig] = None
    buf = np.empty((opts.chunk, rh, rw), dtype=dtype)
    buf_meta = []  # (fila, cuadro, t, rx, ry)
    n = 0
    n_saved = 0
    lost_chunks = 0
    reacquire = False
    t0 = time.time()
    cancelled = False
    notes = []

    def flush():
        nonlocal cfg, cx, cy, reacquire, lost_chunks
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
        v = d["valid"]
        if opts.track:
            if v.sum() >= max(2, k // 10):
                # Centro de la pareja en los últimos cuadros válidos del bloque.
                last = np.where(v)[0][-min(8, int(v.sum())):]
                mx = (d["x1"][last] + d["x2"][last]) / 2 + offx[last]
                my = (d["y1"][last] + d["y2"][last]) / 2 + offy[last]
                cx, cy = float(np.mean(mx)), float(np.mean(my))
            else:
                lost_chunks += 1
                reacquire = True
        buf_meta.clear()

    for idx, frame in reader.iter_frames(start, stop):
        if cancel is not None and cancel.is_set():
            cancelled = True
            break
        if opts.track and reacquire:
            try:
                cx, cy = find_star(frame, near=(cx, cy), radius=int(3 * max(rw, rh)))
            except Exception:
                pass
            reacquire = False
        x0 = int(round(cx - rw / 2)) if opts.track else rx
        y0 = int(round(cy - rh / 2)) if opts.track else ry
        x0 = min(max(x0, 0), W - rw); y0 = min(max(y0, 0), H - rh)
        crop = frame[y0:y0 + rh, x0:x0 + rw]
        if n >= meas.size:
            meas = np.concatenate([meas, np.zeros(1024, dtype=MEAS_DTYPE)])
        buf[len(buf_meta)] = crop
        buf_meta.append((n, idx, idx / info.fps, x0, y0))
        if sink is not None and (idx - start) % every == 0:
            sink.write(idx, crop)
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
    if lost_chunks:
        notes.append(f"Se perdió la estrella en {lost_chunks} bloque(s) de {opts.chunk} cuadros y se volvió a buscar.")
    return ProcessResult(
        meas=meas, options=opts, video=info.to_dict(), n_saved=n_saved,
        elapsed_s=time.time() - t0, cancelled=cancelled, out_dir=opts.out_dir,
        detect_cfg=asdict(cfg) if cfg else {}, track_lost=lost_chunks, notes=notes,
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
