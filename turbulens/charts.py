# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Gráficas dibujadas con QPainter.

La misma descripción (``ChartSpec``) se dibuja en pantalla (``ChartWidget``)
y se exporta a PNG, SVG o PDF, así lo que se ve es exactamente lo que se guarda.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .i18n import integer, localize_number_text, tr

PRINT_PALETTE = {
    "bg": "#FFFFFF", "panel": "#FFFFFF", "text": "#1D2622", "muted": "#55615B", "grid": "#E4E8E6",
    "accent": "#3E7C72", "accent2": "#B4652A", "good": "#2E7D5B", "warn": "#9A6B12", "bad": "#B0452C",
    "track": "#B9C4BF", "border": "#DDE2DF",
    "bars": "#93C6BC", "meanLine": "#C62828", "medianLine": "#1F4FB5",
}


@dataclass
class Series:
    kind: str                      # bars | line | scatter | vline | hline | band | hbars
    x: Sequence = ()
    y: Sequence = ()
    color: str = "accent"
    label: str = ""
    width: float = 2.0
    alpha: float = 1.0
    dash: bool = False
    size: float = 3.0
    x0: float = 0.0
    x1: float = 0.0
    labels: Sequence = ()          # etiquetas de categoría (barras)
    values_on_top: bool = False
    colors: Sequence = ()          # color por barra


@dataclass
class ChartSpec:
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""
    series: list = field(default_factory=list)
    xlim: Optional[tuple] = None
    ylim: Optional[tuple] = None
    legend: bool = True
    note: str = ""
    categorical: bool = False
    ymin_zero: bool = False
    empty: str = ""  # si no está vacío, la gráfica se dibuja sin datos y con este mensaje en el centro


def nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [lo]
    raw = (hi - lo) / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + 1e-9 * step:
        ticks.append(round(v, 10))
        v += step
    return ticks


def _fmt(v: float, step: float = 0.0) -> str:
    if v == 0:
        return "0"
    a = abs(v)
    if step > 0 and a < 1e6:
        dec = max(0, -math.floor(math.log10(step) + 1e-9))
        if abs(step * 10 ** dec - round(step * 10 ** dec)) > 1e-6:
            dec += 1
        s = f"{v:.{dec}f}"
        if a >= 1000 and dec == 0:
            return integer(round(v))
        return localize_number_text(s)
    if a >= 1000:
        s = integer(round(v))
    elif a >= 100:
        s = f"{v:.0f}"
    elif a >= 10:
        s = f"{v:.1f}"
    elif a >= 1:
        s = f"{v:.2f}"
    else:
        s = f"{v:.3f}"
    if "." in s and a < 1000:
        s = s.rstrip("0").rstrip(".")
    return localize_number_text(s) if a < 1000 else s


def _col(pal: dict, key: str, alpha: float = 1.0) -> QColor:
    c = QColor(pal.get(key, key))
    if not c.isValid():
        c = QColor(key)
    c.setAlphaF(max(0.0, min(1.0, alpha * c.alphaF())))
    return c


def _finite(a) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    return a[np.isfinite(a)]


def _data_limits(spec: ChartSpec):
    xs, ys = [], []
    for s in spec.series:
        if s.kind == "bars":
            x = np.asarray(s.x, dtype=float)
            if x.size:
                xs += [x.min(), x.max()]
            ys += list(_finite(s.y)) + [0.0]
        elif s.kind in ("line", "scatter"):
            xs += list(_finite(s.x))
            ys += list(_finite(s.y))
        elif s.kind == "vline":
            xs += list(_finite(s.x))
        elif s.kind == "hline":
            ys += list(_finite(s.y))
        elif s.kind == "band":
            xs += [s.x0, s.x1]
        elif s.kind == "hbars":
            ys += list(_finite(s.y)) + [0.0]
    xs = _finite(xs)
    ys = _finite(ys)
    if spec.categorical:
        n = max((len(s.y) for s in spec.series if s.kind == "hbars"), default=1)
        xl = (-0.5, n - 0.5)
    else:
        xl = (float(xs.min()), float(xs.max())) if xs.size else (0.0, 1.0)
    yl = (float(ys.min()), float(ys.max())) if ys.size else (0.0, 1.0)
    if spec.ymin_zero:
        yl = (min(0.0, yl[0]), yl[1])
    if xl[1] <= xl[0]:
        xl = (xl[0] - 1, xl[1] + 1)
    if yl[1] <= yl[0]:
        yl = (yl[0] - 1, yl[1] + 1)
    if not spec.categorical:
        padx = 0.02 * (xl[1] - xl[0])
        xl = (xl[0] - padx, xl[1] + padx)
    pady = 0.08 * (yl[1] - yl[0])
    yl = (yl[0] - (0 if spec.ymin_zero or yl[0] == 0 else pady), yl[1] + pady)
    return (spec.xlim or xl), (spec.ylim or yl)


def draw_chart(p: QPainter, rect: QRectF, spec: ChartSpec, pal: dict, scale: float = 1.0) -> Optional[dict]:
    """Dibuja la gráfica en ``rect``. Devuelve la geometría (área de datos y límites) para leer puntos con el ratón."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    base = QFont(p.font())
    base.setPointSizeF(9.5 * scale)
    p.setFont(base)
    fm = QFontMetricsF(base)
    lh = fm.height()

    top = rect.top() + (lh * 1.6 if spec.title else lh * 0.5)
    left = rect.left() + lh * 3.6 + (lh * 1.2 if spec.ylabel else 0)
    bottom = rect.bottom() - lh * 1.8 - (lh * 1.2 if spec.xlabel else 0) - (lh * 1.1 if spec.note else 0)
    right = rect.right() - lh * 0.8
    plot = QRectF(QPointF(left, top), QPointF(right, max(top + 10, bottom)))

    if spec.title:
        tf = QFont(base)
        tf.setBold(True)
        tf.setPointSizeF(10.5 * scale)
        p.setFont(tf)
        p.setPen(_col(pal, "text"))
        p.drawText(QRectF(rect.left() + 4 * scale, rect.top(), rect.width(), lh * 1.5), Qt.AlignLeft | Qt.AlignVCenter, spec.title)
        p.setFont(base)

    if spec.empty:
        p.setPen(QPen(_col(pal, "border"), 1 * scale))
        p.drawLine(plot.bottomLeft(), plot.bottomRight())
        p.drawLine(plot.bottomLeft(), plot.topLeft())
        p.setPen(_col(pal, "muted"))
        if spec.xlabel:
            p.drawText(QRectF(plot.left(), plot.bottom() + lh * 0.4, plot.width(), lh * 1.2), Qt.AlignHCenter | Qt.AlignVCenter,
                       spec.xlabel)
        p.drawText(plot.adjusted(lh, lh, -lh, -lh), Qt.AlignCenter | Qt.TextWordWrap, spec.empty)
        p.restore()
        return None

    (x0, x1), (y0, y1) = _data_limits(spec)

    def X(v):
        return plot.left() + (v - x0) / (x1 - x0) * plot.width()

    def Y(v):
        return plot.bottom() - (v - y0) / (y1 - y0) * plot.height()

    # Rejilla y ejes
    grid = QPen(_col(pal, "grid"), 1 * scale)
    p.setPen(grid)
    yt = nice_ticks(y0, y1, 5)
    ystep = (yt[1] - yt[0]) if len(yt) > 1 else 0.0
    for v in yt:
        if y0 <= v <= y1:
            p.drawLine(QPointF(plot.left(), Y(v)), QPointF(plot.right(), Y(v)))
    p.setPen(_col(pal, "muted"))
    for v in yt:
        if y0 <= v <= y1:
            p.drawText(QRectF(rect.left(), Y(v) - lh / 2, plot.left() - rect.left() - 6 * scale, lh),
                       Qt.AlignRight | Qt.AlignVCenter, _fmt(v, ystep))
    if spec.categorical:
        cats = next((s.labels for s in spec.series if s.kind == "hbars"), [])
        n = len(cats)
        step = max(1, int(math.ceil(n / max(1, plot.width() / (lh * 4)))))
        for i, lab in enumerate(cats):
            if i % step:
                continue
            p.drawText(QRectF(X(i) - lh * 3, plot.bottom() + 3 * scale, lh * 6, lh), Qt.AlignHCenter | Qt.AlignTop, str(lab))
    else:
        xt = nice_ticks(x0, x1, max(3, int(plot.width() / (lh * 5))))
        xstep = (xt[1] - xt[0]) if len(xt) > 1 else 0.0
        for v in xt:
            if x0 <= v <= x1:
                p.drawText(QRectF(X(v) - lh * 3, plot.bottom() + 3 * scale, lh * 6, lh), Qt.AlignHCenter | Qt.AlignTop,
                           _fmt(v, xstep))
    p.setPen(QPen(_col(pal, "border"), 1 * scale))
    p.drawLine(plot.bottomLeft(), plot.bottomRight())
    p.drawLine(plot.bottomLeft(), plot.topLeft())

    p.setPen(_col(pal, "muted"))
    if spec.xlabel:
        p.drawText(QRectF(plot.left(), plot.bottom() + lh * 1.3, plot.width(), lh * 1.2), Qt.AlignHCenter | Qt.AlignVCenter, spec.xlabel)
    if spec.ylabel:
        p.save()
        p.translate(rect.left() + lh * 0.7, plot.center().y())
        p.rotate(-90)
        p.drawText(QRectF(-plot.height() / 2, -lh * 0.6, plot.height(), lh * 1.2), Qt.AlignCenter, spec.ylabel)
        p.restore()
    if spec.note:
        p.drawText(QRectF(rect.left() + 4 * scale, rect.bottom() - lh * 1.1, rect.width() - 8 * scale, lh),
                   Qt.AlignLeft | Qt.AlignVCenter, spec.note)

    p.setClipRect(plot.adjusted(-1, -1, 1, 1))
    legend = []
    for s in spec.series:
        col = _col(pal, s.color, s.alpha)
        if s.kind == "band":
            p.fillRect(QRectF(QPointF(X(s.x0), plot.top()), QPointF(X(s.x1), plot.bottom())), col)
            if s.label:
                legend.append((s.label, col, "box"))
        elif s.kind == "bars":
            edges = np.asarray(s.x, dtype=float)
            h = np.asarray(s.y, dtype=float)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(col))
            gap = 0.8 * scale
            for i in range(len(h)):
                if not np.isfinite(h[i]) or h[i] <= 0:
                    continue
                r = QRectF(QPointF(X(edges[i]) + gap / 2, Y(h[i])), QPointF(X(edges[i + 1]) - gap / 2, Y(max(y0, 0))))
                p.drawRect(r.normalized())
            if s.label:
                legend.append((s.label, col, "box"))
        elif s.kind == "hbars":
            h = np.asarray(s.y, dtype=float)
            p.setPen(Qt.NoPen)
            n = len(h)
            bw = plot.width() / max(n, 1) * 0.62
            for i in range(n):
                if not np.isfinite(h[i]):
                    continue
                c = _col(pal, s.colors[i], s.alpha) if len(s.colors) > i else col
                p.setBrush(QBrush(c))
                r = QRectF(QPointF(X(i) - bw / 2, Y(h[i])), QPointF(X(i) + bw / 2, Y(max(y0, 0))))
                p.drawRoundedRect(r.normalized(), 3 * scale, 3 * scale)
                if s.values_on_top:
                    p.setPen(_col(pal, "text"))
                    p.drawText(QRectF(X(i) - bw, Y(h[i]) - lh * 1.1, bw * 2, lh), Qt.AlignCenter, _fmt(h[i]))
                    p.setPen(Qt.NoPen)
            if s.label:
                legend.append((s.label, col, "box"))
        elif s.kind == "line":
            x = np.asarray(s.x, dtype=float)
            y = np.asarray(s.y, dtype=float)
            pen = QPen(col, s.width * scale)
            if s.dash:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath()
            started = False
            for xi, yi in zip(x, y):
                if not (np.isfinite(xi) and np.isfinite(yi)):
                    started = False
                    continue
                pt = QPointF(X(xi), Y(yi))
                if started:
                    path.lineTo(pt)
                else:
                    path.moveTo(pt)
                    started = True
            p.drawPath(path)
            if s.label:
                legend.append((s.label, col, "dash" if s.dash else "line"))
        elif s.kind == "scatter":
            x = np.asarray(s.x, dtype=float)
            y = np.asarray(s.y, dtype=float)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(col))
            r = s.size * scale
            ok = np.isfinite(x) & np.isfinite(y)
            for xi, yi in zip(x[ok], y[ok]):
                p.drawEllipse(QPointF(X(xi), Y(yi)), r, r)
            if s.label:
                legend.append((s.label, col, "dot"))
        elif s.kind == "vline":
            pen = QPen(col, s.width * scale)
            if s.dash:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            for xv in _finite(s.x):
                p.drawLine(QPointF(X(xv), plot.top()), QPointF(X(xv), plot.bottom()))
            if s.label:
                legend.append((s.label, col, "dash" if s.dash else "line"))
        elif s.kind == "hline":
            pen = QPen(col, s.width * scale)
            if s.dash:
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            for yv in _finite(s.y):
                p.drawLine(QPointF(plot.left(), Y(yv)), QPointF(plot.right(), Y(yv)))
            if s.label:
                legend.append((s.label, col, "dash" if s.dash else "line"))
    p.setClipping(False)

    if spec.legend and legend:
        pad = 6 * scale
        sw = lh * 1.4
        widths = [fm.horizontalAdvance(t) for t, _, _ in legend]
        bw = max(widths) + sw + pad * 3
        bh = lh * len(legend) + pad * 2
        box = QRectF(plot.right() - bw - pad, plot.top() + pad, bw, bh)
        bgc = _col(pal, "panel", 0.88)
        p.setPen(QPen(_col(pal, "border"), 1 * scale))
        p.setBrush(QBrush(bgc))
        p.drawRoundedRect(box, 6 * scale, 6 * scale)
        for i, (t, c, k) in enumerate(legend):
            yy = box.top() + pad + i * lh + lh / 2
            xx = box.left() + pad
            if k == "box":
                p.fillRect(QRectF(xx, yy - lh * 0.3, sw, lh * 0.6), c)
            elif k == "dot":
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(c))
                p.drawEllipse(QPointF(xx + sw / 2, yy), 3.5 * scale, 3.5 * scale)
            else:
                pen = QPen(c, 2 * scale)
                if k == "dash":
                    pen.setStyle(Qt.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(xx, yy), QPointF(xx + sw, yy))
            p.setPen(_col(pal, "text"))
            p.drawText(QRectF(xx + sw + pad, yy - lh / 2, bw, lh), Qt.AlignLeft | Qt.AlignVCenter, t)
    p.restore()
    return {"plot": QRectF(plot), "x": (x0, x1), "y": (y0, y1)}


def _tip_num(v: float) -> str:
    """Número corto para la lectura bajo el cursor (4 cifras significativas)."""
    if not np.isfinite(v):
        return "—"
    a = abs(v)
    if a >= 10000:
        return integer(round(v))
    s = f"{v:.4g}"
    if "e" in s:
        s = f"{v:.3e}"
    return localize_number_text(s)


class ChartWidget(QWidget):
    """Muestra una ``ChartSpec``. Al pasar el ratón lee el punto más cercano; con clic derecho se guarda o se copia la
    imagen; con doble clic (o desde el menú) se ve en grande."""

    def __init__(self, parent=None, min_h: int = 220):
        super().__init__(parent)
        self.spec = ChartSpec()
        self.pal = PRINT_PALETTE
        self.geom: Optional[dict] = None
        self._hover: Optional[tuple] = None  # (punto en pantalla, texto)
        self.setMinimumHeight(min_h)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.DefaultContextMenu)
        self.setToolTip("")

    def sizeHint(self):
        return QSize(520, 280)

    def set_palette(self, pal: dict) -> None:
        self.pal = pal
        self.update()

    def set_spec(self, spec: ChartSpec) -> None:
        self.spec = spec
        self._hover = None
        self.update()

    # ------------------------------------------------------------ dibujo
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), _col(self.pal, "panel"))
        self.geom = draw_chart(p, QRectF(self.rect()).adjusted(6, 4, -6, -4), self.spec, self.pal)
        if self._hover and self.geom:
            pt, text = self._hover
            plot = self.geom["plot"]
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(_col(self.pal, "muted", 0.6), 1, Qt.DotLine))
            p.drawLine(QPointF(pt.x(), plot.top()), QPointF(pt.x(), plot.bottom()))
            p.setPen(QPen(_col(self.pal, "text"), 1.6))
            p.setBrush(QBrush(_col(self.pal, "panel")))
            p.drawEllipse(pt, 4.5, 4.5)
            f = QFont(p.font())
            f.setPointSizeF(9)
            p.setFont(f)
            fm = QFontMetricsF(f)
            lines = text.split("\n")
            w = max(fm.horizontalAdvance(t) for t in lines) + 16
            h = fm.height() * len(lines) + 10
            x = pt.x() + 12 if pt.x() + 12 + w < plot.right() else pt.x() - 12 - w
            y = max(plot.top(), min(pt.y() - h - 8, plot.bottom() - h))
            box = QRectF(x, y, w, h)
            p.setPen(QPen(_col(self.pal, "border"), 1))
            p.setBrush(QBrush(_col(self.pal, "panel", 0.95)))
            p.drawRoundedRect(box, 6, 6)
            p.setPen(_col(self.pal, "text"))
            for i, t in enumerate(lines):
                p.drawText(QRectF(x + 8, y + 5 + i * fm.height(), w - 12, fm.height()), Qt.AlignLeft | Qt.AlignVCenter, t)
        p.end()

    # ------------------------------------------------------------ lectura con el ratón
    def _nearest(self, pos: QPointF) -> Optional[tuple]:
        g = self.geom
        if not g or not g["plot"].adjusted(-6, -6, 6, 6).contains(pos):
            return None
        plot = g["plot"]
        (x0, x1), (y0, y1) = g["x"], g["y"]

        def X(v):
            return plot.left() + (v - x0) / (x1 - x0) * plot.width()

        def Y(v):
            return plot.bottom() - (v - y0) / (y1 - y0) * plot.height()

        best = None
        for s in self.spec.series:
            if s.kind in ("line", "scatter"):
                x = np.asarray(s.x, dtype=float)
                y = np.asarray(s.y, dtype=float)
                ok = np.isfinite(x) & np.isfinite(y)
                if not ok.any():
                    continue
                xs, ys = X(x[ok]), Y(y[ok])
                d = (xs - pos.x()) ** 2 + (ys - pos.y()) ** 2
                i = int(np.argmin(d))
                if best is None or d[i] < best[0]:
                    lab = tr(s.label) if s.label else ""
                    best = (float(d[i]), QPointF(float(xs[i]), float(ys[i])), float(x[ok][i]), float(y[ok][i]), lab, "xy")
            elif s.kind == "bars":
                e = np.asarray(s.x, dtype=float)
                h = np.asarray(s.y, dtype=float)
                if e.size < 2:
                    continue
                xv = x0 + (pos.x() - plot.left()) / plot.width() * (x1 - x0)
                i = int(np.searchsorted(e, xv) - 1)
                if 0 <= i < h.size and np.isfinite(h[i]):
                    pt = QPointF((X(e[i]) + X(e[i + 1])) / 2, Y(h[i]))
                    d = (pt.x() - pos.x()) ** 2 / 4
                    if best is None or d < best[0]:
                        best = (d, pt, (float(e[i]), float(e[i + 1])), float(h[i]), tr(s.label) if s.label else "", "bar")
            elif s.kind == "hbars":
                h = np.asarray(s.y, dtype=float)
                i = int(round(x0 + (pos.x() - plot.left()) / plot.width() * (x1 - x0)))
                if 0 <= i < h.size and np.isfinite(h[i]):
                    lab = str(s.labels[i]) if len(s.labels) > i else str(i + 1)
                    best = (0.0, QPointF(X(i), Y(h[i])), lab, float(h[i]), "", "cat")
        if best is None:
            return None
        _, pt, xv, yv, lab, kind = best
        xl = tr(self.spec.xlabel) or "x"
        yl = tr(self.spec.ylabel) or "y"
        if kind == "bar":
            text = f"{xl}: {_tip_num(xv[0])} – {_tip_num(xv[1])}\n{yl}: {_tip_num(yv)}"
        elif kind == "cat":
            text = f"{xv}\n{yl}: {_tip_num(yv)}"
        else:
            text = f"{xl}: {_tip_num(xv)}\n{yl}: {_tip_num(yv)}"
        if lab:
            text = lab + "\n" + text
        return pt, text

    def mouseMoveEvent(self, ev):
        h = self._nearest(ev.position())
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, ev):
        if self._hover is not None:
            self._hover = None
            self.update()
        super().leaveEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        if not getattr(self, "_large", False):
            self.show_large()

    def contextMenuEvent(self, ev):
        from PySide6.QtWidgets import QMenu

        m = QMenu(self)
        if not getattr(self, "_large", False):
            m.addAction(tr("Ver en grande"), self.show_large)
        m.addAction(tr("Guardar imagen (PNG)…"), self.save_png)
        m.addAction(tr("Copiar imagen"), self.copy_image)
        m.exec(ev.globalPos())

    def image(self, w: int = 1600, h: int = 900):
        from PySide6.QtGui import QImage

        img = QImage(w, h, QImage.Format_ARGB32)
        img.fill(QColor(PRINT_PALETTE["bg"]))
        p = QPainter(img)
        draw_chart(p, QRectF(20, 20, w - 40, h - 60), self.spec, PRINT_PALETTE, scale=w / 800)
        _credit(p, QRectF(20, h - 38, w - 40, 30), w / 800, PRINT_PALETTE)
        p.end()
        return img

    def save_png(self):
        from PySide6.QtWidgets import QFileDialog

        name = (self.spec.title or "grafica").strip().replace(" ", "_").replace("/", "-")[:60] + ".png"
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar imagen"), name, "PNG (*.png)")
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            self.image().save(path)

    def copy_image(self):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setImage(self.image())

    def show_large(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout

        dlg = QDialog(self.window())
        dlg.setWindowTitle(tr(self.spec.title) or "TurbuLENS")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(10, 10, 10, 10)
        big = ChartWidget(dlg, min_h=400)
        big._large = True
        big.set_palette(self.pal)
        big.set_spec(self.spec)
        lay.addWidget(big)
        scr = self.screen().availableGeometry() if self.screen() else None
        if scr is not None:
            dlg.resize(int(scr.width() * 0.8), int(scr.height() * 0.75))
        dlg.exec()


# --------------------------------------------------------------- exportación
def render_png(spec: ChartSpec, path: str, w: int = 1600, h: int = 900, pal: dict | None = None) -> None:
    from PySide6.QtGui import QImage

    pal = pal or PRINT_PALETTE
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(pal["bg"]))
    p = QPainter(img)
    draw_chart(p, QRectF(20, 20, w - 40, h - 60), spec, pal, scale=w / 800)
    _credit(p, QRectF(20, h - 38, w - 40, 30), w / 800, pal)
    p.end()
    img.save(path)


def render_svg(spec: ChartSpec, path: str, w: int = 900, h: int = 520, pal: dict | None = None) -> None:
    from PySide6.QtSvg import QSvgGenerator

    pal = pal or PRINT_PALETTE
    gen = QSvgGenerator()
    gen.setFileName(path)
    gen.setSize(QSize(w, h))
    gen.setViewBox(QRectF(0, 0, w, h))
    gen.setTitle(spec.title or "TurbuLENS")
    p = QPainter(gen)
    p.fillRect(QRectF(0, 0, w, h), QColor(pal["bg"]))
    draw_chart(p, QRectF(12, 12, w - 24, h - 40), spec, pal, scale=1.0)
    _credit(p, QRectF(12, h - 26, w - 24, 20), 1.0, pal)
    p.end()


def _credit(p, rect, scale, pal):
    f = QFont(p.font())
    f.setPointSizeF(7.5 * scale)
    p.setFont(f)
    p.setPen(_col(pal, "muted"))
    p.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, "TurbuLENS · D. F. Cagua Lozada, F. E. Cruz Ospina y S. J. Pinto Sanabria · github.com/DiegoCagua/TurbuLENS")


# ------------------------------------------------------------ constructores
def histogram_spec(x, bins=None, title="", xlabel="", ylabel="Cuadros", normal=True, density=False,
                   mean_line=True, median_line=False, sigma_band=0, lim=None, color="bars") -> ChartSpec:
    from .core import stats

    a = _finite(x)
    edges = stats.nice_bins(a, nbins=bins, lo=lim[0] if lim else None, hi=lim[1] if lim else None)
    counts, edges = np.histogram(a, bins=edges)
    s = stats.summarize(a)
    width = edges[1] - edges[0]
    yv = counts / (a.size * width) if density and a.size else counts
    series = []
    if sigma_band and s.n > 1:
        for k, al in ((3, 0.08), (2, 0.12), (1, 0.18)):
            if k <= sigma_band:
                series.append(Series("band", x0=s.mean - k * s.std, x1=s.mean + k * s.std, color="accent2",
                                     alpha=al, label=f"x̄ ± {k}σ" if k == 1 or sigma_band == k else ""))
    series.append(Series("bars", x=edges, y=yv, color=color, alpha=0.9, label="Frecuencia" if not density else "Densidad"))
    if normal and s.n > 2 and s.std > 0:
        xx = np.linspace(edges[0], edges[-1], 200)
        pdf = stats.normal_pdf(xx, s.mean, s.std)
        yy = pdf if density else pdf * a.size * width
        series.append(Series("line", x=xx, y=yy, color="text", width=2, label="Normal (x̄, σ)"))
    if mean_line and s.n:
        series.append(Series("vline", x=[s.mean], color="meanLine", width=2.5, dash=True, label="Media"))
    if median_line and s.n:
        series.append(Series("vline", x=[s.median], color="medianLine", width=2.5, label="Mediana"))
    return ChartSpec(title=title, xlabel=xlabel, ylabel=ylabel, series=series, ymin_zero=True)
