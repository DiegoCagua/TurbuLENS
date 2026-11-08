# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Modo «Satélite»: imágenes de GOES-Este (16 o 19) para ver las nubes sobre el sitio de observación."""

from __future__ import annotations

import csv
import datetime as dt
import os

import numpy as np
from PySide6.QtCore import QDate, QDateTime, QObject, QThread, QTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QGridLayout, QHeaderView, QProgressBar, QSpinBox, QTableWidget,
    QTableWidgetItem, QTimeEdit,
)

from ...core import goes
from ...core.imageio import write_fits, write_png16
from ...i18n import integer, num, tr
from ..imageview import ImageView
from ..widgets import Card, DecSpin, button, choose_files, choose_folder, free_name, hbox, label, notify, vbox
from .base import Page

GOES_HELP = (
    "<b>¿Para qué sirve?</b> Para saber si había nubes sobre tu sitio cuando grabaste el video del DIMM, o para "
    "planear una noche de observación.<br><br>"
    "TurbuLENS busca en los archivos abiertos de NOAA la imagen de <b>disco completo</b> del satélite "
    "<b>GOES-Este</b> más cercana a la fecha y hora que elijas, la descarga en tu carpeta y lee el valor del píxel en tus "
    "coordenadas.<ul style='margin-left:-16px'>"
    "<li><b>Satélite</b>: GOES-16 hasta el 4 de abril de 2025 (15:10 UTC) y GOES-19 desde entonces. En «Automático» se "
    "elige solo según la fecha.</li>"
    "<li><b>Canales 1–6</b> (visible e infrarrojo cercano): reflectancia, solo útiles de día.</li>"
    "<li><b>Canales 7–16</b> (infrarrojo): temperatura de brillo en kelvin, de día y de noche. Para nubes, el "
    "<b>13</b> es el más usado: entre más fría, más alta la nube.</li>"
    "<li>Hay una imagen de disco completo cada 10 minutos.</li></ul>"
    "Los archivos son grandes (≈25 MB por canal de 2 km; el canal 2 pesa ≈330 MB). Si ya están en la carpeta, no se "
    "descargan otra vez.")


class _Job(QObject):
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
            self.failed.emit(str(exc))


class GoesPage(Page):
    title = "Satélite GOES"
    subtitle = "Nubes sobre tu sitio de observación, canal por canal"
    help_text = GOES_HELP

    def __init__(self, main):
        super().__init__(main)
        self.thread = None
        self.job = None
        self.readings: list[goes.ChannelReading] = []
        st = self.main.settings

        top = QGridLayout()
        top.setSpacing(12)
        when = Card("Fecha, hora y lugar", margins=(14, 12, 14, 12))
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setMinimumDate(QDate(2017, 12, 18))
        self.time = QTimeEdit()
        self.time.setDisplayFormat("HH:mm")
        self.zone = QComboBox()
        self.zone.addItem("Hora de Colombia (UTC−5)", -5)
        self.zone.addItem("UTC", 0)
        self.zone.setCurrentIndex(int(st.value("goes/zona", 0, type=int)))
        now = QDateTime.currentDateTimeUtc().addSecs(int(self.zone.currentData()) * 3600 - 3600)  # hace una hora
        self.date.setDate(now.date())
        self.time.setTime(QTime(now.time().hour(), 0))
        self.lat = DecSpin()
        self.lat.setRange(-81, 81)
        self.lat.setDecimals(4)
        self.lat.setValue(float(st.value("goes/lat", goes.OAN_LAT)))
        self.lon = DecSpin()
        self.lon.setRange(-180, 180)
        self.lon.setDecimals(4)
        self.lon.setValue(float(st.value("goes/lon", goes.OAN_LON)))
        self.sat = QComboBox()
        self.sat.addItem("Automático según la fecha", 0)
        self.sat.addItem("GOES-16", 16)
        self.sat.addItem("GOES-19", 19)
        self.sat_lbl = label("", "small", wrap=True)
        self.half = QSpinBox()
        self.half.setRange(20, 1500)
        self.half.setSingleStep(50)
        self.half.setValue(int(st.value("goes/recorte", 300, type=int)))
        self.half.setSuffix(" km")
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.addWidget(label("Fecha"), 0, 0)
        g.addLayout(hbox(self.date, self.time, self.zone, "stretch"), 0, 1)
        g.addWidget(label("Latitud (°, norte +)"), 1, 0)
        g.addLayout(hbox(self.lat, label("Longitud (°, este +)"), self.lon,
                         button("OAN, Bogotá", slot=self._oan, tip="Observatorio Astronómico Nacional"), "stretch"), 1, 1)
        g.addWidget(label("Satélite"), 2, 0)
        g.addLayout(hbox(self.sat, self.sat_lbl, 1), 2, 1)
        g.addWidget(label("Recorte"), 3, 0)
        g.addLayout(hbox(self.half, label("de lado alrededor del punto", "small"), "stretch"), 3, 1)
        when.add(g)
        top.addWidget(when, 0, 0)

        chc = Card("Canales", margins=(14, 12, 14, 12))
        self.checks = {}
        cg = QGridLayout()
        cg.setHorizontalSpacing(14)
        cg.setVerticalSpacing(2)
        saved = str(st.value("goes/canales", "13")).split(",")
        for i, (ch, (wl, name, res, mb)) in enumerate(goes.CHANNELS.items()):
            cb = QCheckBox(f"{ch:>2} · {num(wl, 2)} µm · {tr(name)}")
            cb.setToolTip(tr(goes.CHANNEL_INFO[ch]) + "\n" + tr("Resolución {} km · archivo ≈{} MB").format(num(res, 1), mb))
            cb.setChecked(str(ch) in saved)
            cb.toggled.connect(self._update_size)
            self.checks[ch] = cb
            cg.addWidget(cb, i % 4, i // 4)
        chc.add(cg)
        self.size_lbl = label("", "small")
        chc.add(hbox(button("Solo el 13 (nubes)", slot=lambda: self._pick([13])),
                     button("Infrarrojos 7–16", slot=lambda: self._pick(range(7, 17))),
                     button("Todos", slot=lambda: self._pick(range(1, 17))),
                     button("Ninguno", slot=lambda: self._pick([])), "stretch", self.size_lbl))
        top.addWidget(chc, 1, 0)
        self.lay.addLayout(top)

        self.folder = str(st.value("goes/carpeta", ""))
        self.folder_lbl = label("", "small", wrap=True)
        self.run_b = button("Buscar, descargar y leer", "primary", self.start)
        self.cancel_b = button("Cancelar", slot=self.cancel)
        self.cancel_b.setEnabled(False)
        self.folder_lbl.setWordWrap(False)
        self.lay.addLayout(hbox(button("Carpeta de descarga…", slot=self.pick_folder), self.folder_lbl, "stretch",
                                button("Leer archivos ya descargados…", slot=self.open_local,
                                       tip="Archivos OR_ABI-L2-CMIPF-…nc de GOES-16 o GOES-19")))
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.state = label("", "small", wrap=True)
        self.lay.addLayout(hbox(self.run_b, self.cancel_b, self.bar, 1))
        self.lay.addWidget(self.state)

        res = Card("Valores en tus coordenadas", margins=(12, 10, 12, 10))
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Canal", "λ (µm)", "Valor", "Unidad", "Promedio 3×3", "Lectura",
                                              "Escaneo (UTC)", "Satélite"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setMinimumHeight(200)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.preview = ImageView()
        self.preview.setMinimumSize(320, 300)
        self.prev_lbl = label("", "small", wrap=True)
        res.add(self.table)
        self.res_msg = label("", "small", wrap=True)
        res.add(self.res_msg)
        self.lay.addWidget(res)
        prev = Card("Recorte del canal elegido", margins=(12, 10, 12, 10))
        self.preview.setFixedSize(420, 360)
        prev.add(hbox(self.preview, 12, vbox(self.prev_lbl, hbox(button("Abrir en el visor de píxeles", slot=self.open_viewer),
                                                                 "stretch"), "stretch")))
        self.lay.addWidget(prev)
        self.lay.addWidget(label("Datos: NOAA GOES-R Series, producto ABI L2 Cloud and Moisture Imagery (CMIPF), "
                                 "repositorio abierto NOAA Open Data Dissemination en Amazon Web Services.", "small", wrap=True))
        self.lay.addStretch(1)
        for w in (self.date, self.time):
            (w.dateChanged if w is self.date else w.timeChanged).connect(self._update_sat)
        self.zone.currentIndexChanged.connect(self._update_sat)
        self.sat.currentIndexChanged.connect(self._update_sat)
        self._update_sat()
        self._update_size()
        self._update_folder()

    # ---------------------------------------------------------- opciones
    def _oan(self):
        self.lat.setValue(goes.OAN_LAT)
        self.lon.setValue(goes.OAN_LON)

    def _pick(self, chans):
        chans = set(chans)
        for ch, cb in self.checks.items():
            cb.setChecked(ch in chans)

    def channels(self) -> list[int]:
        return [ch for ch, cb in self.checks.items() if cb.isChecked()]

    def _update_size(self, *_):
        chans = self.channels()
        mb = sum(goes.CHANNELS[c][3] for c in chans)
        self.size_lbl.setText(tr("{} canales · ≈{} MB").format(len(chans), integer(mb)) if chans else tr("Elige al menos un canal"))

    def when_utc(self) -> dt.datetime:
        d, t = self.date.date(), self.time.time()
        local = dt.datetime(d.year(), d.month(), d.day(), t.hour(), t.minute())
        off = int(self.zone.currentData())
        return (local - dt.timedelta(hours=off)).replace(tzinfo=dt.timezone.utc)

    def _update_sat(self, *_):
        w = self.when_utc()
        auto = goes.satellite_for(w)
        chosen = int(self.sat.currentData()) or auto
        txt = tr("{} UTC → GOES-{}").format(w.strftime("%Y-%m-%d %H:%M"), chosen)
        if not self.sat.currentData():
            txt += tr(" (automático: GOES-19 desde el 4 abr 2025, antes GOES-16)")
        self.sat_lbl.setText(txt)

    def _update_folder(self):
        self.folder_lbl.setText(tr("Carpeta: {}").format(self.folder) if self.folder else tr("Carpeta: (sin elegir)"))

    def pick_folder(self):
        d = choose_folder(self, "Carpeta para las imágenes del satélite")
        if d:
            self.folder = d
            self.main.settings.setValue("goes/carpeta", d)
            self._update_folder()

    def _save_settings(self):
        st = self.main.settings
        st.setValue("goes/lat", self.lat.value())
        st.setValue("goes/lon", self.lon.value())
        st.setValue("goes/zona", self.zone.currentIndex())
        st.setValue("goes/recorte", self.half.value())
        st.setValue("goes/canales", ",".join(str(c) for c in self.channels()))

    # ------------------------------------------------------------ trabajo
    def start(self):
        chans = self.channels()
        if not chans:
            notify(self, "Canales", "Elige al menos un canal.", "warning")
            return
        if not self.folder:
            self.pick_folder()
            if not self.folder:
                return
        self._save_settings()
        when = self.when_utc()
        sat = int(self.sat.currentData()) or None
        lat, lon, half, folder = self.lat.value(), self.lon.value(), self.half.value() / 2, self.folder

        def work(job):
            job.progress.emit(tr("Buscando las imágenes más cercanas a {} UTC…").format(when.strftime("%Y-%m-%d %H:%M")), 0, 1)
            used, files = goes.find_files(when, chans, sat)
            if not files:
                raise RuntimeError(tr("No se encontraron imágenes de GOES para esa fecha y hora (o no hay conexión a "
                                      "internet)."))
            total = sum(f.size for f in files)
            base = 0
            out = []
            for i, f in enumerate(files):
                def prog(a, b, i=i, f=f):
                    job.progress.emit(tr("Descargando canal {} ({} de {}): {} / {} MB").format(
                        f.channel, i + 1, len(files), integer(a / 1e6), integer(b / 1e6)), base + a, total)
                    return not job.cancel
                path = goes.download(f, folder, prog)
                base += f.size
                job.progress.emit(tr("Leyendo canal {}…").format(f.channel), base, total)
                out.append(goes.read_point(path, lat, lon, half))
                if job.cancel:
                    raise InterruptedError(tr("Cancelado"))
            return out

        self._run(work)

    def open_local(self):
        ps = choose_files(self, "Archivos de GOES (NetCDF)", "GOES ABI L2 CMIP (*.nc);;Todos (*)")
        if not ps:
            return
        lat, lon, half = self.lat.value(), self.lon.value(), self.half.value() / 2
        self._save_settings()

        def work(job):
            out = []
            for i, p in enumerate(ps):
                job.progress.emit(tr("Leyendo {} ({} de {})…").format(os.path.basename(p), i + 1, len(ps)), i, len(ps))
                out.append(goes.read_point(p, lat, lon, half))
            return out

        self._run(work)

    def _run(self, fn):
        self.thread = QThread(self)
        self.job = _Job(fn)
        self.job.moveToThread(self.thread)
        self.thread.started.connect(self.job.run)
        self.job.progress.connect(self._progress)
        self.job.done.connect(self._done)
        self.job.failed.connect(self._failed)
        self.run_b.setEnabled(False)
        self.cancel_b.setEnabled(True)
        self.bar.setValue(0)
        self.main.set_busy(True)
        self.thread.start()

    def cancel(self):
        if self.job is not None:
            self.job.cancel = True
            self.state.setText(tr("Cancelando…"))

    def _progress(self, text, a, b):
        self.state.setText(text)
        self.bar.setValue(int(1000 * a / max(1, b)))

    def _end(self):
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(3000)
        self.thread = None
        self.job = None
        self.run_b.setEnabled(True)
        self.cancel_b.setEnabled(False)
        self.main.set_busy(False)

    def _failed(self, msg):
        self._end()
        self.state.setText(tr("No se pudo completar: {}").format(msg))

    def _done(self, readings):
        self._end()
        self.bar.setValue(1000)
        self.show_readings(readings)

    # ---------------------------------------------------------- resultados
    def show_readings(self, readings):
        self.readings = sorted(readings, key=lambda r: r.channel)
        t = self.table
        t.setRowCount(len(self.readings))
        for i, r in enumerate(self.readings):
            wl = goes.CHANNELS.get(r.channel, (float("nan"),))[0]
            dec = 4 if r.channel <= 6 else 2
            tmpl, c = goes.describe_value(r.channel, r.value)
            reading = tr(tmpl).format(num(c, 0)) if "{}" in tmpl else tr(tmpl)
            if not r.visible:
                reading = tr("Fuera del disco visible")
            vals = [str(r.channel), num(wl, 2), num(r.value, dec) if np.isfinite(r.value) else "—", tr(r.unit),
                    num(r.mean3, dec) if np.isfinite(r.mean3) else "—", reading,
                    r.start.strftime("%Y-%m-%d %H:%M") if r.start else "—", f"GOES-{r.sat}" if r.sat else "—"]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setToolTip(v)
                if j in (0, 1, 2, 4):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                t.setItem(i, j, it)
        msg = []
        saved = self._save_outputs()
        if saved:
            msg.append(tr("Guardado en la carpeta: {}").format(", ".join(os.path.basename(p) for p in saved[:4])
                                                               + (" …" if len(saved) > 4 else "")))
        self.res_msg.setText(" ".join(msg))
        self.state.setText(tr("Listo: {} canales leídos.").format(len(self.readings)))
        if self.readings:
            t.selectRow(0)

    def _save_outputs(self) -> list[str]:
        folder = self.folder or (os.path.dirname(self.readings[0].path) if self.readings else "")
        if not folder or not self.readings:
            return []
        out = []
        r0 = self.readings[0]
        stamp = r0.start.strftime("%Y%m%d_%H%M") if r0.start else "goes"
        p = free_name(folder, f"turbulens_goes_{stamp}_valores.csv")
        from ... import citation_apa

        try:
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow([tr("canal"), tr("longitud_onda_um"), tr("valor"), tr("unidad"), tr("promedio_3x3"), tr("latitud"),
                            tr("longitud"), tr("columna"), tr("fila"), tr("escaneo_utc"), tr("satelite"), tr("archivo")])
                for r in self.readings:
                    w.writerow([r.channel, goes.CHANNELS.get(r.channel, ("",))[0], f"{r.value:.6g}", r.unit, f"{r.mean3:.6g}",
                                r.lat, r.lon, f"{r.col:.2f}", f"{r.row:.2f}",
                                r.start.strftime("%Y-%m-%dT%H:%M:%SZ") if r.start else "", r.sat, os.path.basename(r.path)])
                w.writerow([])
                w.writerow([tr("Generado con TurbuLENS · ") + citation_apa()])
            out.append(p)
            for r in self.readings:
                if r.cutout is None:
                    continue
                b = f"turbulens_goes_{stamp}_C{r.channel:02d}_recorte"
                q = free_name(folder, b + ".fits")
                write_fits(q, r.cutout, {"TELESCOP": f"GOES-{r.sat}", "INSTRUME": "ABI", "FILTER": f"C{r.channel:02d}",
                                         "WAVELEN": goes.CHANNELS.get(r.channel, (0,))[0], "BUNIT": r.unit,
                                         "DATE-OBS": r.start.strftime("%Y-%m-%dT%H:%M:%S") if r.start else None,
                                         "SITELAT": r.lat, "SITELONG": r.lon, "PIXKM": round(r.pixel_km, 4),
                                         "ROW0": r.cut_origin[0], "COL0": r.cut_origin[1]})
                out.append(q)
                fin = r.cutout[np.isfinite(r.cutout)]
                if fin.size:
                    lo, hi = np.percentile(fin, [0.5, 99.5])
                    if r.channel > 6:  # en infrarrojo, nubes frías en blanco (como en las imágenes del tiempo)
                        png = -r.cutout
                        lo, hi = -hi, -lo
                    else:
                        png = r.cutout
                    write_png16(free_name(folder, b + ".png"), np.nan_to_num(png, nan=lo), lo, hi)
        except OSError as exc:
            self.res_msg.setText(tr("No se pudieron guardar los resultados: {}").format(exc))
        return out

    def _selected(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self.readings[rows[0].row()] if rows and rows[0].row() < len(self.readings) else None

    def _show_selected(self):
        r = self._selected()
        if r is None or r.cutout is None:
            self.preview.set_data(None)
            self.prev_lbl.setText(tr("Sin recorte: el punto no se ve desde el satélite.") if r else "")
            return
        img = -r.cutout if r.channel > 6 else r.cutout
        self.preview.set_data(img)
        self.preview.set_display("lineal", "p995", "gris")
        self.preview.set_marker(r.col - r.cut_origin[1], r.row - r.cut_origin[0])
        h, w = r.cutout.shape
        self.prev_lbl.setText(tr("Canal {} · {} × {} px de {} km · el círculo rojo es tu punto. En infrarrojo las nubes "
                                 "frías se ven blancas.").format(r.channel, w, h, num(r.pixel_km, 2)))

    def open_viewer(self):
        r = self._selected()
        if r is None or r.cutout is None:
            return
        v = self.main.page_by_key["img_ver"]
        self.main.go("img_ver")
        hdr = "\n".join([f"GOES-{r.sat}  ABI  C{r.channel:02d}  {goes.CHANNELS.get(r.channel, ('',))[0]} um",
                         f"{tr('Escaneo (UTC)')}: {r.start:%Y-%m-%d %H:%M:%S}" if r.start else "",
                         f"{tr('Latitud')}: {r.lat}  {tr('Longitud')}: {r.lon}",
                         f"{tr('Unidad')}: {tr(r.unit)}  ·  {tr('Píxel')}: {num(r.pixel_km, 2)} km",
                         f"{tr('Archivo')}: {os.path.basename(r.path)}"])
        v.show_array(r.cutout, f"GOES-{r.sat} C{r.channel:02d}", hdr,
                     marker=(r.col - r.cut_origin[1], r.row - r.cut_origin[0]))
