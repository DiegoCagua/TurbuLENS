# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Animación de los centroides: muestra, cuadro a cuadro, dónde ubicó TurbuLENS cada punto."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QSizePolicy, QSlider, QVBoxLayout, QWidget

from .canvas import fmt_time, to_qimage
from .theme import theme
from .widgets import button, label


class CentroidView(QWidget):
    """Dibuja un recorte ampliado con las cruces de los dos centroides."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.img = None
        self.w = self.h = 1
        self.p1 = self.p2 = None
        self.valid = False
        self.trail1: list = []
        self.trail2: list = []
        self.show_trail = True
        self.caption = ""

    def sizeHint(self):
        return QSize(360, 360)

    def set_frame(self, crop: np.ndarray, p1, p2, valid: bool, trail1, trail2, caption: str):
        self.img = to_qimage(crop)
        self.h, self.w = crop.shape[:2]
        self.p1, self.p2, self.valid = p1, p2, valid
        self.trail1, self.trail2 = trail1, trail2
        self.caption = caption
        self.update()

    def paintEvent(self, ev):
        pal = theme.pal
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(pal["preview"]))
        if self.img is None:
            p.setPen(QColor(pal["muted"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Sin cuadros para mostrar")
            p.end()
            return
        s = min(self.width() / self.w, (self.height() - 4) / self.h)
        ox = (self.width() - self.w * s) / 2
        oy = (self.height() - self.h * s) / 2
        p.setRenderHint(QPainter.SmoothPixmapTransform, False)
        p.drawImage(QRectF(ox, oy, self.w * s, self.h * s), self.img)
        p.setRenderHint(QPainter.Antialiasing, True)

        def W(pt):  # coordenada de píxel (centro en entero) → widget
            return QPointF(ox + (pt[0] + 0.5) * s, oy + (pt[1] + 0.5) * s)

        # Rejilla de píxeles cuando el aumento es grande (para ver la precisión subpíxel)
        if s >= 10:
            pen = QPen(QColor(255, 255, 255, 22), 1)
            p.setPen(pen)
            for i in range(self.w + 1):
                p.drawLine(QPointF(ox + i * s, oy), QPointF(ox + i * s, oy + self.h * s))
            for j in range(self.h + 1):
                p.drawLine(QPointF(ox, oy + j * s), QPointF(ox + self.w * s, oy + j * s))

        c1 = QColor(pal["accent"])
        c2 = QColor(pal["accent2"])
        if self.show_trail:
            for tr, c in ((self.trail1, c1), (self.trail2, c2)):
                n = len(tr)
                for k, pt in enumerate(tr):
                    cc = QColor(c)
                    cc.setAlphaF(0.15 + 0.55 * (k + 1) / max(n, 1))
                    p.setPen(Qt.NoPen)
                    p.setBrush(cc)
                    p.drawEllipse(W(pt), 2.2, 2.2)

        if self.valid and self.p1 is not None:
            a, b = W(self.p1), W(self.p2)
            pen = QPen(QColor("#FFFFFF"), 1.5, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(a, b)
            r = max(7.0, s * 1.6)
            for pt, c in ((a, c1), (b, c2)):
                p.setPen(QPen(c, 2.2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(pt, r, r)
                p.drawLine(QPointF(pt.x() - r * 1.6, pt.y()), QPointF(pt.x() - r * 0.45, pt.y()))
                p.drawLine(QPointF(pt.x() + r * 0.45, pt.y()), QPointF(pt.x() + r * 1.6, pt.y()))
                p.drawLine(QPointF(pt.x(), pt.y() - r * 1.6), QPointF(pt.x(), pt.y() - r * 0.45))
                p.drawLine(QPointF(pt.x(), pt.y() + r * 0.45), QPointF(pt.x(), pt.y() + r * 1.6))
            d = math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])
            mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
            f = QFont(self.font())
            f.setPointSizeF(10)
            f.setBold(True)
            p.setFont(f)
            txt = f"d = {d:.2f} px".replace(".", ",")
            tw = p.fontMetrics().horizontalAdvance(txt) + 12
            box = QRectF(mid.x() + 10, mid.y() - 11, tw, 22)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(box, 5, 5)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(box, Qt.AlignCenter, txt)
        else:
            p.setPen(QColor(pal["bad"]))
            p.drawText(QRectF(0, self.height() - 30, self.width(), 24), Qt.AlignCenter,
                       "En este cuadro no se detectaron los dos puntos")
        p.setPen(QColor("#D8DAE0"))
        f = QFont(self.font())
        f.setPointSizeF(9)
        p.setFont(f)
        p.drawText(QRectF(8, 6, self.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, self.caption)
        p.end()


class CentroidPlayer(QWidget):
    """Reproductor de la animación de centroides, con controles."""

    SPEEDS = [("Lento", 6), ("Normal", 15), ("Rápido", 30), ("Muy rápido", 60)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("transparent")
        self.view = CentroidView()
        self.frames: Optional[np.ndarray] = None
        self.rows = None
        self.meas = None
        self.used = None
        self.fps_video = 30.0
        self.i = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self.view, 1)
        self.play_b = button("▶", "transport", self.toggle, checkable=True, tip="Reproducir / pausar")
        self.prev_b = button("<", "transport", lambda: self.step(-1), tip="Cuadro anterior de la muestra")
        self.next_b = button(">", "transport", lambda: self.step(1), tip="Cuadro siguiente de la muestra")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self._seek)
        self.speed = QComboBox()
        for t, v in self.SPEEDS:
            self.speed.addItem(t, v)
        self.speed.setCurrentIndex(1)
        self.speed.currentIndexChanged.connect(self._speed)
        self.trail = QCheckBox("Rastro")
        self.trail.setChecked(True)
        self.trail.toggled.connect(self._trail)
        row = QHBoxLayout()
        row.setSpacing(6)
        for w in (self.play_b, self.prev_b, self.slider, self.next_b):
            row.addWidget(w, 1 if w is self.slider else 0)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(label("Velocidad", "small"))
        row2.addWidget(self.speed)
        row2.addWidget(self.trail)
        row2.addStretch(1)
        lay.addLayout(row2)
        self.info = label("", "small")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.step(1, loop=True))
        self._speed()

    def set_data(self, frames, rows, meas, used, fps):
        self.timer.stop()
        self.play_b.setChecked(False)
        self.play_b.setText("▶")
        self.frames, self.rows, self.meas, self.used = frames, rows, meas, used
        self.fps_video = fps or 30.0
        ok = frames is not None and rows is not None and len(rows) > 0
        for w in (self.play_b, self.prev_b, self.next_b, self.slider):
            w.setEnabled(ok)
        if not ok:
            self.view.img = None
            self.view.update()
            self.info.setText("No hay cuadros guardados para animar. Vuelve a procesar el video para verlos.")
            return
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(rows) - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        step = int(np.median(np.diff(meas["frame"][rows]))) if len(rows) > 1 else 1
        self.info.setText(f"Muestra de {len(rows)} cuadros (uno de cada {max(1, step)}). Naranja: primer punto · "
                          "segundo color: segundo punto · línea: la distancia que se mide en cada cuadro.")
        self.i = 0
        self._show()

    def _speed(self):
        self.timer.setInterval(int(1000 / (self.speed.currentData() or 15)))

    def _trail(self, on):
        self.view.show_trail = on
        self.view.update()

    def toggle(self):
        if self.frames is None:
            self.play_b.setChecked(False)
            return
        if self.play_b.isChecked():
            self.play_b.setText("❚❚")
            self.timer.start()
        else:
            self.play_b.setText("▶")
            self.timer.stop()

    def stop(self):
        self.timer.stop()
        self.play_b.setChecked(False)
        self.play_b.setText("▶")

    def step(self, d, loop=False):
        if self.frames is None:
            return
        n = len(self.rows)
        i = self.i + d
        if loop:
            i %= n
        self.i = int(min(max(i, 0), n - 1))
        self.slider.blockSignals(True)
        self.slider.setValue(self.i)
        self.slider.blockSignals(False)
        self._show()

    def _seek(self, v):
        self.i = int(v)
        self._show()

    def _pos(self, k):
        r = int(self.rows[k])
        m = self.meas[r]
        ox, oy = float(m["roi_x"]), float(m["roi_y"])
        return (m["x1"] - ox, m["y1"] - oy), (m["x2"] - ox, m["y2"] - oy), bool(m["valid"]), r

    def _show(self):
        if self.frames is None:
            return
        p1, p2, valid, r = self._pos(self.i)
        # Mantener el mismo color para el mismo punto aunque el detector los intercambie
        if self.i > 0:
            q1, q2, _, _ = self._pos(self.i - 1)
            if math.dist(p1, q2) + math.dist(p2, q1) < math.dist(p1, q1) + math.dist(p2, q2):
                p1, p2 = p2, p1
        t1, t2 = [], []
        for k in range(max(0, self.i - 24), self.i):
            a, b, v, _ = self._pos(k)
            if v:
                # Rastro en coordenadas del recorte actual
                dx = float(self.meas[int(self.rows[k])]["roi_x"]) - float(self.meas[r]["roi_x"])
                dy = float(self.meas[int(self.rows[k])]["roi_y"]) - float(self.meas[r]["roi_y"])
                a, b = (a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)
                if math.dist(a, p1) + math.dist(b, p2) > math.dist(a, p2) + math.dist(b, p1):
                    a, b = b, a
                t1.append(a)
                t2.append(b)
        f = int(self.meas["frame"][r])
        cap = f"cuadro {f:,} · {fmt_time(f / self.fps_video)}".replace(",", ".")
        if valid:
            cap += f" · punto 1 ({p1[0]:.2f}; {p1[1]:.2f}) · punto 2 ({p2[0]:.2f}; {p2[1]:.2f}) px".replace(".", ",")
        self.view.set_frame(self.frames[self.i], p1, p2, valid, t1, t2, cap)

    def hideEvent(self, ev):
        self.stop()
        super().hideEvent(ev)
