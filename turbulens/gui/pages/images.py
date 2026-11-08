# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Modo «Imágenes»: calibración con darks, flats y bias, y un visor de píxeles al estilo de DS9."""

from __future__ import annotations

import csv
import os
import time

import numpy as np
from PySide6.QtWidgets import (
    QComboBox, QGridLayout, QHBoxLayout, QListWidget, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget,
)

from ...core import calibration as cal
from ...core.imageio import IMAGE_EXTS, header_text, read_stack, write_fits, write_png16
from ...i18n import integer, num, tr
from ..imageview import CMAPS, LIMITS, STRETCHES, ImageView
from ..widgets import (
    Card, HelpButton, button, choose_file, choose_files, choose_folder, free_base, free_name, hbox, label, notify,
)
from .base import Page

IMAGE_FILTER = "Imágenes (" + " ".join("*" + e for e in IMAGE_EXTS) + ");;FITS (*.fits *.fit *.fts);;Todos (*)"

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
    "<b>Calibración de imágenes</b><ul style='margin-left:-16px'>"
    "<li><b>Luces</b>: tus imágenes del cielo (las que quieres corregir).</li>"
    "<li><b>Darks</b>: con la tapa puesta, con el mismo tiempo de exposición, ganancia y temperatura que las luces. "
    "Quitan la corriente oscura y los píxeles calientes.</li>"
    "<li><b>Flats</b>: de una superficie iluminada de forma pareja (cielo del atardecer o una pantalla blanca), con el "
    "mismo foco. Corrigen el viñeteo y el polvo.</li>"
    "<li><b>Darks de flats</b> (opcional): darks con la exposición de los flats.</li>"
    "<li><b>Bias</b> (opcional): exposición más corta posible con la tapa puesta. Se usa si no hay darks.</li></ul>"
    "Cada grupo se combina en una imagen <b>maestra</b> (la mediana es robusta a rayos cósmicos). Luego "
    "cada luz se corrige así: <b>(luz − dark) ÷ flat normalizado</b>. Los maestros y las luces calibradas se guardan "
    "en FITS de 32 bits, que abren DS9, Astropy y AstroImageJ.")


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
        self.limits_c = self._combo(LIMITS, "zscale")
        self.cmap_c = self._combo(CMAPS, "gris")
        bar.addWidget(label("Escala", "small"))
        bar.addWidget(self.stretch_c)
        bar.addWidget(label("Límites", "small"))
        bar.addWidget(self.limits_c)
        bar.addWidget(label("Colores", "small"))
        bar.addWidget(self.cmap_c)
        bar.addStretch(1)
        bar.addWidget(button("Ajustar", slot=lambda: self.view.fit(), tip="Ajustar la imagen a la ventana"))
        bar.addWidget(button("1:1", slot=lambda: self.view.set_zoom(1.0), tip="Un píxel de la imagen = un píxel de la pantalla"))
        self.lay.addLayout(bar)

        row = QHBoxLayout()
        row.setSpacing(14)
        vc = Card(margins=(8, 8, 8, 8))
        self.view = ImageView()
        self.view.setMinimumHeight(460)
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

    def _combo(self, items, default):
        c = QComboBox()
        for k, t in items:
            c.addItem(t, k)
        c.setCurrentIndex([k for k, _ in items].index(default))
        c.currentIndexChanged.connect(self._display)
        return c

    def _display(self, *_):
        self.view.set_display(self.stretch_c.currentData(), self.limits_c.currentData(), self.cmap_c.currentData())
        self._range()

    def _range(self):
        if self.view.data is not None:
            self.rng.setText(tr("negro = {} · blanco = {}").format(fmt(self.view.lo), fmt(self.view.hi)))

    # ------------------------------------------------------------- abrir
    def open_dialog(self):
        p = choose_file(self, "Abrir imagen", IMAGE_FILTER)
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
        self.view.set_display(self.stretch_c.currentData(), self.limits_c.currentData(), self.cmap_c.currentData())
        self.view.set_marker(*(marker if marker else (None,)), text=marker_text)
        self._range()
        h, w = self.stack.shape[1:]
        self.info_lbl.setText(tr("{} · {} × {} px{}").format(name, w, h, tr(" · {} cuadros").format(len(self.stack))
                                                                    if len(self.stack) > 1 else ""))
        self.hdr.setPlainText(header or tr("(Esta imagen no es FITS: no tiene cabecera.)"))
        self._whole()

    def _frame_changed(self, v):
        if self.stack is not None:
            self.view.set_data(self.stack[v - 1], keep_view=True)
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
        sub = sub[np.isfinite(sub)]
        st = cal.stats(sub) if sub.size else {}
        for k, lb in self.reg_vals.items():
            v = st.get(k)
            lb.setText(integer(v) if k == "n" and v is not None else fmt(v, 3))
        self.reg_box.setText(tr("x {}–{} · y {}–{} ({} × {} px)").format(x0 + 1, x1 + 1, y0 + 1, y1 + 1, x1 - x0 + 1, y1 - y0 + 1))
        self.reg_msg.setText("")

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
GROUPS = [("luces", "Luces (imágenes del cielo)", True), ("darks", "Darks", False), ("flats", "Flats", False),
          ("darkflats", "Darks de los flats (opcional)", False), ("bias", "Bias (opcional)", False)]
METHODS = [("mediana", "Mediana (recomendado)"), ("sigma", "Media con recorte de 3 σ"), ("media", "Media")]


class CalibrationPage(Page):
    title = "Calibración: darks y flats"
    subtitle = "Crea las imágenes maestras y corrige tus imágenes del cielo"
    help_text = CAL_PAGE_HELP

    def __init__(self, main):
        super().__init__(main)
        self.files = {k: [] for k, _, _ in GROUPS}
        self.lists = {}
        self.counts = {}
        self.masters = {}
        self.outputs = []
        grid = QGridLayout()
        grid.setSpacing(12)
        for i, (k, t, _) in enumerate(GROUPS):
            c = Card(t, margins=(12, 10, 12, 10))
            lst = QListWidget()
            lst.setMinimumHeight(90)
            lst.setMaximumHeight(130)
            self.lists[k] = lst
            self.counts[k] = label("0 archivos", "small")
            c.add(lst, hbox(button("Agregar…", slot=lambda _=False, k=k: self.add_files(k)),
                            button("Quitar todo", slot=lambda _=False, k=k: self.clear(k)), "stretch", self.counts[k]))
            grid.addWidget(c, i // 3, i % 3)
        oc = Card("Opciones", margins=(12, 10, 12, 10))
        self.method = QComboBox()
        for k, t in METHODS:
            self.method.addItem(t, k)
        self.out_dir = ""
        self.out_lbl = label("Carpeta de salida: (sin elegir)", "small", wrap=True)
        oc.add(hbox(label("Combinar con"), self.method, "stretch"),
               hbox(button("Carpeta de salida…", slot=self.pick_out), "stretch"), self.out_lbl)
        grid.addWidget(oc, 1, 2)
        self.lay.addLayout(grid)
        self.run_b = button("Crear maestros y calibrar", "primary", self.run)
        self.status = label("", "small", wrap=True)
        self.lay.addLayout(hbox(self.run_b, 8, self.status, "stretch"))
        rc = Card("Resultado")
        self.res_lbl = label("Aún no se ha calibrado nada.", "small", wrap=True)
        self.view_btns = hbox(spacing=8)
        rc.add(self.res_lbl, self.view_btns)
        self.use_b = button("Usar estos maestros en el análisis de video", slot=self.use_in_analysis,
                            tip="El dark, el flat y el bias se aplican a cada cuadro del video antes de medir")
        self.use_b.setEnabled(False)
        rc.add(hbox(self.use_b, HelpButton(
            "Los maestros se aplican cuadro a cuadro al video del DIMM (Análisis → Parámetros → Calibración). "
            "Deben tener el mismo tamaño en píxeles que el video. Con darks y flats las medidas de centroide "
            "son más precisas en estrellas débiles."), "stretch"))
        self.lay.addWidget(rc)
        self.lay.addStretch(1)

    def add_files(self, k):
        ps = choose_files(self, "Elegir imágenes", IMAGE_FILTER)
        for p in ps:
            if p not in self.files[k]:
                self.files[k].append(p)
        self._sync(k)

    def clear(self, k):
        self.files[k] = []
        self._sync(k)

    def _sync(self, k):
        lst = self.lists[k]
        lst.clear()
        for p in self.files[k]:
            lst.addItem(os.path.basename(p))
        self.counts[k].setText(tr("{} archivos").format(len(self.files[k])))

    def pick_out(self):
        d = choose_folder(self, "Carpeta para los maestros y las imágenes calibradas")
        if d:
            self.out_dir = d
            self.out_lbl.setText(tr("Carpeta de salida: {}").format(d))

    def _load(self, paths):
        out = []
        for p in paths:
            a = read_stack(p)
            out.extend(a if a.ndim == 3 else [a])
        return out

    def run(self):
        f = self.files
        if not any(f[k] for k in ("darks", "flats", "bias")):
            notify(self, "Faltan imágenes", "Agrega al menos darks, flats o bias para crear un maestro.", "warning")
            return
        if not self.out_dir:
            self.pick_out()
            if not self.out_dir:
                return
        method = self.method.currentData()
        t0 = time.time()
        self.run_b.setEnabled(False)
        try:
            self._step("Leyendo y combinando los bias…")
            bias = cal.combine(self._load(f["bias"]), method) if f["bias"] else None
            self._step("Leyendo y combinando los darks…")
            dark = cal.combine(self._load(f["darks"]), method) if f["darks"] else None
            dflat = cal.combine(self._load(f["darkflats"]), method) if f["darkflats"] else None
            self._step("Leyendo y combinando los flats…")
            flat = cal.master_flat(self._load(f["flats"]), dflat, bias, method) if f["flats"] else None
            base = free_base(self.out_dir, "turbulens_maestro")
            self.masters = {}
            for k, a in (("bias", bias), ("dark", dark), ("flat", flat)):
                if a is not None:
                    p = os.path.join(self.out_dir, f"{base}_{k}.fits")
                    write_fits(p, a, {"IMAGETYP": f"MASTER {k.upper()}", "NCOMBINE": len(f["darks" if k == "dark" else
                                                                                             ("flats" if k == "flat" else "bias")]),
                                      "COMBINE": method})
                    self.masters[k] = p
            self.outputs = []
            n = 0
            for p in f["luces"]:
                a = read_stack(p)
                frames = a if a.ndim == 3 else [a]
                for j, img in enumerate(frames):
                    self._step(tr("Calibrando {} ({} de {})…").format(os.path.basename(p), j + 1, len(frames)))
                    out = cal.apply_calibration(img, dark, flat, bias)
                    suf = f"_{j + 1:04d}" if len(frames) > 1 else ""
                    q = free_name(self.out_dir, os.path.splitext(os.path.basename(p))[0] + suf + "_calibrada.fits")
                    write_fits(q, out, {"CALSTAT": "".join(c for c, m in (("B", bias), ("D", dark), ("F", flat)) if m is not None)})
                    self.outputs.append(q)
                    n += 1
        except Exception as exc:
            self.status.setText("")
            notify(self, "No se pudo calibrar", str(exc), "warning")
            return
        finally:
            self.run_b.setEnabled(True)
        self.status.setText(tr("Listo en {} s.").format(num(time.time() - t0, 1)))
        parts = [tr("Maestros: {}").format(", ".join(os.path.basename(p) for p in self.masters.values()) or "—"),
                 tr("Imágenes calibradas: {}").format(n), tr("Carpeta: {}").format(self.out_dir)]
        self.res_lbl.setText("<br>".join(parts))
        while self.view_btns.count():
            it = self.view_btns.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for k, p in self.masters.items():
            self.view_btns.addWidget(button(tr("Ver {} maestro").format(k), slot=lambda _=False, p=p: self.open_in_viewer(p)))
        if self.outputs:
            self.view_btns.addWidget(button("Ver la primera calibrada", slot=lambda: self.open_in_viewer(self.outputs[0])))
        self.view_btns.addStretch(1)
        self.use_b.setEnabled(bool(self.masters))

    def _step(self, text):
        from PySide6.QtCore import QEventLoop
        from PySide6.QtWidgets import QApplication

        self.status.setText(tr(text))
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    def open_in_viewer(self, p):
        v = self.main.page_by_key["img_ver"]
        self.main.go("img_ver")
        v.open(p)

    def use_in_analysis(self):
        s = self.main.sessions["analisis"]
        s.cal = {"on": True, "dark": self.masters.get("dark", ""), "flat": self.masters.get("flat", ""),
                 "bias": self.masters.get("bias", "")}
        self.main.toast("Listo: el análisis de video usará estos maestros. Puedes revisarlos o apagarlos en "
                        "Análisis → Parámetros → Calibración.")
