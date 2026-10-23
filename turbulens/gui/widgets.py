# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Piezas reutilizables de la interfaz."""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from .theme import theme


def label(text: str = "", role: Optional[str] = None, wrap: bool = False, rich: bool = False) -> QLabel:
    lb = QLabel(text)
    if role:
        lb.setProperty("role", role)
    if wrap:
        lb.setWordWrap(True)
    if rich:
        lb.setTextFormat(Qt.RichText)
        lb.setOpenExternalLinks(True)
        lb.setTextInteractionFlags(Qt.TextBrowserInteraction)
    return lb


def button(text: str, kind: Optional[str] = None, slot: Optional[Callable] = None, checkable: bool = False,
           tip: str = "") -> QPushButton:
    b = QPushButton(text)
    if kind:
        b.setProperty("kind", kind)
    b.setCheckable(checkable)
    b.setCursor(Qt.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    if slot:
        b.clicked.connect(slot)
    return b


def hbox(*items, spacing: int = 8, margins=(0, 0, 0, 0), stretch_last: bool = False) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        _add(lay, it)
    if stretch_last:
        lay.addStretch(1)
    return lay


def vbox(*items, spacing: int = 8, margins=(0, 0, 0, 0)) -> QVBoxLayout:
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for it in items:
        _add(lay, it)
    return lay


def _add(lay, it):
    if it is None:
        return
    if it == "stretch":
        lay.addStretch(1)
    elif isinstance(it, int):
        lay.addSpacing(it)
    elif isinstance(it, QWidget):
        lay.addWidget(it)
    else:
        lay.addLayout(it)


class Card(QFrame):
    def __init__(self, title: str = "", kind: str = "true", parent=None, help_text: str = "", margins=(16, 14, 16, 14)):
        super().__init__(parent)
        self.setProperty("card", kind)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(10)
        if title:
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(label(title, "h2"))
            if help_text:
                row.addWidget(HelpButton(help_text))
            row.addStretch(1)
            self.lay.addLayout(row)

    def add(self, *items):
        for it in items:
            _add(self.lay, it)
        return self


class HelpPopup(QFrame):
    def __init__(self, text: str, parent=None):
        super().__init__(parent, Qt.Popup)
        self.setObjectName("popup")
        self.setAttribute(Qt.WA_DeleteOnClose)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lb = QLabel(text)
        lb.setWordWrap(True)
        lb.setTextFormat(Qt.RichText)
        lb.setOpenExternalLinks(True)
        lb.setMaximumWidth(380)
        lb.setMinimumWidth(260)
        lay.addWidget(lb)


class HelpButton(QToolButton):
    """Botón «!»: al hacer clic muestra una explicación breve."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.text_ = text
        self.setText("!")
        self.setProperty("kind", "help")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("¿Cómo funciona?")
        self.setAccessibleName("Ayuda")
        self.clicked.connect(self._show)

    def _show(self):
        pop = HelpPopup(self.text_, self.window())
        pop.adjustSize()
        g = self.mapToGlobal(QPoint(0, self.height() + 6))
        scr = self.screen().availableGeometry() if self.screen() else None
        x, y = g.x(), g.y()
        if scr is not None:
            x = min(x, scr.right() - pop.width() - 8)
            if y + pop.height() > scr.bottom():
                y = self.mapToGlobal(QPoint(0, 0)).y() - pop.height() - 6
        pop.move(max(0, x), max(0, y))
        pop.show()


class ChipGroup(QWidget):
    """Grupo de botones-ficha: uno solo seleccionado (o varios si ``multi``)."""

    changed = Signal()

    def __init__(self, options: Iterable[tuple[str, str]], multi: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("transparent")
        self.multi = multi
        self.buttons: dict[str, QPushButton] = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.group = QButtonGroup(self)
        self.group.setExclusive(not multi)
        for key, text in options:
            b = button(text, "chip", checkable=True)
            self.group.addButton(b)
            self.buttons[key] = b
            lay.addWidget(b)
            b.toggled.connect(lambda *_: self.changed.emit())
        lay.addStretch(1)

    def value(self) -> Optional[str]:
        for k, b in self.buttons.items():
            if b.isChecked():
                return k
        return None

    def values(self) -> list[str]:
        return [k for k, b in self.buttons.items() if b.isChecked()]

    def set_value(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def set_values(self, keys: Iterable[str]) -> None:
        keys = set(keys)
        for k, b in self.buttons.items():
            b.setChecked(k in keys)


class Kpi(QFrame):
    def __init__(self, title: str, accent: bool = False, help_text: str = ""):
        super().__init__()
        self.setProperty("card", "true")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.t = label(title, "small")
        row.addWidget(self.t)
        if help_text:
            row.addWidget(HelpButton(help_text))
        row.addStretch(1)
        lay.addLayout(row)
        self.v = label("—", "kpiAccent" if accent else "kpi")
        self.n = label("", "small")
        self.n.setWordWrap(True)
        lay.addWidget(self.v)
        lay.addWidget(self.n)

    def set(self, value: str, note: str = "", color: Optional[str] = None):
        self.v.setText(value)
        self.n.setText(note)
        if color:
            self.n.setStyleSheet(f"color: {color}; font-weight: 600;")
        else:
            self.n.setStyleSheet("")


def scroll(widget: QWidget) -> QScrollArea:
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(widget)
    return sa


def app_icon(size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    acc = QColor(theme.pal["accent"])
    p.setPen(QPen(acc, max(1.5, size / 16)))
    m = size * 0.08
    p.drawEllipse(int(m), int(m), int(size - 2 * m), int(size - 2 * m))
    p.setPen(Qt.NoPen)
    p.setBrush(acc)
    r = size * 0.09
    p.drawEllipse(int(size * 0.38 - r), int(size * 0.41 - r), int(2 * r), int(2 * r))
    p.drawEllipse(int(size * 0.62 - r), int(size * 0.59 - r), int(2 * r), int(2 * r))
    p.end()
    return pm


def sun_moon_icon(dark: bool, color: str, size: int = 22) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    c = QColor(color)
    if dark:  # mostrar sol (pasar a claro)
        p.setPen(QPen(c, 1.8))
        cx = cy = size / 2
        p.drawEllipse(int(cx - 4.5), int(cy - 4.5), 9, 9)
        import math

        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(int(cx + 7 * math.cos(a)), int(cy + 7 * math.sin(a)), int(cx + 9.5 * math.cos(a)), int(cy + 9.5 * math.sin(a)))
    else:  # mostrar luna (pasar a oscuro)
        path = QPainterPath()
        path.addEllipse(3, 3, size - 6, size - 6)
        cut = QPainterPath()
        cut.addEllipse(8, 0, size - 6, size - 8)
        moon = path.subtracted(cut)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(moon)
    p.end()
    return QIcon(pm)


# ------------------------------------------------------------------ FlowLayout
from PySide6.QtCore import QRect  # noqa: E402
from PySide6.QtWidgets import QLayout  # noqa: E402


class FlowLayout(QLayout):
    """Distribuye los elementos en filas que se ajustan al ancho disponible."""

    def __init__(self, parent=None, spacing: int = 6):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self._items:
            hint = it.sizeHint()
            nx = x + hint.width() + sp
            if nx - sp > rect.right() and line_h > 0:
                x = rect.x()
                y += line_h + sp
                nx = x + hint.width() + sp
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


def dialog_options():
    """En Linux se usa el selector de archivos de Qt: no depende de GTK ni de los portales del escritorio."""
    import sys

    from PySide6.QtWidgets import QFileDialog

    if sys.platform.startswith("linux"):
        return QFileDialog.Option.DontUseNativeDialog
    return QFileDialog.Option(0)


def fullscreen_icon(color: str, exit_: bool = False, size: int = 20) -> QIcon:
    """Cuatro esquinas: hacia afuera (entrar a pantalla completa) o hacia adentro (salir)."""
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(2, 2)
    p.setPen(QPen(QColor(color), 1.9, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    a, b, L = 3.5, size - 3.5, 5.0
    for cx, cy, dx, dy in ((a, a, 1, 1), (b, a, -1, 1), (a, b, 1, -1), (b, b, -1, -1)):
        if exit_:
            ox, oy = cx + dx * L, cy + dy * L
            p.drawLine(int(ox - dx * L), int(oy), int(ox), int(oy))
            p.drawLine(int(ox), int(oy - dy * L), int(ox), int(oy))
        else:
            p.drawLine(int(cx), int(cy), int(cx + dx * L), int(cy))
            p.drawLine(int(cx), int(cy), int(cx), int(cy + dy * L))
    p.end()
    return QIcon(pm)


# ------------------------------------------------------- reproducción (común)
# Las mismas velocidades y los mismos botones en toda la aplicación.
# La velocidad es relativa al video real: 1.0× = el video a su velocidad original.
PLAYBACK_SPEEDS = [("0.25×", 0.25), ("0.5×", 0.5), ("1.0×", 1.0), ("2.0×", 2.0), ("4.0×", 4.0),
                   ("8.0×", 8.0), ("16.0×", 16.0), ("32.0×", 32.0)]
TRANSPORT_TIPS = {
    "<<": "Reproducir hacia atrás a velocidad constante (presiona otra vez para detener)",
    "<": "Un cuadro hacia atrás",
    ">": "Un cuadro hacia adelante",
    ">>": "Reproducir hacia adelante a velocidad constante (presiona otra vez para detener)",
}
TRANSPORT_HELP = ("<ul style='margin-left:-16px'><li><b>&lt;&lt;</b> y <b>&gt;&gt;</b> reproducen hacia atrás o hacia "
                  "adelante a velocidad constante; presiónalos otra vez para detener.</li><li><b>&lt;</b> y <b>&gt;</b> "
                  "mueven exactamente un cuadro.</li><li>La lista elige la velocidad respecto al video real: "
                  "<b>1.0×</b> es la velocidad original, <b>2.0×</b> el doble, <b>0.5×</b> la mitad.</li></ul>")


def speed_combo(default: float = 1.0):
    from PySide6.QtWidgets import QComboBox

    c = QComboBox()
    for t, v in PLAYBACK_SPEEDS:
        c.addItem(t, v)
    c.setCurrentIndex([v for _, v in PLAYBACK_SPEEDS].index(default))
    c.setToolTip("Velocidad de reproducción respecto al video real")
    return c


def transport_buttons(on_rew, on_prev, on_next, on_ff):
    """Devuelve los botones << < > >> con el mismo aspecto y comportamiento en toda la app."""
    rew = button("<<", "transport", on_rew, checkable=True, tip=TRANSPORT_TIPS["<<"])
    prev = button("<", "transport", on_prev, tip=TRANSPORT_TIPS["<"])
    nxt = button(">", "transport", on_next, tip=TRANSPORT_TIPS[">"])
    ff = button(">>", "transport", on_ff, checkable=True, tip=TRANSPORT_TIPS[">>"])
    return rew, prev, nxt, ff


class FormulaLabel(QWidget):
    """Fórmula en LaTeX (imagen pregenerada con scripts/formulas.py); sigue el tema y el idioma y se
    reduce para caber en el ancho disponible sin cortarse."""

    DPR = 2.2

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self._img = None
        sp = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)
        self.setMinimumWidth(60)
        theme.changed.connect(lambda *_: self._load())
        self._load()

    def _load(self):
        import os
        import sys

        from PySide6.QtGui import QImage

        from .. import i18n

        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        t = "dark" if theme.dark else "light"
        path = os.path.join(base, "assets", "formulas", f"{self.name}_{i18n.lang()}_{t}.png")
        if not os.path.isfile(path):
            path = os.path.join(base, "assets", "formulas", f"{self.name}_es_{t}.png")
        self._img = QImage(path)
        self.updateGeometry()
        self.update()

    def _natural(self):
        if self._img is None or self._img.isNull():
            return 1.0, 1.0
        return self._img.width() / self.DPR, self._img.height() / self.DPR

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        nw, nh = self._natural()
        return int(nh * min(1.0, max(w, 1) / nw)) + 2

    def sizeHint(self):
        nw, nh = self._natural()
        return QSize(int(nw), int(nh) + 2)

    def paintEvent(self, ev):
        if self._img is None or self._img.isNull():
            return
        nw, nh = self._natural()
        k = min(1.0, self.width() / nw)
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        from PySide6.QtCore import QRectF

        p.drawImage(QRectF(0, 0, nw * k, nh * k), self._img)
        p.end()


def ask(parent, title: str, text: str) -> bool:
    """Pregunta Sí / No con los botones en el idioma de la app (no en inglés)."""
    from PySide6.QtWidgets import QMessageBox

    from ..i18n import tr

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(tr(title))
    box.setText(tr(text))
    yes = box.addButton(tr("Sí"), QMessageBox.YesRole)
    no = box.addButton(tr("No"), QMessageBox.NoRole)
    box.setDefaultButton(no)
    box.exec()
    return box.clickedButton() is yes


def notify(parent, title: str, text: str, kind: str = "info") -> None:
    """Aviso con el botón «Aceptar» en el idioma de la app."""
    from PySide6.QtWidgets import QMessageBox

    from ..i18n import tr

    box = QMessageBox(parent)
    box.setIcon({"info": QMessageBox.Information, "warning": QMessageBox.Warning,
                 "error": QMessageBox.Critical}.get(kind, QMessageBox.Information))
    box.setWindowTitle(tr(title))
    box.setText(tr(text))
    box.addButton(tr("Aceptar"), QMessageBox.AcceptRole)
    box.exec()


def ask_text(parent, title: str, label_text: str, text: str = "", multiline: bool = False):
    """Pide un texto con los botones «Aceptar» y «Cancelar» en el idioma de la app. Devuelve (texto, ok)."""
    from PySide6.QtWidgets import QInputDialog

    from ..i18n import tr

    dlg = QInputDialog(parent)
    dlg.setWindowTitle(tr(title))
    dlg.setLabelText(tr(label_text))
    dlg.setOkButtonText(tr("Aceptar"))
    dlg.setCancelButtonText(tr("Cancelar"))
    if multiline:
        dlg.setOption(QInputDialog.UsePlainTextEditForTextInput, True)
    dlg.setTextValue(text)
    ok = dlg.exec() == QInputDialog.Accepted
    return dlg.textValue(), ok
