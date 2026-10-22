"""Guardado de cuadros en disco.

Formatos:

* ``PNG``   sin pérdida, liviano (8 o 16 bits). Predeterminado.
* ``TIFF``  sin pérdida, conserva 16 bits.
* ``JPG``   con pérdida; el más liviano pero altera los píxeles.
* ``NPY``   un solo archivo NumPy con todos los cuadros (cubo n × alto × ancho).
* ``FITS``  un solo cubo FITS, estándar en astronomía.

Las imágenes sueltas se codifican en varios hilos, con una cola acotada para
que la memoria no crezca aunque el video sea muy largo.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .fits import FitsCubeWriter

FORMATS = {
    "PNG": {"label": "PNG", "ext": "png", "lossless": True, "single_file": False},
    "TIFF": {"label": "TIFF 16 bits", "ext": "tif", "lossless": True, "single_file": False},
    "JPG": {"label": "JPG", "ext": "jpg", "lossless": False, "single_file": False},
    "NPY": {"label": "NumPy (.npy)", "ext": "npy", "lossless": True, "single_file": True},
    "FITS": {"label": "FITS", "ext": "fits", "lossless": True, "single_file": True},
}

# Bytes por píxel aproximados (para estimar el espacio antes de procesar).
BYTES_PER_PIXEL = {"PNG": 0.2, "TIFF": 0.3, "JPG": 0.2, "NPY": 1.0, "FITS": 1.0}


def estimate_bytes(fmt: str, n_frames: int, w: int, h: int, bit_depth: int = 8) -> float:
    bpp = BYTES_PER_PIXEL.get(fmt, 1.0)
    if fmt in ("NPY", "FITS") and bit_depth > 8:
        bpp = 2.0
    if fmt == "PNG" and bit_depth > 8:
        bpp = 0.9
    return float(n_frames) * w * h * bpp


class FrameSink:
    def __init__(self, fmt: str, folder: str, base: str, n_expected: int, h: int, w: int, dtype,
                 extra: dict | None = None):
        if fmt not in FORMATS:
            raise ValueError(f"Formato desconocido: {fmt}")
        self.fmt = fmt
        self.folder = folder
        self.base = base
        self.n_expected = int(n_expected)
        self.h, self.w = int(h), int(w)
        self.dtype = np.dtype(dtype)
        self.n = 0
        self.digits = max(6, len(str(max(n_expected, 1))))
        os.makedirs(folder, exist_ok=True)
        self._err: Exception | None = None
        self._pool = None
        self._sem = None
        self._mm = None
        self._fits = None
        if fmt == "NPY":
            path = os.path.join(folder, f"{base}.npy")
            self.path = path
            self._mm = np.lib.format.open_memmap(path, mode="w+", dtype=self.dtype, shape=(self.n_expected, self.h, self.w))
        elif fmt == "FITS":
            path = os.path.join(folder, f"{base}.fits")
            self.path = path
            self._fits = FitsCubeWriter(path, self.n_expected, self.h, self.w, self.dtype, extra=extra)
        else:
            self.path = folder
            workers = max(2, min(8, (os.cpu_count() or 2)))
            self._pool = ThreadPoolExecutor(max_workers=workers)
            self._sem = threading.BoundedSemaphore(workers * 4)

    def _save_image(self, arr: np.ndarray, path: str) -> None:
        try:
            from PIL import Image

            if self.fmt == "JPG":
                if arr.dtype != np.uint8:
                    arr = (arr >> 8).astype(np.uint8)
                Image.fromarray(arr).save(path, quality=95)
            elif self.fmt == "TIFF":
                if arr.dtype == np.uint8:
                    arr = arr.astype(np.uint16) * 257
                Image.fromarray(arr).save(path, compression="tiff_deflate")
            else:
                Image.fromarray(arr).save(path, compress_level=1)
        except Exception as exc:  # pragma: no cover
            self._err = exc
        finally:
            self._sem.release()

    def write(self, frame_index: int, arr: np.ndarray) -> None:
        if self._err:
            raise self._err
        if self._mm is not None:
            if self.n < self.n_expected:
                self._mm[self.n] = arr
        elif self._fits is not None:
            self._fits.write(arr)
        else:
            ext = FORMATS[self.fmt]["ext"]
            path = os.path.join(self.folder, f"{self.base}_{frame_index:0{self.digits}d}.{ext}")
            self._sem.acquire()
            self._pool.submit(self._save_image, np.ascontiguousarray(arr), path)
        self.n += 1

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
        if self._mm is not None:
            self._mm.flush()
            n_written = min(self.n, self.n_expected)
            del self._mm
            self._mm = None
            if n_written != self.n_expected:
                # Recortar el cubo al número real de cuadros.
                full = np.load(self.path, mmap_mode="r")
                part = np.array(full[:n_written])
                del full
                np.save(self.path, part)
        if self._fits is not None:
            self._fits.close()
        if self._err:
            raise self._err
