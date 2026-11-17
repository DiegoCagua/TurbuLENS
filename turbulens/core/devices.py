# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Equipos del Observatorio Astronómico Nacional que se usan con el DIMM (botón «Dispositivos del OAN»).

Con un telescopio, una cámara y una máscara se llenan D, B y la escala de placa:

    escala (″/px) = 206,265 × píxel (µm) ÷ focal (mm)

En las cámaras de fotos que graban video (Nikon, Canon) el píxel que vale es el **efectivo**: el ancho del sensor
dividido entre el ancho del video, porque la cámara reduce la imagen completa del sensor al tamaño del video.
Las cámaras astronómicas (QHY) graban con los píxeles reales del sensor.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Telescope:
    key: str
    name: str
    aperture_mm: float
    focal_mm: float
    note: str = ""

    @property
    def f_ratio(self) -> float:
        return self.focal_mm / self.aperture_mm


@dataclass(frozen=True)
class Camera:
    key: str
    name: str
    sensor_w_mm: float
    sensor_h_mm: float
    width_px: int  # resolución de foto (sensor completo)
    height_px: int
    video: bool  # True: cámara de fotos que graba video reduciendo el sensor
    video_widths: tuple = ()
    note: str = ""

    @property
    def pixel_um(self) -> float:
        return self.sensor_w_mm * 1000.0 / self.width_px

    def effective_pixel_um(self, video_width: Optional[int] = None, as_video: bool = True) -> float:
        if self.video and as_video:
            w = video_width or (self.video_widths[0] if self.video_widths else self.width_px)
            return self.sensor_w_mm * 1000.0 / w
        return self.pixel_um


@dataclass(frozen=True)
class Mask:
    key: str
    name: str
    D_cm: Optional[float]
    B_cm: Optional[float]
    note: str = ""


TELESCOPES = [
    Telescope("8se", "Celestron NexStar 8SE", 203.2, 2032.0,
              "Schmidt-Cassegrain de 8 pulgadas, f/10. Es el telescopio de las mediciones del grupo."),
    Telescope("meade10", "Meade 10″ (LX200)", 254.0, 2500.0,
              "Schmidt-Cassegrain de 10 pulgadas, f/10. Comprueba la focal en la etiqueta del tubo: si tiene un "
              "reductor f/6,3 la focal es unos 1600 mm."),
]

CAMERAS = [
    Camera("d5600", "Nikon D5600", 23.5, 15.6, 6000, 4000, True, (1920, 1280),
           "APS-C de 24 Mpx. En video Full HD reduce los 6000 px del sensor a 1920 px."),
    Camera("t5i", "Canon T5i (700D)", 22.3, 14.9, 5184, 3456, True, (1920, 1280),
           "APS-C de 18 Mpx. En video Full HD reduce los 5184 px del sensor a 1920 px."),
    Camera("qhy174", "QHY174M-GPS", 11.25, 7.03, 1920, 1200, False, (),
           "Cámara astronómica monocromática (sensor Sony IMX174, píxeles de 5,86 µm). Graba con los píxeles reales."),
]

MASKS = [
    Mask("grupo8", "Del grupo · 4,2 / 14,4 cm", 4.2, 14.4, "Orificios de 4,2 cm separados 14,4 cm entre centros."),
    Mask("protocolo8", "Protocolo 8″ · 2,5 / 14 cm", 2.5, 14.0,
         "La del protocolo «Determina la nitidez del cielo nocturno» (ANDEAN ROAD, 2026): 2,5 cm y 14 cm."),
    Mask("propia", "Conservar D y B", None, None, "No cambia los valores de D y B que ya escribiste."),
]


def by_key(items, key):
    for it in items:
        if it.key == key:
            return it
    return None


def plate_scale(tel: Telescope, cam: Camera, video_width: Optional[int] = None, as_video: bool = True) -> float:
    """Escala de placa en ″/px."""
    return 206.265 * cam.effective_pixel_um(video_width, as_video) / tel.focal_mm
