# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Lienzo de la región (como en Paint) y línea de tiempo del tramo."""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import theme


def to_qimage(arr: np.ndarray, stretch: bool = True) -> QImage:
    a = np.asarray(arr)
    if a.dtype != np.uint8 or stretch:
        f = a.astype(np.float32)
        sub = f[:: max(1, f.shape[0] // 270), :: max(1, f.shape[1] // 480)]
        lo = float(np.percentile(sub, 1))
        hi = float(max(np.percentile(sub, 99.95), f.max() * 0.9, lo + 1))
        f = np.clip((f - lo) / (hi - lo), 0, 1) ** 0.6
        a = (f * 255).astype(np.uint8)
    a = np.ascontiguousarray(a)
    h, w = a.shape
    img = QImage(a.data, w, h, w, QImage.Format_Grayscale8)
    return img.copy()


def fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    m = int(sec // 60)
    s = sec - 60 * m
    return f"{m:02d}:{s:04.1f}"


class RoiCanvas(QWidget):
    """Muestra un cuadro del video y permite dibujar/mover/redimensionar la región.

    * Arrastrar en un área vacía: dibuja una región nueva.
    * Arrastrar desde adentro: mueve la región.
    * Arrastrar uno de los 8 cuadritos: cambia el tamaño.
    * Clic simple: centra la región en ese punto.
    * Rueda del ratón: zoom. Botón derecho arrastrando: desplaza la vista.
    * Teclado: flechas mueven 1 px; Mayús + flechas cambian el tamaño.
    """

    roi_changed = Signal(tuple)

    HANDLE = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(420, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.img: Optional[QImage] = None
        self.W = self.H = 1
        self.roi = (0, 0, 64, 64)
        self.track_roi: Optional[tuple] = None
        self.zoom = 4.0
        self.center = None  # centro de la vista en coordenadas de la imagen
        self.overlay = ""
        self._drag = None
        self._pan = None
        self.setAccessibleName("Lienzo de la región de la estrella")

    def sizeHint(self):
        return QSize(800, 450)

    # ------------------------------------------------------------ datos
    def set_frame(self, arr: Optional[np.ndarray]):
        if arr is None:
            self.img = None
        else:
            self.img = to_qimage(arr)
            self.H, self.W = arr.shape[:2]
        if self.center is None:
            x, y, w, h = self.roi
            self.center = (x + w / 2, y + h / 2)
        self.update()

    def set_roi(self, roi: tuple, recenter: bool = False):
        self.roi = tuple(int(v) for v in roi)
        if recenter or self.center is None:
            x, y, w, h = self.roi
            self.center = (x + w / 2, y + h / 2)
        self.update()

    def set_zoom(self, z: float):
        self.zoom = float(max(1.0, min(32.0, z)))
        x, y, w, h = self.roi
        self.center = (x + w / 2, y + h / 2)
        self.update()

    # ------------------------------------------------------- transformación
    def _scale(self) -> float:
        if self.W <= 0 or self.H <= 0:
            return 1.0
        fit = min(self.width() / self.W, self.height() / self.H)
        return fit * self.zoom

    def _clamp_center(self):
        s = self._scale()
        vw, vh = self.width() / s, self.height() / s
        cx, cy = self.center or (self.W / 2, self.H / 2)
        cx = min(max(cx, vw / 2), self.W - vw / 2) if vw < self.W else self.W / 2
        cy = min(max(cy, vh / 2), self.H - vh / 2) if vh < self.H else self.H / 2
        self.center = (cx, cy)

    def to_widget(self, x: float, y: float) -> QPointF:
        s = self._scale()
        cx, cy = self.center
        return QPointF((x - cx) * s + self.width() / 2, (y - cy) * s + self.height() / 2)

    def to_image(self, p: QPointF) -> tuple[float, float]:
        s = self._scale()
        cx, cy = self.center
        return ((p.x() - self.width() / 2) / s + cx, (p.y() - self.height() / 2) / s + cy)

    def _roi_rect_w(self) -> QRectF:
        x, y, w, h = self.roi
        return QRectF(self.to_widget(x, y), self.to_widget(x + w, y + h))

    def _clamp_roi(self, x, y, w, h):
        w = int(round(max(16, min(w, self.W))))
        h = int(round(max(16, min(h, self.H))))
        x = int(round(min(max(x, 0), self.W - w)))
        y = int(round(min(max(y, 0), self.H - h)))
        return (x, y, w, h)

    def _hit(self, p: QPointF) -> str:
        r = self._roi_rect_w()
        tol = self.HANDLE
        xs = {"w": r.left(), "c": r.center().x(), "e": r.right()}
        ys = {"n": r.top(), "c": r.center().y(), "s": r.bottom()}
        for ky, yv in ys.items():
            for kx, xv in xs.items():
                if kx == "c" and ky == "c":
                    continue
                if abs(p.x() - xv) <= tol and abs(p.y() - yv) <= tol:
                    return (ky if ky != "c" else "") + (kx if kx != "c" else "")
        if r.contains(p):
            return "move"
        return "new"

    CURSORS = {"n": Qt.SizeVerCursor, "s": Qt.SizeVerCursor, "e": Qt.SizeHorCursor, "w": Qt.SizeHorCursor,
               "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor, "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor,
               "move": Qt.SizeAllCursor, "new": Qt.CrossCursor}

    # ------------------------------------------------------------ eventos
    def mousePressEvent(self, ev):
        if self.img is None:
            return
        self._clamp_center()
        if ev.button() in (Qt.RightButton, Qt.MiddleButton):
            self._pan = (ev.position(), self.center)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if ev.button() != Qt.LeftButton:
            return
        kind = self._hit(ev.position())
        ix, iy = self.to_image(ev.position())
        self._drag = {"kind": kind, "sx": ix, "sy": iy, "r0": self.roi, "moved": False}

    def mouseMoveEvent(self, ev):
        if self.img is None:
            return
        if self._pan is not None:
            p0, c0 = self._pan
            s = self._scale()
            d = ev.position() - p0
            self.center = (c0[0] - d.x() / s, c0[1] - d.y() / s)
            self._clamp_center()
            self.update()
            return
        if self._drag is None:
            self.setCursor(self.CURSORS[self._hit(ev.position())])
            return
        d = self._drag
        ix, iy = self.to_image(ev.position())
        dx, dy = ix - d["sx"], iy - d["sy"]
        if abs(dx) * self._scale() > 3 or abs(dy) * self._scale() > 3:
            d["moved"] = True
        if not d["moved"]:
            return
        x, y, w, h = d["r0"]
        k = d["kind"]
        if k == "move":
            self.roi = self._clamp_roi(x + dx, y + dy, w, h)
        else:
            x1, y1, x2, y2 = x, y, x + w, y + h
            if k == "new":
                x1, y1, x2, y2 = d["sx"], d["sy"], ix, iy
            else:
                if "n" in k:
                    y1 += dy
                if "s" in k:
                    y2 += dy
                if "w" in k:
                    x1 += dx
                if "e" in k:
                    x2 += dx
            self.roi = self._clamp_roi(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        self.update()
        self.roi_changed.emit(self.roi)

    def mouseReleaseEvent(self, ev):
        if self._pan is not None:
            self._pan = None
            self.setCursor(Qt.CrossCursor)
            return
        d = self._drag
        self._drag = None
        if d is None:
            return
        if not d["moved"]:
            x, y, w, h = d["r0"]
            self.roi = self._clamp_roi(d["sx"] - w / 2, d["sy"] - h / 2, w, h)
            self.update()
            self.roi_changed.emit(self.roi)

    def wheelEvent(self, ev):
        if self.img is None:
            return
        before = self.to_image(ev.position())
        f = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.zoom = float(max(1.0, min(32.0, self.zoom * f)))
        after = self.to_image(ev.position())
        cx, cy = self.center
        self.center = (cx + before[0] - after[0], cy + before[1] - after[1])
        self._clamp_center()
        self.update()

    def keyPressEvent(self, ev):
        m = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}.get(ev.key())
        if m is None:
            return super().keyPressEvent(ev)
        x, y, w, h = self.roi
        if ev.modifiers() & Qt.ShiftModifier:
            self.roi = self._clamp_roi(x - m[0], y - m[1], w + 2 * m[0], h + 2 * m[1])
        else:
            self.roi = self._clamp_roi(x + m[0], y + m[1], w, h)
        self.update()
        self.roi_changed.emit(self.roi)

    # ------------------------------------------------------------ dibujo
    def paintEvent(self, ev):
        pal = theme.pal
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal["preview"]))
        if self.img is None:
            p.setPen(QColor(pal["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Carga un video para ver la imagen")
            p.end()
            return
        self._clamp_center()
        s = self._scale()
        tl = self.to_widget(0, 0)
        target = QRectF(tl.x(), tl.y(), self.W * s, self.H * s)
        p.setRenderHint(QPainter.SmoothPixmapTransform, s < 2.5)
        p.drawImage(target, self.img)
        p.setRenderHint(QPainter.Antialiasing, True)

        acc = QColor(pal["accent"])
        r = self._roi_rect_w()
        # Oscurecer lo que queda fuera de la región.
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        inner = QPainterPath()
        inner.addRect(r)
        p.fillPath(outside.subtracted(inner), QColor(0, 0, 0, 90))

        if self.track_roi is not None:
            tx, ty, tw, th = self.track_roi
            tr = QRectF(self.to_widget(tx, ty), self.to_widget(tx + tw, ty + th))
            pen = QPen(QColor(pal["accent2"]), 1.5, Qt.DotLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(tr)

        pen = QPen(acc, 2, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        hs = self.HANDLE
        p.setPen(QPen(acc, 2))
        p.setBrush(QBrush(QColor("#FFFFFF")))
        for hx in (r.left(), r.center().x(), r.right()):
            for hy in (r.top(), r.center().y(), r.bottom()):
                if hx == r.center().x() and hy == r.center().y():
                    continue
                p.drawRect(QRectF(hx - hs / 2, hy - hs / 2, hs, hs))
        # Etiqueta de tamaño
        tag = f"{self.roi[2]} × {self.roi[3]} px"
        f = QFont(self.font())
        f.setPointSizeF(9)
        p.setFont(f)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(tag) + 12
        ty = r.bottom() + 6 if r.bottom() + 26 < self.height() else r.top() - 24
        p.setPen(Qt.NoPen)
        p.setBrush(acc)
        p.drawRoundedRect(QRectF(r.left(), ty, tw, 20), 4, 4)
        p.setPen(QColor(pal["onAccent"]))
        p.drawText(QRectF(r.left(), ty, tw, 20), Qt.AlignCenter, tag)
        if self.overlay:
            p.setPen(QColor("#D8DAE0"))
            p.drawText(QRectF(10, 6, self.width() - 20, 22), Qt.AlignLeft | Qt.AlignVCenter, self.overlay)
        p.end()


class Timeline(QWidget):
    """Línea de tiempo: arrastra Entrada y Salida; clic para mover la vista previa."""

    frame_changed = Signal(int)
    range_changed = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.n = 1
        self.fps = 30.0
        self.tin = 0
        self.tout = 0
        self.frame = 0
        self._drag = None
        self.setMinimumHeight(46)
        self.setMaximumHeight(52)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Línea de tiempo del tramo")

    def set_video(self, n: int, fps: float):
        self.n = max(1, n)
        self.fps = fps
        self.update()

    def set_state(self, tin: int, tout: int, frame: int):
        self.tin, self.tout, self.frame = tin, tout, frame
        self.update()

    def _bar(self) -> QRectF:
        return QRectF(8, 4, self.width() - 16, self.height() - 22)

    def _x(self, f: int) -> float:
        b = self._bar()
        return b.left() + f / max(1, self.n - 1) * b.width()

    def _f(self, x: float) -> int:
        b = self._bar()
        return int(round(min(max((x - b.left()) / max(1, b.width()), 0), 1) * (self.n - 1)))

    def mousePressEvent(self, ev):
        x = ev.position().x()
        tol = 9
        if abs(x - self._x(self.tin)) <= tol:
            self._drag = "tin"
        elif abs(x - self._x(self.tout)) <= tol:
            self._drag = "tout"
        else:
            self._drag = "head"
        self._apply(x)

    def mouseMoveEvent(self, ev):
        x = ev.position().x()
        if self._drag:
            self._apply(x)
        else:
            near = abs(x - self._x(self.tin)) <= 9 or abs(x - self._x(self.tout)) <= 9
            self.setCursor(Qt.SizeHorCursor if near else Qt.PointingHandCursor)

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def _apply(self, x: float):
        f = self._f(x)
        if self._drag == "tin":
            self.tin = min(f, self.tout - 1)
            self.frame = self.tin
            self.range_changed.emit(self.tin, self.tout)
        elif self._drag == "tout":
            self.tout = max(f, self.tin + 1)
            self.frame = self.tout
            self.range_changed.emit(self.tin, self.tout)
        else:
            self.frame = f
        self.frame_changed.emit(self.frame)
        self.update()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Left, Qt.Key_Right):
            step = int(self.fps) if ev.modifiers() & Qt.ShiftModifier else 1
            self.frame = int(min(max(self.frame + (step if ev.key() == Qt.Key_Right else -step), 0), self.n - 1))
            self.frame_changed.emit(self.frame)
            self.update()
        else:
            super().keyPressEvent(ev)

    def paintEvent(self, ev):
        pal = theme.pal
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        b = self._bar()
        p.setPen(QPen(QColor(pal["border"]), 1))
        p.setBrush(QColor(pal["panel2"]))
        p.drawRoundedRect(b, 6, 6)
        sel = QRectF(QPointF(self._x(self.tin), b.top()), QPointF(self._x(self.tout), b.bottom()))
        c = QColor(pal["accent"])
        c.setAlphaF(0.22)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRect(sel)
        p.setBrush(QColor(pal["accent"]))
        for f in (self.tin, self.tout):
            x = self._x(f)
            p.drawRoundedRect(QRectF(x - 3, b.top() - 2, 6, b.height() + 4), 3, 3)
        p.setPen(QPen(QColor(pal["text"]), 2))
        x = self._x(self.frame)
        p.drawLine(QPointF(x, b.top() - 3), QPointF(x, b.bottom() + 3))
        p.setPen(QColor(pal["muted"]))
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        dur = (self.n - 1) / self.fps if self.fps else 0
        for i in range(5):
            frac = i / 4
            xx = b.left() + frac * b.width()
            al = Qt.AlignLeft if i == 0 else (Qt.AlignRight if i == 4 else Qt.AlignHCenter)
            r = QRectF(xx - (0 if i == 0 else (80 if i == 4 else 40)), b.bottom() + 2, 80, 16)
            p.drawText(r, al | Qt.AlignVCenter, fmt_time(frac * dur))
        p.end()
