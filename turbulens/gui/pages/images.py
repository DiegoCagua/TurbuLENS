# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Modo «Imágenes»: calibración con darks, flats y bias, y un visor de píxeles al estilo de DS9."""

from __future__ import annotations

import csv
import os
import time

import numpy as np
from PySide6.QtCore import QEventLoop, QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QHeaderView, QPlainTextEdit,
    QProgressBar, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ...core import calframes as cf
from ...core import calibration as cal
from ...core.imageio import IMAGE_EXTS, header_text, read_stack, write_fits, write_png16
from ...i18n import integer, num, tr
from ..imageview import CMAPS, LIMITS, STRETCHES, ImageView
from ..theme import theme
from ..widgets import (
    Card, HelpButton, button, choose_file, choose_files, choose_folder, free_base, free_name, hbox, label, notify,
)
from .base import Page

def image_filter() -> str:
    """Filtro del selector de archivos (en el idioma activo)."""
    return (tr("Imágenes") + " (" + " ".join("*" + e for e in IMAGE_EXTS) + ");;FITS (*.fits *.fit *.fts);;"
            + tr("Todos") + " (*)")

VIEWER_HELP = (
    "<b>Visor de píxeles</b> (como SAOImage DS9).<ul style='margin-left:-16px'>"
    "<li><b>Rueda del ratón</b>: acercar o alejar alrededor del cursor. <b>Arrastrar</b>: mover la imagen.</li>"
    "<li><b>Mayús + arrastrar</b> o <b>clic derecho y arrastrar</b>: dibuja una región y calcula su estadística.</li>"
    "<li>Abajo se lee la <b>posición</b> y el <b>valor</b> del píxel bajo el cursor (columna y fila desde 1; la fila 1 es la "
    "de arriba).</li>"
    "<li><b>Escala</b>: cómo se reparte el brillo. <b>Lineal</b> es fiel; <b>logarítmica</b>, <b>raíz</b> y <b>asinh</b> "
    "realzan lo débil; <b>histograma ecualizado</b> reparte los tonos por igual.</li>"
    "<li><b>Límites</b>: qué valores quedan en negro y en blanco. <b>ZScale</b> es el de DS9: ignora las estrellas "
    "brillantes y muestra bien el fondo.</li></ul>"
    "Los datos no cambian al cambiar la escala o los colores: solo cambia cómo se ven.")

CAL_PAGE_HELP = (
    "<b>Calibración guiada por las cabeceras</b><br>Agrega una carpeta completa (con subcarpetas) o imágenes sueltas. "
    "TurbuLENS lee la cabecera de cada una (FITS, o EXIF de las fotos) y:<ul style='margin-left:-16px'>"
    "<li><b>Las clasifica</b> en luces, darks, flats, darks de flat y bias: por la cabecera (IMAGETYP), y si no la "
    "tiene, por el nombre del archivo o de la carpeta. Lo que no se pueda saber se toma como luz y se marca.</li>"
    "<li><b>Empareja</b>: cada luz recibe los darks de su misma <b>exposición</b>, ganancia (o ISO), temperatura, "
    "binning y tamaño, y los flats de su mismo <b>filtro</b>. Los flats reciben sus propios darks (darks de flat).</li>"
    "<li>Si no hay darks de la misma exposición pero sí bias, <b>escala</b> el dark: (dark − bias) · t<sub>luz</sub> / "
    "t<sub>dark</sub> + bias.</li></ul>"
    "Antes de calibrar ves el plan con los avisos. Cada maestro se crea una sola vez y se guarda en FITS de 32 bits "
    "(carpeta «maestros»); cada luz se corrige como <b>(luz − dark) ÷ flat normalizado</b> (carpeta «calibradas»).")


FWHM_HALF = 1.1774100225154747  # FWHM/2 en unidades de σ: √(2 ln 2)


def fmt(v, d=3):
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    if a != 0 and (a >= 1e6 or a < 1e-3):
        return f"{v:.3e}"
    return num(v, d)


# --------------------------------------------------------------------- visor
class ImageViewerPage(Page):
    title = "Visor de píxeles"
    subtitle = "Abre una imagen FITS, PNG, TIFF o JPG y lee el valor de cada píxel"
    help_text = VIEWER_HELP

    def __init__(self, main):
        super().__init__(main)
        self.path = ""
        self.stack = None
        self.name = ""
        self.header = ""
        self.setAcceptDrops(True)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(button("Abrir imagen…", "primary", self.open_dialog))
        self.frame = QSpinBox()
        self.frame.setMinimum(1)
        self.frame.setPrefix(tr("Cuadro "))
        self.frame.setVisible(False)
        self.frame.valueChanged.connect(self._frame_changed)
        bar.addWidget(self.frame)
        bar.addSpacing(8)
        self.stretch_c = self._combo(STRETCHES, "lineal")
        self.limits_c = self._combo(LIMITS + [("manual", "Manual")], "zscale")
        self.cmap_c = self._combo(CMAPS, "gris")
        self.shape_c = QComboBox()
        for k, t in (("rect", "Rectángulo"), ("circle", "Círculo"), ("ellipse", "Elipse")):
            self.shape_c.addItem(t, k)
        self.shape_c.setToolTip(tr("Forma de la región que dibujas con Mayús + arrastrar"))
        self.shape_c.currentIndexChanged.connect(lambda *_: self.view.set_region_shape(self.shape_c.currentData()))
        bar.addWidget(label("Escala", "small"))
        bar.addWidget(self.stretch_c)
        bar.addWidget(label("Límites", "small"))
        bar.addWidget(self.limits_c)
        bar.addWidget(label("Colores", "small"))
        bar.addWidget(self.cmap_c)
        bar.addWidget(label("Región", "small"))
        bar.addWidget(self.shape_c)
        bar.addStretch(1)
        bar.addWidget(button("Ajustar", slot=lambda: self.view.fit(), tip="Ajustar la imagen a la ventana"))
        bar.addWidget(button("1:1", slot=lambda: self.view.set_zoom(1.0), tip="Un píxel de la imagen = un píxel de la pantalla"))
        self.lay.addLayout(bar)

        row = QHBoxLayout()
        row.setSpacing(14)
        vc = Card(margins=(8, 8, 8, 8))
        self.view = ImageView()
        self.view.setMinimumHeight(460)
        from PySide6.QtWidgets import QSizePolicy

        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.hovered.connect(self._hover)
        self.view.left.connect(lambda: self.pix.setText(tr("Mueve el cursor sobre la imagen")))
        self.view.region.connect(self._region)
        vc.add(self.view)
        self.pix = label("Mueve el cursor sobre la imagen", "mono")
        self.rng = label("", "small")
        vc.add(hbox(self.pix, "stretch", self.rng))
        row.addWidget(vc, 3)

        side = QVBoxLayout()
        side.setSpacing(12)
        info = Card("Imagen")
        self.info_lbl = label("Ninguna imagen abierta.", "small", wrap=True)
        info.add(self.info_lbl)
        info.add(hbox(button("Guardar FITS…", slot=lambda: self.save("fits")),
                      button("Guardar PNG…", slot=lambda: self.save("png"), tip="PNG de 16 bits con la escala de la pantalla"),
                      "stretch"))
        side.addWidget(info)
        rc = Card("Región")
        rc.add(label("Mayús + arrastrar (o clic derecho y arrastrar) sobre la imagen.", "small", wrap=True))
        self.reg_grid = QGridLayout()
        self.reg_grid.setHorizontalSpacing(14)
        self.reg_vals = {}
        for i, (k, t) in enumerate([("n", "Píxeles"), ("media", "Media"), ("mediana", "Mediana"), ("sigma", "σ"),
                                    ("mad", "σ robusta"), ("min", "Mínimo"), ("max", "Máximo"), ("suma", "Suma")]):
            self.reg_grid.addWidget(label(t, "small"), i // 2, (i % 2) * 2)
            v = label("—", "mono")
            self.reg_grid.addWidget(v, i // 2, (i % 2) * 2 + 1)
            self.reg_vals[k] = v
        rc.add(self.reg_grid)
        self.reg_box = label("", "small")
        rc.add(self.reg_box)
        rc.add(hbox(button("Toda la imagen", slot=self._whole),
                    button("Exportar CSV…", slot=self.export_region, tip="Guarda x, y y el valor de cada píxel de la región"),
                    "stretch"))
        self.reg_msg = label("", "small", wrap=True)
        rc.add(self.reg_msg)
        side.addWidget(rc)
        hc = Card("Cabecera FITS")
        self.hdr = QPlainTextEdit()
        self.hdr.setReadOnly(True)
        self.hdr.setMinimumHeight(180)
        self.hdr.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.hdr.setStyleSheet("font-family: monospace; font-size: 11px;")
        hc.add(self.hdr)
        side.addWidget(hc, 1)
        sw = QWidget()
        sw.setObjectName("transparent")
        sw.setLayout(side)
        sw.setMinimumWidth(360)
        sw.setMaximumWidth(440)
        row.addWidget(sw, 1)
        self.lay.addLayout(row, 1)
        self.region = None
        self.fit = None
        self._build_tools()

    def _build_tools(self):
        from PySide6.QtWidgets import QSizePolicy

        from ... import charts
        from ..widgets import DecSpin

        row = QHBoxLayout()
        row.setSpacing(14)
        # ---- escala variable
        sc = Card("Escala (como en DS9)", help_text=(
            "<b>Escala variable</b><br>El histograma muestra cuántos píxeles tienen cada valor. Las líneas marcan el "
            "<b>negro</b> (todo lo que está por debajo se ve negro) y el <b>blanco</b> (todo lo de arriba se ve blanco). "
            "Escribe otros valores para cambiar el contraste: los límites pasan a «Manual». Con «Mismos límites en "
            "todos los cuadros» puedes comparar cuadros (por ejemplo, antes y después de calibrar) con el mismo "
            "contraste."))
        self.c_hist = charts.ChartWidget(min_h=190)
        sc.add(self.c_hist)
        self.lo_s = DecSpin()
        self.hi_s = DecSpin()
        for sp in (self.lo_s, self.hi_s):
            sp.setDecimals(4)
            sp.setRange(-1e12, 1e12)
            sp.setFixedWidth(110)
            sp.editingFinished.connect(self._manual_limits)
        self.lock_cb = QCheckBox(tr("Mismos límites en todos los cuadros"))
        sc.add(hbox(label("Negro", "small"), self.lo_s, label("Blanco", "small"), self.hi_s, "stretch"))
        sc.add(hbox(self.lock_cb, "stretch", button("Automático", slot=lambda: self.limits_c.setCurrentIndex(
            self.limits_c.findData("zscale")))))
        row.addWidget(sc, 1)
        # ---- estrella: FWHM y seeing
        st = Card("Estrella: FWHM y seeing", help_text=(
            "<b>Medir una estrella</b><br>Dibuja una región (mejor un círculo) alrededor de una estrella aislada y pulsa "
            "«Medir». TurbuLENS ajusta una <b>gaussiana 2D</b> con fondo: I = B + A·exp(−[(x−x₀)²/2σx² + (y−y₀)²/2σy²])."
            "<ul style='margin-left:-16px'><li><b>σ</b> es el radio en el que el brillo cae al 61 % del pico (el «primer "
            "sigma»): el círculo interior.</li><li><b>FWHM</b> = 2,355·σ es el ancho a media altura (50 % del pico): el "
            "círculo exterior.</li><li>Con la <b>escala de placa</b> (″/px) el FWHM pasa a segundos de arco. En una "
            "exposición larga, ese FWHM es el <b>seeing</b> (más el desenfoque y el seguimiento, que lo agrandan).</li>"
            "</ul>"))
        self.scale_s = DecSpin()
        self.scale_s.setDecimals(4)
        self.scale_s.setRange(0, 1000)
        self.scale_s.setSuffix(" ″/px")
        self.scale_s.setValue(float(self.main.settings.value("imagenes/escala", 0.0)))
        self.scale_s.setToolTip(tr("Escala de placa = 206,265 × píxel (µm) ÷ focal (mm). 0 = sin escala."))
        self.scale_s.valueChanged.connect(lambda v: (self.main.settings.setValue("imagenes/escala", v), self._show_fit()))
        st.add(hbox(label("Escala de placa", "small"), self.scale_s,
                    button("De Parámetros", slot=self._scale_from_params,
                           tip="Usa la escala del modo medición (telescopio y cámara)"), "stretch"))
        st.add(hbox(button("Medir la estrella de la región", "primary", self.measure_star), "stretch"))
        self.fit_lbl = label("Dibuja una región alrededor de una estrella y pulsa «Medir».", "small", wrap=True, rich=True)
        self.fit_lbl.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        from ..widgets import FormulaLabel

        fbox = Card(kind="panel2", margins=(12, 8, 12, 8))
        fbox.add(FormulaLabel("gauss2d"), FormulaLabel("fwhm"),
                 label("s = escala de placa (″/px). σ: el brillo cae al 61 % del pico; FWHM: al 50 %.", "small", wrap=True))
        st.add(self.fit_lbl, fbox, "stretch")
        row.addWidget(st, 1)
        # ---- gráficas
        gc = Card("Gráficas de la imagen")
        self.plot_c = QComboBox()
        for k, t in (("radial", "Perfil radial de la estrella"), ("hist", "Histograma de la región"),
                     ("fila", "Perfil horizontal (fila del centro)"), ("col", "Perfil vertical (columna del centro)")):
            self.plot_c.addItem(t, k)
        self.plot_c.currentIndexChanged.connect(lambda *_: self._plot())
        self.c_plot = charts.ChartWidget(min_h=280)
        self.c_plot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        gc.add(hbox(self.plot_c, "stretch"), self.c_plot)
        self.lay.addLayout(row)
        self.lay.addWidget(gc)

    def _scale_from_params(self):
        sc = self.main.sessions["analisis"].params.scale_arcsec_px
        if sc:
            self.scale_s.setValue(float(sc))
        else:
            notify(self, "Escala de placa", "Todavía no hay escala en el modo medición: elige tu equipo en Parámetros "
                                            "o escribe la escala aquí.", "info")

    def _manual_limits(self):
        lo, hi = self.lo_s.value(), self.hi_s.value()
        if hi <= lo or self.view.data is None:
            return
        self.limits_c.blockSignals(True)
        self.limits_c.setCurrentIndex(self.limits_c.findData("manual"))
        self.limits_c.blockSignals(False)
        self.view.set_display(self.stretch_c.currentData(), None, self.cmap_c.currentData(), lo=lo, hi=hi)
        self._range()

    def diff_note(self):
        """Tras abrir «antes y después»: mismos límites en los dos cuadros para que la diferencia se vea."""
        self.lock_cb.setChecked(True)
        self.main.toast("Cuadro 1 = original, cuadro 2 = calibrada. Cambia de cuadro arriba para comparar; los dos usan "
                        "los mismos límites de brillo.")

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = [u.toLocalFile() for u in ev.mimeData().urls() if u.toLocalFile()]
        if urls:
            self.open(urls[0])

    def _combo(self, items, default):
        c = QComboBox()
        for k, t in items:
            c.addItem(t, k)
        c.setCurrentIndex([k for k, _ in items].index(default))
        c.currentIndexChanged.connect(self._display)
        return c

    def _display(self, *_):
        if self.limits_c.currentData() == "manual":
            self._manual_limits()
            return
        self.view.set_display(self.stretch_c.currentData(), self.limits_c.currentData(), self.cmap_c.currentData())
        self._range()

    def _range(self):
        if self.view.data is None:
            return
        self.rng.setText(tr("negro = {} · blanco = {}").format(fmt(self.view.lo), fmt(self.view.hi)))
        if hasattr(self, "lo_s"):
            for sp, v in ((self.lo_s, self.view.lo), (self.hi_s, self.view.hi)):
                sp.blockSignals(True)
                sp.setValue(float(v))
                sp.blockSignals(False)
            self._hist()

    def _hist(self):
        from ...charts import ChartSpec, Series

        d = self.view.data
        v = d[np.isfinite(d)].ravel()
        if v.size == 0:
            self.c_hist.set_spec(ChartSpec(empty=tr("Sin datos")))
            return
        v = v[:: max(1, v.size // 300000)]
        lo, hi = np.percentile(v, [0.1, 99.9])
        lo, hi = min(lo, self.view.lo), max(hi, self.view.hi)
        if hi <= lo:
            hi = lo + 1
        cnt, edges = np.histogram(v, bins=80, range=(lo, hi))
        self.c_hist.set_spec(ChartSpec(xlabel=tr("Valor del píxel"), ylabel=tr("Píxeles (log)"), legend=False,
                                       series=[Series("bars", x=edges, y=np.log10(cnt + 1), color="bars"),
                                               Series("vline", x=[float(self.view.lo)], color="medianLine", width=1.6),
                                               Series("vline", x=[float(self.view.hi)], color="meanLine", width=1.6)]))

    # ------------------------------------------------------------- abrir
    def open_dialog(self):
        p = choose_file(self, "Abrir imagen", image_filter())
        if p:
            self.open(p)

    def open(self, path: str):
        try:
            a = read_stack(path)
        except Exception as exc:
            notify(self, "No se pudo abrir", tr("No se pudo leer la imagen: {}").format(exc), "warning")
            return False
        self.path = path
        self.header = header_text(path)
        self.show_array(a, os.path.basename(path), self.header)
        return True

    def show_array(self, a: np.ndarray, name: str, header: str = "", marker=None, marker_text: str = ""):
        """Muestra un arreglo 2D o 3D (cubo) ya cargado (lo usan la calibración y el satélite)."""
        a = np.asarray(a, dtype=np.float32)
        self.stack = a if a.ndim == 3 else a[None]
        self.name = name
        self.header = header
        self.frame.blockSignals(True)
        self.frame.setMaximum(len(self.stack))
        self.frame.setValue(1)
        self.frame.blockSignals(False)
        self.frame.setVisible(len(self.stack) > 1)
        self.view.set_data(self.stack[0])
        self.view.set_overlays([])
        self.fit = None
        if hasattr(self, "fit_lbl"):
            self.fit_lbl.setText(tr("Dibuja una región alrededor de una estrella y pulsa «Medir»."))
        lim = self.limits_c.currentData()
        self.view.set_display(self.stretch_c.currentData(), "zscale" if lim == "manual" else lim, self.cmap_c.currentData())
        self.view.set_marker(*(marker if marker else (None,)), text=marker_text)
        self._range()
        h, w = self.stack.shape[1:]
        self.info_lbl.setText(tr("{} · {} × {} px{}").format(name, w, h, tr(" · {} cuadros").format(len(self.stack))
                                                                    if len(self.stack) > 1 else ""))
        self.hdr.setPlainText(header or tr("(Esta imagen no es FITS: no tiene cabecera.)"))
        self._whole()

    def _frame_changed(self, v):
        if self.stack is not None:
            lo, hi = self.view.lo, self.view.hi
            self.view.set_data(self.stack[v - 1], keep_view=True)
            if self.lock_cb.isChecked():
                self.view.set_display(self.stretch_c.currentData(), None, self.cmap_c.currentData(), lo=lo, hi=hi)
            self._range()
            if self.region:
                self._region(*self.region)

    # ------------------------------------------------------ lectura
    def _hover(self, c, r, v):
        if c < 0:
            self.pix.setText(tr("Fuera de la imagen"))
            return
        self.pix.setText(tr("x = {}   y = {}   valor = {}").format(c + 1, r + 1, fmt(v, 4)))

    def _whole(self):
        if self.view.data is None:
            return
        h, w = self.view.data.shape
        self._region(0, 0, w - 1, h - 1)

    def _region(self, x0, y0, x1, y1):
        if self.view.data is None:
            return
        self.region = (x0, y0, x1, y1)
        sub = self.view.data[y0:y1 + 1, x0:x1 + 1]
        m = self.view.region_mask()
        if m is not None and m.shape == sub.shape and self.view.region_shape != "rect":
            sub = sub[m]
        sub = sub[np.isfinite(sub)]
        st = cal.stats(sub) if sub.size else {}
        for k, lb in self.reg_vals.items():
            v = st.get(k)
            lb.setText(integer(v) if k == "n" and v is not None else fmt(v, 3))
        self.reg_box.setText(tr("x {}–{} · y {}–{} ({} × {} px)").format(x0 + 1, x1 + 1, y0 + 1, y1 + 1, x1 - x0 + 1, y1 - y0 + 1))
        self.reg_msg.setText("")
        if hasattr(self, "c_plot"):
            self._plot()

    # ---------------------------------------------------------- estrella
    def _region_arrays(self):
        if self.view.data is None or not self.region:
            return None
        x0, y0, x1, y1 = self.region
        sub = self.view.data[y0:y1 + 1, x0:x1 + 1]
        m = self.view.region_mask()
        if m is None or m.shape != sub.shape or self.view.region_shape == "rect":
            m = None
        return sub, x0, y0, m

    def measure_star(self):
        from ...core.starfit import fit_star

        ra = self._region_arrays()
        if ra is None:
            self.fit_lbl.setText(tr("Primero dibuja una región alrededor de una estrella."))
            return
        sub, x0, y0, m = ra
        if sub.size > 250000:
            self.fit_lbl.setText(tr("La región es muy grande: dibuja una más pequeña alrededor de una sola estrella."))
            return
        self.fit = fit_star(sub, x0, y0, m)
        self._show_fit()
        self.plot_c.setCurrentIndex(0)
        self._plot()

    def _show_fit(self):
        f = getattr(self, "fit", None)
        if f is None:
            return
        if not f.ok:
            self.fit_lbl.setText(tr("No se pudo medir: {}.").format(tr(f.message)))
            self.view.set_overlays([])
            return
        sc = self.scale_s.value()
        lines = [tr("Centro: x = {}, y = {}").format(num(f.x0 + 1, 2), num(f.y0 + 1, 2)),
                 tr("Pico sobre el fondo: {} · fondo: {}").format(fmt(f.amp), fmt(f.bg)),
                 tr("σx = {} px · σy = {} px · elipticidad {}").format(num(f.sx, 2), num(f.sy, 2), num(f.ellipticity, 2)),
                 tr("Radio al primer sigma (61 % del pico): <b>{} px</b>").format(num(f.sigma, 2)),
                 tr("FWHM (50 % del pico) = 2,355·σ: <b>{} px</b>").format(num(f.fwhm, 2))]
        if sc > 0:
            lines.append(tr("Con {} ″/px: σ = {}″ · FWHM = <b>{}″</b>").format(num(sc, 3), num(f.sigma * sc, 2),
                                                                           num(f.fwhm * sc, 2)))
            lines.append(tr("<b>Seeing ≈ {}″</b> (si la exposición es larga y la estrella está enfocada)").format(
                num(f.fwhm * sc, 2)))
        else:
            lines.append(tr("Escribe la escala de placa para tener el FWHM en segundos de arco y el seeing."))
        self.fit_lbl.setText("<br>".join(lines))
        t = np.linspace(0, 2 * np.pi, 90)
        ov = []
        for k, col in ((1.0, "#33E07A"), (FWHM_HALF, "#FFD54A")):
            ov.append(([np.column_stack([f.x0 + 0.5 + k * f.sx * np.cos(t), f.y0 + 0.5 + k * f.sy * np.sin(t)])], col, 1.6))
        self.view.set_overlays(ov)

    def _plot(self):
        from ...charts import ChartSpec, Series, histogram_spec

        kind = self.plot_c.currentData()
        ra = self._region_arrays()
        if ra is None:
            self.c_plot.set_spec(ChartSpec(empty=tr("Dibuja una región para ver sus gráficas.")))
            return
        sub, x0, y0, m = ra
        vals = sub[m] if m is not None else sub.ravel()
        vals = vals[np.isfinite(vals)]
        if kind == "hist":
            self.c_plot.set_spec(histogram_spec(vals, title=tr("Histograma de la región"), xlabel=tr("Valor del píxel"),
                                                ylabel=tr("Píxeles"), normal=False) if vals.size else ChartSpec(empty=tr("Sin datos")))
            return
        if kind in ("fila", "col"):
            f = getattr(self, "fit", None)
            h, w = sub.shape
            if kind == "fila":
                r = int(round(f.y0 - y0)) if f is not None and f.ok and 0 <= f.y0 - y0 < h else h // 2
                xs, ys, xl = np.arange(w) + x0 + 1, sub[r], tr("Columna x (fila y = {})").format(r + y0 + 1)
            else:
                c = int(round(f.x0 - x0)) if f is not None and f.ok and 0 <= f.x0 - x0 < w else w // 2
                xs, ys, xl = np.arange(h) + y0 + 1, sub[:, c], tr("Fila y (columna x = {})").format(c + x0 + 1)
            self.c_plot.set_spec(ChartSpec(title=self.plot_c.currentText(), xlabel=xl, ylabel=tr("Valor"), legend=False,
                                           series=[Series("line", x=xs, y=ys, color="accent", width=1.8),
                                                   Series("scatter", x=xs, y=ys, color="accent", size=2.5)]))
            return
        from ...core.starfit import radial_profile

        f = getattr(self, "fit", None)
        if f is None or not f.ok:
            self.c_plot.set_spec(ChartSpec(title=tr("Perfil radial de la estrella"),
                                           empty=tr("Pulsa «Medir la estrella de la región» para ver su perfil.")))
            return
        r, v, prof = radial_profile(sub, f, x0, y0, 0.5, m)
        step = max(1, r.size // 3000)
        rr = np.linspace(0, float(r.max()) if r.size else 1, 200)
        sg = f.sigma
        model = f.bg + f.amp * np.exp(-rr ** 2 / (2 * sg * sg))
        ser = [Series("scatter", x=r[::step], y=v[::step], color="muted", alpha=0.5, size=2, label=tr("Píxeles")),
               Series("line", x=rr, y=model, color="accent", width=2, label=tr("Gaussiana")),
               Series("vline", x=[sg], color="good", width=1.4, dash=True, label="σ"),
               Series("vline", x=[f.fwhm / 2], color="warn", width=1.4, dash=True, label="FWHM/2")]
        if prof.size:
            ser.insert(1, Series("line", x=prof[:, 0], y=prof[:, 1], color="accent2", width=1.4, label=tr("Promedio")))
        self.c_plot.set_spec(ChartSpec(title=tr("Perfil radial de la estrella"), xlabel=tr("Distancia al centro (px)"),
                                       ylabel=tr("Valor"), series=ser))

    # ---------------------------------------------------------- guardar
    def _base(self):
        return os.path.splitext(self.name or "imagen")[0]

    def export_region(self):
        if self.view.data is None or not self.region:
            return
        folder = choose_folder(self, "Carpeta para guardar los píxeles de la región")
        if not folder:
            return
        x0, y0, x1, y1 = self.region
        sub = self.view.data[y0:y1 + 1, x0:x1 + 1]
        if sub.size > 4_000_000:
            self.reg_msg.setText(tr("La región es muy grande ({} píxeles): elige una más pequeña.").format(integer(sub.size)))
            return
        p = free_name(folder, f"{self._base()}_region_x{x0 + 1}-{x1 + 1}_y{y0 + 1}-{y1 + 1}.csv")
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        from ... import citation_apa

        with open(p, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow([tr("x (columna, desde 1)"), tr("y (fila, desde 1, de arriba hacia abajo)"), tr("valor")])
            for x, y, v in zip(xx.ravel() + 1, yy.ravel() + 1, sub.ravel()):
                wr.writerow([int(x), int(y), f"{float(v):.6g}"])
            wr.writerow([])
            wr.writerow([tr("Imagen: {}").format(self.name)])
            wr.writerow([tr("Generado con TurbuLENS · ") + citation_apa()])
        self.reg_msg.setText(tr("Guardado: {} ({} píxeles)").format(os.path.basename(p), integer(sub.size)))

    def save(self, kind):
        if self.view.data is None:
            return
        folder = choose_folder(self, "Carpeta para guardar la imagen")
        if not folder:
            return
        base = free_base(folder, self._base() + "_turbulens")
        if kind == "fits":
            p = os.path.join(folder, base + ".fits")
            write_fits(p, self.view.data, {"FILENAME": self.name[:60]})
        else:
            p = os.path.join(folder, base + ".png")
            write_png16(p, self.view.data, self.view.lo, self.view.hi)
        self.reg_msg.setText(tr("Guardado: {}").format(os.path.basename(p)))

    def on_theme(self, pal):
        self.view.update()


# ----------------------------------------------------------- calibración
METHODS = [("mediana", "Mediana (recomendado)"), ("sigma", "Media con recorte de 3 σ"), ("media", "Media")]
KIND_ORDER = ["light", "dark", "flat", "darkflat", "bias"]


def _exp_text(e):
    if e is None:
        return "—"
    return (num(e, 3).rstrip("0").rstrip(",.") or "0") + " s"


def _arg(a):
    """Números de los avisos con el formato del idioma (60 y no 60.0)."""
    if isinstance(a, float):
        return num(a, 3).rstrip("0").rstrip(",.") or "0"
    return a


def _dark_text(c) -> str:
    """Descripción corta de lo que se resta a un grupo."""
    if c is None or c.mode == "ninguno":
        return tr("nada")
    if c.mode == "bias":
        return tr("bias ({})").format(len(c.bias_paths))
    if c.mode == "escalado":
        return tr("dark de {} escalado ×{} con bias ({} + {})").format(_exp_text(c.exptime), num(c.scale, 3),
                                                                      len(c.paths), len(c.bias_paths))
    return tr("dark de {} ({})").format(_exp_text(c.exptime), len(c.paths))


def _localized(args) -> tuple:
    """Los números que llegan ya escritos («0.675») salen con el separador decimal del idioma."""
    import re

    from ...i18n import localize_number_text

    return tuple(localize_number_text(a) if isinstance(a, str) and re.fullmatch(r"-?\d+(\.\d+)?", a) else a
                 for a in args)


class _CalJob(QObject):
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.cancel = False

    def run(self):
        try:
            self.done.emit(self.fn(self))
        except Exception as exc:  # se muestra en la interfaz
            self.failed.emit(str(exc) or exc.__class__.__name__)


class CalibrationPage(Page):
    title = "Calibración: darks y flats"
    subtitle = "Agrega imágenes o carpetas completas: TurbuLENS lee cada cabecera y empareja los darks y flats"
    help_text = CAL_PAGE_HELP

    def __init__(self, main):
        super().__init__(main)
        self.frames: list = []
        self.plan = None
        self.result = None
        self.thread = None
        self.job = None
        self.out_dir = ""
        self.setAcceptDrops(True)

        add = Card("1. Imágenes", margins=(14, 12, 14, 12))
        self.count_lbl = label("Ninguna imagen todavía: agrega una carpeta o suelta aquí las imágenes.", "small", wrap=True)
        add.add(hbox(button("Agregar carpeta…", "primary", self.add_folder,
                            tip="Se recorren también las subcarpetas (por ejemplo Luces/, Darks/, Flats/)"),
                     button("Agregar imágenes…", slot=self.add_files), button("Quitar todo", slot=self.clear), "stretch",
                     self.count_lbl))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Archivo", "Tipo", "Según", "Exposición", "Ganancia / ISO", "Temp. (°C)",
                                              "Filtro", "Tamaño", "Binning"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setMinimumHeight(220)
        self.table.setMaximumHeight(320)
        self.kind_c = QComboBox()
        for k in KIND_ORDER:
            self.kind_c.addItem(cf.KIND_NAMES[k], k)
        add.add(self.table, hbox(label("Si alguna quedó mal clasificada, selecciónala y márcala como", "small"), self.kind_c,
                                 button("Cambiar", slot=self.set_kind), "stretch"))
        self.lay.addWidget(add)

        plan = Card("2. Qué se va a hacer", margins=(14, 12, 14, 12))
        self.method = QComboBox()
        for k, t in METHODS:
            self.method.addItem(t, k)
        self.scale_chk = QCheckBox(tr("Escalar darks con el bias si no hay de la misma exposición"))
        self.scale_chk.setChecked(True)
        self.method.currentIndexChanged.connect(self._replan)
        self.scale_chk.toggled.connect(self._replan)
        plan.add(hbox(label("Combinar con"), self.method, 12, self.scale_chk, "stretch"))
        self.plan_lbl = label("Agrega imágenes para ver el plan.", wrap=True, rich=True)
        self.plan_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        plan.add(self.plan_lbl)
        self.lay.addWidget(plan)

        run = Card("3. Calibrar", margins=(14, 12, 14, 12))
        self.out_lbl = label("Carpeta de salida: (sin elegir)", "small", wrap=True)
        self.run_b = button("Crear maestros y calibrar", "primary", self.run)
        self.cancel_b = button("Cancelar", slot=self.cancel)
        self.cancel_b.setEnabled(False)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.status = label("", "small", wrap=True)
        run.add(hbox(button("Carpeta de salida…", slot=self.pick_out), self.out_lbl, "stretch"),
                hbox(self.run_b, self.cancel_b, self.bar, 1), self.status)
        self.res_lbl = label("", "small", wrap=True)
        self.view_btns = hbox(spacing=8)
        self.use_b = button("Usar en el modo medición", slot=self.use_in_analysis,
                            tip="El dark, el flat y el bias del grupo principal se aplican a cada cuadro del video antes de medir")
        self.use_b.setEnabled(False)
        run.add(self.res_lbl, self.view_btns, hbox(self.use_b, HelpButton(
            "Los maestros del grupo principal (el de más luces) se aplican cuadro a cuadro al video del DIMM "
            "(Medición → Parámetros → Calibración). Deben tener el mismo tamaño en píxeles que el video y, el dark, la "
            "misma exposición que cada cuadro del video."), "stretch"))
        self.lay.addWidget(run)
        self.lay.addStretch(1)

    # ------------------------------------------------------------ agregar
    def add_files(self):
        self._add(choose_files(self, "Elegir imágenes", image_filter()))

    def add_folder(self):
        d = choose_folder(self, "Carpeta con las imágenes (puede tener subcarpetas)")
        if d:
            self._add([d])

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        self._add([u.toLocalFile() for u in ev.mimeData().urls() if u.toLocalFile()])

    def _add(self, paths):
        if not paths:
            return
        known = {f.path for f in self.frames}

        def prog(a, b):
            self.count_lbl.setText(tr("Leyendo cabeceras… {} de {}").format(a, b))
            QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

        new = [f for f in cf.scan(paths, prog) if f.path not in known]
        self.frames += new
        order = {k: i for i, k in enumerate(KIND_ORDER)}
        self.frames.sort(key=lambda f: (bool(f.error), order.get(f.kind, 9), f.path.lower()))
        self._fill()
        self._replan()

    def clear(self):
        self.frames = []
        self._fill()
        self._replan()

    def set_kind(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        k = self.kind_c.currentData()
        for r in rows:
            if r < len(self.frames):
                self.frames[r].kind, self.frames[r].kind_source = k, "manual"
        self._fill()
        self._replan()

    def _fill(self):
        t = self.table
        t.setRowCount(len(self.frames))
        for i, f in enumerate(self.frames):
            if f.error:
                vals = [f.name, tr("No se pudo leer"), f.error, "", "", "", "", "", ""]
            else:
                vals = [f.name, tr(cf.KIND_NAMES[f.kind]), tr(cf.SOURCE_NAMES[f.kind_source]), _exp_text(f.exptime),
                        "—" if f.gain is None else num(f.gain, 1).rstrip("0").rstrip(",."),
                        "—" if f.temp is None else num(f.temp, 1), f.filter or "—",
                        f"{f.width} × {f.height}" + (f" · {f.frames}" if f.frames > 1 else ""),
                        "—" if not f.binning else f"{f.binning[0]}×{f.binning[1]}"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j == 0:
                    it.setToolTip(f.path + (f"\n{f.type_text}" if f.type_text else ""))
                if j == 2 and f.kind_source == "supuesto":
                    it.setForeground(QColor(theme.pal["warn"]))
                t.setItem(i, j, it)
        c = {k: sum(1 for f in self.frames if f.kind == k and not f.error) for k in KIND_ORDER}
        bad = sum(1 for f in self.frames if f.error)
        if self.frames:
            self.count_lbl.setText(tr("{} luces · {} darks · {} flats · {} darks de flat · {} bias").format(
                c["light"], c["dark"], c["flat"], c["darkflat"], c["bias"]) + (tr(" · {} sin leer").format(bad) if bad else ""))
        else:
            self.count_lbl.setText(tr("Ninguna imagen todavía: agrega una carpeta o suelta aquí las imágenes."))

    # ------------------------------------------------------------ plan
    def _opts(self):
        return cf.MatchOptions(method=self.method.currentData(), scale_darks=self.scale_chk.isChecked())

    def _replan(self, *_):
        if not self.frames:
            self.plan = None
            self.plan_lbl.setText(tr("Agrega imágenes para ver el plan."))
            return
        self.plan = cf.build_plan(self.frames, self._opts())
        pal = theme.pal
        lines = []
        for g in self.plan.groups:
            head = (tr("<b>1 luz</b> · {} · {}{} · {} × {} px") if len(g.lights) == 1 else
                    tr("<b>{} luces</b> · {} · {}{} · {} × {} px").replace("{}", str(len(g.lights)), 1)).format( _exp_text(g.exptime), tr("filtro {}").format(g.filter) if g.filter else tr("sin filtro"),
                "" if g.gain is None else tr(" · ganancia {}").format(num(g.gain, 0)), g.size[0], g.size[1])
            what = tr("se resta: {} · se divide: {}").format(
                _dark_text(g.dark), tr("flat {} ({})").format(g.flat.filter or "", len(g.flat.paths)).replace("  ", " ")
                if g.flat and g.flat.paths else tr("nada"))
            warn = "".join(f"<br><span style='color:{pal['warn']}'>⚠ {tr(w).format(*[_arg(x) for x in a])}</span>"
                           for w, a in g.warnings)
            lines.append(f"{head}<br>→ {what}{warn}")
        for kind, ref, ch in self.plan.masters_only:
            n = len(getattr(ch, "paths", []) or getattr(ch, "bias_paths", []))
            lines.append(tr("<b>Maestro de {}</b> con {} imágenes · {} · {} × {} px").format(
                tr(cf.KIND_NAMES[kind]).lower(), n, _exp_text(ref.exptime), ref.width, ref.height))
        if not lines:
            lines.append(tr("No hay luces ni imágenes de calibración para combinar."))
        if self.plan.unreadable:
            lines.append(f"<span style='color:{pal['bad']}'>" + tr("{} archivos no se pudieron leer y se omiten.").format(
                len(self.plan.unreadable)) + "</span>")
        self.plan_lbl.setText("<br><br>".join(lines))

    # ------------------------------------------------------------ correr
    def pick_out(self):
        d = choose_folder(self, "Carpeta para los maestros y las imágenes calibradas")
        if d:
            self.out_dir = d
            self.out_lbl.setText(tr("Carpeta de salida: {}").format(d))

    def run(self):
        if not self.plan or not (self.plan.groups or self.plan.masters_only):
            notify(self, "Faltan imágenes", "Agrega luces con sus darks y flats, o solo darks, flats o bias para crear maestros.",
                   "warning")
            return
        if not self.out_dir:
            self.pick_out()
            if not self.out_dir:
                return
        plan, frames, out, opts = self.plan, list(self.frames), self.out_dir, self._opts()

        def work(job):
            c = cf.Calibrator(out, opts, progress=lambda t, a, x, y: job.progress.emit(tr(t).format(*a), x, y),
                              cancelled=lambda: job.cancel)
            return c.run(plan, frames)

        self.thread = QThread(self)
        self.job = _CalJob(work)
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.progress.connect(self._progress)
        self.job.done.connect(self._done)
        self.job.failed.connect(self._failed)
        self.run_b.setEnabled(False)
        self.cancel_b.setEnabled(True)
        self.bar.setValue(0)
        self.t0 = time.time()
        self.main.set_busy(True)
        self.thread.start()

    def cancel(self):
        if self.job is not None:
            self.job.cancel = True
            self.status.setText(tr("Cancelando…"))

    def _progress(self, text, a, b):
        self.status.setText(text)
        self.bar.setValue(int(1000 * a / max(1, b)))

    def _end(self):
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(5000)
        self.thread = None
        self.job = None
        self.run_b.setEnabled(True)
        self.cancel_b.setEnabled(False)
        self.main.set_busy(False)

    def _failed(self, msg):
        self._end()
        self.status.setText("")
        notify(self, "No se pudo calibrar", msg, "warning")

    def _done(self, res):
        self._end()
        self.result = res
        self.bar.setValue(1000)
        self.status.setText(tr("Cancelado: se conserva lo que alcanzó a calibrarse.") if res.cancelled else
                            tr("Listo en {} s.").format(num(time.time() - self.t0, 1)))
        self.res_lbl.setText("<br>".join([
            tr("Maestros ({}): {}").format(len(res.masters), ", ".join(res.masters) or "—"),
            tr("Imágenes calibradas: {} (en «calibradas»)").format(len(res.outputs)),
            tr("Carpeta: {}").format(self.out_dir)] + ["• " + tr(t).format(*_localized(a)) for t, a in res.notes]))
        while self.view_btns.count():
            it = self.view_btns.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()
        for k in ("dark", "flat", "bias"):
            p = res.first.get(k)
            if p:
                self.view_btns.addWidget(button(tr("Ver {} maestro").format(k), slot=lambda _=False, p=p: self.open_in_viewer(p)))
        if res.outputs:
            self.view_btns.addWidget(button("Ver la primera calibrada", slot=lambda: self.open_in_viewer(res.outputs[0])))
        if res.pairs:
            self.view_btns.addWidget(button("Comparar antes y después", slot=self.compare,
                                            tip="Abre la primera luz original y calibrada como un cubo de 2 cuadros"))
        self.view_btns.addStretch(1)
        self.use_b.setEnabled(any(res.first.get(k) for k in ("dark", "flat", "bias")))

    def compare(self):
        if not self.result or not self.result.pairs:
            return
        src, j, out = self.result.pairs[0]
        try:
            a = read_stack(src)
            a = a[min(j, len(a) - 1)] if a.ndim == 3 else a
            b = read_stack(out)
            b = b[0] if b.ndim == 3 else b
        except Exception as exc:
            notify(self, "Comparar", tr("No se pudo leer: {}").format(exc), "warning")
            return
        if a.shape != b.shape:
            return
        v = self.main.page_by_key["img_ver"]
        self.main.go("img_ver")
        v.show_array(np.stack([a.astype(np.float32), b.astype(np.float32)]),
                     tr("{} · 1 = original, 2 = calibrada").format(os.path.basename(src)),
                     tr("Cuadro 1: original · Cuadro 2: calibrada"))
        v.diff_note()

    def open_in_viewer(self, p):
        v = self.main.page_by_key["img_ver"]
        self.main.go("img_ver")
        v.open(p)

    def use_in_analysis(self):
        if not self.result:
            return
        f = self.result.first
        s = self.main.sessions["analisis"]
        s.cal = {"on": True, "dark": f.get("dark", ""), "flat": f.get("flat", ""), "bias": f.get("bias", "")}
        self.main.toast("Listo: el modo medición usará estos maestros en cada cuadro del video. Puedes revisarlos o "
                        "apagarlos en Medición → Parámetros → Calibración.")
