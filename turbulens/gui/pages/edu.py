# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Modo educativo: aprender estadística a partir de un ejemplo astronómico.

La estadística es el eje: diez lecciones interactivas con datos reales (la
distancia entre los dos puntos de una estrella, cuadro a cuadro). La parte
astronómica se cuenta de la forma más sencilla posible.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from ... import charts
from ...charts import ChartSpec, Series, histogram_spec
from ...core import stats
from ...core.dimm import DimmParams, k_coefficients, r0_from_variance, seeing_from_r0
from ..session import resource_path
from ..theme import theme
from ..widgets import dialog_options, Card, ChipGroup, HelpButton, button, hbox, label, vbox
from .base import Page


def f(v, d=3):
    if v is None or not np.isfinite(v):
        return "—"
    return f"{v:.{d}f}".replace(".", ",")


# --------------------------------------------------------------------- datos
class EduData:
    """Datos para las lecciones: el ejemplo de Altair o el video propio."""

    _sample = None

    @classmethod
    def sample(cls) -> dict:
        if cls._sample is None:
            with np.load(resource_path("data", "altair_ejemplo.npz")) as z:
                cls._sample = {k: z[k] for k in z.files}
                cls._sample["name"] = "Altair (ejemplo)"
        return cls._sample

    @staticmethod
    def from_session(s) -> dict | None:
        if s.dimm is None or s.result is None:
            return None
        a = s.dimm.arrays
        used = a["used"]
        return {"t": s.result.meas["t"][used], "sep": a["sep"][used], "lon": a["lon"][used], "tra": a["tra"][used],
                "name": f"Mi video ({s.result.video.get('name')})"}


def seeing_example(sigma_px: float, scale: float = 1.0) -> float:
    kl, _ = k_coefficients(14 / 2.5)
    r0 = r0_from_variance((sigma_px * scale / 206264.806) ** 2, kl, 550e-9, 0.025)
    return seeing_from_r0(r0, 550e-9)


# ------------------------------------------------------------------ widgets
class MiniQuiz(Card):
    def __init__(self, question: str, options: list[str], ok: int, good: str, bad: str):
        super().__init__("Comprueba", kind="panel2", margins=(12, 10, 12, 10))
        self.ok, self.good, self.bad = ok, good, bad
        self.add(label(question, wrap=True))
        self.btns = []
        for i, o in enumerate(options):
            b = button(o, "option", lambda _=False, i=i: self.pick(i))
            self.btns.append(b)
            self.add(b)
        self.fb = label("", wrap=True)
        self.add(self.fb)

    def pick(self, i):
        for j, b in enumerate(self.btns):
            b.setProperty("state", "ok" if j == self.ok else ("bad" if j == i else ""))
            b.style().unpolish(b)
            b.style().polish(b)
        pal = theme.pal
        right = i == self.ok
        self.fb.setText(self.good if right else self.bad)
        self.fb.setStyleSheet(f"color:{pal['good'] if right else pal['bad']}; font-weight:600;")


def slider(lo, hi, val, step=1) -> QSlider:
    s = QSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setValue(val)
    s.setSingleStep(step)
    s.setPageStep(max(step, (hi - lo) // 10))
    return s


class Readouts(QWidget):
    def __init__(self, cols: int = 2):
        super().__init__()
        self.setObjectName("transparent")
        self.g = QGridLayout(self)
        self.g.setContentsMargins(0, 0, 0, 0)
        self.g.setHorizontalSpacing(10)
        self.g.setVerticalSpacing(8)
        self.cols = cols
        self.cells = {}

    def set(self, items: list[tuple[str, str]]):
        for i, (k, v) in enumerate(items):
            if k not in self.cells:
                c = Card(kind="true", margins=(10, 8, 10, 8))
                c.lay.setSpacing(0)
                t = label(k, "small")
                val = label(v, "mono")
                val.setStyleSheet("font-size:18px;")
                c.add(t, val)
                self.cells[k] = val
                self.g.addWidget(c, i // self.cols, i % self.cols)
            self.cells[k].setText(v)


# ---------------------------------------------------------------- lecciones
class LessonPage(Page):
    number = 0
    title = ""
    subtitle = ""
    text = ""
    tryit: list[str] = []
    quiz = None  # (pregunta, opciones, correcta, bien, mal)

    def __init__(self, main):
        super().__init__(main)
        self.h1.setText(f"{self.number}. {self.title}" if self.number else self.title)
        src = hbox(label("Datos:", "small"), spacing=6)
        self.src = ChipGroup([("ejemplo", "Altair (ejemplo)"), ("propio", "Mi video")])
        self.src.set_value("ejemplo")
        self.src.changed.connect(self._src_changed)
        src.addWidget(self.src)
        self.head.addLayout(src)

        row = QHBoxLayout()
        row.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(12)
        tc = Card()
        tl = label(self.text, wrap=True, rich=True)
        tl.setStyleSheet("font-size:15px; line-height:150%;")
        tc.add(tl)
        if self.tryit:
            tc.add(label("Pruébalo", "h2"))
            tc.add(label("".join(f"• {t}<br>" for t in self.tryit), wrap=True, rich=True))
        left.addWidget(tc)
        if self.quiz:
            left.addWidget(MiniQuiz(*self.quiz))
        left.addStretch(1)
        right = QVBoxLayout()
        right.setSpacing(12)
        cc = Card(margins=(8, 8, 8, 8))
        self.chart = charts.ChartWidget(min_h=300)
        cc.add(self.chart)
        right.addWidget(cc, 1)
        self.controls = Card("Controles")
        right.addWidget(self.controls)
        self.read = Readouts(cols=3)
        right.addWidget(self.read)
        lw = QWidget()
        lw.setObjectName("transparent")
        lw.setLayout(left)
        lw.setMinimumWidth(320)
        lw.setMaximumWidth(470)
        row.addWidget(lw, 2)
        row.addLayout(right, 3)
        self.lay.addLayout(row)
        self.build()

    # Datos activos
    def data(self) -> dict:
        if self.src.value() == "propio":
            d = EduData.from_session(self.main.sessions["educativo"])
            if d is not None:
                return d
        return EduData.sample()

    def _src_changed(self):
        if self.src.value() == "propio" and EduData.from_session(self.main.sessions["educativo"]) is None:
            self.src.set_value("ejemplo")
            self.main.toast("Aún no has procesado un video en el modo educativo. Ve a «Tu propio video».")
        self.update_view()

    def refresh(self):
        own = EduData.from_session(self.main.sessions["educativo"]) is not None
        self.src.buttons["propio"].setEnabled(own)
        if not own:
            self.src.set_value("ejemplo")
        self.update_view()

    def on_theme(self, pal):
        self.chart.set_palette(pal)

    def ctl(self, text: str, w: QWidget, value_label: QLabel | None = None, help_text: str = ""):
        row = QHBoxLayout()
        row.setSpacing(10)
        lb = label(text)
        lb.setMinimumWidth(170)
        row.addWidget(lb)
        row.addWidget(w, 1)
        if value_label is not None:
            value_label.setMinimumWidth(70)
            row.addWidget(value_label)
        if help_text:
            row.addWidget(HelpButton(help_text))
        self.controls.add(row)
        if isinstance(w, QSlider):
            w.valueChanged.connect(self.update_view)
        elif isinstance(w, QCheckBox):
            w.toggled.connect(self.update_view)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(self.update_view)
        elif isinstance(w, QSpinBox):
            w.valueChanged.connect(self.update_view)
        return w

    def build(self):
        pass

    def update_view(self, *a):
        pass

    def show_chart(self, spec):
        self.chart.set_spec(spec)
        self.chart.set_palette(theme.pal)


class L1Datos(LessonPage):
    number = 1
    title = "Datos y mediciones"
    subtitle = "Cada cuadro del video nos da un dato"
    text = ("Una <b>medición</b> es un número que obtenemos al observar algo. Aquí medimos la <b>distancia entre los dos "
            "puntos</b> de la imagen de la estrella, en píxeles (px).<br><br>"
            "Cada cuadro del video da <b>un dato</b>. Con un video de 2 minutos a 60 cuadros por segundo tenemos más de "
            "8.000 datos de la misma <b>variable</b>.<br><br>"
            "Los datos que tenemos son una <b>muestra</b>. La <b>población</b> serían todas las mediciones posibles de esa "
            "noche. Con estadística usamos la muestra para conocer la población.")
    tryit = ["Aumenta los cuadros mostrados: ¿la distancia es siempre la misma?",
             "Observa que los datos suben y bajan sin un patrón fijo: eso es la turbulencia."]
    quiz = ("Un video de 10 s a 60 cuadros por segundo, ¿cuántos datos da?", ["60", "600", "6.000"], 1,
            "¡Exacto! 10 × 60 = 600 cuadros, un dato por cuadro.", "Multiplica la duración por los cuadros por segundo.")

    def build(self):
        self.n = slider(20, 2000, 240, 10)
        self.n_lbl = label("", "mono")
        self.ctl("Cuadros mostrados", self.n, self.n_lbl)
        self.first = label("", "mono", wrap=True)
        self.controls.add(label("Los primeros datos:", "small"), self.first)

    def update_view(self, *a):
        d = self.data()
        n = min(self.n.value(), d["sep"].size)
        self.n_lbl.setText(str(n))
        t, x = d["t"][:n], d["sep"][:n]
        self.show_chart(ChartSpec(title="Distancia entre los dos puntos, cuadro a cuadro", xlabel="Tiempo (s)",
                                  ylabel="Distancia (px)", legend=False,
                                  series=[Series("line", x=t, y=x, color="accent", width=1.2, alpha=0.6),
                                          Series("scatter", x=t, y=x, color="accent", size=2.2)]))
        self.first.setText("   ".join(f"{v:.2f}".replace(".", ",") for v in d["sep"][:10]) + " …")
        s = stats.summarize(d["sep"])
        self.read.set([("Datos en total", f"{s.n:,}".replace(",", ".")), ("Mínimo", f(s.min, 2) + " px"),
                       ("Máximo", f(s.max, 2) + " px")])


class L2Histograma(LessonPage):
    number = 2
    title = "El histograma"
    subtitle = "Ordenar miles de datos en una sola imagen"
    text = ("Con miles de datos no sirve mirarlos uno por uno. Un <b>histograma</b> los agrupa en <b>intervalos</b> "
            "(por ejemplo de 12,0 a 12,2 px) y cuenta cuántos datos caen en cada uno.<br><br>"
            "La altura de cada barra es la <b>frecuencia</b>. Si la dividimos entre el total, obtenemos la "
            "<b>frecuencia relativa</b> (la proporción, entre 0 y 1).<br><br>"
            "La forma del histograma nos cuenta cómo se <b>distribuyen</b> los datos: dónde se concentran y qué tan "
            "dispersos están.")
    tryit = ["Usa muy pocos intervalos: se pierde el detalle.",
             "Usa muchísimos: aparecen huecos y picos que son solo ruido.",
             "Busca un número intermedio en el que se vea una forma clara."]
    quiz = ("¿Qué pasa si usas demasiados intervalos con pocos datos?",
            ["El histograma se ve más preciso", "Aparecen huecos y picos sin significado", "Las barras se vuelven más altas"], 1,
            "Correcto: cada intervalo tiene tan pocos datos que la forma se vuelve dentada.",
            "Piensa en cuántos datos caen en cada intervalo cuando hay muchos intervalos.")

    def build(self):
        self.bins = slider(3, 90, 20)
        self.b_lbl = label("", "mono")
        self.ctl("Número de intervalos", self.bins, self.b_lbl)
        self.rel = QCheckBox("Mostrar frecuencia relativa")
        self.ctl("Eje vertical", self.rel)

    def update_view(self, *a):
        d = self.data()
        x = d["sep"]
        nb = self.bins.value()
        self.b_lbl.setText(str(nb))
        edges = stats.nice_bins(x, nb)
        counts, _ = np.histogram(x, edges)
        y = counts / max(1, x.size) if self.rel.isChecked() else counts
        self.show_chart(ChartSpec(title="Histograma de la distancia", xlabel="Distancia (px)",
                                  ylabel="Frecuencia relativa" if self.rel.isChecked() else "Cuadros", legend=False,
                                  series=[Series("bars", x=edges, y=y, color="accent")], ymin_zero=True))
        k = int(np.argmax(counts))
        self.read.set([("Ancho del intervalo", f(edges[1] - edges[0], 3) + " px"),
                       ("Intervalo más frecuente", f"{f(edges[k], 2)}–{f(edges[k + 1], 2)}"),
                       ("Datos en ese intervalo", str(int(counts[k])))])


class L3MediaMediana(LessonPage):
    number = 3
    title = "Media y mediana"
    subtitle = "Dos formas de encontrar el valor «típico»"
    text = ("La <b>media</b> (promedio) suma todos los datos y divide entre cuántos son:<br>"
            "<span style='font-family:monospace'>x̄ = (x₁ + x₂ + … + x_N) / N</span><br><br>"
            "La <b>mediana</b> es el dato del medio cuando los ordenamos de menor a mayor: la mitad de los datos queda "
            "por debajo y la otra mitad por encima.<br><br>"
            "Si los datos son simétricos, media y mediana casi coinciden. Si hay datos muy raros, la media se deja "
            "arrastrar y la mediana casi no se mueve: decimos que la mediana es <b>robusta</b>.")
    tryit = ["Agrega datos raros (distancias cercanas a 0 px, como las de una detección fallida).",
             "Compara cuánto se mueve la media y cuánto la mediana."]
    quiz = ("Si aparecen algunos datos muy extremos, ¿cuál cambia menos?", ["La media", "La mediana", "Las dos cambian igual"], 1,
            "¡Bien! La mediana solo mira el dato del medio, así que los extremos casi no la afectan.",
            "Recuerda: la media suma todos los valores, incluidos los extremos.")

    def build(self):
        self.n = slider(20, 8484, 2000, 20)
        self.n_lbl = label("", "mono")
        self.ctl("Cuadros usados", self.n, self.n_lbl)
        self.bad = slider(0, 300, 0, 5)
        self.bad_lbl = label("", "mono")
        self.ctl("Datos raros agregados", self.bad, self.bad_lbl)

    def update_view(self, *a):
        d = self.data()
        n = min(self.n.value(), d["sep"].size)
        x = d["sep"][:n]
        k = self.bad.value()
        rng = np.random.default_rng(1)
        x = np.concatenate([x, rng.uniform(0.2, 1.5, k)])
        self.n_lbl.setText(str(n))
        self.bad_lbl.setText(str(k))
        s = stats.summarize(x)
        sp = histogram_spec(x, bins=40, title="Histograma con la media y la mediana", xlabel="Distancia (px)",
                            normal=False, mean_line=True, median_line=True)
        self.show_chart(sp)
        self.read.set([("Media x̄", f(s.mean) + " px"), ("Mediana", f(s.median) + " px"),
                       ("Diferencia", f(s.mean - s.median) + " px")])


class L4Dispersion(LessonPage):
    number = 4
    title = "Dispersión: varianza y desviación estándar"
    subtitle = "Qué tan separados están los datos de la media"
    text = ("Dos grupos pueden tener la misma media y ser muy distintos: uno con datos apretados y otro muy disperso. "
            "La <b>desviación estándar</b> σ mide la distancia típica de los datos a la media:<br>"
            "<span style='font-family:monospace'>σ = √( Σ (xᵢ − x̄)² / (N − 1) )</span><br>"
            "La <b>varianza</b> es σ².<br><br>"
            "<b>Aquí está la clave del experimento:</b> si el aire estuviera quieto, la distancia entre los dos puntos "
            "sería siempre igual y σ sería cero. La turbulencia hace que la distancia cambie; <b>σ mide la turbulencia</b>. "
            "Con σ y la física del instrumento se calcula el seeing.")
    tryit = ["Mueve «Turbulencia»: la campana se ensancha o se angosta.",
             "Fíjate en que la media no cambia, pero σ y el seeing sí."]
    quiz = ("Si cada desviación (xᵢ − x̄) se duplica, la desviación estándar…", ["Se duplica", "Se cuadruplica", "No cambia"], 0,
            "Correcto. (La varianza, que es σ², sí se cuadruplica.)",
            "σ está en las mismas unidades que los datos: si las distancias a la media se duplican, σ también.")

    def build(self):
        self.fac = slider(25, 250, 100, 5)
        self.f_lbl = label("", "mono")
        self.ctl("Turbulencia (× la real)", self.fac, self.f_lbl,
                 "Simula un cielo más quieto o más turbulento multiplicando las desviaciones respecto a la media.")

    def update_view(self, *a):
        d = self.data()
        k = self.fac.value() / 100
        self.f_lbl.setText(f"{k:.2f}×".replace(".", ","))
        x0 = d["sep"]
        m = float(np.mean(x0))
        x = m + k * (x0 - m)
        s = stats.summarize(x)
        lim = (m - 4 * 2.5 * np.std(x0), m + 4 * 2.5 * np.std(x0))
        sp = histogram_spec(x, bins=60, title="La banda sombreada es x̄ ± σ", xlabel="Distancia (px)", normal=True,
                            mean_line=True, sigma_band=1, lim=lim)
        self.show_chart(sp)
        self.read.set([("Desviación σ", f(s.std) + " px"), ("Varianza σ²", f(s.var) + " px²"),
                       ("Seeing (escala 1″/px)", f(seeing_example(s.std), 2) + "″")])


class L5Normal(LessonPage):
    number = 5
    title = "La distribución normal"
    subtitle = "La campana de Gauss y la regla 68–95–99,7"
    text = ("Cuando una medición depende de muchísimos efectos pequeños y al azar (como miles de burbujas de aire), "
            "los datos suelen formar una <b>campana</b>: la distribución <b>normal</b> o de Gauss.<br><br>"
            "La campana queda definida solo por la media x̄ y la desviación σ, y cumple la <b>regla 68–95–99,7</b>:"
            "<br>• cerca del 68 % de los datos está a menos de 1 σ de la media,<br>• cerca del 95 % a menos de 2 σ,"
            "<br>• casi todos (99,7 %) a menos de 3 σ.<br><br>"
            "Compara los porcentajes de tus datos reales con los de la teoría.")
    tryit = ["Activa las bandas de 1, 2 y 3 σ.", "¿Se parece la curva teórica a las barras reales?"]
    quiz = ("Aproximadamente, ¿qué porcentaje de los datos cae a menos de 2 σ de la media?", ["50 %", "68 %", "95 %"], 2,
            "¡Exacto! Alrededor del 95 %.", "Revisa la regla 68–95–99,7.")

    def build(self):
        self.k = QComboBox()
        for t in ("1 σ", "2 σ", "3 σ"):
            self.k.addItem(t)
        self.ctl("Mostrar bandas hasta", self.k)

    def update_view(self, *a):
        d = self.data()
        x = d["sep"]
        s = stats.summarize(x)
        k = self.k.currentIndex() + 1
        sp = histogram_spec(x, bins=50, title="Datos reales y curva normal teórica", xlabel="Distancia (px)",
                            ylabel="Densidad", density=True, normal=True, mean_line=True, sigma_band=k)
        self.show_chart(sp)
        real = [stats.fraction_within(x, s.mean, s.std, j) * 100 for j in (1, 2, 3)]
        self.read.set([("Dentro de 1 σ (teoría 68,3 %)", f(real[0], 1) + " %"),
                       ("Dentro de 2 σ (teoría 95,4 %)", f(real[1], 1) + " %"),
                       ("Dentro de 3 σ (teoría 99,7 %)", f(real[2], 1) + " %")])


class L6Muestras(LessonPage):
    number = 6
    title = "Muestras y error de la media"
    subtitle = "¿Cuántos cuadros necesito para confiar en el resultado?"
    text = ("Si tomamos solo unos pocos cuadros al azar, su media cambia cada vez. Si repetimos eso miles de veces, las "
            "medias también forman una campana (es el <b>teorema del límite central</b>).<br><br>"
            "El ancho de esa campana de medias es el <b>error estándar de la media</b>:<br>"
            "<span style='font-family:monospace'>error = σ / √n</span><br><br>"
            "Por eso grabamos miles de cuadros: con <b>4 veces más</b> cuadros el error se reduce a la <b>mitad</b>; con "
            "100 veces más, a la décima parte.")
    tryit = ["Pon un tamaño de muestra pequeño (5) y luego grande (500).",
             "Compara el error predicho σ/√n con la dispersión real de las 1.000 medias."]
    quiz = ("Si usas 4 veces más cuadros, el error de la media…", ["Se multiplica por 4", "Se reduce a la mitad", "No cambia"], 1,
            "¡Muy bien! √4 = 2, así que el error se divide entre 2.", "Recuerda: error = σ/√n.")

    def build(self):
        self.n = slider(2, 1000, 10)
        self.n_lbl = label("", "mono")
        self.ctl("Tamaño de cada muestra (n)", self.n, self.n_lbl)
        self.seed = 0
        self.controls.add(button("Tomar otras 1.000 muestras", slot=self._again))

    def _again(self):
        self.seed += 1
        self.update_view()

    def update_view(self, *a):
        d = self.data()
        x = d["sep"]
        n = self.n.value()
        self.n_lbl.setText(str(n))
        means = stats.sample_means(x, n, repeats=1000, seed=self.seed)
        s = stats.summarize(x)
        sm = stats.summarize(means)
        lim = (s.mean - 4 * s.std / math.sqrt(2), s.mean + 4 * s.std / math.sqrt(2))
        sp = histogram_spec(means, bins=40, title=f"Medias de 1.000 muestras de {n} cuadros", xlabel="Media de la muestra (px)",
                            ylabel="Muestras", normal=True, mean_line=True, lim=lim)
        self.show_chart(sp)
        self.read.set([("σ de los datos", f(s.std) + " px"), ("Error predicho σ/√n", f(s.std / math.sqrt(n), 4) + " px"),
                       ("Dispersión real de las medias", f(sm.std, 4) + " px")])


class L7Atipicos(LessonPage):
    number = 7
    title = "Datos atípicos"
    subtitle = "Un error que cambió un resultado real"
    text = ("Un <b>dato atípico</b> está muy lejos del resto. Puede ser real o un error de medición.<br><br>"
            "<b>Historia real:</b> en el programa original con el que empezó este proyecto, 68 cuadros del video de Altair "
            "mostraban un solo punto. El programa los emparejó mal y produjo distancias falsas cercanas a 0 px. Con solo "
            "68 datos malos entre 8.484, la desviación estándar <b>casi se duplicó</b> y el seeing salía peor de lo real."
            "<br><br>TurbuLENS detecta esos cuadros y además aplica un <b>recorte robusto</b>: descarta los datos que se "
            "alejan más de 5 «σ robustas» de la mediana (usa la MAD, que no se deja arrastrar por los extremos).")
    tryit = ["Agrega detecciones fallidas y mira cuánto crece σ.", "Activa la limpieza: σ vuelve a su valor real."]
    quiz = ("Unos pocos datos falsos cercanos a 0 px hacen que σ…", ["Aumente mucho", "Disminuya", "No cambie"], 0,
            "Exacto: como están muy lejos de la media, pesan muchísimo en la suma de cuadrados.",
            "Piensa en (xᵢ − x̄)²: un dato muy lejano aporta un cuadrado enorme.")

    def build(self):
        self.bad = slider(0, 200, 68, 1)
        self.b_lbl = label("", "mono")
        self.ctl("Detecciones fallidas", self.bad, self.b_lbl)
        self.clean = QCheckBox("Aplicar limpieza (recorte a 5 σ robustas)")
        self.ctl("Limpieza", self.clean)

    def update_view(self, *a):
        d = self.data()
        k = self.bad.value()
        self.b_lbl.setText(str(k))
        rng = np.random.default_rng(7)
        x = np.concatenate([d["sep"], rng.uniform(0.1, 1.2, k)])
        removed = 0
        if self.clean.isChecked():
            keep = stats.sigma_clip_mask(x, 5.0)
            removed = int((~keep).sum())
            x = x[keep]
        s = stats.summarize(x)
        s0 = stats.summarize(d["sep"])
        sp = histogram_spec(x, bins=70, title="Histograma (los atípicos aparecen a la izquierda)", xlabel="Distancia (px)",
                            normal=False, mean_line=True, median_line=True, lim=(0, float(np.max(d["sep"])) + 0.5))
        self.show_chart(sp)
        self.read.set([("Desviación σ", f(s.std) + " px"), ("σ sin atípicos", f(s0.std) + " px"),
                       ("Datos descartados", str(removed))])


class L8Correlacion(LessonPage):
    number = 8
    title = "Dos variables: correlación"
    subtitle = "¿Una medición se parece a la otra?"
    text = ("Cuando tenemos <b>dos variables</b> para cada cuadro, un <b>diagrama de dispersión</b> pone una en el eje "
            "x y otra en el eje y. El <b>coeficiente de correlación r</b> va de −1 a 1:<br>"
            "• r ≈ 1: cuando una sube, la otra también;<br>• r ≈ −1: cuando una sube, la otra baja;<br>"
            "• r ≈ 0: no hay relación lineal.<br><br>"
            "La atmósfera tiene «memoria» corta: un cuadro se parece al siguiente (r alto) pero no a uno de medio segundo "
            "después. Así se ve que la turbulencia cambia en milisegundos.")
    tryit = ["Compara «un cuadro y el siguiente» con «medio segundo después».",
             "Mira el movimiento longitudinal contra el transversal."]
    quiz = ("Si r está muy cerca de 0, significa que…", ["Las variables son iguales", "No hay relación lineal entre ellas",
                                                          "Una es el doble de la otra"], 1,
            "Correcto.", "r mide qué tan bien se alinean los puntos en una recta.")

    def build(self):
        self.mode = QComboBox()
        for t in ("Un cuadro y el siguiente", "Un cuadro y 5 cuadros después", "Un cuadro y medio segundo después",
                  "Longitudinal vs. transversal"):
            self.mode.addItem(t)
        self.ctl("Comparar", self.mode)

    def update_view(self, *a):
        d = self.data()
        i = self.mode.currentIndex()
        if i == 3:
            x = d["lon"] - np.mean(d["lon"])
            y = d["tra"] - np.mean(d["tra"])
            xl, yl = "Δ longitudinal (px)", "Δ transversal (px)"
        else:
            lag = {0: 1, 1: 5, 2: 30}[i]
            sep = d["sep"]
            x, y = sep[:-lag], sep[lag:]
            xl, yl = "Distancia en el cuadro i (px)", f"Distancia en el cuadro i + {lag} (px)"
        r = stats.pearson_r(x, y)
        step = max(1, x.size // 2500)
        self.show_chart(ChartSpec(title="Diagrama de dispersión", xlabel=xl, ylabel=yl, legend=False,
                                  series=[Series("scatter", x=x[::step], y=y[::step], color="accent", alpha=0.35, size=2.0)]))
        self.read.set([("Correlación r", f(r, 2)), ("Puntos", str(x.size)), ("r²", f(r * r, 2))])


class L9Laboratorio(LessonPage):
    number = 9
    title = "Laboratorio libre"
    subtitle = "Explora los datos como quieras"
    text = ("Combina todo lo aprendido. Elige la variable, cuántos cuadros usar y cómo ver el histograma.<br><br>"
            "<b>Separación</b>: la distancia entre los dos puntos.<br><b>Longitudinal</b>: el movimiento a lo largo de la "
            "línea que une los dos orificios.<br><b>Transversal</b>: el movimiento perpendicular.<br><br>"
            "Puedes guardar los datos en CSV para seguir analizándolos en una hoja de cálculo.")
    tryit = ["¿Tienen la misma σ el movimiento longitudinal y el transversal?",
             "¿Con cuántos cuadros se estabiliza la media?"]

    def build(self):
        self.var = QComboBox()
        for t in ("Separación", "Longitudinal", "Transversal"):
            self.var.addItem(t)
        self.ctl("Variable", self.var)
        self.n = slider(20, 8484, 8484, 20)
        self.n_lbl = label("", "mono")
        self.ctl("Cuadros", self.n, self.n_lbl)
        self.bins = slider(5, 90, 40)
        self.b_lbl = label("", "mono")
        self.ctl("Intervalos", self.bins, self.b_lbl)
        self.curve = QCheckBox("Curva normal")
        self.curve.setChecked(True)
        self.band = QCheckBox("Banda ± σ")
        self.ctl("Mostrar", self.curve)
        self.ctl("", self.band)
        self.controls.add(button("Guardar estos datos (CSV)…", slot=self._csv))

    def _x(self):
        d = self.data()
        key = ("sep", "lon", "tra")[self.var.currentIndex()]
        n = min(self.n.value(), d[key].size)
        return d[key][:n], d["t"][:n]

    def update_view(self, *a):
        x, _ = self._x()
        self.n_lbl.setText(str(x.size))
        self.b_lbl.setText(str(self.bins.value()))
        sp = histogram_spec(x, bins=self.bins.value(), title=f"{self.var.currentText()}: histograma", xlabel="px",
                            normal=self.curve.isChecked(), mean_line=True, median_line=True,
                            sigma_band=1 if self.band.isChecked() else 0)
        self.show_chart(sp)
        s = stats.summarize(x)
        self.read.set([("N", str(s.n)), ("Media", f(s.mean)), ("Mediana", f(s.median)), ("σ", f(s.std)),
                       ("Error de la media", f(s.sem, 4)), ("Rango", f"{f(s.min, 2)} – {f(s.max, 2)}")])

    def _csv(self):
        x, t = self._x()
        p, _ = QFileDialog.getSaveFileName(self, "Guardar datos", "datos_turbulens.csv", "CSV (*.csv)", options=dialog_options())
        if not p:
            return
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("tiempo_s,valor_px\n")
            for a, b in zip(t, x):
                fh.write(f"{a:.4f},{b:.5f}\n")
        self.main.toast("Datos guardados.")


# ------------------------------------------------------------------- quiz
QUIZ = [
    ("Cada cuadro del video aporta…", ["Un dato de la distancia entre los dos puntos", "Diez datos", "Ningún dato"], 0,
     "Un dato por cuadro."),
    ("Un histograma muestra…", ["Cómo cambia un dato en el tiempo", "Cuántos datos caen en cada intervalo",
                                "La foto de la estrella"], 1, "Cuenta datos por intervalo."),
    ("La mediana es…", ["El promedio", "El dato del medio al ordenarlos", "El dato más repetido"], 1,
     "La mitad de los datos queda a cada lado."),
    ("En el DIMM, una desviación estándar σ más grande significa…", ["Cielo más quieto", "Más turbulencia",
                                                                      "Telescopio más grande"], 1,
     "σ mide cuánto se mueve la imagen: más turbulencia."),
    ("Según la regla 68–95–99,7, ¿qué fracción cae a menos de 1 σ?", ["Cerca del 68 %", "Cerca del 95 %", "El 100 %"], 0,
     "Alrededor de dos tercios."),
    ("Para reducir a la mitad el error de la media necesito…", ["El doble de cuadros", "4 veces más cuadros",
                                                                 "La mitad de cuadros"], 1, "Error = σ/√n."),
    ("¿Qué estadístico es más robusto frente a datos atípicos?", ["La media", "La mediana", "La varianza"], 1,
     "La mediana casi no se mueve con los extremos."),
    ("¿Por qué titilan las estrellas?", ["Porque cambian de brillo de verdad", "Por el aire en movimiento de nuestra atmósfera",
                                         "Por el telescopio"], 1, "Las burbujas de aire desvían la luz."),
    ("¿Por qué el DIMM usa dos orificios y no uno?",
     ["Para tener más luz", "Para medir la diferencia: si el telescopio tiembla, los dos puntos se mueven juntos",
      "Para ver dos estrellas"], 1, "Medir la diferencia cancela las vibraciones del telescopio."),
    ("Un seeing de 1″ es…", ["Excelente", "Aceptable", "Muy turbulento"], 0, "Como en los mejores observatorios."),
    ("Si r = 0,9 entre un cuadro y el siguiente, significa que…", ["Se parecen mucho", "No tienen relación",
                                                                    "Son opuestos"], 0,
     "La atmósfera cambia poco en 1/60 de segundo."),
]


class QuizPage(Page):
    title = "10. Ponte a prueba"
    subtitle = "Preguntas de estadística y del experimento"

    def __init__(self, main):
        super().__init__(main)
        self.score = label("", "h2")
        self.head.addWidget(self.score)
        self.items = []
        grid = QGridLayout()
        grid.setSpacing(12)
        for k, (q, opts, ok, why) in enumerate(QUIZ):
            c = Card(margins=(14, 12, 14, 12))
            c.add(label(f"{k + 1}. {q}", "h2", wrap=True))
            bs = []
            fb = label("", wrap=True)
            for i, o in enumerate(opts):
                b = button(o, "option")
                b.clicked.connect(lambda _=False, k=k, i=i: self.pick(k, i))
                bs.append(b)
                c.add(b)
            c.add(fb)
            self.items.append({"btns": bs, "fb": fb, "ok": ok, "why": why, "ans": None})
            grid.addWidget(c, k // 2, k % 2)
        self.lay.addLayout(grid)
        self.lay.addLayout(hbox(button("Reiniciar respuestas", slot=self.reset), "stretch"))
        self.lay.addStretch(1)
        self._score()

    def pick(self, k, i):
        it = self.items[k]
        it["ans"] = i
        pal = theme.pal
        for j, b in enumerate(it["btns"]):
            b.setProperty("state", "ok" if j == it["ok"] else ("bad" if j == i else ""))
            b.style().unpolish(b)
            b.style().polish(b)
        right = i == it["ok"]
        it["fb"].setText(("¡Correcto! " if right else "No exactamente. ") + it["why"])
        it["fb"].setStyleSheet(f"color:{pal['good'] if right else pal['bad']}; font-weight:600;")
        self._score()

    def reset(self):
        for it in self.items:
            it["ans"] = None
            it["fb"].setText("")
            for b in it["btns"]:
                b.setProperty("state", "")
                b.style().unpolish(b)
                b.style().polish(b)
        self._score()

    def _score(self):
        done = [it for it in self.items if it["ans"] is not None]
        ok = sum(1 for it in done if it["ans"] == it["ok"])
        self.score.setText(f"{ok} de {len(self.items)} correctas" if done else f"{len(self.items)} preguntas")


# --------------------------------------------------------- astronomía sencilla
class SeeingScale(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(54)

    def paintEvent(self, ev):
        pal = theme.pal
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        parts = [(1, pal["good"], "≈ 1″ excelente"), (2, pal["warn"], "2–3″ aceptable"), (2, pal["bad"], "más de 3″ muy turbulento")]
        x = 0.0
        tot = sum(a for a, _, _ in parts)
        for a, c, t in parts:
            ww = w * a / tot
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawRoundedRect(QRectF(x + 1, 4, ww - 2, 16), 6, 6)
            p.setPen(QColor(pal["muted"]))
            p.drawText(QRectF(x, 24, ww, 22), Qt.AlignHCenter | Qt.AlignVCenter, t)
            x += ww
        p.end()


class AstroTitilan(Page):
    title = "¿Por qué titilan las estrellas?"
    subtitle = "La estrella, en sencillo"

    def __init__(self, main):
        super().__init__(main)
        c = Card()
        t = label(
            "Imagina que miras una moneda en el fondo de una piscina. Si el agua está quieta, la ves nítida. Si alguien "
            "mueve el agua, la moneda <b>tiembla</b> y se ve borrosa.<br><br>"
            "Con las estrellas pasa lo mismo: su luz cruza el <b>aire</b> de la Tierra, que tiene burbujas calientes y "
            "frías moviéndose todo el tiempo. Esas burbujas desvían la luz un poquito y la estrella parece <b>bailar</b> "
            "y titilar.<br><br>"
            "El <b>seeing</b> es un número que dice <b>qué tanto</b> baila la estrella. Se mide en «segundos de arco» (″), "
            "una medida de ángulo muy pequeña: <b>1″ es el tamaño de una moneda de 1 cm vista a 2 km</b>.<br><br>"
            "Entre más pequeño el seeing, más nítido el cielo y mejor para observar.", wrap=True, rich=True)
        t.setStyleSheet("font-size:16px;")
        c.add(t, label("Escala del seeing", "h2"), SeeingScale())
        self.lay.addWidget(c)
        self.lay.addLayout(hbox(button("Siguiente: el truco de los dos huequitos →", "primary",
                                       lambda: self.main.go("dimm")), "stretch"))
        self.lay.addStretch(1)


class AstroDimm(Page):
    title = "El truco de los dos huequitos"
    subtitle = "Así funciona el DIMM, paso a paso"

    def __init__(self, main):
        super().__init__(main)
        c = Card()
        t = label(
            "Tapamos el telescopio con una cartulina que tiene <b>dos huequitos</b>. Así la luz de la estrella entra por "
            "dos caminos distintos y vemos <b>dos puntos</b> en vez de uno.<br><br>"
            "Si el telescopio tiembla (por el viento o por tocarlo), <b>los dos puntos se mueven juntos</b>. Pero la "
            "turbulencia del aire afecta a cada camino de forma distinta, así que los puntos se acercan y se alejan "
            "<b>entre sí</b>.<br><br>"
            "Por eso no medimos dónde está la estrella, sino la <b>distancia entre los dos puntos</b>. Esa distancia "
            "cambia un poquito en cada cuadro del video, y la estadística de esos cambios nos dice el seeing.",
            wrap=True, rich=True)
        t.setStyleSheet("font-size:16px;")
        c.add(t)
        self.lay.addWidget(c)
        steps = [("1", "Un telescopio", "Uno de 4 pulgadas o más es suficiente."),
                 ("2", "La máscara", "Cartulina con dos huequitos. Para 8 pulgadas: de 2,5 cm, separados 14 cm."),
                 ("3", "Una cámara de video", "Una cámara de 30 cuadros por segundo o más, o una DSLR en modo video."),
                 ("4", "Desenfoca un poquito", "Así se ven dos puntos separados, uno por cada huequito."),
                 ("5", "Graba 15 a 20 segundos", "Elige una estrella brillante y alta en el cielo (más de 40°).")]
        g = QGridLayout()
        g.setSpacing(12)
        for i, (n, a, b) in enumerate(steps):
            k = Card(margins=(14, 12, 14, 12))
            num = label(n, "chip")
            num.setFixedWidth(34)
            num.setAlignment(Qt.AlignCenter)
            k.add(num, label(a, "h2"), label(b, "muted", wrap=True))
            g.addWidget(k, 0, i)
        self.lay.addLayout(g)
        self.lay.addWidget(label("Basado en el protocolo «Determina la nitidez del cielo nocturno» (ANDEAN ROAD, 2026), capítulo 4.", "small"))
        self.lay.addLayout(hbox(button("Siguiente: el simulador →", "primary", lambda: self.main.go("simulador")), "stretch"))
        self.lay.addStretch(1)


class StarSim(QWidget):
    """Dos puntos que bailan según la turbulencia elegida."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 300)
        self.turb = 0.35
        self.off = [(0.0, 0.0), (0.0, 0.0)]
        self.sep_px = 60.0

    def step(self):
        a = self.turb * 9
        # Movimiento común (como si temblara el telescopio) + diferencial (turbulencia)
        cx, cy = random.gauss(0, a * 0.6), random.gauss(0, a * 0.6)
        d1 = (random.gauss(0, a), random.gauss(0, a))
        d2 = (random.gauss(0, a), random.gauss(0, a))
        self.off = [(cx + d1[0], cy + d1[1]), (cx + d2[0], cy + d2[1])]
        self.update()
        x1 = -self.sep_px / 2 + self.off[0][0]
        x2 = self.sep_px / 2 + self.off[1][0]
        y1, y2 = self.off[0][1], self.off[1][1]
        return math.hypot(x2 - x1, y2 - y1)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.pal["preview"]))
        cx, cy = self.width() / 2, self.height() / 2
        blur = 6 + self.turb * 22
        for k, sx in enumerate((-self.sep_px / 2, self.sep_px / 2)):
            x = cx + sx + self.off[k][0]
            y = cy + self.off[k][1]
            g = QRadialGradient(QPointF(x, y), blur)
            g.setColorAt(0, QColor(255, 255, 255, 255))
            g.setColorAt(0.35, QColor(255, 240, 220, 200))
            g.setColorAt(1, QColor(255, 220, 180, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(x, y), blur, blur)
        p.setPen(QColor("#D8DAE0"))
        p.drawText(QRectF(10, 6, 300, 20), Qt.AlignLeft, "Simulación ilustrativa")
        p.end()


class AstroSim(Page):
    title = "Simulador de turbulencia"
    subtitle = "Mira cómo baila la estrella y cómo se arma el histograma"

    def __init__(self, main):
        super().__init__(main)
        row = QHBoxLayout()
        row.setSpacing(16)
        left = Card(margins=(8, 8, 8, 8))
        self.sim = StarSim()
        left.add(self.sim)
        right = QVBoxLayout()
        ctl = Card("Controles")
        self.t = slider(5, 100, 35)
        self.t.valueChanged.connect(self._turb)
        ctl.add(hbox(label("Turbulencia"), self.t))
        self.pause = button("Pausa", slot=self._pause, checkable=True)
        ctl.add(hbox(self.pause, button("Reiniciar datos", slot=self._reset), "stretch"))
        right.addWidget(ctl)
        cc = Card(margins=(8, 8, 8, 8))
        self.chart = charts.ChartWidget(min_h=220)
        cc.add(self.chart)
        right.addWidget(cc, 1)
        self.read = Readouts(cols=3)
        right.addWidget(self.read)
        row.addWidget(left, 1)
        row.addLayout(right, 1)
        self.lay.addLayout(row)
        self.lay.addWidget(label("Cada vez que la estrella se mueve, el simulador mide la distancia entre los dos puntos y la "
                                 "agrega al histograma. Con más turbulencia la campana se ensancha: σ crece y el seeing empeora. "
                                 "El temblor que mueve a los dos puntos juntos no cambia la distancia: por eso el DIMM no se "
                                 "confunde con las vibraciones del telescopio.", "muted", wrap=True))
        self.lay.addLayout(hbox(button("Ahora aprende la estadística →", "primary", lambda: self.main.go("l1")),
                                button("Analiza un video real", slot=lambda: self.main.go("video")), "stretch"))
        self.lay.addStretch(1)
        self.data = []
        self.timer = QTimer(self)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._tick)

    def _turb(self, v):
        self.sim.turb = v / 100
        self._reset()

    def _pause(self):
        if self.pause.isChecked():
            self.timer.stop()
        elif self.isVisible():
            self.timer.start()

    def _reset(self):
        self.data = []

    def _tick(self):
        self.data.append(self.sim.step())
        if len(self.data) % 3 == 0:
            self._draw()

    def _draw(self):
        x = np.array(self.data[-3000:])
        if x.size < 3:
            return
        sp = histogram_spec(x, bins=30, title="Distancias medidas por el simulador", xlabel="Distancia (px)",
                            normal=x.size > 20, mean_line=True, lim=(30, 90))
        self.chart.set_spec(sp)
        self.chart.set_palette(theme.pal)
        s = stats.summarize(x)
        self.read.set([("Mediciones", str(s.n)), ("σ", f(s.std, 2) + " px"),
                       ("Seeing (ilustrativo)", f(0.4 + s.std * 0.33, 1) + "″")])

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self.pause.isChecked():
            self.timer.start()

    def hideEvent(self, ev):
        self.timer.stop()
        super().hideEvent(ev)

    def on_theme(self, pal):
        self.chart.set_palette(pal)


class Welcome(Page):
    title = "Aprende estadística midiendo cómo tiembla una estrella"
    subtitle = "Modo educativo de TurbuLENS · para colegios y cursos"

    def __init__(self, main):
        super().__init__(main)
        intro = Card()
        t = label("Vamos a usar un experimento real de astronomía para aprender <b>estadística</b>: datos, histogramas, "
                  "media, mediana, desviación estándar, la campana de Gauss, el error de una medición, los datos atípicos "
                  "y la correlación.<br><br>Todo con miles de mediciones reales de una estrella grabada con un telescopio. "
                  "Puedes usar los datos de ejemplo (la estrella Altair) o procesar tu propio video.", wrap=True, rich=True)
        t.setStyleSheet("font-size:16px;")
        intro.add(t)
        self.lay.addWidget(intro)
        g = QGridLayout()
        g.setSpacing(14)
        paths = [
            ("Estadística con una estrella", "El corazón del modo educativo: 9 lecciones interactivas y una prueba final.",
             "Empezar la lección 1 →", "l1", True),
            ("La estrella, en sencillo", "Por qué titilan las estrellas y cómo se mide, en 3 pasos cortos.",
             "Ver la estrella →", "titilan", False),
            ("Tu propio video", "Procesa un video grabado por tu clase y estudia tus propios datos.",
             "Cargar un video →", "video", False),
        ]
        for i, (a, b, c, key, main_) in enumerate(paths):
            k = Card(margins=(18, 16, 18, 16))
            k.add(label(a, "h2"), label(b, "muted", wrap=True), "stretch",
                  hbox(button(c, "primary" if main_ else None, lambda _=False, key=key: self.main.go(key)), "stretch"))
            g.addWidget(k, 0, i)
        self.lay.addLayout(g)
        self.lay.addStretch(1)


LESSONS = [L1Datos, L2Histograma, L3MediaMediana, L4Dispersion, L5Normal, L6Muestras, L7Atipicos, L8Correlacion, L9Laboratorio]
