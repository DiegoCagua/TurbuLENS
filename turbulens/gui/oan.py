# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Ventana «Dispositivos del OAN»: elegir telescopio, cámara y máscara y ver la escala de placa resultante."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QCheckBox, QDialog, QGridLayout, QSpinBox, QVBoxLayout

from ..core import devices as dv
from ..i18n import num, tr
from .theme import theme
from .widgets import Card, ChipGroup, button, hbox, label


class OanDevicesDialog(QDialog):
    def __init__(self, parent=None, video_width: Optional[int] = None, last: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("Dispositivos del OAN"))
        self.setModal(True)
        self.setMinimumWidth(700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        lay.addWidget(label("Dispositivos del OAN", "h1"))
        lay.addWidget(label("Elige el telescopio, la cámara y la máscara: TurbuLENS llena D, B y la escala de placa.",
                            "muted", wrap=True))
        self.tel = ChipGroup([(t.key, t.name) for t in dv.TELESCOPES])
        self.cam = ChipGroup([(c.key, c.name) for c in dv.CAMERAS])
        self.mask = ChipGroup([(m.key, m.name) for m in dv.MASKS])
        parts = (last or "").split(",")
        self.tel.set_value(parts[0] if len(parts) > 0 and dv.by_key(dv.TELESCOPES, parts[0]) else dv.TELESCOPES[0].key)
        self.cam.set_value(parts[1] if len(parts) > 1 and dv.by_key(dv.CAMERAS, parts[1]) else dv.CAMERAS[0].key)
        self.mask.set_value(parts[2] if len(parts) > 2 and dv.by_key(dv.MASKS, parts[2]) else dv.MASKS[0].key)
        self.as_video = QCheckBox(tr("Grabé en video"))
        self.as_video.setChecked(not (len(parts) > 3 and parts[3] == "0"))
        self.vw = QSpinBox()
        self.vw.setRange(64, 20000)
        self.vw.setSuffix(" px")
        self.vw.setValue(int(video_width or 1920))
        self.vw_note = label("tomado del video cargado" if video_width else "ancho del video (Full HD = 1920)", "small")
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(10)
        for r, (t, w) in enumerate((("Telescopio", self.tel), ("Cámara", self.cam), ("Máscara", self.mask))):
            g.addWidget(label(t), r, 0)
            g.addWidget(w, r, 1)
        g.addWidget(label("Video"), 3, 0)
        g.addLayout(hbox(self.as_video, 12, self.vw, self.vw_note, "stretch"), 3, 1)
        card = Card(margins=(14, 12, 14, 12))
        card.add(g)
        lay.addWidget(card)
        self.result = Card(kind="soft", margins=(14, 12, 14, 12))
        self.res_lbl = label("", wrap=True, rich=True)
        self.notes = label("", "small", wrap=True)
        self.result.add(self.res_lbl, self.notes)
        lay.addWidget(self.result)
        self.ok_b = button("Aplicar", "primary", self.accept)
        lay.addLayout(hbox("stretch", button("Cancelar", slot=self.reject), self.ok_b))
        for w in (self.tel, self.cam, self.mask):
            w.changed.connect(self._update)
        self.as_video.toggled.connect(self._update)
        self.vw.valueChanged.connect(self._update)
        self._update()

    def selection(self):
        tel = dv.by_key(dv.TELESCOPES, self.tel.value())
        cam = dv.by_key(dv.CAMERAS, self.cam.value())
        mask = dv.by_key(dv.MASKS, self.mask.value())
        as_video = cam.video and self.as_video.isChecked()
        vw = self.vw.value() if as_video else None
        return tel, cam, mask, as_video, vw, dv.plate_scale(tel, cam, vw, as_video)

    def _update(self, *_):
        tel, cam, mask, as_video, vw, scale = self.selection()
        self.as_video.setEnabled(cam.video)
        self.vw.setEnabled(as_video)
        px = cam.effective_pixel_um(vw, as_video)
        how = (tr("píxel efectivo = {} mm ÷ {} px = {} µm").format(num(cam.sensor_w_mm, 2), vw, num(px, 2)) if as_video
               else tr("píxel del sensor = {} µm").format(num(px, 2)))
        acc = theme.pal["accent"]
        d = "" if not mask.D_cm else tr("D = {} cm · B = {} cm · ").format(num(mask.D_cm, 1), num(mask.B_cm, 1))
        self.res_lbl.setText(
            f"<span style='font-size:22px; color:{acc}; font-weight:600'>{num(scale, 3)} ″/px</span><br>"
            + d + tr("focal {} mm (f/{}) · {}").format(num(tel.focal_mm, 0), num(tel.f_ratio, 1), how))
        self.notes.setText("<br>".join(tr(x) for x in (tel.note, cam.note, mask.note) if x))
