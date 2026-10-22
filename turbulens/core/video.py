# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Lectura de video.

TurbuLENS usa PyAV, que trae FFmpeg incluido, así que abre cientos de formatos
(MOV, MP4, AVI, MKV, WMV, MTS, WebM, SER, FITS, …) sin instalar nada más.
Si PyAV no está disponible se usa OpenCV como respaldo.

Todas las imágenes se entregan como arreglos de NumPy en escala de grises:
``uint8`` para videos de 8 bits y ``uint16`` para cámaras de mayor profundidad.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Iterator, Optional, Tuple

import numpy as np

try:  # pragma: no cover - depende del entorno
    import av  # type: ignore

    HAVE_AV = True
except Exception:  # pragma: no cover
    av = None
    HAVE_AV = False

try:  # pragma: no cover
    import cv2  # type: ignore

    HAVE_CV2 = True
except Exception:  # pragma: no cover
    cv2 = None
    HAVE_CV2 = False


VIDEO_EXTENSIONS = [
    "mov", "mp4", "m4v", "avi", "mkv", "webm", "wmv", "asf", "flv", "mts", "m2ts", "ts",
    "mpg", "mpeg", "m2v", "vob", "3gp", "3g2", "mxf", "ogv", "dv", "ser", "fits", "fit",
    "y4m", "gif", "h264", "h265", "hevc", "mjpeg", "mjpg", "nut", "rm", "rmvb", "divx", "xvid",
]


class VideoError(RuntimeError):
    """Error al abrir o leer un video."""


@dataclass
class VideoInfo:
    path: str
    name: str
    size_bytes: int
    container: str
    codec: str
    width: int
    height: int
    fps: float
    n_frames: int
    duration: float
    pix_fmt: str
    bit_depth: int
    backend: str

    def to_dict(self) -> dict:
        return asdict(self)


def _bit_depth_from_pixfmt(fmt: str) -> int:
    f = (fmt or "").lower()
    for tag in ("16", "14", "12", "10", "9"):
        if tag in f and not f.startswith("rgb8"):
            return int(tag)
    return 8


class VideoReader:
    """Lector de video cuadro a cuadro.

    ``frame_at(i)`` entrega el cuadro ``i`` (con caché y lectura secuencial cuando
    se avanza de a pocos cuadros, para que la reproducción sea fluida) e
    ``iter_frames`` recorre un tramo sin cargar el video completo en memoria.
    """

    def __init__(self, path: str, backend: Optional[str] = None):
        if not os.path.isfile(path):
            raise VideoError(f"No se encontró el archivo: {path}")
        self.path = path
        if backend is None:
            backend = "av" if HAVE_AV else ("cv2" if HAVE_CV2 else None)
        if backend is None:
            raise VideoError("No hay ningún lector de video disponible (PyAV u OpenCV).")
        self.backend = backend
        self._seq = None  # generador secuencial abierto
        self._seq_next = -1  # índice que entregará el generador
        self._cache: dict[int, np.ndarray] = {}
        self._cache_order: list[int] = []
        if backend == "av":
            self._open_av()
        else:
            self._open_cv2()

    # ------------------------------------------------------------------ PyAV
    def _open_av(self) -> None:
        try:
            self._container = av.open(self.path)
        except Exception as exc:
            raise VideoError(f"No se pudo abrir el video: {exc}") from exc
        if not self._container.streams.video:
            raise VideoError("El archivo no contiene una pista de video.")
        st = self._container.streams.video[0]
        try:
            st.thread_type = "AUTO"
        except Exception:
            pass
        self._stream = st
        cc = st.codec_context
        fps = float(st.average_rate or st.guessed_rate or st.base_rate or 30.0)
        tb = float(st.time_base) if st.time_base else 1.0 / fps
        dur = None
        if st.duration:
            dur = float(st.duration * tb)
        elif self._container.duration:
            dur = float(self._container.duration) / 1e6
        n = int(st.frames or 0)
        if n <= 0 and dur:
            n = int(round(dur * fps))
        if not dur:
            dur = n / fps if n else 0.0
        pix = cc.format.name if cc.format is not None else (st.format.name if getattr(st, "format", None) else "")
        bd = _bit_depth_from_pixfmt(pix)
        self._tb = tb
        self._start_pts = st.start_time if st.start_time is not None else 0
        self._out_fmt = "gray16le" if bd > 8 else "gray"
        self.info = VideoInfo(
            path=self.path,
            name=os.path.basename(self.path),
            size_bytes=os.path.getsize(self.path),
            container=self._container.format.name if self._container.format else "",
            codec=(cc.name or "").upper(),
            width=int(cc.width or st.width),
            height=int(cc.height or st.height),
            fps=fps,
            n_frames=max(n, 1),
            duration=float(dur),
            pix_fmt=pix,
            bit_depth=bd,
            backend="PyAV / FFmpeg",
        )

    def _av_frame_index(self, frame) -> Optional[int]:
        if frame.pts is None:
            return None
        t = (frame.pts - self._start_pts) * self._tb
        return int(round(t * self.info.fps))

    def _av_to_gray(self, frame) -> np.ndarray:
        arr = frame.to_ndarray(format=self._out_fmt)
        if arr.ndim == 3:
            arr = arr[..., 0]
        return arr

    def _av_seek(self, index: int) -> None:
        t = index / self.info.fps
        ts = int(self._start_pts + t / self._tb)
        try:
            self._container.seek(max(ts, int(self._start_pts)), stream=self._stream, backward=True, any_frame=False)
        except Exception:
            self._container.seek(0)

    def _av_iter_from(self, index: int) -> Iterator[Tuple[int, np.ndarray]]:
        """Decodifica desde el cuadro clave anterior a ``index`` y entrega (i, cuadro)."""
        self._av_seek(index)
        counter = None
        for frame in self._container.decode(self._stream):
            fi = self._av_frame_index(frame)
            if counter is None:
                counter = fi if fi is not None else 0
            else:
                counter += 1
                # Con tasa constante el índice por pts coincide con el contador;
                # si hay saltos (cuadros perdidos) confiamos en el pts.
                if fi is not None and fi > counter:
                    counter = fi
            if counter < index:
                continue
            yield counter, self._av_to_gray(frame)

    # ---------------------------------------------------------------- OpenCV
    def _open_cv2(self) -> None:
        cap = cv2.VideoCapture(self.path)
        if not cap.isOpened():
            raise VideoError("No se pudo abrir el video (OpenCV).")
        self._cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        four = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        codec = "".join(chr((four >> 8 * i) & 0xFF) for i in range(4)).strip("\x00").upper()
        self.info = VideoInfo(
            path=self.path,
            name=os.path.basename(self.path),
            size_bytes=os.path.getsize(self.path),
            container=os.path.splitext(self.path)[1].lstrip(".").lower(),
            codec=codec,
            width=w,
            height=h,
            fps=float(fps),
            n_frames=max(n, 1),
            duration=n / fps if fps else 0.0,
            pix_fmt="bgr24",
            bit_depth=8,
            backend="OpenCV",
        )

    def _cv2_iter_from(self, index: int) -> Iterator[Tuple[int, np.ndarray]]:
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        i = index
        while True:
            ok, frame = self._cap.read()
            if not ok:
                return
            if frame.ndim == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            yield i, frame
            i += 1

    # ---------------------------------------------------------------- común
    def _iter_from(self, index: int) -> Iterator[Tuple[int, np.ndarray]]:
        if self.backend == "av":
            return self._av_iter_from(index)
        return self._cv2_iter_from(index)

    def _remember(self, i: int, arr: np.ndarray) -> None:
        if i in self._cache:
            return
        self._cache[i] = arr
        self._cache_order.append(i)
        if len(self._cache_order) > 48:
            old = self._cache_order.pop(0)
            self._cache.pop(old, None)

    def frame_at(self, index: int) -> np.ndarray:
        """Cuadro ``index`` en escala de grises (con caché y lectura secuencial)."""
        n = self.info.n_frames
        index = int(min(max(index, 0), n - 1))
        if index in self._cache:
            return self._cache[index]
        # Avanzar sin buscar si el pedido está un poco más adelante.
        if self._seq is None or not (self._seq_next <= index <= self._seq_next + 240):
            self._seq = self._iter_from(index)
            self._seq_next = index
        last = None
        for i, arr in self._seq:
            self._seq_next = i + 1
            if i >= index:
                self._remember(i, arr)
                return arr
            last = (i, arr)
        # Fin del video: devolver el último cuadro disponible.
        self._seq = None
        if last is not None:
            self._remember(last[0], last[1])
            return last[1]
        if self._cache:
            return self._cache[self._cache_order[-1]]
        raise VideoError("No se pudo leer el cuadro pedido.")

    def iter_frames(self, start: int = 0, stop: Optional[int] = None) -> Iterator[Tuple[int, np.ndarray]]:
        """Recorre los cuadros ``start..stop`` (incluido) en orden."""
        if stop is None:
            stop = self.info.n_frames - 1
        self._seq = None
        for i, arr in self._iter_from(start):
            if i > stop:
                break
            yield i, arr

    def close(self) -> None:
        self._seq = None
        try:
            if self.backend == "av":
                self._container.close()
            else:
                self._cap.release()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def file_dialog_filter() -> str:
    exts = " ".join(f"*.{e} *.{e.upper()}" for e in VIDEO_EXTENSIONS)
    return f"Videos ({exts});;Todos los archivos (*)"
