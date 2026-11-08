# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Animaciones del modo educativo (dibujadas con QPainter, sin archivos externos).

* :class:`TwinkleAnim`: la moneda en la piscina y la estrella que titila al cruzar la atmósfera.
* :class:`DimmAnim`: la máscara de dos huequitos, los dos caminos de luz y los dos puntos que bailan.

Los movimientos usan sumas de senos (suaves y repetibles) en vez de ruido al azar. Las animaciones
solo corren mientras se ven en pantalla.
"""

from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..i18n import num, tr
from .theme import theme


def wobble(t: float, seed: float, speed: float = 1.0) -> float:
    """Ruido suave entre −1 y 1 hecho con senos de frecuencias inconmensurables."""
    s = seed * 12.9898
    return (math.sin(t * 1.7 * speed + s) * 0.5 + math.sin(t * 2.9 * speed + 1.3 * s) * 0.3
            + math.sin(t * 5.3 * speed + 2.1 * s) * 0.2)


class _Animated(QWidget):
    def __init__(self, min_h: int = 260):
        super().__init__()
        self.setMinimumHeight(min_h)
        self.level = 0.5  # 0 = quieto, 1 = muy turbulento
        self.t0 = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.update)

    def set_level(self, v: float):
        self.level = max(0.0, min(1.0, v))
        self.update()

    def now(self) -> float:
        return time.monotonic() - self.t0

    def showEvent(self, ev):
        super().showEvent(ev)
        self.timer.start()

    def hideEvent(self, ev):
        self.timer.stop()
        super().hideEvent(ev)

    def _caption(self, p: QPainter, rect: QRectF, text: str):
        f = QFont(p.font())
        f.setPointSizeF(9.5)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#E8EAEE"))
        p.drawText(rect.adjusted(10, 6, -10, 0), Qt.AlignLeft | Qt.AlignTop, tr(text))

    def _star(self, p: QPainter, c: QPointF, r: float, bright: float = 1.0):
        g = QRadialGradient(c, r)
        a = int(255 * max(0.15, min(1.0, bright)))
        g.setColorAt(0, QColor(255, 255, 255, a))
        g.setColorAt(0.3, QColor(255, 244, 214, int(a * 0.8)))
        g.setColorAt(1, QColor(255, 220, 170, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, r, r)


class TwinkleAnim(_Animated):
    """Izquierda: moneda en el fondo de una piscina. Derecha: la luz de una estrella cruzando burbujas de aire."""

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        gap = 12
        half = (W - gap) / 2
        left = QRectF(0, 0, half, H)
        right = QRectF(half + gap, 0, half, H)
        t = self.now()
        self._pool(p, left, t)
        self._sky(p, right, t)
        p.end()

    def _pool(self, p: QPainter, r: QRectF, t: float):
        L = self.level
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        p.fillRect(r, QColor("#202B33"))
        surf = r.top() + r.height() * 0.30
        # agua
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#2E8CA8"))
        g.setColorAt(1, QColor("#0F3F55"))
        wave = QPainterPath()
        wave.moveTo(r.left(), r.bottom())
        n = 60
        amp = 2 + 10 * L
        for i in range(n + 1):
            x = r.left() + r.width() * i / n
            y = surf + amp * math.sin(x / 26 + t * (1.5 + 3 * L)) + amp * 0.5 * math.sin(x / 11 - t * 2.3)
            wave.lineTo(x, y)
        wave.lineTo(r.right(), r.bottom())
        wave.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawPath(wave)
        # fondo de baldosas
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        for k in range(1, 8):
            x = r.left() + r.width() * k / 8
            p.drawLine(QPointF(x, r.bottom() - r.height() * 0.22), QPointF(x, r.bottom()))
        p.drawLine(QPointF(r.left(), r.bottom() - r.height() * 0.22), QPointF(r.right(), r.bottom() - r.height() * 0.22))
        # moneda vista a través del agua: se desplaza y se deforma
        cx, cy = r.center().x(), r.bottom() - r.height() * 0.13
        dx = 14 * L * wobble(t, 1.0, 1 + 2 * L)
        dy = 5 * L * wobble(t, 2.0, 1 + 2 * L)
        sx = 1 + 0.25 * L * wobble(t, 3.0, 1.5)
        rad = min(r.width(), r.height()) * 0.09
        for k, a in ((2, 50), (1, 90), (0, 255)):  # copias tenues = borroso
            o = k * 3 * L
            p.setBrush(QColor(232, 186, 64, a))
            p.setPen(QPen(QColor(150, 110, 20, a), 2))
            p.drawEllipse(QPointF(cx + dx + o, cy + dy), rad * sx, rad * 0.55 / sx)
        # ojo arriba
        ex, ey = r.center().x(), r.top() + r.height() * 0.13
        p.setPen(QPen(QColor(255, 255, 255, 160), 1.4, Qt.DashLine))
        p.drawLine(QPointF(ex, ey + 8), QPointF(cx + dx, cy + dy - rad * 0.5))
        p.setPen(QPen(QColor("#E8EAEE"), 2))
        p.setBrush(QColor("#E8EAEE"))
        p.drawEllipse(QPointF(ex, ey), 9, 5)
        p.setBrush(QColor("#202B33"))
        p.drawEllipse(QPointF(ex, ey), 3, 3)
        p.setClipping(False)
        self._caption(p, r, "Una moneda en una piscina")

    def _sky(self, p: QPainter, r: QRectF, t: float):
        L = self.level
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#05070F"))
        g.setColorAt(0.55, QColor("#14213D"))
        g.setColorAt(1, QColor("#2A3B5C"))
        p.fillRect(r, QBrush(g))
        top, bot = r.top() + r.height() * 0.30, r.top() + r.height() * 0.72
        # burbujas de aire caliente y frío que se desplazan con el viento
        speed = 10 + 60 * L
        for i in range(14):
            bx = r.left() + ((i * 53.7 + t * speed * (0.6 + 0.08 * (i % 5))) % (r.width() + 80)) - 40
            by = top + (bot - top) * ((i * 0.37) % 1.0)
            br = 16 + (i * 7) % 22
            warm = i % 2 == 0
            c = QColor(255, 140, 90, int(18 + 40 * L)) if warm else QColor(110, 170, 255, int(18 + 40 * L))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(bx, by), br, br * 0.7)
        # estrella real (lejana) y rayo de luz que se desvía en la capa turbulenta
        sx, sy = r.center().x(), r.top() + r.height() * 0.15
        self._star(p, QPointF(sx, sy), 7)
        ox, oy = r.center().x(), r.bottom() - r.height() * 0.10
        ray = QPainterPath(QPointF(sx, sy))
        steps = 24
        dev = 0.0
        for k in range(1, steps + 1):
            y = sy + (oy - sy) * k / steps
            if top < y < bot:
                dev += 2.2 * L * wobble(t * (1 + L), k * 0.7, 1.8)
            ray.lineTo(sx + dev, y)
        p.setPen(QPen(QColor(255, 236, 190, 170), 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawPath(ray)
        # observador (telescopio sencillo)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#C9CED8"))
        p.drawRoundedRect(QRectF(ox - 10, oy - 6, 20, 26), 3, 3)
        # lo que ve el observador: la estrella baila y cambia de brillo
        ix, iy = r.right() - 60, r.bottom() - 62
        box = QRectF(ix - 44, iy - 44, 88, 88)
        p.setBrush(QColor("#000000"))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawRoundedRect(box, 8, 8)
        jx = 14 * L * wobble(t, 5.0, 2 + 3 * L)
        jy = 14 * L * wobble(t, 6.0, 2 + 3 * L)
        bright = 1 - 0.65 * L * (0.5 + 0.5 * wobble(t, 7.0, 4 + 6 * L))
        self._star(p, QPointF(ix + jx, iy + jy), 10 + 10 * L, bright)
        f = QFont(p.font())
        f.setPointSizeF(8)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#AEB4C0"))
        p.drawText(QRectF(box.left() - 30, box.top() - 18, box.width() + 30, 16), Qt.AlignRight, tr("Lo que vemos"))
        p.drawText(QRectF(r.left() + 10, top - 18, r.width() - 20, 16), Qt.AlignLeft, tr("Aire en movimiento"))
        p.setClipping(False)
        self._caption(p, r, "La luz de una estrella cruza el aire")


class DimmAnim(_Animated):
    """La máscara con dos huequitos (izquierda) y los dos puntos que se ven en la cámara (derecha)."""

    def __init__(self, min_h: int = 260):
        super().__init__(min_h)
        self.shake = False

    def set_shake(self, on: bool):
        self.shake = bool(on)
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        gap = 12
        half = (W - gap) / 2
        t = self.now()
        L = self.level
        # movimiento común (temblor) y diferencial (turbulencia en cada camino)
        cx = (18 * wobble(t, 11.0, 3.0) if self.shake else 0.0)
        cy = (12 * wobble(t, 12.0, 3.4) if self.shake else 0.0)
        d1 = (9 * L * wobble(t, 1.0, 2 + 2 * L), 9 * L * wobble(t, 2.0, 2 + 2 * L))
        d2 = (9 * L * wobble(t, 3.0, 2 + 2 * L), 9 * L * wobble(t, 4.0, 2 + 2 * L))
        self._mask(p, QRectF(0, 0, half, H), t, d1, d2)
        self._camera(p, QRectF(half + gap, 0, half, H), (cx + d1[0], cy + d1[1]), (cx + d2[0], cy + d2[1]))
        p.end()

    def _mask(self, p: QPainter, r: QRectF, t: float, d1, d2):
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        p.fillRect(r, QColor("#0B1020"))
        L = self.level
        # turbulencia que pasa por encima
        for i in range(10):
            bx = r.left() + ((i * 61.3 + t * (12 + 50 * L)) % (r.width() + 60)) - 30
            by = r.top() + r.height() * (0.22 + 0.18 * ((i * 0.41) % 1.0))
            c = QColor(255, 140, 90, int(14 + 40 * L)) if i % 2 else QColor(110, 170, 255, int(14 + 40 * L))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(bx, by), 20, 13)
        # tubo del telescopio visto de frente con la máscara
        c = QPointF(r.center().x(), r.top() + r.height() * 0.66)
        R = min(r.width(), r.height()) * 0.27
        p.setBrush(QColor("#2B2F3A"))
        p.setPen(QPen(QColor("#8A90A0"), 3))
        p.drawEllipse(c, R, R)
        hole = R * 0.22
        h1 = QPointF(c.x() - R * 0.55, c.y())
        h2 = QPointF(c.x() + R * 0.55, c.y())
        # rayos de luz que bajan hacia cada huequito, cada uno con su desvío
        for h, d in ((h1, d1), (h2, d2)):
            top = QPointF(h.x(), r.top() + 24)
            mid = QPointF(h.x() + d[0] * 1.6, r.top() + r.height() * 0.32)
            ray = QPainterPath(top)
            ray.quadTo(mid, h)
            p.setPen(QPen(QColor(255, 236, 190, 160), 2.2))
            p.setBrush(Qt.NoBrush)
            p.drawPath(ray)
        p.setPen(QPen(QColor("#D0D4DC"), 1.5))
        p.setBrush(QColor("#000000"))
        p.drawEllipse(h1, hole, hole)
        p.drawEllipse(h2, hole, hole)
        f = QFont(p.font())
        f.setPointSizeF(8)
        p.setFont(f)
        p.setPen(QColor("#AEB4C0"))
        p.drawText(QRectF(r.left(), c.y() + R + 4, r.width(), 16), Qt.AlignHCenter, tr("Máscara con dos huequitos"))
        p.setClipping(False)
        self._caption(p, r, "La luz entra por dos caminos")

    def _camera(self, p: QPainter, r: QRectF, o1, o2):
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        p.fillRect(r, QColor("#000000"))
        c = r.center()
        sep = r.width() * 0.32
        a = QPointF(c.x() - sep / 2 + o1[0], c.y() + o1[1])
        b = QPointF(c.x() + sep / 2 + o2[0], c.y() + o2[1])
        # posiciones de referencia
        p.setPen(QPen(QColor(255, 255, 255, 40), 1, Qt.DotLine))
        p.drawLine(QPointF(c.x() - sep / 2, r.top() + 30), QPointF(c.x() - sep / 2, r.bottom() - 40))
        p.drawLine(QPointF(c.x() + sep / 2, r.top() + 30), QPointF(c.x() + sep / 2, r.bottom() - 40))
        rr = 12 + 8 * self.level
        self._star(p, a, rr)
        self._star(p, b, rr)
        p.setPen(QPen(QColor(theme.pal.get("accent", "#F28C28")), 2, Qt.DashLine))
        p.drawLine(a, b)
        d = math.hypot(b.x() - a.x(), b.y() - a.y())
        d0 = sep
        f = QFont(p.font())
        f.setPointSizeF(9)
        p.setFont(f)
        p.setPen(QColor("#E8EAEE"))
        p.drawText(QRectF(r.left() + 10, r.bottom() - 34, r.width() - 20, 18), Qt.AlignLeft,
                   tr("Distancia entre los puntos: {} px").format(num(d, 1)))
        p.setPen(QColor("#AEB4C0"))
        p.drawText(QRectF(r.left() + 10, r.bottom() - 18, r.width() - 20, 16), Qt.AlignLeft,
                   tr("Cambio por la turbulencia: {} px").format(("+" if d - d0 >= 0 else "−") + num(abs(d - d0), 1)))
        p.setClipping(False)
        self._caption(p, r, "Lo que ve la cámara")
