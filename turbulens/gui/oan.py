# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Ventana «Dispositivos»: elegir telescopio, cámara y máscara (del OAN o propios) y ver la escala de placa resultante."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QGridLayout, QLineEdit, QSpinBox, QVBoxLayout

from ..core import devices as dv
from ..i18n import num, tr
from .theme import theme
from .widgets import Card, ChipGroup, DecSpin, button, hbox, label, notify

CUSTOM_KEY = "equipos/propios"


def load_custom() -> tuple[list, list, list]:
    return dv.custom_from_json(QSettings("TurbuLENS", "TurbuLENS").value(CUSTOM_KEY, "", type=str))


def save_custom(tels, cams, masks) -> None:
    QSettings("TurbuLENS", "TurbuLENS").setValue(CUSTOM_KEY, dv.custom_to_json(tels, cams, masks))


def _spin(lo, hi, value, dec, suffix):
    sp = DecSpin()
    sp.setDecimals(dec)
    sp.setRange(lo, hi)
    sp.setValue(value)
    sp.setSuffix(" " + suffix)
    sp.setToolTip(tr("Valores permitidos: de {} a {} {}.").format(num(lo, dec), num(hi, dec), suffix))
    return sp


class CustomDeviceDialog(QDialog):
    """Formulario para agregar un telescopio, una cámara o una máscara propios."""

    def __init__(self, parent, kind: str):
        super().__init__(parent)
        self.kind = kind
        titles = {"tel": "Telescopio propio", "cam": "Cámara propia", "mask": "Máscara propia"}
        self.setWindowTitle(tr(titles[kind]))
        self.setModal(True)
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        lay.addWidget(label(titles[kind], "h2"))
        f = QFormLayout()
        f.setVerticalSpacing(8)
        self.name = QLineEdit()
        self.name.setPlaceholderText({"tel": "ej. Mi refractor 80 mm", "cam": "ej. ZWO ASI120MM",
                                      "mask": "ej. Máscara del club"}[kind])
        f.addRow(tr("Nombre"), self.name)
        if kind == "tel":
            self.ap = _spin(10, 2000, 80, 0, "mm")
            self.focal = _spin(50, 20000, 600, 0, "mm")
            f.addRow(tr("Apertura"), self.ap)
            f.addRow(tr("Distancia focal"), self.focal)
            hint = "La focal está en la etiqueta del tubo; con reductor o Barlow, multiplícala por su factor."
        elif kind == "cam":
            self.sw = _spin(1, 60, 6.4, 2, "mm")
            self.wpx = QSpinBox()
            self.wpx.setRange(64, 20000)
            self.wpx.setValue(1280)
            self.wpx.setSuffix(" px")
            self.video = QCheckBox(tr("El video sale con menos píxeles que el sensor"))
            self.vw = QSpinBox()
            self.vw.setRange(64, 20000)
            self.vw.setValue(1920)
            self.vw.setSuffix(" px")
            self.vw.setEnabled(False)
            self.video.toggled.connect(self.vw.setEnabled)
            f.addRow(tr("Ancho del sensor"), self.sw)
            f.addRow(tr("Ancho del sensor en píxeles"), self.wpx)
            f.addRow(self.video)
            f.addRow(tr("Ancho del video"), self.vw)
            hint = ("El píxel es el ancho del sensor dividido entre su número de píxeles (ej. 6,4 mm ÷ 1280 px = 5 µm). "
                    "Las cámaras de fotos y los celulares guardan el video a menor resolución que el sensor: marca la "
                    "casilla y escribe el ancho del video (1920 px en Full HD). Las cámaras astronómicas suelen grabar "
                    "con todo el sensor; en ese caso déjala desmarcada.")
        else:
            self.D = _spin(0.1, 100, 2.5, 2, "cm")
            self.B = _spin(0.2, 300, 14.0, 2, "cm")
            f.addRow(tr("Diámetro de cada orificio (D)"), self.D)
            f.addRow(tr("Separación entre centros (B)"), self.B)
            hint = "B debe ser mayor que D: los orificios no pueden tocarse."
        lay.addLayout(f)
        lay.addWidget(label(hint, "small", wrap=True))
        lay.addLayout(hbox("stretch", button("Cancelar", slot=self.reject), button("Guardar", "primary", self._ok)))

    def _ok(self):
        if not self.name.text().strip():
            notify(self, "Equipo propio", "Escribe un nombre.", "warning")
            return
        if self.kind == "mask" and self.B.value() <= self.D.value():
            notify(self, "Equipo propio", "B debe ser mayor que D.", "warning")
            return
        self.accept()

    def item(self, key: str):
        n = self.name.text().strip()
        if self.kind == "tel":
            return dv.Telescope(key, n, self.ap.value(), self.focal.value(), "Telescopio propio.")
        if self.kind == "cam":
            w = self.wpx.value()
            vids = (self.vw.value(),) if self.video.isChecked() else ()
            return dv.Camera(key, n, self.sw.value(), self.sw.value() * 2 / 3, w, round(w * 2 / 3),
                             self.video.isChecked(), vids, "Cámara propia.")
        return dv.Mask(key, n, self.D.value(), self.B.value(), "Máscara propia.")


class OanDevicesDialog(QDialog):
    def __init__(self, parent=None, video_width: Optional[int] = None, last: str = ""):
        super().__init__(parent)
        self.setWindowTitle(tr("Dispositivos"))
        self.setModal(True)
        self.setMinimumWidth(940)
        self.video_width = video_width
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)
        lay.addWidget(label("Dispositivos del OAN y propios", "h1"))
        lay.addWidget(label("Elige el telescopio, la cámara y la máscara: TurbuLENS llena D, B y la escala de placa. "
                            "Con «+ Propio» agregas tus equipos; quedan guardados para la próxima vez.", "muted", wrap=True))
        self.ctel, self.ccam, self.cmask = load_custom()
        self.g = QGridLayout()
        self.g.setHorizontalSpacing(12)
        self.g.setVerticalSpacing(10)
        self.as_video = QCheckBox(tr("Grabé en video"))
        parts = (last or "").split(",")
        self.as_video.setChecked(not (len(parts) > 3 and parts[3] == "0"))
        self.vw = QSpinBox()
        self.vw.setRange(64, 20000)
        self.vw.setSuffix(" px")
        self.vw.setValue(int(video_width or 1920))
        self.vw_note = label("tomado del video cargado" if video_width else "ancho del video (Full HD = 1920)", "small")
        self.rows = {}
        for r, (kind, title) in enumerate((("tel", "Telescopio"), ("cam", "Cámara"), ("mask", "Máscara"))):
            self.g.addWidget(label(title), r, 0)
            add_b = button("+ Propio…", slot=lambda *_, k=kind: self._add(k), tip="Agregar un equipo propio")
            del_b = button("Quitar", slot=lambda *_, k=kind: self._remove(k), tip="Quitar el equipo propio elegido")
            self.rows[kind] = {"add": add_b, "del": del_b, "chips": None}
            self.g.addLayout(hbox(add_b, del_b), r, 2)
        self.g.addWidget(label("Video"), 3, 0)
        self.g.addLayout(hbox(self.as_video, 12, self.vw, self.vw_note, "stretch"), 3, 1, 1, 2)
        self.g.setColumnStretch(1, 1)
        self._build_chips(parts)
        card = Card(margins=(14, 12, 14, 12))
        card.add(self.g)
        lay.addWidget(card)
        self.result = Card(kind="soft", margins=(14, 12, 14, 12))
        self.res_lbl = label("", wrap=True, rich=True)
        self.notes = label("", "small", wrap=True)
        self.result.add(self.res_lbl, self.notes)
        lay.addWidget(self.result)
        self.ok_b = button("Aplicar", "primary", self.accept)
        lay.addLayout(hbox("stretch", button("Cancelar", slot=self.reject), self.ok_b))
        self.as_video.toggled.connect(self._update)
        self.vw.valueChanged.connect(self._update)
        self._update()

    # ------------------------------------------------------------------ listas
    def _lists(self):
        return {"tel": dv.TELESCOPES + self.ctel, "cam": dv.CAMERAS + self.ccam, "mask": dv.MASKS + self.cmask}

    def _build_chips(self, wanted=None):
        lists = self._lists()
        for r, kind in enumerate(("tel", "cam", "mask")):
            old = self.rows[kind]["chips"]
            cur = wanted[r] if wanted and len(wanted) > r else (old.value() if old else "")
            if old is not None:
                self.g.removeWidget(old)
                old.hide()
                old.deleteLater()
            items = lists[kind]
            chips = ChipGroup([(x.key, x.name + (" ★" if x.key.startswith("u:") else "")) for x in items], wrap=True)
            chips.set_value(cur if dv.by_key(items, cur) else items[0].key)
            chips.changed.connect(self._update)
            self.rows[kind]["chips"] = chips
            self.g.addWidget(chips, r, 1)

    def _add(self, kind):
        dlg = CustomDeviceDialog(self, kind)
        if dlg.exec() != QDialog.Accepted:
            return
        target = {"tel": self.ctel, "cam": self.ccam, "mask": self.cmask}[kind]
        item = dlg.item(dv.new_key(target))
        target.append(item)
        save_custom(self.ctel, self.ccam, self.cmask)
        vals = [self.rows[k]["chips"].value() for k in ("tel", "cam", "mask")]
        vals[("tel", "cam", "mask").index(kind)] = item.key
        self._build_chips(vals)
        self._update()

    def _remove(self, kind):
        key = self.rows[kind]["chips"].value()
        if not key.startswith("u:"):
            notify(self, "Equipo propio", "Solo se pueden quitar los equipos propios (marcados con ★).", "info")
            return
        target = {"tel": self.ctel, "cam": self.ccam, "mask": self.cmask}[kind]
        target[:] = [x for x in target if x.key != key]
        save_custom(self.ctel, self.ccam, self.cmask)
        self._build_chips()
        self._update()

    # ------------------------------------------------------------------ selección
    def selection(self):
        lists = self._lists()
        tel = dv.by_key(lists["tel"], self.rows["tel"]["chips"].value())
        cam = dv.by_key(lists["cam"], self.rows["cam"]["chips"].value())
        mask = dv.by_key(lists["mask"], self.rows["mask"]["chips"].value())
        as_video = cam.video and self.as_video.isChecked()
        vw = self.vw.value() if as_video else None
        return tel, cam, mask, as_video, vw, dv.plate_scale(tel, cam, vw, as_video)

    def _update(self, *_):
        tel, cam, mask, as_video, vw, scale = self.selection()
        for kind, x in (("tel", tel), ("cam", cam), ("mask", mask)):
            self.rows[kind]["del"].setEnabled(x.key.startswith("u:"))
        self.as_video.setEnabled(cam.video)
        self.vw.setEnabled(as_video)
        if cam.video and cam.video_widths and not self.video_width and getattr(self, "_last_cam", None) != cam.key:
            self.vw.blockSignals(True)
            self.vw.setValue(cam.video_widths[0])
            self.vw.blockSignals(False)
            vw = self.vw.value() if as_video else None
            scale = dv.plate_scale(tel, cam, vw, as_video)
        self._last_cam = cam.key
        px = cam.effective_pixel_um(vw, as_video)
        how = (tr("píxel efectivo = {} mm ÷ {} px = {} µm").format(num(cam.sensor_w_mm, 2), vw, num(px, 2)) if as_video
               else tr("píxel del sensor = {} µm").format(num(px, 2)))
        acc = theme.pal["accent"]
        d = "" if not mask.D_cm else tr("D = {} cm · B = {} cm · ").format(num(mask.D_cm, 1), num(mask.B_cm, 1))
        self.res_lbl.setText(
            f"<span style='font-size:22px; color:{acc}; font-weight:600'>{num(scale, 3)} ″/px</span><br>"
            + d + tr("focal {} mm (f/{}) · {}").format(num(tel.focal_mm, 0), num(tel.f_ratio, 1), how))
        self.notes.setText("<br>".join(tr(x) for x in (tel.note, cam.note, mask.note) if x))
