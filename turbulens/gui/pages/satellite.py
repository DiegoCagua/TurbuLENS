# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Modo «Satélite»: imágenes de GOES-Este (16 o 19) para ver las nubes sobre el sitio y estimar el seeing de una noche."""

from __future__ import annotations

import csv
import datetime as dt
import math
import os

import numpy as np
from PySide6.QtCore import QDate, QDateTime, QObject, QThread, QTime, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QGridLayout, QHBoxLayout, QHeaderView, QProgressBar, QSpinBox,
    QTableWidget, QTableWidgetItem, QTimeEdit,
)

from ... import charts
from ...charts import ChartSpec, Series
from ...core import goes, mapdata
from ...core import satseeing as ss
from ...core.imageio import write_fits, write_png16
from ...i18n import integer, num, sci, tr
from ..imageview import ImageView
from ..theme import theme
from ..widgets import Card, DecSpin, HelpButton, button, choose_files, choose_folder, hbox, label, notify, vbox
from .base import Page

MIN_CUT_KM = 10  # 5 píxeles de 2 km: con menos no hay imagen útil

GOES_HELP = (
    "<b>¿Para qué sirve?</b> Para saber si había nubes sobre tu sitio cuando grabaste el video del DIMM, para "
    "planear una noche de observación y para <b>estimar el seeing</b> a lo largo de una noche con tres canales "
    "infrarrojos.<br><br>"
    "TurbuLENS busca en los archivos abiertos de NOAA las imágenes de <b>disco completo</b> del satélite "
    "<b>GOES-Este</b> más cercanas a cada hora que elijas y lee el valor en tus coordenadas.<ul style='margin-left:-16px'>"
    "<li><b>Horas</b>: «Desde» y «Hasta» con un <b>intervalo</b> de 30 o 60 minutos (o una sola imagen). Si «Hasta» es "
    "menor que «Desde», la serie pasa la medianoche.</li>"
    "<li><b>Seeing</b>: activa «Calcular el seeing» y se usan los canales 9, 13 y 16. Necesita al menos tres horas de "
    "noche para calcular la tendencia.</li>"
    "<li><b>Lectura</b>: «solo la zona» pide al servidor únicamente las partes del archivo que cubren tu recorte "
    "(≈2 MB por canal en lugar de ≈25 MB).</li>"
    "<li><b>Resultados</b>: cada evaluación se guarda en una subcarpeta nueva, "
    "<i>evaluadas_dia_AAAAMMDD_HH-HH_fecha_hora</i>, para que nunca se sobrescriba.</li></ul>"
    "En la página <b>«Cómo funciona»</b> está la explicación de cada canal y del método.")

INFO_GOES = (
    "Los <b>GOES</b> (Geostationary Operational Environmental Satellites) de NOAA giran a 35 786 km de altura sobre el "
    "ecuador, a la misma velocidad que la Tierra: desde el suelo parecen quietos. <b>GOES-Este</b> está sobre la "
    "longitud 75,2° O, casi encima de Colombia (GOES-16 hasta el 4 de abril de 2025 y GOES-19 desde entonces). Su "
    "cámara, el <b>ABI</b> (Advanced Baseline Imager), toma una imagen del disco completo de la Tierra cada 10 minutos "
    "en <b>16 canales</b>: 6 de luz visible e infrarrojo cercano, que reflejan la luz del Sol y solo sirven de día, y "
    "10 infrarrojos que miden la <b>temperatura de brillo</b> (la temperatura a la que un cuerpo negro emitiría esa "
    "radiación), de día y de noche. El píxel mide 2 km bajo el satélite (0,5–1 km en algunos canales visibles) y un "
    "poco más lejos de él.<br><br>"
    "Cada canal «ve» a una altura distinta: donde el aire es transparente a esa longitud de onda, el satélite ve el suelo "
    "o el tope de las nubes; donde un gas (vapor de agua, CO₂, ozono) absorbe, ve la capa de la atmósfera en la que ese "
    "gas emite. Comparando canales se obtiene información de varias alturas a la vez.")
INFO_SEEING_1 = (
    "La turbulencia óptica nace donde se mezclan capas de aire con temperaturas distintas. Cavazzani, Ortolani y Zitelli "
    "(2012) propusieron medir esa inestabilidad con tres canales infrarrojos que ven a alturas diferentes: vapor de "
    "agua (capas medias), infrarrojo limpio (suelo o tope de nubes) y CO₂ (capas altas). En GOES-16/19 son los canales "
    "<b>9</b> (6,9 µm), <b>13</b> (10,3 µm) y <b>16</b> (13,3 µm).<br><br>"
    "<b>1. Función de estabilidad</b> (en kelvin), con las temperaturas promediadas en un cuadro alrededor del sitio "
    "(1° × 1° como en el artículo, o 3 × 3 píxeles):")
INFO_SEEING_2 = (
    "<b>2. Tendencia de la noche.</b> Con todas las horas usadas se ajusta una recta F<sup>tend</sup>(t). Lo que mide la "
    "turbulencia es cuánto se <b>aparta</b> F de esa tendencia en cada hora: un cielo estable sigue la tendencia; uno "
    "turbulento la cruza de un lado a otro.<br><br>"
    "<b>3. Turbulencia entre 4 y 8 km</b>, con θ el ángulo cenital del satélite visto desde el sitio (≈5,6° en Bogotá) y "
    "z el espesor de la capa (4 km):")
INFO_SEEING_3 = (
    "<b>4. Seeing</b>, con el modelo de Kolmogorov (r<sub>0</sub> y ε = 0,98 λ/r<sub>0</sub>); con λ en metros sale en "
    "radianes, y TurbuLENS lo pasa a segundos de arco (× 206 265):")
INFO_SUN = (
    "<b>El Sol.</b> De día el Sol calienta el suelo y las capas bajas, y las temperaturas de brillo cambian por razones "
    "que no son la turbulencia nocturna; el método se calibró solo con datos de noche. TurbuLENS calcula la altura del "
    "Sol en cada hora y, según el criterio que elijas, deja fuera de la tendencia y del seeing las horas de día o también "
    "las de crepúsculo (se ven en gris en las gráficas).<br><br>"
    "<b>Alcance.</b> Es un método <b>empírico</b>: se comparó con el seeing medido en Paranal (Chile) y en el Roque de los Muchachos (La Palma), mide "
    "solo la capa de 4 a 8 km (no la turbulencia cerca del suelo, que suele dominar en un sitio urbano) y las nubes lo "
    "invalidan. Sirve para comparar horas y noches en un mismo sitio; para un valor absoluto, compáralo con el DIMM. Si "
    "cambias z, el seeing cambia como z<sup>−3/5</sup>.<br><br>"
    "<span style='font-size:12px'>Cavazzani, S., Ortolani, S. y Zitelli, V. (2012). <i>Site testing at astronomical "
    "sites: seeing evaluation from satellite based data</i>. arXiv:1112.3497. · Datos: NOAA GOES-R Series, ABI L2 Cloud "
    "and Moisture Imagery (CMIPF), NOAA Open Data Dissemination. · Mapa: Natural Earth (dominio público).</span>")

CHANNEL_DETAIL = {
    1: "Luz azul reflejada. Aerosoles, humo y polvo; calidad del aire. Solo de día.",
    2: "Luz roja reflejada, el canal más nítido (0,5 km). Nubes bajas y tormentas de día.",
    3: "Infrarrojo cercano «vegetación»: vegetación sana, quemas, inundaciones. Solo de día.",
    4: "Cirros: el vapor de agua de abajo absorbe y solo se ven las nubes delgadas y altas. De día.",
    5: "Nieve y hielo: distingue nubes de hielo de nieve en el suelo y nubes de agua. De día.",
    6: "Tamaño de las partículas de las nubes y puntos calientes de incendios. De día.",
    7: "Infrarrojo de onda corta (3,9 µm): niebla y nubes bajas de noche, incendios.",
    8: "Vapor de agua en la troposfera alta (≈ 300–400 hPa): corrientes en chorro, ondas de montaña.",
    9: "Vapor de agua en la troposfera media (≈ 400–500 hPa). Para el seeing: capas medias.",
    10: "Vapor de agua en la troposfera baja (≈ 500–700 hPa): humedad baja, dióxido de azufre.",
    11: "Fase de las nubes (agua o hielo), polvo y ceniza.",
    12: "Ozono: ozono total, corrientes en chorro y aire de la estratosfera.",
    13: "Infrarrojo «limpio» (10,3 µm): el aire casi no absorbe; ve el suelo o el tope de las nubes. Base de la "
        "detección de nubes y del seeing.",
    14: "Infrarrojo clásico (11,2 µm): nubes y temperatura de la superficie.",
    15: "Infrarrojo «sucio» (12,3 µm): humedad baja, polvo y ceniza volcánica.",
    16: "Dióxido de carbono (13,3 µm): el CO₂ emite desde capas altas; altura de los topes de nubes. Para el seeing: "
        "capas altas.",
}


def channels_table_html() -> str:
    rows = []
    for ch, (wl, name, res, _mb) in goes.CHANNELS.items():
        bold = " style='font-weight:600'" if ch in ss.SEEING_CHANNELS else ""
        rows.append(f"<tr{bold}><td align='right'>{ch}</td><td align='right'>{num(wl, 2)}</td><td>{tr(name)}</td>"
                    f"<td align='right'>{num(res, 1)}</td><td>{tr(CHANNEL_DETAIL[ch])}</td></tr>")
    head = tr("<table cellspacing='0' cellpadding='4' border='0'><tr><th>Canal</th><th>λ (µm)</th><th>Nombre</th>"
              "<th>km</th><th>Para qué sirve</th></tr>")
    foot = tr("</table><p style='font-size:12px'>En negrita, los canales que se usan para el seeing.</p>")
    return head + "".join(rows) + foot


class GoesInfoPage(Page):
    title = "Cómo funciona"
    subtitle = "El satélite GOES, sus canales y el seeing desde el espacio"

    def __init__(self, main):
        super().__init__(main)
        from ..widgets import FormulaLabel

        def text(t):
            lb = label(t, wrap=True, rich=True)
            lb.setStyleSheet("font-size:14px; line-height:150%;")
            return lb

        c1 = Card("El satélite GOES")
        c1.add(text(INFO_GOES))
        self.lay.addWidget(c1)
        c2 = Card("Qué mide cada canal")
        self.table_lbl = text("")
        c2.add(self.table_lbl)
        self.lay.addWidget(c2)
        c3 = Card("Seeing desde el satélite")
        c3.add(text(INFO_SEEING_1))
        for name in ("goes_f",):
            c3.add(self._formula(FormulaLabel(name)))
        c3.add(text(INFO_SEEING_2), self._formula(FormulaLabel("goes_cn2")), text(INFO_SEEING_3),
               self._formula(FormulaLabel("goes_fwhm")), text(INFO_SUN))
        self.lay.addWidget(c3)
        self.lay.addStretch(1)
        self.refresh()

    @staticmethod
    def _formula(w):
        box = Card(kind="panel2", margins=(14, 10, 14, 10))
        box.add(w)
        return box

    def refresh(self):
        self.table_lbl.setText(channels_table_html())


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


def _cell(text, right=False, color=None):
    it = QTableWidgetItem(text)
    it.setToolTip(text)
    if right:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if color:
        from PySide6.QtGui import QBrush, QColor

        it.setForeground(QBrush(QColor(color)))
    return it


class GoesPage(Page):
    title = "Satélite GOES"
    subtitle = "Nubes y seeing sobre tu sitio de observación, hora por hora"
    help_text = GOES_HELP

    def __init__(self, main):
        super().__init__(main)
        self.thread = None
        self.job = None
        self.instants: list[ss.SatInstant] = []
        self.readings: list[goes.ChannelReading] = []
        self.method = ""
        self.params = None
        self.eval_dir = ""
        self.setAcceptDrops(True)
        st = self.main.settings

        # ------------------------------------------------------------ fecha, horas y lugar
        when = Card("Fecha, horas y lugar", margins=(14, 12, 14, 12))
        self.date = QDateEdit()
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd")
        self.date.setMinimumDate(QDate(2017, 12, 18))
        self.t0 = QTimeEdit()
        self.t0.setDisplayFormat("HH:mm")
        self.t1 = QTimeEdit()
        self.t1.setDisplayFormat("HH:mm")
        self.step = QComboBox()
        self.step.addItem("Una sola imagen", 0)
        self.step.addItem("Cada 30 minutos", 30)
        self.step.addItem("Cada 60 minutos", 60)
        self.step.setCurrentIndex(int(st.value("goes/intervalo", 2, type=int)))
        self.zone = QComboBox()
        self.zone.addItem("Hora de Colombia (UTC−5)", -5)
        self.zone.addItem("UTC", 0)
        self.zone.setCurrentIndex(int(st.value("goes/zona", 0, type=int)))
        yesterday = QDateTime.currentDateTimeUtc().addSecs(int(self.zone.currentData()) * 3600 - 86400)
        self.date.setDate(yesterday.date())
        self.t0.setTime(QTime(int(st.value("goes/desde", 18, type=int)), 0))
        self.t1.setTime(QTime(int(st.value("goes/hasta", 23, type=int)), 0))
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
        self.half.setRange(MIN_CUT_KM, 1500)
        self.half.setSingleStep(50)
        self.half.setValue(max(MIN_CUT_KM, int(st.value("goes/recorte", 300, type=int))))
        self.half.setSuffix(" km")
        self.half.setToolTip(tr("Valores permitidos: de {} a {} km.").format(MIN_CUT_KM, 1500))
        self.n_lbl = label("", "small")
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.addWidget(label("Fecha"), 0, 0)
        g.addLayout(hbox(self.date, label("Desde"), self.t0, label("Hasta"), self.t1, self.step, self.zone, "stretch"), 0, 1)
        g.addWidget(label(""), 1, 0)
        g.addWidget(self.n_lbl, 1, 1)
        g.addWidget(label("Latitud (°, norte +)"), 2, 0)
        g.addLayout(hbox(self.lat, label("Longitud (°, este +)"), self.lon,
                         button("OAN, Bogotá", slot=self._oan, tip="Observatorio Astronómico Nacional"), "stretch"), 2, 1)
        g.addWidget(label("Satélite"), 3, 0)
        g.addLayout(hbox(self.sat, self.sat_lbl, 1), 3, 1)
        g.addWidget(label("Recorte"), 4, 0)
        g.addLayout(hbox(self.half, label(tr("de lado alrededor del punto · mínimo {} km (5 píxeles de 2 km): con menos "
                                             "no hay imagen útil").format(MIN_CUT_KM), "small"), "stretch"), 4, 1)
        when.add(g)
        self.lay.addWidget(when)

        # ------------------------------------------------------------ canales
        chc = Card("Canales", margins=(14, 12, 14, 12))
        self.seeing_cb = QCheckBox(tr("Calcular el seeing (usa los canales 9, 13 y 16)"))
        self.seeing_cb.setStyleSheet("font-weight:600;")
        self.seeing_cb.setChecked(st.value("goes/seeing", "true") in (True, "true"))
        chc.add(hbox(self.seeing_cb, HelpButton(
            "<b>Seeing desde el satélite</b><br>Con los canales 9 (vapor de agua medio), 13 (infrarrojo limpio) y 16 "
            "(CO₂) se calcula F = T9 − (T16 − T13), su tendencia durante la noche y, con lo que se aparta de ella, la "
            "turbulencia entre 4 y 8 km y el seeing. Los tres canales quedan marcados y no se pueden desmarcar mientras "
            "esta opción esté activa; puedes agregar otros. La explicación completa está en «Cómo funciona»."), "stretch"))
        self.checks = {}
        cg = QGridLayout()
        cg.setHorizontalSpacing(14)
        cg.setVerticalSpacing(2)
        saved = str(st.value("goes/canales", "9,13,16")).split(",")
        for i, (ch, (wl, name, res, mb)) in enumerate(goes.CHANNELS.items()):
            cb = QCheckBox(f"{ch:>2} · {num(wl, 2)} µm · {tr(name)}")
            cb.setToolTip(tr(CHANNEL_DETAIL[ch]) + "\n" + tr("Resolución {} km · archivo ≈{} MB").format(num(res, 1), mb))
            cb.setChecked(str(ch) in saved)
            cb.toggled.connect(self._update_size)
            self.checks[ch] = cb
            cg.addWidget(cb, i % 4, i // 4)
        chc.add(cg)
        self.size_lbl = label("", "small")
        self.pick_row = hbox(button("Solo el 13 (nubes)", slot=lambda: self._pick([13])),
                             button("Infrarrojos 7–16", slot=lambda: self._pick(range(7, 17))),
                             button("Todos", slot=lambda: self._pick(range(1, 17))),
                             button("Ninguno", slot=lambda: self._pick([])), "stretch", self.size_lbl)
        chc.add(self.pick_row)
        self.lay.addWidget(chc)

        # ------------------------------------------------------------ parámetros del seeing
        self.sp = Card("Seeing desde el satélite", margins=(14, 12, 14, 12))
        self.lam = QSpinBox()
        self.lam.setRange(400, 1000)
        self.lam.setValue(int(st.value("goes/lambda", 500, type=int)))
        self.lam.setSuffix(" nm")
        self.zkm = DecSpin()
        self.zkm.setRange(0.5, 20)
        self.zkm.setDecimals(1)
        self.zkm.setValue(float(st.value("goes/z", 4.0)))
        self.zkm.setSuffix(" km")
        self.box = QComboBox()
        self.box.addItem("1° × 1° (≈111 km, como en el artículo)", 111.0)
        self.box.addItem("3 × 3 píxeles (≈6 km)", 6.0)
        self.box.addItem("Solo el píxel del sitio", 0.0)
        self.box.setCurrentIndex(int(st.value("goes/cuadro", 0, type=int)))
        self.crit = QComboBox()
        for k, (lim, txt) in ss.SUN_CRITERIA.items():
            self.crit.addItem(txt, k)
        self.crit.setCurrentIndex(max(0, self.crit.findData(st.value("goes/criterio", "noche"))))
        self.theta_lbl = label("", "small", wrap=True)
        sg = QGridLayout()
        sg.setHorizontalSpacing(10)
        sg.addWidget(label("Longitud de onda λ"), 0, 0)
        sg.addLayout(hbox(self.lam, 16, label("Espesor de la capa z"), self.zkm, 16, label("Promedio en"), self.box,
                          "stretch"), 0, 1)
        sg.addWidget(label("Criterio del Sol"), 1, 0)
        sg.addLayout(hbox(self.crit, self.theta_lbl, 1), 1, 1)
        self.sp.add(sg)
        self.lay.addWidget(self.sp)

        # ------------------------------------------------------------ carpeta y ejecución
        self.folder = str(st.value("goes/carpeta", ""))
        self.folder_lbl = label("", "small", wrap=True)
        self.mode = QComboBox()
        self.mode.addItem("Leer solo la zona (rápido, ≈2 MB por canal)", "zona")
        self.mode.addItem("Descargar los archivos completos (≈25 MB por canal)", "completo")
        self.mode.setCurrentIndex(int(st.value("goes/modo", 0, type=int)))
        self.lay.addLayout(hbox(button("Carpeta de resultados…", slot=self.pick_folder), self.folder_lbl, "stretch",
                                self.mode,
                                button("Leer archivos ya descargados…", slot=lambda: self.open_local(),
                                       tip="Archivos OR_ABI-L2-CMIPF-…nc de GOES-16 o GOES-19")))
        self.run_b = button("Buscar, leer y calcular", "primary", self.start)
        self.cancel_b = button("Cancelar", slot=self.cancel)
        self.cancel_b.setEnabled(False)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.state = label("", "small", wrap=True)
        self.lay.addLayout(hbox(self.run_b, self.cancel_b, self.bar, 1))
        self.lay.addWidget(self.state)

        # ------------------------------------------------------------ serie de la noche
        self.series_card = Card("Serie de la noche", margins=(12, 10, 12, 10))
        r = QHBoxLayout()
        r.setSpacing(12)
        self.c_seeing = charts.ChartWidget(min_h=260)
        self.c_f = charts.ChartWidget(min_h=260)
        r.addWidget(self.c_seeing, 1)
        r.addWidget(self.c_f, 1)
        self.series_card.add(r)
        self.stable = QTableWidget(0, 9)
        self.stable.setHorizontalHeaderLabels(["Hora local", "Sol (°)", "Estado", "F (K)", "Tendencia (K)", "|ΔF| (K)",
                                               "Seeing (″)", "r0 (cm)", "Nota"])
        self._table_setup(self.stable, 8)
        self.stable.itemSelectionChanged.connect(self._instant_selected)
        self.series_card.add(self.stable)
        self.series_msg = label("", "small", wrap=True)
        self.series_card.add(self.series_msg)
        self.series_card.setVisible(False)
        self.lay.addWidget(self.series_card)

        # ------------------------------------------------------------ valores por canal
        self.empty_card = Card(kind="soft", margins=(14, 12, 14, 12))
        self.empty_card.add(label("Elige la fecha, las horas y el lugar y pulsa «Buscar, leer y calcular». Aquí aparecerán la "
                                  "serie de la noche, los valores de cada canal y el recorte con el mapa.", wrap=True))
        self.lay.addWidget(self.empty_card)
        res = Card("Valores en tus coordenadas", margins=(12, 10, 12, 10))
        self.values_card = res
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Canal", "λ (µm)", "Valor", "Unidad", "Promedio 3×3", "Promedio del cuadro",
                                              "Lectura", "Escaneo (UTC)", "Satélite"])
        self._table_setup(self.table, 6)
        self.table.itemSelectionChanged.connect(self._show_selected)
        res.add(self.table)
        self.res_msg = label("", "small", wrap=True)
        res.add(self.res_msg)
        self.lay.addWidget(res)

        # ------------------------------------------------------------ recorte con mapa
        prev = Card("Recorte del canal elegido", margins=(12, 10, 12, 10))
        self.prev_card = prev
        self.preview = ImageView()
        self.preview.empty_text = "Elige un canal en la tabla de arriba"
        self.preview.setFixedSize(520, 440)
        self.preview.hovered.connect(self._hover)
        self.preview.left.connect(lambda: self.hover_lbl.setText(""))
        self.map_cb = QCheckBox(tr("Mapa: costas, países y departamentos"))
        self.map_cb.setChecked(True)
        self.map_cb.toggled.connect(lambda *_: self._show_selected())
        self.prev_lbl = label("", "small", wrap=True)
        self.hover_lbl = label("", "small", wrap=True)
        prev.add(hbox(self.preview, 12, vbox(self.prev_lbl, self.map_cb, self.hover_lbl,
                                             hbox(button("Ver completo", slot=lambda: self.preview.fit()),
                                                  button("Abrir en el visor de píxeles", slot=self.open_viewer), "stretch"),
                                             "stretch")))
        self.lay.addWidget(prev)
        self.lay.addWidget(label("Datos: NOAA GOES-R Series, producto ABI L2 Cloud and Moisture Imagery (CMIPF), "
                                 "repositorio abierto NOAA Open Data Dissemination en Amazon Web Services. Mapa: Natural "
                                 "Earth (dominio público).", "small", wrap=True))
        self.lay.addStretch(1)

        self.values_card.setVisible(False)
        self.prev_card.setVisible(False)
        for sig in (self.date.dateChanged, self.t0.timeChanged, self.t1.timeChanged, self.zone.currentIndexChanged,
                    self.sat.currentIndexChanged, self.step.currentIndexChanged):
            sig.connect(self._update_sat)
        self.seeing_cb.toggled.connect(self._seeing_toggled)
        for w in (self.lat, self.lon):
            w.valueChanged.connect(self._update_theta)
        self._seeing_toggled(self.seeing_cb.isChecked())
        self._update_sat()
        self._update_theta()
        self._update_folder()

    @staticmethod
    def _table_setup(t, stretch_col):
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setSelectionMode(QAbstractItemView.SingleSelection)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(stretch_col, QHeaderView.Stretch)
        t.setMinimumHeight(200)

    # ---------------------------------------------------------- opciones
    def _oan(self):
        self.lat.setValue(goes.OAN_LAT)
        self.lon.setValue(goes.OAN_LON)

    def _pick(self, chans):
        chans = set(chans)
        if self.seeing_cb.isChecked():
            chans |= set(ss.SEEING_CHANNELS)
        for ch, cb in self.checks.items():
            cb.setChecked(ch in chans)

    def _seeing_toggled(self, on):
        for ch in ss.SEEING_CHANNELS:
            cb = self.checks[ch]
            if on:
                cb.setChecked(True)
            cb.setEnabled(not on)
        self.sp.setVisible(on)
        self._update_size()

    def channels(self) -> list[int]:
        return [ch for ch, cb in self.checks.items() if cb.isChecked()]

    def times(self) -> list[dt.datetime]:
        d = self.date.date()
        return ss.build_times(dt.date(d.year(), d.month(), d.day()), self._qtime(self.t0), self._qtime(self.t1),
                              int(self.step.currentData()), float(self.zone.currentData()))

    @staticmethod
    def _qtime(w) -> dt.time:
        t = w.time()
        return dt.time(t.hour(), t.minute())

    def _update_size(self, *_):
        chans = self.channels()
        n = len(self.times()) if hasattr(self, "step") else 1
        if not chans:
            self.size_lbl.setText(tr("Elige al menos un canal"))
            return
        full = sum(goes.CHANNELS[c][3] for c in chans) * n
        part = 2 * len(chans) * n
        self.size_lbl.setText(tr("{} canales × {} horas · ≈{} MB leyendo solo la zona (≈{} MB completos)").format(
            len(chans), n, integer(part), integer(full)))

    def when_utc(self) -> dt.datetime:
        return self.times()[0].astimezone(dt.timezone.utc)

    def _update_sat(self, *_):
        ts = self.times()
        w = ts[0].astimezone(dt.timezone.utc)
        auto = goes.satellite_for(w)
        chosen = int(self.sat.currentData()) or auto
        txt = tr("{} UTC → GOES-{}").format(w.strftime("%Y-%m-%d %H:%M"), chosen)
        if not self.sat.currentData():
            txt += tr(" (automático: GOES-19 desde el 4 abr 2025, antes GOES-16)")
        self.sat_lbl.setText(txt)
        single = int(self.step.currentData()) == 0
        self.t1.setEnabled(not single)
        if single:
            self.n_lbl.setText(tr("1 imagen a las {}").format(ts[0].strftime("%H:%M")))
        else:
            self.n_lbl.setText(tr("{} imágenes por canal: de {} a {}{}").format(
                len(ts), ts[0].strftime("%H:%M"), ts[-1].strftime("%H:%M"),
                tr(" (del día siguiente)") if ts[-1].date() != ts[0].date() else ""))
        self._update_size()

    def _update_theta(self, *_):
        th = ss.satellite_zenith_deg(self.lat.value(), self.lon.value())
        self.theta_lbl.setText(tr("Ángulo cenital del satélite θ = {}° · Λ(θ) = {}").format(
            num(th, 2), sci(ss.LAMBDA_COEF / math.cos(math.radians(th)), 3)))

    def _update_folder(self):
        self.folder_lbl.setText(tr("Carpeta: {}").format(self.folder) if self.folder else tr("Carpeta: (sin elegir)"))

    def pick_folder(self):
        d = choose_folder(self, "Carpeta para los resultados del satélite", self.folder)
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
        st.setValue("goes/intervalo", self.step.currentIndex())
        st.setValue("goes/desde", self.t0.time().hour())
        st.setValue("goes/hasta", self.t1.time().hour())
        st.setValue("goes/seeing", "true" if self.seeing_cb.isChecked() else "false")
        st.setValue("goes/lambda", self.lam.value())
        st.setValue("goes/z", self.zkm.value())
        st.setValue("goes/cuadro", self.box.currentIndex())
        st.setValue("goes/criterio", self.crit.currentData())
        st.setValue("goes/modo", self.mode.currentIndex())

    def sat_params(self) -> ss.SatParams:
        return ss.SatParams(self.lat.value(), self.lon.value(), z_km=self.zkm.value(), lambda_nm=float(self.lam.value()),
                            criterion=str(self.crit.currentData()), box_km=float(self.box.currentData()))

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
        times = self.times()
        sat = int(self.sat.currentData()) or None
        lat, lon, half, folder = self.lat.value(), self.lon.value(), self.half.value() / 2, self.folder
        box_km = float(self.box.currentData()) if self.seeing_cb.isChecked() else 6.0
        partial = self.mode.currentData() == "zona"
        dl_dir = os.path.join(folder, "descargas_goes")

        def work(job):
            cache: dict = {}
            out = []
            n_total = len(times) * len(chans)
            k = 0
            for i, t_local in enumerate(times):
                when = t_local.astimezone(dt.timezone.utc)
                job.progress.emit(tr("Hora {} de {} ({}): buscando las imágenes…").format(
                    i + 1, len(times), t_local.strftime("%H:%M")), k, n_total)
                used, files = goes.find_files(when, chans, sat, cache=cache)
                it = ss.SatInstant(local=t_local, utc=when)
                if not files:
                    it.note = tr("sin imágenes para esa hora")
                    out.append(it)
                    k += len(chans)
                    continue
                for f in files:
                    def prog(a, b=None, f=f, i=i, k=k):
                        job.progress.emit(tr("Hora {} de {} ({}) · canal {}: {} MB").format(
                            i + 1, len(times), t_local.strftime("%H:%M"), f.channel, num(a / 1e6, 1)), k, n_total)
                        return not job.cancel
                    if partial:
                        try:
                            with goes.open_remote(f, progress=prog) as hf:
                                r = goes.read_point(hf, lat, lon, half, box_km)
                        except goes.RangeNotSupported:
                            r = goes.read_point(goes.download(f, dl_dir, prog), lat, lon, half, box_km)
                    else:
                        r = goes.read_point(goes.download(f, dl_dir, prog), lat, lon, half, box_km)
                    if f.start and abs((f.start - when).total_seconds()) > 20 * 60:
                        it.note = tr("la imagen más cercana está a más de 20 min")
                    it.readings[f.channel] = r
                    k += 1
                    if job.cancel:
                        raise InterruptedError(tr("Cancelado"))
                out.append(it)
            return out

        self._run(work)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        ps = [u.toLocalFile() for u in ev.mimeData().urls() if u.toLocalFile().lower().endswith(".nc")]
        if ps and self.thread is None:
            self.open_local(ps)

    def open_local(self, ps=None):
        if not ps:
            ps = choose_files(self, "Archivos de GOES (NetCDF)", "GOES ABI L2 CMIP (*.nc);;" + tr("Todos") + " (*)")
        if not ps:
            return
        if not self.folder:
            self.folder = os.path.dirname(ps[0])
            self._update_folder()
        lat, lon, half = self.lat.value(), self.lon.value(), self.half.value() / 2
        box_km = float(self.box.currentData()) if self.seeing_cb.isChecked() else 6.0
        off = float(self.zone.currentData())
        self._save_settings()

        def work(job):
            groups: dict = {}
            for i, p in enumerate(ps):
                job.progress.emit(tr("Leyendo {} ({} de {})…").format(os.path.basename(p), i + 1, len(ps)), i, len(ps))
                r = goes.read_point(p, lat, lon, half, box_km)
                start = r.start or dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)
                key = start.replace(second=0, microsecond=0, minute=start.minute - start.minute % 10)
                groups.setdefault(key, {})[r.channel] = r
            out = []
            for key in sorted(groups):
                local = key.astimezone(dt.timezone(dt.timedelta(hours=off)))
                out.append(ss.SatInstant(local=local, utc=key, readings=groups[key]))
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

    def _done(self, instants):
        self._end()
        self.bar.setValue(1000)
        self.show_instants(instants)

    # ---------------------------------------------------------- resultados
    def show_instants(self, instants: list[ss.SatInstant]):
        self.instants = instants
        self.empty_card.setVisible(not instants)
        self.values_card.setVisible(bool(instants))
        self.prev_card.setVisible(bool(instants))
        self.params = self.sat_params()
        do_seeing = self.seeing_cb.isChecked() and any(all(c in i.readings for c in ss.SEEING_CHANNELS) for i in instants)
        self.method = ss.compute_series(instants, self.params) if do_seeing else ""
        if not do_seeing:
            for it in instants:
                it.sun_alt = ss.sun_altitude_deg(it.utc, self.params.lat, self.params.lon)
                it.state = ss.sun_state(it.sun_alt)
        self._fill_series(do_seeing)
        self.eval_dir = self._save_outputs(do_seeing)
        n_ch = sum(len(i.readings) for i in instants)
        if len(instants) == 1 and n_ch == 1:
            msg = tr("Listo: una imagen leída.")
        elif len(instants) == 1:
            msg = tr("Listo: una hora, {} imágenes leídas.").format(n_ch)
        else:
            msg = tr("Listo: {} horas, {} imágenes leídas.").format(len(instants), n_ch)
        if self.eval_dir:
            msg += " " + tr("Resultados en: {}").format(self.eval_dir)
        self.state.setText(msg)
        if instants:
            self.stable.selectRow(0)
            self._instant_selected()

    def _fill_series(self, do_seeing):
        inst = self.instants
        self.series_card.setVisible(len(inst) > 1 or do_seeing)
        t = self.stable
        t.setRowCount(len(inst))
        pal = theme.pal
        for i, it in enumerate(inst):
            muted = pal.get("muted") if not it.used and do_seeing else None
            vals = [it.local.strftime("%Y-%m-%d %H:%M"), num(it.sun_alt, 1), tr(it.state),
                    num(it.F, 2) if math.isfinite(it.F) else "—", num(it.F_trend, 2) if math.isfinite(it.F_trend) else "—",
                    num(it.dF, 2) if math.isfinite(it.dF) else "—", num(it.seeing, 2) if math.isfinite(it.seeing) else "—",
                    num(it.r0_cm, 1) if math.isfinite(it.r0_cm) else "—", tr(it.note)]
            for j, v in enumerate(vals):
                t.setItem(i, j, _cell(v, right=j in (1, 3, 4, 5, 6, 7), color=muted))
        hrs = ss.series_hours(inst)
        if do_seeing:
            used = np.array([i.used for i in inst])
            see = np.array([i.seeing for i in inst])
            okp = used & np.isfinite(see)
            ser = []
            if okp.any():
                ser.append(Series("line", x=hrs[okp], y=see[okp], color="accent", width=2, label="Seeing (″)"))
                ser.append(Series("scatter", x=hrs[okp], y=see[okp], color="accent", size=4))
                ser.append(Series("hline", y=[float(np.nanmedian(see[okp]))], color="muted", dash=True, width=1.5,
                                  label="Mediana"))
            spec = ChartSpec(title="Seeing estimado por el satélite", xlabel="Hora local (h; 24 = medianoche)",
                             ylabel="Seeing (″)", series=ser, ymin_zero=True,
                             empty="" if okp.any() else tr("Sin horas de noche con los tres canales: no hay seeing."))
            self.c_seeing.set_spec(spec)
            F = np.array([i.F for i in inst])
            Ft = np.array([i.F_trend for i in inst])
            fs = []
            if np.isfinite(F).any():
                if (~used & np.isfinite(F)).any():
                    fs.append(Series("scatter", x=hrs[~used & np.isfinite(F)], y=F[~used & np.isfinite(F)], color="muted",
                                     size=4, label="Excluida (Sol)"))
                if okp.any() or (used & np.isfinite(F)).any():
                    m = used & np.isfinite(F)
                    fs.append(Series("scatter", x=hrs[m], y=F[m], color="accent", size=4.5, label="F"))
                if np.isfinite(Ft).any():
                    fs.append(Series("line", x=hrs, y=Ft, color="accent2", width=1.8, dash=True, label="Tendencia"))
            self.c_f.set_spec(ChartSpec(title="F = T9 − (T16 − T13) y su tendencia", xlabel="Hora local (h)",
                                        ylabel="F (K)", series=fs, empty="" if fs else tr("Sin datos de los canales 9, 13 y 16.")))
            n_used = int(used.sum())
            txt = tr("Tendencia: {} con {} horas usadas · θ = {}° · z = {} km · λ = {} nm.").format(
                tr(self.method), n_used, num(self.params.theta, 2), num(self.params.z_km, 1), integer(self.params.lambda_nm))
            if n_used < 3:
                txt += " " + tr("Con menos de 3 horas de noche no se puede ajustar la tendencia: amplía el intervalo.")
            if okp.any():
                txt += " " + tr("Seeing: mediana {}″, de {}″ a {}″.").format(
                    num(float(np.nanmedian(see[okp])), 2), num(float(np.nanmin(see[okp])), 2), num(float(np.nanmax(see[okp])), 2))
            self.series_msg.setText(txt)
        else:
            ch = next((c for c in (13, 14, 9) if any(c in i.readings for i in inst)), None)
            if ch is None and inst and inst[0].readings:
                ch = sorted(inst[0].readings)[0]
            if ch is not None:
                y = np.array([i.readings[ch].value if ch in i.readings else np.nan for i in inst])
                ok = np.isfinite(y)
                self.c_seeing.set_spec(ChartSpec(title=tr("Canal {} en tu punto").format(ch), xlabel="Hora local (h)",
                                                 ylabel=tr(goes.channel_unit(ch)),
                                                 series=[Series("line", x=hrs[ok], y=y[ok], color="accent", width=2),
                                                         Series("scatter", x=hrs[ok], y=y[ok], color="accent", size=4)],
                                                 legend=False, empty="" if ok.any() else tr("Sin datos.")))
            self.c_f.set_spec(ChartSpec(title="Seeing", empty=tr("Activa «Calcular el seeing» para ver F y su tendencia.")))
            self.series_msg.setText("")

    def _instant_selected(self):
        rows = self.stable.selectionModel().selectedRows() if self.stable.selectionModel() else []
        i = rows[0].row() if rows else 0
        if not self.instants or i >= len(self.instants):
            self.show_readings([])
            return
        it = self.instants[i]
        self.show_readings(list(it.readings.values()))
        self.res_msg.setText(tr("Hora {} · Sol a {}° ({})").format(it.local.strftime("%Y-%m-%d %H:%M"), num(it.sun_alt, 1),
                                                                    tr(it.state)))

    def show_readings(self, readings):
        prev = self._selected()
        prev_ch = prev.channel if prev else None
        self.readings = sorted(readings, key=lambda r: r.channel)
        t = self.table
        t.setRowCount(len(self.readings))
        sel = 0
        for i, r in enumerate(self.readings):
            if r.channel == prev_ch:
                sel = i
            wl = goes.CHANNELS.get(r.channel, (float("nan"),))[0]
            dec = 4 if r.channel <= 6 else 2
            tmpl, c = goes.describe_value(r.channel, r.value)
            reading = tr(tmpl).format(num(c, 0)) if "{}" in tmpl else tr(tmpl)
            if not r.visible:
                reading = tr("Fuera del disco visible")
            vals = [str(r.channel), num(wl, 2), num(r.value, dec) if np.isfinite(r.value) else "—", tr(r.unit),
                    num(r.mean3, dec) if np.isfinite(r.mean3) else "—",
                    (num(r.box_mean, dec) + f" ({r.box_px}×{r.box_px})") if np.isfinite(r.box_mean) else "—", reading,
                    r.start.strftime("%Y-%m-%d %H:%M") if r.start else "—", f"GOES-{r.sat}" if r.sat else "—"]
            for j, v in enumerate(vals):
                t.setItem(i, j, _cell(v, right=j in (0, 1, 2, 4, 5)))
        if self.readings:
            t.selectRow(sel)
        else:
            self.preview.set_data(None)

    def _save_outputs(self, do_seeing) -> str:
        if not self.instants or not self.folder:
            return ""
        from ... import citation_apa

        first = self.instants[0].local
        last = self.instants[-1].local
        name = ss.eval_folder_name(first.date(), first.time(), last.time(), dt.datetime.now(),
                                   single=len(self.instants) == 1)
        out_dir = os.path.join(self.folder, name)
        k = 2
        while os.path.exists(out_dir):
            out_dir = os.path.join(self.folder, f"{name}_{k}")
            k += 1
        try:
            os.makedirs(os.path.join(out_dir, "recortes"), exist_ok=True)
            cite = tr("Generado con TurbuLENS · ") + citation_apa()
            if do_seeing:
                ss.write_series_csv(os.path.join(out_dir, "serie_seeing.csv"), self.instants, self.params, self.method, cite)
            with open(os.path.join(out_dir, "valores_por_canal.csv"), "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow([tr("hora_local"), tr("canal"), tr("longitud_onda_um"), tr("valor"), tr("unidad"),
                            tr("promedio_3x3"), tr("promedio_cuadro"), tr("cuadro_px"), tr("latitud"), tr("longitud"),
                            tr("columna"), tr("fila"), tr("escaneo_utc"), tr("satelite"), tr("archivo")])
                for it in self.instants:
                    for ch in sorted(it.readings):
                        r = it.readings[ch]
                        w.writerow([it.local.strftime("%Y-%m-%d %H:%M"), r.channel, goes.CHANNELS.get(r.channel, ("",))[0],
                                    f"{r.value:.6g}", r.unit, f"{r.mean3:.6g}", f"{r.box_mean:.6g}", r.box_px, r.lat, r.lon,
                                    f"{r.col:.2f}", f"{r.row:.2f}",
                                    r.start.strftime("%Y-%m-%dT%H:%M:%SZ") if r.start else "", r.sat,
                                    os.path.basename(str(r.path))])
                w.writerow([])
                w.writerow([cite])
            for it in self.instants:
                for ch, r in sorted(it.readings.items()):
                    if r.cutout is None:
                        continue
                    b = os.path.join(out_dir, "recortes", f"{it.local:%Y%m%d_%H%M}_C{ch:02d}")
                    write_fits(b + ".fits", r.cutout, {
                        "TELESCOP": f"GOES-{r.sat}", "INSTRUME": "ABI", "FILTER": f"C{ch:02d}",
                        "WAVELEN": goes.CHANNELS.get(ch, (0,))[0], "BUNIT": r.unit,
                        "DATE-OBS": r.start.strftime("%Y-%m-%dT%H:%M:%S") if r.start else None,
                        "SITELAT": r.lat, "SITELONG": r.lon, "PIXKM": round(r.pixel_km, 4),
                        "ROW0": r.cut_origin[0], "COL0": r.cut_origin[1]})
                    fin = r.cutout[np.isfinite(r.cutout)]
                    if fin.size:
                        lo, hi = np.percentile(fin, [0.5, 99.5])
                        img = -r.cutout if ch > 6 else r.cutout
                        if ch > 6:
                            lo, hi = -hi, -lo
                        write_png16(b + ".png", np.nan_to_num(img, nan=lo), lo, hi)
            from ...charts import render_png

            for name_png, w in (("grafica_seeing.png", self.c_seeing), ("grafica_F_tendencia.png", self.c_f)):
                spec = getattr(w, "spec", None)
                if spec is not None and self.series_card.isVisible():
                    render_png(spec, os.path.join(out_dir, name_png))
            with open(os.path.join(out_dir, "LEEME.txt"), "w", encoding="utf-8") as fh:
                p = self.params
                fh.write(tr("Evaluación del satélite GOES con TurbuLENS") + "\n\n")
                fh.write(tr("Fecha y horas: {} a {} (hora local)").format(first.strftime("%Y-%m-%d %H:%M"),
                                                                          last.strftime("%Y-%m-%d %H:%M")) + "\n")
                fh.write(tr("Lugar: latitud {}, longitud {}").format(p.lat, p.lon) + "\n")
                fh.write(tr("Canales: {}").format(", ".join(str(c) for c in self.channels())) + "\n")
                if do_seeing:
                    fh.write(tr("Seeing: F = T9 − (T16 − T13); ∫Cn² dz = Λ(θ)·|F − F_tendencia|/z; Λ(θ) = 1e-12/cos θ; "
                                "FWHM = 0,58·λ^(−1/5)·[4π²·Λ(θ)·|F − F_tendencia|/z]^(3/5)") + "\n")
                    fh.write(tr("θ = {}°, z = {} km, λ = {} nm, cuadro {} km, criterio del Sol: {}, tendencia: {}").format(
                        f"{p.theta:.3f}", p.z_km, p.lambda_nm, p.box_km, p.criterion, self.method) + "\n")
                    fh.write(tr("Método: Cavazzani, Ortolani y Zitelli (2012), arXiv:1112.3497.") + "\n")
                fh.write("\n" + cite + "\n")
        except OSError as exc:
            self.res_msg.setText(tr("No se pudieron guardar los resultados: {}").format(exc))
        return out_dir

    def _selected(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return self.readings[rows[0].row()] if rows and rows[0].row() < len(self.readings) else None

    def _show_selected(self):
        r = self._selected()
        if r is None or r.cutout is None:
            self.preview.set_data(None)
            self.preview.set_overlays([])
            self.prev_lbl.setText(tr("Sin recorte: el punto no se ve desde el satélite.") if r else "")
            return
        img = -r.cutout if r.channel > 6 else r.cutout
        self.preview.set_data(img)
        self.preview.set_display("lineal", "p995", "gris")
        self.preview.set_marker(r.col - r.cut_origin[1], r.row - r.cut_origin[0])
        if self.map_cb.isChecked() and r.proj is not None:
            self.preview.set_overlays(mapdata.project(r.proj, r.cut_origin, r.cutout.shape))
        else:
            self.preview.set_overlays([])
        h, w = r.cutout.shape
        self.prev_lbl.setText(tr("Canal {} · {} × {} px de {} km (≈{} km de lado) · el círculo rojo es tu punto. En "
                                 "infrarrojo las nubes frías se ven blancas. Amarillo: costas; blanco: países; azul: "
                                 "departamentos o estados.").format(r.channel, w, h, num(r.pixel_km, 2),
                                                                     integer(w * r.pixel_km)))

    def _hover(self, c, rr, v):
        r = self._selected()
        if r is None or r.proj is None or c < 0:
            self.hover_lbl.setText("")
            return
        p = r.proj
        la, lo = p.latlon(p.x0 + (r.cut_origin[1] + c) * p.dx, p.y0 + (r.cut_origin[0] + rr) * p.dy)
        val = r.cutout[rr, c] if 0 <= rr < r.cutout.shape[0] and 0 <= c < r.cutout.shape[1] else float("nan")
        unit = "" if r.channel <= 6 else " K"
        extra = f" ({num(val - 273.15, 1)} °C)" if r.channel > 6 and np.isfinite(val) else ""
        self.hover_lbl.setText(tr("Bajo el cursor: lat {}°, lon {}° · {}{}{}").format(
            num(la, 3), num(lo, 3), num(val, 2) if np.isfinite(val) else "—", unit, extra))

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
                         f"{tr('Archivo')}: {os.path.basename(str(r.path))}"])
        v.show_array(r.cutout, f"GOES-{r.sat} C{r.channel:02d}", hdr,
                     marker=(r.col - r.cut_origin[1], r.row - r.cut_origin[0]))
