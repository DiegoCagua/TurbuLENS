# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Visor de imágenes científicas al estilo de SAOImage DS9.

* Escalas de brillo: lineal, logarítmica, raíz cuadrada, asinh e histograma ecualizado.
* Límites: mínimo–máximo, percentiles o ZScale (el algoritmo de IRAF que usa DS9 por defecto).
* Mapas de color: grises, grises invertidos, calor, viridis y «frío–cálido».
* Rueda: zoom alrededor del cursor. Arrastrar: mover. Mayús + arrastrar (o clic derecho y arrastrar): región.
* Señales con la posición y el valor del píxel bajo el cursor y con la región elegida.

Las coordenadas que se muestran empiezan en 1, como en DS9 (el píxel 1,1 es el de abajo a la izquierda
en FITS; aquí la fila 1 es la de arriba en pantalla, y así se indica en la interfaz).
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..i18n import tr
from .theme import theme

STRETCHES = [("lineal", "Lineal"), ("log", "Logarítmica"), ("raiz", "Raíz cuadrada"), ("asinh", "Asinh"),
             ("histeq", "Histograma ecualizado")]
LIMITS = [("minmax", "Mínimo – máximo"), ("p995", "99,5 %"), ("p99", "99 %"), ("p95", "95 %"), ("zscale", "ZScale")]
CMAPS = [("gris", "Grises"), ("inv", "Grises invertidos"), ("calor", "Calor"), ("viridis", "Viridis"),
         ("frio", "Frío – cálido")]

_CMAP_POINTS = {
    "gris": [(0, (0, 0, 0)), (1, (255, 255, 255))],
    "inv": [(0, (255, 255, 255)), (1, (0, 0, 0))],
    "calor": [(0, (0, 0, 0)), (0.35, (180, 20, 0)), (0.7, (255, 170, 0)), (1, (255, 255, 255))],
    "viridis": [(0, (68, 1, 84)), (0.25, (59, 82, 139)), (0.5, (33, 145, 140)), (0.75, (94, 201, 98)),
                (1, (253, 231, 37))],
    "frio": [(0, (40, 60, 200)), (0.5, (235, 235, 235)), (1, (200, 40, 30))],
}


def colormap(name: str) -> list[int]:
    pts = _CMAP_POINTS.get(name, _CMAP_POINTS["gris"])
    xs = np.array([p[0] for p in pts])
    cols = np.array([p[1] for p in pts], dtype=float)
    t = np.linspace(0, 1, 256)
    rgb = np.stack([np.interp(t, xs, cols[:, k]) for k in range(3)], 1).astype(int)
    return [0xFF000000 | (r << 16) | (g << 8) | b for r, g, b in rgb]


def zscale(a: np.ndarray, n_samples: int = 1000, contrast: float = 0.25, max_reject: float = 0.5,
           krej: float = 2.5, max_iter: int = 5) -> tuple[float, float]:
    """Límites ZScale (IRAF/DS9): recta ajustada a los valores ordenados de una muestra, con rechazo iterativo."""
    v = a[np.isfinite(a)].ravel()
    if v.size == 0:
        return 0.0, 1.0
    stride = max(1, v.size // n_samples)
    s = np.sort(v[::stride])
    n = s.size
    lo, hi = float(s[0]), float(s[-1])
    if n < 5:
        return lo, hi
    center = (n - 1) // 2
    med = float(np.median(s))
    x = np.arange(n, dtype=float)
    good = np.ones(n, bool)
    min_pix = max(5, int(n * (1 - max_reject)))
    slope = 0.0
    for _ in range(max_iter):
        if good.sum() < min_pix:
            break
        A = np.vstack([x[good], np.ones(good.sum())]).T
        slope, icpt = np.linalg.lstsq(A, s[good], rcond=None)[0]
        resid = s - (slope * x + icpt)
        sd = float(np.std(resid[good])) or 1e-12
        new = np.abs(resid) < krej * sd
        if new.sum() == good.sum():
            break
        good = new
    if good.sum() < min_pix or contrast <= 0:
        return lo, hi
    slope /= contrast
    z1 = max(lo, med - (center - 1) * slope)
    z2 = min(hi, med + (n - center) * slope)
    return (z1, z2) if z2 > z1 else (lo, hi)


def limits(a: np.ndarray, mode: str) -> tuple[float, float]:
    v = a[np.isfinite(a)]
    if v.size == 0:
        return 0.0, 1.0
    if mode == "zscale":
        return zscale(a)
    if mode.startswith("p"):
        q = {"p995": 99.5, "p99": 99.0, "p95": 95.0}.get(mode, 99.5)
        sub = v.ravel()[:: max(1, v.size // 400000)]
        lo, hi = np.percentile(sub, [100 - q, q])
        return float(lo), float(hi)
    return float(v.min()), float(v.max())


def stretch(a: np.ndarray, lo: float, hi: float, kind: str) -> np.ndarray:
    """Valores escalados a 0–255 (uint8)."""
    span = hi - lo if hi > lo else 1.0
    t = np.clip((np.nan_to_num(a, nan=lo) - lo) / span, 0, 1)
    if kind == "log":
        t = np.log10(1 + 1000 * t) / 3.0
    elif kind == "raiz":
        t = np.sqrt(t)
    elif kind == "asinh":
        t = np.arcsinh(10 * t) / math.asinh(10)
    elif kind == "histeq":
        sub = t.ravel()[:: max(1, t.size // 400000)]
        hist, edges = np.histogram(sub, bins=1024, range=(0, 1))
        cdf = np.cumsum(hist).astype(float)
        cdf /= cdf[-1] if cdf[-1] else 1
        t = np.interp(t, edges[1:], cdf)
    return (t * 255 + 0.5).astype(np.uint8)


class ImageView(QWidget):
    hovered = Signal(int, int, float)  # columna, fila (desde 0) y valor; -1 si fuera
    left = Signal()
    region = Signal(int, int, int, int)  # x0, y0, x1, y1 (incluidos)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 260)
        self.setFocusPolicy(Qt.StrongFocus)
        self.data: Optional[np.ndarray] = None
        self.stretch_kind = "lineal"
        self.limit_mode = "zscale"
        self.cmap = "gris"
        self.lo, self.hi = 0.0, 1.0
        self.img: Optional[QImage] = None
        self._buf = None
        self.zoom = 1.0
        self.center = QPointF(0, 0)  # en píxeles de la imagen
        self._drag = None
        self._sel = None  # QRectF en píxeles de la imagen
        self._sel_start = None
        self.marker: Optional[tuple[float, float]] = None
        self.marker_label = ""

    # ---------------------------------------------------------------- datos
    def set_data(self, a: Optional[np.ndarray], keep_view: bool = False):
        self.data = None if a is None else np.asarray(a, dtype=np.float32)
        if self.data is not None and self.data.ndim != 2:
            raise ValueError("se espera una imagen 2D")
        if not keep_view:
            self._sel = None
        self._render(fit=not keep_view)

    def set_display(self, stretch_kind: Optional[str] = None, limit_mode: Optional[str] = None, cmap: Optional[str] = None,
                    lo: Optional[float] = None, hi: Optional[float] = None):
        if stretch_kind:
            self.stretch_kind = stretch_kind
        if limit_mode:
            self.limit_mode = limit_mode
        if cmap:
            self.cmap = cmap
        self._render(fit=False, manual=(lo, hi) if lo is not None and hi is not None else None)

    def set_marker(self, col: Optional[float], row: Optional[float] = None, text: str = ""):
        self.marker = None if col is None else (col, row)
        self.marker_label = text
        self.update()

    def _render(self, fit: bool, manual=None):
        if self.data is None:
            self.img = None
            self.update()
            return
        self.lo, self.hi = manual if manual else limits(self.data, self.limit_mode)
        u8 = np.ascontiguousarray(stretch(self.data, self.lo, self.hi, self.stretch_kind))
        h, w = u8.shape
        self._buf = u8
        img = QImage(u8.data, w, h, w, QImage.Format_Indexed8)
        img.setColorTable(colormap(self.cmap))
        self.img = img
        if fit:
            self.fit()
        self.update()

    def fit(self):
        if self.data is None:
            return
        h, w = self.data.shape
        self.zoom = max(1e-3, min(self.width() / w, self.height() / h))
        self.center = QPointF(w / 2, h / 2)
        self.update()

    def set_zoom(self, z: float, anchor: Optional[QPointF] = None):
        z = max(0.02, min(64.0, z))
        if anchor is not None:
            before = self.to_image(anchor)
            self.zoom = z
            after = self.to_image(anchor)
            self.center += before - after
        else:
            self.zoom = z
        self.update()

    def center_on(self, col: float, row: float, zoom: Optional[float] = None):
        if zoom:
            self.zoom = zoom
        self.center = QPointF(col + 0.5, row + 0.5)
        self.update()

    # ------------------------------------------------------- coordenadas
    def to_image(self, p: QPointF) -> QPointF:
        return QPointF((p.x() - self.width() / 2) / self.zoom + self.center.x(),
                       (p.y() - self.height() / 2) / self.zoom + self.center.y())

    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF((x - self.center.x()) * self.zoom + self.width() / 2,
                       (y - self.center.y()) * self.zoom + self.height() / 2)

    # ------------------------------------------------------------ dibujo
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.pal.get("preview", "#000")))
        if self.img is None:
            p.setPen(QColor(theme.pal.get("muted", "#888")))
            p.drawText(self.rect(), Qt.AlignCenter, tr("Abre una imagen para verla aquí"))
            p.end()
            return
        h, w = self.data.shape
        tl = self.to_screen(0, 0)
        target = QRectF(tl.x(), tl.y(), w * self.zoom, h * self.zoom)
        p.setRenderHint(QPainter.SmoothPixmapTransform, self.zoom < 1)
        p.drawImage(target, self.img)
        if self._sel is not None:
            a = self.to_screen(self._sel.left(), self._sel.top())
            b = self.to_screen(self._sel.right(), self._sel.bottom())
            p.setPen(QPen(QColor("#33E07A"), 1.6, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(a, b))
        if self.marker is not None:
            c = self.to_screen(self.marker[0] + 0.5, self.marker[1] + 0.5)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QPen(QColor("#FF3B30"), 2))
            p.drawEllipse(c, 9, 9)
            p.drawLine(QPointF(c.x() - 16, c.y()), QPointF(c.x() - 5, c.y()))
            p.drawLine(QPointF(c.x() + 5, c.y()), QPointF(c.x() + 16, c.y()))
            p.drawLine(QPointF(c.x(), c.y() - 16), QPointF(c.x(), c.y() - 5))
            p.drawLine(QPointF(c.x(), c.y() + 5), QPointF(c.x(), c.y() + 16))
            if self.marker_label:
                p.setPen(QColor("#FFFFFF"))
                p.drawText(QPointF(c.x() + 14, c.y() - 12), self.marker_label)
        p.end()

    # ------------------------------------------------------------- ratón
    def wheelEvent(self, ev):
        if self.data is None:
            return
        k = 1.25 if ev.angleDelta().y() > 0 else 1 / 1.25
        self.set_zoom(self.zoom * k, ev.position())

    def mousePressEvent(self, ev):
        if self.data is None:
            return
        if ev.button() == Qt.RightButton or (ev.button() == Qt.LeftButton and ev.modifiers() & Qt.ShiftModifier):
            q = self.to_image(ev.position())
            self._sel_start = QPointF(math.floor(q.x()), math.floor(q.y()))
            self._sel = QRectF(self._sel_start, self._sel_start + QPointF(1, 1))
            self.update()
        elif ev.button() == Qt.LeftButton:
            self._drag = (ev.position(), QPointF(self.center))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, ev):
        if self.data is None:
            return
        if self._drag is not None:
            start, c0 = self._drag
            d = ev.position() - start
            self.center = c0 - QPointF(d.x() / self.zoom, d.y() / self.zoom)
            self.update()
        elif self._sel_start is not None:
            q = self.to_image(ev.position())
            x0, y0 = self._sel_start.x(), self._sel_start.y()
            x1, y1 = math.floor(q.x()), math.floor(q.y())
            self._sel = QRectF(QPointF(min(x0, x1), min(y0, y1)), QPointF(max(x0, x1) + 1, max(y0, y1) + 1))
            self.update()
        q = self.to_image(ev.position())
        c, r = int(math.floor(q.x())), int(math.floor(q.y()))
        h, w = self.data.shape
        if 0 <= c < w and 0 <= r < h:
            self.hovered.emit(c, r, float(self.data[r, c]))
        else:
            self.hovered.emit(-1, -1, float("nan"))

    def mouseReleaseEvent(self, ev):
        if self._drag is not None:
            self._drag = None
            self.unsetCursor()
        if self._sel_start is not None:
            self._sel_start = None
            self.emit_region()

    def emit_region(self):
        if self._sel is None or self.data is None:
            return
        h, w = self.data.shape
        x0 = int(max(0, self._sel.left()))
        y0 = int(max(0, self._sel.top()))
        x1 = int(min(w, self._sel.right())) - 1
        y1 = int(min(h, self._sel.bottom())) - 1
        if x1 >= x0 and y1 >= y0:
            self.region.emit(x0, y0, x1, y1)

    def set_region(self, x0: int, y0: int, x1: int, y1: int):
        self._sel = QRectF(QPointF(x0, y0), QPointF(x1 + 1, y1 + 1))
        self.update()
        self.emit_region()

    def leaveEvent(self, ev):
        self.left.emit()
        super().leaveEvent(ev)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.data is not None and ev.oldSize().width() <= 0:
            self.fit()
