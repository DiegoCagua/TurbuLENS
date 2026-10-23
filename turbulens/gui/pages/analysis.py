# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Páginas del flujo de análisis (compartidas por los dos modos)."""

from __future__ import annotations

import math
import os
import threading
import time

import numpy as np
from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ... import charts
from ...core import pipeline, stats
from ...core.detect import config_for_radius, detect_pairs, estimate_spot_size
from ...core.dimm import quality_label
from ...core.export import CHART_FORMATS, DATA_FORMATS, REPORT_FORMATS, export_analysis, export_history_table
from ...core.video import VideoError, file_dialog_filter
from ...core.writers import FORMATS, estimate_bytes
from ... import reports
from ..canvas import RoiCanvas, Timeline, fmt_time, to_qimage
from ..theme import theme
from ..widgets import TRANSPORT_HELP, ask, ask_text, notify, dialog_options, speed_combo, transport_buttons, Card, ChipGroup, HelpButton, Kpi, button, hbox, label, vbox
from .base import Page
from ...i18n import integer, localize_number_text, num, tr


def fnum(v, d=2, unit=""):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    s = num(v, d)
    return s + unit


def miles(n) -> str:
    return integer(n)


def human_bytes(b: float) -> str:
    if b >= 1e9:
        return fnum(b / 1e9, 2, " GB")
    if b >= 1e6:
        return fnum(b / 1e6, 1, " MB")
    return fnum(max(b, 1e3) / 1e3, 0, " kB")


def nav_row(back=None, nxt=None):
    row = QHBoxLayout()
    if back:
        row.addWidget(button(back[0], slot=back[1]))
    row.addStretch(1)
    if nxt:
        row.addWidget(button(nxt[0], "primary", slot=nxt[1]))
    return row


# =============================================================================
class VideoPage(Page):
    title = "Cargar video"
    subtitle = "MOV, MP4, AVI, MKV, WMV, MTS, WebM, SER, FITS y muchos más formatos"

    def __init__(self, main):
        super().__init__(main)
        self.setAcceptDrops(True)
        self.lay.addWidget(self.edu_tip(
            "<b>¿Qué vas a hacer?</b> Un video es una serie de fotos muy rápidas («cuadros»). "
            "La app mide cada cuadro por separado y después usa estadística para resumir miles de mediciones en un número: el seeing."))
        self.drop = button("Suelta tu video aquí\no haz clic para buscarlo en tu computador", "drop", self.pick)
        self.drop.setMinimumHeight(230)
        note = label("El video no se copia: se lee directamente desde su carpeta.", "muted")
        self.empty = QWidget()
        self.empty.setObjectName("transparent")
        self.empty.setLayout(vbox(self.drop, hbox(note, "stretch")))

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(420, 236)
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setStyleSheet("background: #000; border-radius: 12px;")
        self.info_card = Card("Información del video")
        self.info_grid = QGridLayout()
        self.info_grid.setHorizontalSpacing(16)
        self.info_grid.setVerticalSpacing(6)
        self.info_card.add(self.info_grid)
        self.info_card.add(hbox(button("Cambiar video", slot=self.pick), "stretch",
                                button("Siguiente: recorte y tramo →", "primary", slot=lambda: self.main.go("region"))))
        self.info_card.setMinimumWidth(320)
        self.loaded = QWidget()
        self.loaded.setObjectName("transparent")
        row = QHBoxLayout(self.loaded)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        row.addWidget(self.preview, 3)
        row.addWidget(self.info_card, 2)
        self.lay.addWidget(self.empty)
        self.lay.addWidget(self.loaded)
        self.lay.addStretch(1)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        if urls:
            self.open(urls[0].toLocalFile())

    def pick(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Elegir video"), "", file_dialog_filter(), options=dialog_options())
        if path:
            self.open(path)

    def open(self, path: str):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.s.open_video(path)
        except (VideoError, Exception) as exc:
            QApplication.restoreOverrideCursor()
            notify(self, "No se pudo abrir el video", str(exc), "warning")
            return
        QApplication.restoreOverrideCursor()
        self.refresh()

    def refresh(self):
        has = self.s.info is not None
        self.empty.setVisible(not has)
        self.loaded.setVisible(has)
        if not has:
            return
        i = self.s.info
        while self.info_grid.count():
            it = self.info_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rows = [
            ("Archivo", i.name), ("Formato", f"{i.codec} · {i.container.split(',')[0].upper()}"),
            ("Resolución", f"{i.width} × {i.height} px"), ("Cuadros por segundo", fnum(i.fps, 2)),
            ("Cuadros", miles(i.n_frames)), ("Duración", fmt_time(i.duration)),
            ("Profundidad", f"{i.bit_depth} bits"), ("Tamaño", human_bytes(i.size_bytes)),
        ]
        for r, (k, v) in enumerate(rows):
            self.info_grid.addWidget(label(k, "muted"), r, 0)
            lv = label(v, "mono", wrap=True)
            self.info_grid.addWidget(lv, r, 1)
        self._show_preview()

    def _show_preview(self):
        arr = self.s.frame_image(0)
        if arr is None:
            return
        pm = QPixmap.fromImage(to_qimage(arr))
        self.preview.setPixmap(pm.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.s.info is not None:
            self._show_preview()


# =============================================================================
REGION_HELP = (
    "<b>Región (recorte)</b><br>La estrella ocupa unos pocos píxeles de la imagen. Guardar y medir solo esa zona hace "
    "los archivos cientos de veces más livianos y el análisis más rápido.<br><br>"
    "<b>Cómo se usa, como en Paint:</b><ul style='margin-left:-16px'>"
    "<li><b>Arrastra</b> en la imagen para dibujar una región nueva.</li>"
    "<li><b>Arrastra desde adentro</b> para moverla.</li>"
    "<li>Tira de los <b>cuadritos blancos</b> para cambiar su tamaño.</li>"
    "<li>Un <b>clic</b> la centra en ese punto.</li>"
    "<li><b>Rueda</b> del ratón: zoom. <b>Clic derecho</b> arrastrando: mover la vista.</li>"
    "<li>Teclado: flechas mueven 1 px; Mayús + flechas cambian el tamaño.</li></ul>"
    "Deja margen alrededor de los dos puntos: la turbulencia los hace moverse."
)
TRACK_HELP = (
    "<b>Seguir a la estrella</b><br>Si el telescopio no tiene motor de seguimiento, la estrella se desplaza por la imagen "
    "durante el video. Con esta opción la región se recentra sola en cada bloque de cuadros, así nunca se pierde la "
    "estrella y todas las imágenes guardadas quedan centradas en ella."
)
TRAMO_HELP = (
    "<b>Tramo: la parte del video que se usa</b><br>Quita el inicio y el final si moviste el telescopio al grabar, y "
    "cualquier momento con nubes o golpes. Se recomiendan al menos 15 a 20 segundos estables.<br><br>"
    "<b>Línea de tiempo:</b> arrastra las barras de <b>Entrada</b> y <b>Salida</b>; haz clic en otro punto para ver ese cuadro."
    "<br><br><b>Botones:</b><ul style='margin-left:-16px'>"
    "<li><b>&lt;&lt;</b> y <b>&gt;&gt;</b> reproducen hacia atrás o hacia adelante a velocidad constante; la lista elige "
    "la velocidad respecto al video real (<b>1.0×</b> es la original). Presiónalos otra vez para detener.</li>"
    "<li><b>&lt;</b> y <b>&gt;</b> mueven exactamente un cuadro.</li>"
    "<li><b>[ Entrada</b> y <b>Salida ]</b> marcan el inicio y el fin del tramo en el cuadro que estás viendo.</li>"
    "<li><b>Ir a</b>: escribe un número de cuadro (por ejemplo 1820) o un tiempo (por ejemplo 01:05.5).</li></ul>"
    "Después de procesar, Resultados muestra si hubo golpes o ráfagas para ajustar el tramo."
)


class RegionPage(Page):
    title = "Recorte y tramo"
    subtitle = "Dónde mirar en cada cuadro y qué parte del video usar"
    scrollable = False


    def __init__(self, main):
        super().__init__(main)
        self.lay.setSpacing(10)
        self.lay.addWidget(self.edu_tip(
            "<b>Dos decisiones:</b> 1) la <b>región</b> que rodea a la estrella (los dos puntos brillantes) y 2) el "
            "<b>tramo</b> del video que vas a medir. Pulsa los botones <b>!</b> para ver cómo funciona cada control."))

        # Barra de la región (una sola línea)
        self.zoom_chips = ChipGroup([(str(z), f"{z}×") for z in (1, 2, 4, 8, 16)])
        self.zoom_chips.set_value("4")
        self.zoom_chips.changed.connect(self._zoom)
        self.size_box = QComboBox()
        self.size_box.addItem("Tamaño rápido…", None)
        for s in (48, 64, 96, 128, 192, 256):
            self.size_box.addItem(f"{s} × {s} px", s)
        self.size_box.addItem("Cuadro completo", 0)
        self.size_box.activated.connect(self._size)
        self.track = QCheckBox(tr("Seguir a la estrella"))
        self.track.setChecked(True)
        self.track.toggled.connect(self._track)
        self.status = label("", "small")
        bar = hbox(label("Región", "h2"), HelpButton(REGION_HELP), 10, label("Zoom", "small"), self.zoom_chips,
                   button("◎ Ajustar a la estrella", slot=self.autofit, tip="Busca la imagen doble y ajusta la región"),
                   self.size_box, self.track, HelpButton(TRACK_HELP), "stretch", spacing=8)
        self.lay.addLayout(bar)

        # Lienzo + columna derecha
        self.canvas = RoiCanvas()
        self.canvas.roi_changed.connect(self._roi_from_canvas)
        side = QVBoxLayout()
        side.setSpacing(8)
        self.zoomview = QLabel()
        self.zoomview.setFixedSize(200, 200)
        self.zoomview.setAlignment(Qt.AlignCenter)
        self.zoomview.setStyleSheet("background:#000; border-radius:8px;")
        side.addWidget(label("Dentro de la región", "small"))
        side.addWidget(self.zoomview)
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        g = QGridLayout()
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(4)
        self.spins = {}
        for i, (k, t) in enumerate((("x", "x"), ("y", "y"), ("w", "ancho"), ("h", "alto"))):
            sp = QSpinBox()
            sp.setRange(0, 20000)
            sp.setSuffix(" px")
            sp.editingFinished.connect(self._roi_from_spins)
            self.spins[k] = sp
            g.addWidget(label(t, "small"), i // 2 * 2, i % 2)
            g.addWidget(sp, i // 2 * 2 + 1, i % 2)
        side.addLayout(g)
        side.addStretch(1)
        sidew = QWidget()
        sidew.setObjectName("transparent")
        sidew.setLayout(side)
        sidew.setFixedWidth(208)
        mid = QHBoxLayout()
        mid.setSpacing(12)
        mid.addWidget(self.canvas, 1)
        mid.addWidget(sidew)
        self.lay.addLayout(mid, 1)

        # Tramo: línea de tiempo + controles en una línea
        self.timeline = Timeline()
        self.timeline.frame_changed.connect(self._frame_from_timeline)
        self.timeline.range_changed.connect(self._range_from_timeline)
        self.span_lbl = label("", "small")
        self.lay.addLayout(hbox(label("Tramo", "h2"), HelpButton(TRAMO_HELP), "stretch", self.span_lbl, spacing=8))
        self.lay.addWidget(self.timeline)

        self.b_rew, self.b_prev, self.b_next, self.b_ff = transport_buttons(
            self._rew, lambda: self.step(-1), lambda: self.step(1), self._ff)
        self.pos_lbl = label("00:00.0 · 0", "mono")
        self.pos_lbl.setMinimumWidth(130)
        self.pos_lbl.setAlignment(Qt.AlignCenter)
        self.speed = speed_combo(8.0)
        self.goto = QLineEdit()
        self.goto.setPlaceholderText("cuadro o mm:ss.s")
        self.goto.setFixedWidth(130)
        self.goto.returnPressed.connect(self._goto)
        trow = hbox(self.b_rew, self.b_prev, self.pos_lbl, self.b_next, self.b_ff, self.speed, 12,
                    button("[ Entrada", slot=self.mark_in, tip="Marcar el inicio del tramo aquí"),
                    button("Salida ]", slot=self.mark_out, tip="Marcar el fin del tramo aquí"),
                    button("Todo", slot=self.use_all, tip="Usar el video completo"), 12,
                    label("Ir a", "small"), self.goto, button("Ir", slot=self._goto), "stretch", spacing=6)
        self.lay.addLayout(trow)
        self.lay.addLayout(nav_row(("← Video", lambda: self.main.go("video")),
                                   ("Siguiente: parámetros →", lambda: self.main.go("parametros"))))

        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._tick)
        self._play_dir = 0
        self._play_pos = 0.0
        self._last_t = 0.0

    # ----------------------------------------------------------------- estado
    def refresh(self):
        s = self.s
        has = s.info is not None
        for w in (self.canvas, self.timeline):
            w.setEnabled(has)
        if not has:
            self.canvas.set_frame(None)
            self.status.setText("Primero carga un video.")
            return
        self.timeline.set_video(s.info.n_frames, s.info.fps)
        self.canvas.set_roi(s.roi, recenter=True)
        self.track.setChecked(s.track)
        self._show_frame(s.frame)
        self._sync_spins()
        self._update_span()

    def _show_frame(self, idx: int):
        s = self.s
        idx = int(min(max(idx, 0), s.info.n_frames - 1))
        s.frame = idx
        prev_idx = getattr(self, "_shown_idx", None)
        arr = s.frame_image(idx)
        self._arr = arr
        self._shown_idx = idx
        if s.track and prev_idx is not None and prev_idx != idx:
            self._follow_star(arr)
        self.canvas.track_roi = s.tracked_roi_at(idx)
        self.canvas.overlay = tr("Zoom {}× · cuadro {} · {}").format(localize_number_text(f"{self.canvas.zoom:g}"), miles(idx),
                                                                  fmt_time(idx / s.info.fps))
        self.canvas.set_frame(arr)
        self.timeline.set_state(s.tin, s.tout, idx)
        self.pos_lbl.setText(f"{fmt_time(idx / s.info.fps)} · {miles(idx)}")
        self._update_zoomview()

    def _follow_star(self, arr):
        """«Seguir a la estrella»: recentra la región sobre la imagen doble en el cuadro que se muestra."""
        x, y, w, h = self.s.roi
        try:
            cx, cy = pipeline.find_star(arr, near=(x + w / 2, y + h / 2), radius=int(max(48, 1.5 * max(w, h))))
        except Exception:
            return
        roi = self.canvas._clamp_roi(cx - w / 2, cy - h / 2, w, h)
        if roi != tuple(self.s.roi):
            self.s.set_roi(roi, frame=self.s.frame)
            self.canvas.set_roi(roi, recenter=True)
            self._sync_spins()

    def _update_zoomview(self):
        if getattr(self, "_arr", None) is None:
            return
        x, y, w, h = self.s.roi
        crop = self._arr[y:y + h, x:x + w]
        if crop.size == 0:
            return
        pm = QPixmap.fromImage(to_qimage(crop)).scaled(200, 200, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.zoomview.setPixmap(pm)
        # Revisión rápida: ¿están los dos puntos dentro y con margen?
        try:
            sub = crop.astype(np.float32)
            d = detect_pairs(sub[None], config_for_radius(estimate_spot_size(sub[None])))
            ok = bool(d["valid"][0])
            m = min(d["x1"][0], d["x2"][0], d["y1"][0], d["y2"][0], w - d["x1"][0], w - d["x2"][0],
                    h - d["y1"][0], h - d["y2"][0])
        except Exception:
            ok, m = False, 0
        pal = theme.pal
        if w * h > 0.5 * self.s.info.width * self.s.info.height:
            txt, col = "Región muy grande: archivos pesados. Pulsa «Ajustar a la estrella».", pal["warn"]
        elif not ok:
            txt, col = "No se ven los dos puntos en este cuadro: mueve o agranda la región.", pal["bad"]
        elif m < 8:
            txt, col = "Muy ajustada: deja más margen para el movimiento.", pal["warn"]
        else:
            txt, col = "Contiene los dos puntos ✓", pal["good"]
        self.status.setText(txt)
        self.status.setStyleSheet(f"color:{col}; font-weight:600;")

    def _sync_spins(self):
        x, y, w, h = self.s.roi
        for k, v in zip("xywh", (x, y, w, h)):
            sp = self.spins[k]
            sp.blockSignals(True)
            sp.setValue(int(v))
            sp.blockSignals(False)

    def _update_span(self):
        s = self.s
        n = s.tout - s.tin + 1
        sec = n / s.info.fps
        warn = "" if sec >= 15 else tr(" · menos de 15 s: menos confiable")
        self.span_lbl.setText(tr("Tramo {} – {} · {} s · {} cuadros").format(
            fmt_time(s.tin / s.info.fps), fmt_time(s.tout / s.info.fps), fnum(sec, 1), miles(n)) + warn)
        self.span_lbl.setStyleSheet(f"color:{theme.pal['warn']};" if warn else "")

    # -------------------------------------------------------------- región
    def _roi_from_canvas(self, roi):
        self.s.set_roi(roi, frame=self.s.frame)
        self._sync_spins()
        self._update_zoomview()

    def _roi_from_spins(self):
        x, y, w, h = (self.spins[k].value() for k in "xywh")
        roi = self.canvas._clamp_roi(x, y, w, h)
        self.s.set_roi(roi, frame=self.s.frame)
        self.canvas.set_roi(roi)
        self._sync_spins()
        self._update_zoomview()

    def _zoom(self):
        v = self.zoom_chips.value()
        if v:
            self.canvas.set_zoom(float(v))
            self._show_frame(self.s.frame)

    def _size(self):
        if self.s.info is None:
            return
        sz = self.size_box.currentData()
        self.size_box.setCurrentIndex(0)
        if sz is None:
            return
        W, H = self.s.info.width, self.s.info.height
        if sz == 0:
            roi = (0, 0, W, H)
        else:
            x, y, w, h = self.s.roi
            cx, cy = x + w / 2, y + h / 2
            roi = self.canvas._clamp_roi(cx - sz / 2, cy - sz / 2, sz, sz)
        self.s.set_roi(roi, frame=self.s.frame)
        self.canvas.set_roi(roi, recenter=True)
        self._sync_spins()
        self._update_zoomview()

    def autofit(self):
        if getattr(self, "_arr", None) is None:
            return
        roi = pipeline.fit_roi(self._arr)
        self.s.set_roi(roi, frame=self.s.frame)
        self.canvas.set_roi(roi, recenter=True)
        self._sync_spins()
        self._update_zoomview()

    def _track(self, on):
        self.s.track = bool(on)

    # -------------------------------------------------------------- tiempo
    def _frame_from_timeline(self, f):
        self.stop()
        self._show_frame(f)

    def _range_from_timeline(self, a, b):
        self.s.tin, self.s.tout = a, b
        self._update_span()

    def step(self, d):
        if self.s.info is None:
            return
        self.stop()
        self._show_frame(self.s.frame + d)

    def _rew(self):
        self._play(-1 if self.b_rew.isChecked() else 0)

    def _ff(self):
        self._play(1 if self.b_ff.isChecked() else 0)

    def _play(self, direction):
        if self.s.info is None:
            self.b_rew.setChecked(False)
            self.b_ff.setChecked(False)
            return
        self._play_dir = direction
        self.b_rew.setChecked(direction < 0)
        self.b_ff.setChecked(direction > 0)
        if direction == 0:
            self.timer.stop()
            return
        self._play_pos = float(self.s.frame)
        self._last_t = time.perf_counter()
        self.timer.start()

    def stop(self):
        if self._play_dir:
            self._play(0)

    def _tick(self):
        now = time.perf_counter()
        dt = min(0.25, now - self._last_t)
        self._last_t = now
        sp = self.speed.currentData() or 1.0
        self._play_pos += self._play_dir * sp * self.s.info.fps * dt
        n = self.s.info.n_frames
        if self._play_pos <= 0 or self._play_pos >= n - 1:
            self._play_pos = min(max(self._play_pos, 0), n - 1)
            self._show_frame(int(self._play_pos))
            self._play(0)
            return
        self._show_frame(int(self._play_pos))

    def mark_in(self):
        if self.s.info is None:
            return
        self.s.tin = min(self.s.frame, self.s.tout - 1)
        self.timeline.set_state(self.s.tin, self.s.tout, self.s.frame)
        self._update_span()

    def mark_out(self):
        if self.s.info is None:
            return
        self.s.tout = max(self.s.frame, self.s.tin + 1)
        self.timeline.set_state(self.s.tin, self.s.tout, self.s.frame)
        self._update_span()

    def use_all(self):
        if self.s.info is None:
            return
        self.s.tin, self.s.tout = 0, self.s.info.n_frames - 1
        self.timeline.set_state(self.s.tin, self.s.tout, self.s.frame)
        self._update_span()

    def _goto(self):
        if self.s.info is None:
            return
        t = self.goto.text().strip().replace(",", ".")
        idx = None
        try:
            if ":" in t:
                mm, ss = t.split(":", 1)
                idx = int(round((int(mm) * 60 + float(ss)) * self.s.info.fps))
            elif "." in t:
                idx = int(round(float(t) * self.s.info.fps))
            elif t:
                idx = int(t)
        except ValueError:
            idx = None
        if idx is None or not (0 <= idx < self.s.info.n_frames):
            self.goto.setProperty("invalid", True)
            self.goto.style().unpolish(self.goto)
            self.goto.style().polish(self.goto)
            self.goto.setToolTip(tr("Escribe un cuadro entre 0 y {} o un tiempo mm:ss.s").format(self.s.info.n_frames - 1))
            return
        self.goto.setProperty("invalid", False)
        self.goto.style().unpolish(self.goto)
        self.goto.style().polish(self.goto)
        self.goto.clear()
        self.stop()
        self._show_frame(idx)

    def hideEvent(self, ev):
        self.stop()
        super().hideEvent(ev)


# =============================================================================
PARAMS_HELP = (
    "<b>Datos del montaje</b><ul style='margin-left:-16px'>"
    "<li><b>Diámetro de cada orificio (D)</b> y <b>separación entre centros (B)</b> de la máscara. Para un telescopio "
    "de 8 pulgadas: orificios de 2,5 cm separados 14 cm.</li>"
    "<li><b>Longitud de onda</b>: 550 nm (luz visible, verde) si no usas filtro.</li>"
    "<li><b>Escala de placa</b>: cuántos segundos de arco del cielo caben en un píxel. Depende de la focal del "
    "telescopio y del tamaño de píxel de la cámara: 206,265 × píxel (µm) ÷ focal (mm).</li>"
    "<li><b>Altura</b> (opcional): si la conoces, el seeing también se corrige al cenit.</li></ul>"
    "Si cambias estos datos después de procesar, el resultado se recalcula al instante."
)
SAVE_HELP = (
    "<b>Imágenes a guardar</b><br>Cada cuadro del tramo se guarda recortado a la región (y centrado en la estrella si "
    "la sigues).<ul style='margin-left:-16px'>"
    "<li><b>PNG</b> (predeterminado): sin pérdida y el más liviano para medir.</li>"
    "<li><b>TIFF 16 bits</b>: conserva toda la profundidad de cámaras astronómicas.</li>"
    "<li><b>JPG</b>: más liviano, pero altera los píxeles; no recomendado para medir.</li>"
    "<li><b>NumPy / FITS</b>: un solo archivo con todos los cuadros (cubo), listo para Python o DS9.</li></ul>"
    "En la carpeta de salida también quedan <b>mediciones.csv</b> y <b>resumen.json</b>."
)


class ParamsPage(Page):
    title = "Parámetros"
    subtitle = "Datos de tu telescopio y de la máscara, y qué imágenes guardar"

    def __init__(self, main):
        super().__init__(main)
        self.lay.addWidget(self.edu_tip(
            "<b>¿Para qué sirven?</b> La app mide en <b>píxeles</b>. Con estos datos convierte píxeles en un ángulo del "
            "cielo (segundos de arco) y aplica el modelo físico del DIMM para obtener el seeing."))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        tel = Card("Telescopio y máscara", help_text=PARAMS_HELP)
        self.D = self._dspin(0.1, 100, 2.5, " cm", 2)
        self.B = self._dspin(0.2, 300, 14.0, " cm", 2)
        self.lam = self._dspin(300, 1100, 550, " nm", 0)
        self.scale = QLineEdit()
        self.scale.setPlaceholderText("ej. 1,0")
        self.scale.setFixedWidth(120)
        self.scale.textChanged.connect(self._changed)
        self.alt_on = QCheckBox(tr("Conozco la altura de la estrella"))
        self.alt = self._dspin(5, 90, 60, "°", 0)
        self.alt.setEnabled(False)
        self.alt_on.toggled.connect(lambda on: (self.alt.setEnabled(on), self._changed()))
        f = QGridLayout()
        f.setHorizontalSpacing(12)
        f.setVerticalSpacing(8)
        for r, (t, w) in enumerate((("Diámetro de cada orificio (D)", self.D), ("Separación entre orificios (B)", self.B),
                                    ("Longitud de onda (λ)", self.lam), ("Escala de placa (″/px)", self.scale))):
            f.addWidget(label(t), r, 0)
            f.addWidget(w, r, 1, Qt.AlignRight)
        f.addWidget(self.alt_on, 4, 0)
        f.addWidget(self.alt, 4, 1, Qt.AlignRight)
        tel.add(f)
        calc = Card(kind="panel2", margins=(12, 10, 12, 10))
        self.pix = self._dspin(0.5, 50, 4.3, " µm", 2)
        self.focal = self._dspin(50, 20000, 1000, " mm", 0)
        self.calc_lbl = label("", "mono")
        calc.add(label("¿No conoces la escala? Calcúlala:", "small"),
                 hbox(label("Píxel", "small"), self.pix, label("Focal", "small"), self.focal, self.calc_lbl, "stretch",
                      button("Usar", slot=self._use_calc)))
        for w in (self.pix, self.focal):
            w.valueChanged.connect(self._calc)
        tel.add(calc)
        from ... import SCALE_LINKS

        links = "<br>".join(f"• <a href='{u}'>{tr(t)}</a>" for u, t in SCALE_LINKS)
        tel.add(label(tr("<b>Datos para tu equipo:</b> la focal del telescopio está en la etiqueta del tubo (por ejemplo "
                         "«D = 203 mm, F = 2032 mm») y el tamaño de píxel en la ficha de la cámara.<br>") + links,
                      "small", wrap=True, rich=True))
        self.prof = QComboBox()
        self.prof.setMinimumWidth(160)
        self.prof.activated.connect(self._load_profile)
        self.ex_btn = button("Usar valores de ejemplo de la clase", slot=self._example)
        tel.add(hbox(label("Perfil de equipo", "small"), self.prof, button("Guardar perfil", slot=self._save_profile),
                     button("Eliminar", slot=self._del_profile), "stretch"))
        tel.add(self.ex_btn)

        sav = Card("Imágenes a guardar", help_text=SAVE_HELP)
        self.save_on = QCheckBox(tr("Guardar los cuadros como imágenes"))
        self.save_on.setChecked(True)
        self.save_on.toggled.connect(self._changed)
        self.fmt = ChipGroup([("PNG", "PNG · recomendado"), ("TIFF", "TIFF 16 bits"), ("JPG", "JPG"),
                              ("NPY", "NumPy"), ("FITS", "FITS")])
        self.fmt.set_value("PNG")
        self.fmt.changed.connect(self._changed)
        self.every = QSpinBox()
        self.every.setRange(1, 1000)
        self.every.setValue(1)
        self.every.valueChanged.connect(self._changed)
        self.out = QLineEdit()
        self.out.textChanged.connect(self._changed)
        self.est = label("", wrap=True)
        estc = Card(kind="soft", margins=(12, 10, 12, 10))
        estc.add(self.est)
        sav.add(self.save_on, self.fmt,
                hbox(label("Guardar 1 de cada"), self.every, label("cuadros"), "stretch"),
                label("Carpeta de salida", "small"),
                hbox(self.out, button("Cambiar…", slot=self._pick_out)),
                estc)
        sav.lay.addStretch(1)

        grid.addWidget(tel, 0, 0)
        grid.addWidget(sav, 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.lay.addLayout(grid)
        self.lay.addLayout(nav_row(("← Recorte y tramo", lambda: self.main.go("region")),
                                   ("Siguiente: procesar →", lambda: self.main.go("procesar"))))
        self.lay.addStretch(1)
        self._loading = False
        self._calc()

    def _dspin(self, lo, hi, val, suffix, dec):
        sp = QDoubleSpinBox()
        sp.setRange(lo, hi)
        sp.setDecimals(dec)
        sp.setValue(val)
        sp.setSuffix(suffix)
        sp.setFixedWidth(120)
        sp.valueChanged.connect(self._changed)
        return sp

    def _scale_value(self):
        t = self.scale.text().strip().replace(",", ".")
        try:
            v = float(t)
            return v if v > 0 else None
        except ValueError:
            return None

    def refresh(self):
        self._loading = True
        s = self.s
        p = s.params
        self.D.setValue(p.D_cm)
        self.B.setValue(p.B_cm)
        self.lam.setValue(p.lambda_nm)
        self.scale.setText("" if not p.scale_arcsec_px else fnum(p.scale_arcsec_px, 3).rstrip("0").rstrip(","))
        self.alt_on.setChecked(p.altitude_deg is not None)
        if p.altitude_deg is not None:
            self.alt.setValue(p.altitude_deg)
        self.save_on.setChecked(s.save_images)
        self.fmt.set_value(s.fmt)
        self.every.setValue(s.every_n)
        self.out.setText(s.out_dir)
        self.ex_btn.setVisible(self.is_edu)
        self._reload_profiles()
        self._loading = False
        self._update_est()

    def _changed(self, *a):
        if self._loading:
            return
        s = self.s
        p = s.params
        p.D_cm = self.D.value()
        p.B_cm = self.B.value()
        p.lambda_nm = self.lam.value()
        p.scale_arcsec_px = self._scale_value()
        p.altitude_deg = self.alt.value() if self.alt_on.isChecked() else None
        bad = self.scale.text().strip() != "" and p.scale_arcsec_px is None
        self.scale.setProperty("invalid", bad)
        self.scale.style().unpolish(self.scale)
        self.scale.style().polish(self.scale)
        s.save_images = self.save_on.isChecked()
        s.fmt = self.fmt.value() or "PNG"
        s.every_n = self.every.value()
        s.out_dir = self.out.text().strip()
        for w in (self.fmt, self.every, self.out):
            w.setEnabled(s.save_images)
        self._update_est()
        if s.result is not None:
            s.reanalyze()

    def _update_est(self):
        s = self.s
        if s.info is None:
            self.est.setText("Carga un video para estimar el espacio en disco.")
            return
        n = s.tout - s.tin + 1
        nsave = (n + s.every_n - 1) // s.every_n if s.save_images else 0
        b = estimate_bytes(s.fmt, nsave, s.roi[2], s.roi[3], s.info.bit_depth)
        self.est.setText(tr("Se guardarán <b>{}</b> imágenes de {} × {} px · espacio aproximado: <b>{}</b>").format(
            miles(nsave), s.roi[2], s.roi[3], human_bytes(b) if nsave else tr("0 (solo análisis)")))

    def _calc(self):
        v = 206.265 * self.pix.value() / self.focal.value()
        self.calc_lbl.setText(f"= {fnum(v, 3)} ″/px")
        self._calc_v = v

    def _use_calc(self):
        self.scale.setText(fnum(self._calc_v, 3))

    def _example(self):
        self.D.setValue(2.5)
        self.B.setValue(14)
        self.lam.setValue(550)
        self.scale.setText("1,0")

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de salida", self.out.text() or "", options=dialog_options() | QFileDialog.Option.ShowDirsOnly)
        if d:
            self.out.setText(d)

    # Perfiles de equipo (JSON en la carpeta de datos)
    def _profiles_path(self):
        from ...core.history import app_data_dir

        return os.path.join(self.s.history.root, f"perfiles_{self.s.mode}.json")

    def _read_profiles(self) -> dict:
        import json

        try:
            with open(self._profiles_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _reload_profiles(self):
        self.prof.clear()
        self.prof.addItem("—", None)
        for k in sorted(self._read_profiles()):
            self.prof.addItem(k, k)

    def _save_profile(self):
        import json

        name, ok = ask_text(self, "Guardar perfil", "Nombre del perfil (ej. «Celestron 8 + Nikon D5300»):")
        if not ok or not name.strip():
            return
        d = self._read_profiles()
        p = self.s.params
        d[name.strip()] = {"D_cm": p.D_cm, "B_cm": p.B_cm, "lambda_nm": p.lambda_nm, "scale": p.scale_arcsec_px}
        with open(self._profiles_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        self._reload_profiles()
        self.prof.setCurrentIndex(self.prof.findData(name.strip()))

    def _load_profile(self):
        k = self.prof.currentData()
        if not k:
            return
        v = self._read_profiles().get(k)
        if not v:
            return
        self.D.setValue(v.get("D_cm", 2.5))
        self.B.setValue(v.get("B_cm", 14))
        self.lam.setValue(v.get("lambda_nm", 550))
        sc = v.get("scale")
        self.scale.setText("" if not sc else fnum(sc, 3))

    def _del_profile(self):
        import json

        k = self.prof.currentData()
        if not k:
            return
        d = self._read_profiles()
        d.pop(k, None)
        with open(self._profiles_path(), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        self._reload_profiles()


# =============================================================================
class Worker(QObject):
    progress = Signal(int, int, float)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, reader, opts):
        super().__init__()
        self.reader = reader
        self.opts = opts
        self.cancel = threading.Event()

    def run(self):
        try:
            res = pipeline.run(self.reader, self.opts, progress=lambda a, b, f: self.progress.emit(a, b, f),
                               cancel=self.cancel)
            self.done.emit(res)
        except Exception as exc:  # pragma: no cover
            import traceback

            self.failed.emit(f"{exc}\n\n{traceback.format_exc(limit=3)}")


class ProcessPage(Page):
    title = "Procesar"
    subtitle = "Separa el video en imágenes y mide la distancia entre los dos puntos en cada cuadro"
    help_text = ("<b>¿Qué pasa al procesar?</b><br>En cada cuadro del tramo se recorta la región (siguiendo a la estrella), "
                 "se guarda la imagen y se buscan los dos puntos. Su centro se calcula como un «centro de masa» de la luz, "
                 "con precisión menor a un píxel. Al terminar se calculan las estadísticas y el seeing.<br><br>"
                 "Puedes cancelar en cualquier momento.")

    def __init__(self, main):
        super().__init__(main)
        self.lay.addWidget(self.edu_tip(
            "En cada cuadro la app busca los dos puntos brillantes, calcula su <b>centroide</b> (el centro de masa de la luz) "
            "y mide la distancia entre ellos. Al final tendrás miles de distancias: una por cuadro."))
        row = QHBoxLayout()
        row.setSpacing(16)
        run = Card("Estado")
        self.state = label("Listo para empezar", "h2")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.detail = label("", "muted")
        self.start_b = button("▶  Iniciar", "primary", self.start)
        self.start_b.setMinimumHeight(44)
        self.cancel_b = button("■  Cancelar", slot=self.cancel)
        self.cancel_b.setEnabled(False)
        self.res_b = button("Ver resultados →", "primary", lambda: self.main.go("resultados"))
        self.res_b.setVisible(False)
        run.add(self.state, self.bar, self.detail, hbox(self.start_b, self.cancel_b, self.res_b, "stretch"))
        run.lay.addStretch(1)
        self.sumc = Card("Resumen")
        self.sum_grid = QGridLayout()
        self.sum_grid.setVerticalSpacing(6)
        self.sumc.add(self.sum_grid)
        self.sumc.setMinimumWidth(300)
        row.addWidget(run, 3)
        row.addWidget(self.sumc, 2)
        self.lay.addLayout(row)
        self.lay.addStretch(1)
        self.thread = None
        self.worker = None

    def refresh(self):
        s = self.s
        while self.sum_grid.count():
            it = self.sum_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if s.info is None:
            self.start_b.setEnabled(False)
            self.state.setText("Primero carga un video")
            return
        if self.thread is None:
            self.start_b.setEnabled(True)
        n = s.tout - s.tin + 1
        nsave = (n + s.every_n - 1) // s.every_n if s.save_images else 0
        rows = [("Video", s.info.name), ("Tramo", f"{fmt_time(s.tin / s.info.fps)} – {fmt_time(s.tout / s.info.fps)}"),
                ("Cuadros a medir", miles(n)), ("Región", f"{s.roi[2]} × {s.roi[3]} px" + (tr(" · con seguimiento") if s.track else "")),
                ("Imágenes", f"{miles(nsave)} · {FORMATS[s.fmt]['label']}" if s.save_images else "No se guardan"),
                ("Escala", fnum(s.params.scale_arcsec_px, 3, " ″/px") if s.params.scale_arcsec_px else "Falta (sin seeing)"),
                ("Salida", s.out_dir if s.save_images else "—")]
        for r, (k, v) in enumerate(rows):
            self.sum_grid.addWidget(label(k, "muted"), r, 0, Qt.AlignTop)
            self.sum_grid.addWidget(label(v, wrap=True), r, 1)
        if s.result is not None and self.thread is None:
            self.res_b.setVisible(True)

    def start(self):
        s = self.s
        if s.info is None or self.thread is not None:
            return
        roi = s.roi
        if s.track and s.tin != s.roi_frame:
            try:
                f = s.frame_image(s.tin)
                x, y, w, h = roi
                cx, cy = pipeline.find_star(f, near=(x + w / 2, y + h / 2), radius=int(4 * max(w, h)))
                roi = (int(round(cx - w / 2)), int(round(cy - h / 2)), w, h)
            except Exception:
                pass
        base = os.path.splitext(s.info.name)[0][:40].replace(" ", "_") or "cuadro"
        opts = pipeline.ProcessOptions(roi=roi, start=s.tin, stop=s.tout, track=s.track, save_images=s.save_images,
                                       fmt=s.fmt, every_n=s.every_n, out_dir=s.out_dir if s.save_images else "",
                                       base_name=base)
        if s.save_images:
            try:
                os.makedirs(s.out_dir, exist_ok=True)
            except OSError as exc:
                notify(self, "Carpeta de salida", tr("No se pudo crear la carpeta:") + f"\n{exc}", "warning")
                return
        # Lector propio para el hilo (el de la vista previa sigue libre)
        from ...core.video import VideoReader

        reader = VideoReader(s.info.path)
        self.thread = QThread(self)
        self.worker = Worker(reader, opts)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self._reader = reader
        self._session = s
        self.start_b.setEnabled(False)
        self.cancel_b.setEnabled(True)
        self.res_b.setVisible(False)
        self.state.setText("Procesando…")
        self.bar.setValue(0)
        self.main.set_busy(True)
        self.thread.start()

    def _progress(self, a, b, fps):
        self.bar.setValue(int(1000 * a / max(1, b)))
        eta = (b - a) / fps if fps > 0 else 0
        self.detail.setText(tr("{} de {} cuadros · {} cuadros/s · faltan ~{}").format(miles(a), miles(b), fnum(fps, 0), fmt_time(eta)))

    def _finish_thread(self):
        if self.thread is not None:
            self.thread.quit()
            self.thread.wait(5000)
        try:
            self._reader.close()
        except Exception:
            pass
        self.thread = None
        self.worker = None
        self.start_b.setEnabled(True)
        self.cancel_b.setEnabled(False)
        self.main.set_busy(False)

    def _done(self, res):
        sess = self._session
        self._finish_thread()
        if res.cancelled:
            self.state.setText("Cancelado")
            self.detail.setText(tr("Se alcanzaron a medir {} cuadros.").format(miles(res.meas.size)))
            if res.meas.size < 10:
                return
        else:
            self.state.setText("Listo ✓")
            self.bar.setValue(1000)
            self.detail.setText(tr("{} cuadros en {} s · {} imágenes guardadas").format(
                miles(res.meas.size), fnum(res.elapsed_s, 1), miles(res.n_saved))
                + (" · " + " ".join(tr(n) for n in res.notes) if res.notes else ""))
        sess.set_result(res)
        self.res_b.setVisible(True)
        if not res.cancelled and sess is self.s:
            self.main.go("resultados")

    def _failed(self, msg):
        self._finish_thread()
        self.state.setText("Ocurrió un error")
        notify(self, "Error al procesar", msg, "error")

    def cancel(self):
        if self.worker is not None:
            self.worker.cancel.set()
            self.state.setText("Cancelando…")


# =============================================================================
def export_panel(owner, on_export, include_report=True, title="Exportar"):
    card = Card(title, help_text=(
        "<b>Formatos</b><ul style='margin-left:-16px'>"
        "<li><b>Datos</b>: CSV (hojas de cálculo), Excel, JSON (programación), NumPy (Python) y tabla FITS (astronomía).</li>"
        "<li><b>Gráficas</b>: «PDF solo gráficas» reúne las gráficas sin texto; PNG y SVG guardan cada gráfica por separado.</li>"
        "<li><b>Informe</b>: PDF con el resumen, los parámetros y las gráficas.</li></ul>"
        "Elige uno o varios formatos y pulsa Exportar."))
    groups = [("Datos", DATA_FORMATS), ("Gráficas", CHART_FORMATS)]
    if include_report:
        groups.append(("Informe", REPORT_FORMATS))
    chips = {}
    grid = QGridLayout()
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(8)
    for r, (gt, opts) in enumerate(groups):
        cg = ChipGroup(list(opts.items()), multi=True)
        chips[gt] = cg
        lb = label(gt, "small")
        lb.setMinimumWidth(70)
        grid.addWidget(lb, r, 0)
        grid.addWidget(cg, r, 1)
    grid.setColumnStretch(1, 1)
    chips["Datos"].set_values(["csv", "xlsx"])
    chips["Gráficas"].set_values(["pdfg"])
    card.add(grid)
    msg = label("", "small", wrap=True)
    btn = button("Exportar…", "primary", lambda: on_export([k for c in chips.values() for k in c.values()], msg))
    open_b = button("Abrir carpeta", slot=lambda: card._folder and open_folder(card._folder))
    open_b.setVisible(False)
    card.add(hbox(btn, msg, open_b, "stretch"))
    card.chips = chips
    card._folder = None

    def show_open(folder):
        card._folder = folder
        open_b.setVisible(True)

    card.show_open = show_open
    return card


def open_folder(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(path))


class ResultsPage(Page):
    title = "Resultados"
    subtitle = ""

    def __init__(self, main):
        super().__init__(main)
        self.labelEdit = QLineEdit()
        self.labelEdit.setPlaceholderText("Etiqueta (opcional), ej. «Altair, noche 1»")
        self.labelEdit.setFixedWidth(260)
        self.save_b = button("Guardar en historial", "primary", self.save)
        self.head.addWidget(self.labelEdit)
        self.head.addWidget(self.save_b)

        self.empty = Card()
        self.empty.add(label("Aún no hay resultados", "h2"),
                       label("Carga un video y procésalo para ver aquí el seeing, las estadísticas y las gráficas.", "muted", wrap=True),
                       hbox(button("Ir a procesar", "primary", lambda: self.main.go("procesar")), "stretch"))
        self.lay.addWidget(self.empty)

        self.body = QWidget()
        self.body.setObjectName("transparent")
        b = QVBoxLayout(self.body)
        b.setContentsMargins(0, 0, 0, 0)
        b.setSpacing(14)
        self.note = Card(kind="soft", margins=(14, 10, 14, 10))
        self.note_lbl = label("", wrap=True)
        self.note.add(self.note_lbl)
        b.addWidget(self.note)
        k = QGridLayout()
        k.setSpacing(12)
        self.k_eps = Kpi("Seeing estimado", accent=True, help_text=(
            "<b>Seeing (ε)</b>: el tamaño angular con que la turbulencia «borronea» una estrella, en segundos de arco (″). "
            "Es el promedio de los valores longitudinal y transversal. ≈1″ excelente, 2–3″ aceptable, más de 3″ muy turbulento."))
        self.k_l = Kpi("Seeing longitudinal", help_text="Calculado con la varianza del movimiento <b>a lo largo</b> de la línea que une los dos orificios.")
        self.k_t = Kpi("Seeing transversal", help_text="Calculado con la varianza del movimiento <b>perpendicular</b> a la línea que une los orificios. Debe parecerse al longitudinal.")
        self.k_r0 = Kpi("Parámetro de Fried r0", help_text="Diámetro de una «celda» de aire en la que la turbulencia casi no deforma la luz. Más grande = mejor cielo.")
        self.k_sep = Kpi("Separación media")
        self.k_sd = Kpi("Desviación estándar σ", help_text="Cuánto varía la separación entre cuadros. Más σ = más turbulencia.")
        self.k_n = Kpi("Cuadros usados", help_text="Cuadros con los dos puntos detectados, tras descartar datos atípicos (más de 5 σ robustas de la mediana).")
        self.k_z = Kpi("Seeing en el cenit", help_text="Seeing corregido a la vertical con la altura de la estrella: ε·(cos z)^(3/5).")
        for i, w in enumerate((self.k_eps, self.k_l, self.k_t, self.k_r0, self.k_sep, self.k_sd, self.k_n, self.k_z)):
            k.addWidget(w, i // 4, i % 4)
        b.addLayout(k)
        self.c_hist = charts.ChartWidget(min_h=300)
        self.c_sc = charts.ChartWidget(min_h=240)
        self.c_t = charts.ChartWidget(min_h=240)
        r1 = QHBoxLayout()
        r1.setSpacing(12)
        ca = Card("Centroides cuadro a cuadro", margins=(12, 10, 12, 10), help_text=(
            "<b>¿Qué es el centroide?</b><br>Cada punto de la imagen doble ocupa varios píxeles. El <b>centroide</b> es su "
            "«centro de masa de la luz»: el promedio de las posiciones de los píxeles, pesado por su brillo. Por eso puede caer "
            "<b>entre</b> píxeles y medir movimientos de centésimas de píxel.<br><br>"
            "La animación muestra una muestra de los cuadros procesados: las cruces son los centroides que encontró "
            "TurbuLENS y la línea punteada es la distancia que se mide en cada cuadro. Con <b>Rastro</b> se ven las posiciones "
            "anteriores: así se ve cómo la turbulencia mueve cada punto.<ul style='margin-left:-16px'>"
            "<li><b>▶</b> reproduce o pausa; <b>&lt;</b> y <b>&gt;</b> avanzan un cuadro de la muestra.</li>"
            "<li>La barra permite ir a cualquier cuadro y la lista cambia la velocidad.</li></ul>"))
        from ..centroids import CentroidPlayer

        self.player = CentroidPlayer()
        self.player.setMinimumHeight(380)
        ca.add(self.player)
        ch = Card(margins=(8, 8, 8, 8))
        ch.add(self.c_hist)
        r1.addWidget(ca, 2)
        r1.addWidget(ch, 3)
        b.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(12)
        ct = Card(margins=(8, 8, 8, 8))
        ct.add(self.c_t, hbox(label("Una subida aislada de σ suele ser un golpe al telescopio o una ráfaga de viento.", "small"),
                              "stretch", button("Ajustar el tramo y procesar de nuevo", slot=lambda: self.main.go("region"))))
        cs = Card(margins=(8, 8, 8, 8))
        cs.add(self.c_sc)
        r2.addWidget(ct, 3)
        r2.addWidget(cs, 2)
        b.addLayout(r2)
        self.lay_edu_centroid = self.edu_tip(
            "<b>Mira la animación:</b> TurbuLENS no adivina dónde están los puntos; los calcula en cada cuadro como el centro "
            "de masa de la luz. Fíjate en que los dos puntos no se mueven igual: esa diferencia es lo que mide la turbulencia.")
        b.addWidget(self.lay_edu_centroid)
        self.edu = self.edu_tip(
            "<b>Lee la gráfica:</b> el histograma muestra cuántos cuadros tuvieron cada distancia. Tiene forma de campana: casi "
            "todas las medidas están cerca de la media y pocas lejos. Qué tan <b>ancha</b> es la campana (σ) dice cuánta "
            "turbulencia hay. En el menú <b>Estadística</b> puedes explorar estos mismos datos paso a paso.")
        b.addWidget(self.edu)
        self.exp = export_panel(self, self.export)
        b.addWidget(self.exp)
        b.addLayout(hbox(button("Abrir carpeta de cuadros", slot=lambda: self.s.result and open_folder(self.s.result.out_dir)),
                         "stretch", label("Seeing calculado con el modelo de Tokovinin (2002), a partir de la varianza del "
                                          "movimiento diferencial.", "small")))
        self.lay.addWidget(self.body)
        self.lay.addStretch(1)

    def refresh(self):
        s = self.s
        has = s.result is not None and s.dimm is not None
        self.empty.setVisible(not has)
        self.body.setVisible(has)
        self.save_b.setVisible(has)
        self.labelEdit.setVisible(has)
        if not has:
            self.sub.setText("")
            return
        d = s.dimm
        r = s.result
        fps = r.video.get("fps", 30)
        self.sub.setText(tr("{} · tramo {} – {} · {} cuadros").format(
            r.video.get('name'), fmt_time(r.options.start / fps), fmt_time(r.options.stop / fps), miles(d.n_frames)))
        self.sub.setVisible(True)
        pal = theme.pal
        q = quality_label(d.eps)
        qcol = pal["good"] if q == "Excelente" else (pal["warn"] if q == "Aceptable" else (pal["bad"] if q == "Muy turbulento" else pal["muted"]))
        self.k_eps.set(fnum(d.eps, 2, "″"), q, qcol)
        self.k_l.set(fnum(d.eps_l, 2, "″"), f"σ = {fnum(d.sigma_l_px, 3)} px")
        self.k_t.set(fnum(d.eps_t, 2, "″"), f"σ = {fnum(d.sigma_t_px, 3)} px")
        self.k_r0.set(fnum(d.r0_cm, 1, " cm"), "")
        sc = s.params.scale_arcsec_px
        self.k_sep.set(fnum(d.mean_sep_px, 2, " px"), tr("= {}″ en el cielo").format(fnum(d.mean_sep_px * sc, 2)) if sc else tr("mediana {} px").format(fnum(d.median_sep_px, 2)))
        self.k_sd.set(fnum(d.std_sep_px, 3, " px"), "movimiento diferencial")
        pct = 100 * d.n_used / max(1, d.n_frames)
        self.k_n.set(miles(d.n_used), tr("{} % del tramo · {} sin detección").format(fnum(pct, 1), miles(d.n_frames - d.n_detected)))
        self.k_z.set(fnum(d.eps_zenith, 2, "″"), tr("masa de aire {}").format(fnum(d.airmass, 2)) if math.isfinite(d.airmass) else "indica la altura en Parámetros")
        notes = []
        if not sc:
            notes.append("<b>Falta la escala de placa:</b> ingrésala en Parámetros para obtener el seeing en segundos de arco. "
                         "El resultado se recalcula al instante, sin volver a procesar.")
        if r.notes:
            notes += [tr(n) for n in r.notes]
        if r.cancelled:
            notes.append("El procesamiento se canceló: estos resultados son parciales.")
        self.note.setVisible(bool(notes))
        self.note_lbl.setText("<br>".join(notes))
        self.specs = reports.analysis_charts(d, r.meas["t"], fps)
        if getattr(self, "_player_src", None) is not r:
            self._player_src = r
            self.player.set_data(r.preview_frames, r.preview_rows, r.meas, d.arrays.get("used"), fps)
        self.c_hist.set_spec(self.specs[0])
        if len(self.specs) > 2:
            self.c_t.set_spec(self.specs[1])
            self.c_sc.set_spec(self.specs[2])
        self.on_theme(pal)
        self.save_b.setText(tr("Guardado ✓ (#{})").format(s.saved_id) if s.saved_id else "Guardar en historial")
        self.save_b.setEnabled(not s.saved_id)

    def on_theme(self, pal):
        for c in (self.c_hist, self.c_sc, self.c_t):
            c.set_palette(pal)

    def save(self):
        s = self.s
        if s.result is None:
            return
        rid = s.save_to_history(self.labelEdit.text().strip())
        self.save_b.setText(tr("Guardado ✓ (#{})").format(rid))
        self.save_b.setEnabled(False)

    def export(self, formats, msg):
        s = self.s
        if not formats:
            msg.setText("Elige al menos un formato.")
            return
        start = s.result.out_dir or os.path.dirname(s.info.path) if s.info else ""
        folder = QFileDialog.getExistingDirectory(self, tr("Carpeta para exportar"), start, options=dialog_options() | QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        base = os.path.splitext(s.result.video.get("name", "turbulens"))[0][:40].replace(" ", "_")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            rec = s.record()
            out = export_analysis(rec, s.result.meas, s.dimm, formats, folder, base)
            out += reports.export_analysis_charts(self.specs, formats, folder, base, rec)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            notify(self, "Exportar", tr("No se pudo exportar:") + f"\n{exc}", "warning")
            return
        QApplication.restoreOverrideCursor()
        msg.setText(tr("Listo: {} archivo(s) en {}").format(len(out), folder))
        self.exp.show_open(folder)


# =============================================================================
class HistoryPage(Page):
    title = "Historial"
    subtitle = ""

    COLS = ["", "#", "Guardado", "Etiqueta", "Video", "Tramo", "Cuadros", "σ (px)", "Seeing (″)", "Escala (″/px)", "Notas"]

    def __init__(self, main):
        super().__init__(main)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setMinimumHeight(220)
        self.table.itemChanged.connect(lambda *_: self._chart())
        self.empty = Card()
        self.empty.add(label("Aún no hay análisis guardados", "h2"),
                       label("En Resultados pulsa «Guardar en historial». Guarda varios tramos, noches o escalas para compararlos.",
                             "muted", wrap=True))
        self.lay.addWidget(self.empty)
        self.content = QWidget()
        self.content.setObjectName("transparent")
        c = QVBoxLayout(self.content)
        c.setContentsMargins(0, 0, 0, 0)
        c.setSpacing(12)
        c.addLayout(hbox(button("Seleccionar todo", slot=self._all), button("Abrir en Resultados", slot=self._open),
                         button("Etiqueta y notas…", slot=self._notes), button("Eliminar seleccionados", slot=self._delete),
                         "stretch"))
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.table, 3)
        cc = Card(margins=(8, 8, 8, 8))
        self.chart = charts.ChartWidget(min_h=240)
        cc.add(self.chart)
        row.addWidget(cc, 2)
        c.addLayout(row)
        self.exp = export_panel(self, self.export, title="Exportar los análisis seleccionados")
        c.addWidget(self.exp)
        self.lay.addWidget(self.content)
        self.lay.addStretch(1)
        self._rows = []

    def refresh(self):
        s = self.s
        self.h1.setText("Mis mediciones" if self.is_edu else "Historial de estadísticas")
        self.sub.setText("Las mediciones del modo educativo se guardan aparte de las científicas." if self.is_edu else
                         "Base de datos local de tus análisis científicos, para comparar noches y épocas del año.")
        self.sub.setVisible(True)
        self._rows = s.history.list()
        has = bool(self._rows)
        self.empty.setVisible(not has)
        self.content.setVisible(has)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._rows))
        for i, r in enumerate(self._rows):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked)
            self.table.setItem(i, 0, chk)
            fps = r.get("fps") or 30
            vals = [str(r["id"]), r.get("created") or "", r.get("label") or "", r.get("video_name") or "",
                    f"{fmt_time((r.get('start') or 0) / fps)}–{fmt_time((r.get('stop') or 0) / fps)}",
                    miles(r.get("n_used") or 0), fnum(r.get("std_sep_px"), 3), fnum(r.get("eps"), 2),
                    fnum(r.get("scale"), 3), r.get("notes") or ""]
            for j, v in enumerate(vals, start=1):
                self.table.setItem(i, j, QTableWidgetItem(v))
        self.table.blockSignals(False)
        self._chart()

    def _selected(self) -> list[dict]:
        out = []
        for i, r in enumerate(self._rows):
            it = self.table.item(i, 0)
            if it is not None and it.checkState() == Qt.Checked:
                out.append(r)
        return out

    def _chart(self):
        sel = self._selected()
        specs = reports.history_charts(sel) if sel else []
        self.chart.set_spec(specs[0] if specs else charts.ChartSpec(title="Selecciona análisis para compararlos"))
        self.chart.set_palette(theme.pal)

    def on_theme(self, pal):
        self.chart.set_palette(pal)

    def _all(self):
        sel = self._selected()
        st = Qt.Unchecked if len(sel) == len(self._rows) else Qt.Checked
        self.table.blockSignals(True)
        for i in range(len(self._rows)):
            self.table.item(i, 0).setCheckState(st)
        self.table.blockSignals(False)
        self._chart()

    def _current(self):
        i = self.table.currentRow()
        return self._rows[i] if 0 <= i < len(self._rows) else (self._selected() or [None])[0]

    def _open(self):
        r = self._current()
        if not r:
            return
        arrs = self.s.history.load_arrays(r["id"])
        if not arrs or "mediciones" not in arrs:
            notify(self, "Historial", "No se encontraron las mediciones por cuadro de este análisis.")
            return
        import json

        s = self.s
        meas = arrs["mediciones"]
        roi = json.loads(r["roi"]) if r.get("roi") else [0, 0, 64, 64]
        opts = pipeline.ProcessOptions(roi=tuple(roi), start=int(r.get("start") or 0), stop=int(r.get("stop") or 0),
                                       out_dir=r.get("out_dir") or "")
        res = pipeline.ProcessResult(meas=meas, options=opts, video={"name": r.get("video_name"), "path": r.get("video_path"),
                                                                     "fps": r.get("fps") or 30},
                                     n_saved=0, elapsed_s=0, cancelled=False, out_dir=r.get("out_dir") or "", detect_cfg={})
        from ...core.dimm import DimmParams

        s.params = DimmParams(D_cm=r.get("D_cm") or 2.5, B_cm=r.get("B_cm") or 14, lambda_nm=r.get("lambda_nm") or 550,
                              scale_arcsec_px=r.get("scale"), altitude_deg=r.get("altitude"))
        if "preview_frames" in arrs and "preview_rows" in arrs:
            res.preview_frames = arrs["preview_frames"]
            res.preview_rows = arrs["preview_rows"]
        s.result = res
        s.reanalyze()
        s.saved_id = r["id"]
        self.main.go("resultados")

    def _notes(self):
        r = self._current()
        if not r:
            return
        lab, ok = ask_text(self, "Etiqueta", "Etiqueta:", r.get("label") or "")
        if not ok:
            return
        notes, ok = ask_text(self, "Notas", "Notas (condiciones, viento, nubes, equipo):", r.get("notes") or "", multiline=True)
        if not ok:
            return
        self.s.history.update_notes(r["id"], notes, lab)
        self.refresh()

    def _delete(self):
        sel = self._selected()
        if not sel:
            return
        if not ask(self, "Eliminar", tr("¿Eliminar {} análisis del historial?").format(len(sel))):
            return
        for r in sel:
            self.s.history.delete(r["id"])
        self.refresh()

    def export(self, formats, msg):
        sel = self._selected()
        if not sel:
            msg.setText("Selecciona al menos un análisis.")
            return
        if not formats:
            msg.setText("Elige al menos un formato.")
            return
        folder = QFileDialog.getExistingDirectory(self, tr("Carpeta para exportar"), "", options=dialog_options() | QFileDialog.Option.ShowDirsOnly)
        if not folder:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            base = "mis_mediciones" if self.is_edu else "historial"
            out = export_history_table(sel, formats, folder, base)
            out += reports.export_history_charts(sel, formats, folder, base)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            notify(self, "Exportar", tr("No se pudo exportar:") + f"\n{exc}", "warning")
            return
        QApplication.restoreOverrideCursor()
        msg.setText(tr("Listo: {} archivo(s) en {}").format(len(out), folder))
        self.exp.show_open(folder)
