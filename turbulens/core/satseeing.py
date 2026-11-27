# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Seeing estimado desde el satélite GOES con tres canales infrarrojos.

Método de Cavazzani, Ortolani y Zitelli (2012, arXiv:1112.3497), adaptado a los canales del ABI de GOES-16/19:

* Función de estabilidad de la columna de aire, con las temperaturas de brillo (K) de los canales 9 (vapor de agua
  medio, 6,9 µm), 13 (infrarrojo limpio, 10,3 µm) y 16 (CO₂, 13,3 µm)::

      F = T9 − (T16 − T13)

* La turbulencia entre 4 y 8 km es proporcional a cuánto se aparta F de su tendencia durante la noche::

      ∫ Cn²(z) dz  (4–8 km)  =  Λ(θ) · |F − F_tendencia| / z ,    Λ(θ) = 10⁻¹² / cos θ

  con θ el ángulo cenital del satélite visto desde el sitio y z el espesor de la capa (4 km, en km).

* Con la integral en el modelo de Kolmogorov (r₀ y ε = 0,98 λ/r₀)::

      FWHM_sat = 0,58 · λ^(−1/5) · [4π² · Λ(θ) · |F − F_tendencia| / z]^(3/5)      (radianes, λ en metros)

El método es empírico (se comparó con el seeing medido en Paranal y en el Roque de los Muchachos): sirve para comparar horas y noches en un mismo
sitio y debe contrastarse con un DIMM. Las temperaturas de los canales infrarrojos cambian con el Sol, así que de
día los valores no son comparables con los de la noche.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

ARCSEC = 206264.80624709636
LAMBDA_COEF = 1e-12  # Λ(θ) = 10⁻¹² / cos θ
SEEING_CHANNELS = (9, 13, 16)
GOES_EAST_LON = -75.2  # posición real de GOES-16/19 (la proyección de los archivos usa −75,0)

# Criterios con la altura del Sol: se usan los instantes con el Sol por debajo del límite (grados).
SUN_CRITERIA = {
    "noche": (-18.0, "Solo de noche (Sol a más de 18° bajo el horizonte)"),
    "crepusculo": (0.0, "Noche y crepúsculo (Sol bajo el horizonte)"),
    "todas": (91.0, "Todas las horas (incluye el día)"),
}


# --------------------------------------------------------------------------------------- geometría y Sol
def satellite_zenith_deg(lat: float, lon: float, sat_lon: float = GOES_EAST_LON) -> float:
    """Ángulo cenital (°) del satélite geoestacionario visto desde (lat, lon): 0° si está justo encima."""
    R, r = 6371.0, 42164.0
    cg = math.cos(math.radians(lat)) * math.cos(math.radians(lon - sat_lon))
    d = math.sqrt(R * R + r * r - 2 * R * r * cg)
    return math.degrees(math.acos(max(-1.0, min(1.0, (r * cg - R) / d))))


def sun_altitude_deg(when: dt.datetime, lat: float, lon: float) -> float:
    """Altura del Sol (°) sobre el horizonte, con las fórmulas aproximadas del Almanaque Astronómico (±0,5°)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    n = when.timestamp() / 86400.0 + 2440587.5 - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    ha = math.radians(gmst + lon) - ra
    phi = math.radians(lat)
    return math.degrees(math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(ha)))


def sun_state(alt: float) -> str:
    if alt < -18:
        return "noche"
    if alt < 0:
        return "crepúsculo"
    return "día"


# --------------------------------------------------------------------------------------- fórmulas
def f_stability(t9: float, t13: float, t16: float) -> float:
    """F = T9 − (T16 − T13), en kelvin."""
    return t9 - (t16 - t13)


def seeing_from_deviation(dF: float, theta_deg: float, z_km: float = 4.0, lambda_nm: float = 500.0) -> dict:
    """Seeing (″), r₀ (cm) y ∫Cn²dz (m^(1/3)) a partir de |F − F_tendencia| (K)."""
    lam = lambda_nm * 1e-9
    big_l = LAMBDA_COEF / max(1e-6, math.cos(math.radians(theta_deg)))
    cn2 = big_l * abs(dF) / z_km if math.isfinite(dF) else float("nan")
    if not math.isfinite(cn2):
        return {"cn2": float("nan"), "seeing": float("nan"), "r0_cm": float("nan"), "Lambda": big_l}
    fwhm = 0.58 * lam ** (-0.2) * (4 * math.pi ** 2 * cn2) ** 0.6 * ARCSEC
    r0 = (0.423 * (2 * math.pi / lam) ** 2 * cn2) ** (-0.6) * 100 if cn2 > 0 else float("inf")
    return {"cn2": cn2, "seeing": fwhm, "r0_cm": r0, "Lambda": big_l}


def trend(hours: np.ndarray, F: np.ndarray, use: np.ndarray) -> tuple[np.ndarray, str]:
    """Tendencia de F durante la noche: recta de mínimos cuadrados con los instantes usados (≥ 3) o su promedio."""
    hours = np.asarray(hours, float)
    F = np.asarray(F, float)
    ok = np.asarray(use, bool) & np.isfinite(F)
    if ok.sum() >= 3:
        a, b = np.polyfit(hours[ok], F[ok], 1)
        return a * hours + b, "recta"
    if ok.sum() >= 1:
        return np.full(F.shape, float(np.mean(F[ok]))), "promedio"
    return np.full(F.shape, np.nan), "sin datos"


# --------------------------------------------------------------------------------------- serie de una noche
def build_times(date: dt.date, start: dt.time, end: dt.time, step_min: int, utc_offset_h: float) -> list[dt.datetime]:
    """Instantes locales (con zona) desde ``start`` hasta ``end`` cada ``step_min`` minutos (0 = solo ``start``).

    Si ``end`` es anterior o igual a ``start`` se entiende que la serie pasa la medianoche.
    """
    tz = dt.timezone(dt.timedelta(hours=utc_offset_h))
    t0 = dt.datetime.combine(date, start, tz)
    if step_min <= 0:
        return [t0]
    t1 = dt.datetime.combine(date, end, tz)
    if t1 <= t0:
        t1 += dt.timedelta(days=1)
    out, t = [], t0
    while t <= t1 + dt.timedelta(seconds=1):
        out.append(t)
        t += dt.timedelta(minutes=step_min)
    return out


def eval_folder_name(date: dt.date, start: dt.time, end: dt.time, now: dt.datetime, single: bool = False) -> str:
    """Nombre de la subcarpeta de una evaluación, p. ej. ``evaluadas_dia_20261019_18-23_20261126_100953``."""
    hrs = f"{start.hour:02d}" if single else f"{start.hour:02d}-{end.hour:02d}"
    return f"evaluadas_dia_{date:%Y%m%d}_{hrs}_{now:%Y%m%d_%H%M%S}"


@dataclass
class SatInstant:
    local: dt.datetime
    utc: dt.datetime
    readings: dict = field(default_factory=dict)  # canal → goes.ChannelReading
    sun_alt: float = float("nan")
    state: str = ""
    used: bool = False
    T9: float = float("nan")
    T13: float = float("nan")
    T16: float = float("nan")
    F: float = float("nan")
    F_trend: float = float("nan")
    dF: float = float("nan")
    cn2: float = float("nan")
    seeing: float = float("nan")
    r0_cm: float = float("nan")
    scan: Optional[dt.datetime] = None
    note: str = ""

    @property
    def hours(self) -> float:
        """Horas locales desde la medianoche del día de inicio (pasan de 24 después de la medianoche)."""
        return self.local.hour + self.local.minute / 60 + self.local.second / 3600


@dataclass
class SatParams:
    lat: float
    lon: float
    z_km: float = 4.0
    lambda_nm: float = 500.0
    criterion: str = "noche"
    box_km: float = 111.0  # 1° × 1° como en Cavazzani et al.
    sat_lon: float = GOES_EAST_LON

    @property
    def theta(self) -> float:
        return satellite_zenith_deg(self.lat, self.lon, self.sat_lon)


def compute_series(instants: list[SatInstant], p: SatParams) -> str:
    """Llena F, la tendencia, la desviación y el seeing de cada instante. Devuelve el método de la tendencia."""
    if not instants:
        return "sin datos"
    day0 = instants[0].local.date()
    hours = []
    limit = SUN_CRITERIA.get(p.criterion, SUN_CRITERIA["noche"])[0]
    for it in instants:
        it.sun_alt = sun_altitude_deg(it.utc, p.lat, p.lon)
        it.state = sun_state(it.sun_alt)
        vals = {}
        for ch in SEEING_CHANNELS:
            r = it.readings.get(ch)
            vals[ch] = r.box_mean if r is not None and r.visible else float("nan")
        it.T9, it.T13, it.T16 = vals[9], vals[13], vals[16]
        it.F = f_stability(it.T9, it.T13, it.T16)
        it.used = math.isfinite(it.F) and it.sun_alt < limit
        if not math.isfinite(it.F):
            it.note = "faltan canales"
        elif not it.used:
            it.note = "excluido por la altura del Sol"
        hours.append((it.local.date() - day0).days * 24 + it.hours)
        scans = [r.start for r in it.readings.values() if r is not None and r.start]
        it.scan = min(scans) if scans else None
    tr_vals, method = trend(np.array(hours), np.array([i.F for i in instants]), np.array([i.used for i in instants]))
    for it, ft in zip(instants, tr_vals):
        it.F_trend = float(ft)
        it.dF = abs(it.F - it.F_trend) if it.used else float("nan")
        s = seeing_from_deviation(it.dF, p.theta, p.z_km, p.lambda_nm)
        it.cn2, it.seeing, it.r0_cm = s["cn2"], s["seeing"], s["r0_cm"]
    return method


def series_hours(instants: list[SatInstant]) -> np.ndarray:
    if not instants:
        return np.zeros(0)
    day0 = instants[0].local.date()
    return np.array([(i.local.date() - day0).days * 24 + i.hours for i in instants])


SERIES_COLUMNS = ["hora_local", "hora_utc", "escaneo_utc", "altura_sol_grados", "estado", "usado", "T9_K", "T13_K", "T16_K",
                  "F_K", "F_tendencia_K", "desviacion_K", "integral_Cn2_m^(1/3)", "seeing_arcsec", "r0_cm", "nota"]


def write_series_csv(path: str, instants: list[SatInstant], p: SatParams, method: str, footer: str = "") -> None:
    def g(v, fmt="{:.4f}"):
        return fmt.format(v) if isinstance(v, (int, float)) and math.isfinite(v) else ""

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(SERIES_COLUMNS)
        for it in instants:
            w.writerow([it.local.strftime("%Y-%m-%d %H:%M"), it.utc.strftime("%Y-%m-%d %H:%M"),
                        it.scan.strftime("%Y-%m-%d %H:%M:%S") if it.scan else "", g(it.sun_alt, "{:.2f}"), it.state,
                        "sí" if it.used else "no", g(it.T9, "{:.3f}"), g(it.T13, "{:.3f}"), g(it.T16, "{:.3f}"),
                        g(it.F, "{:.3f}"), g(it.F_trend, "{:.3f}"), g(it.dF, "{:.3f}"), g(it.cn2, "{:.4e}"),
                        g(it.seeing, "{:.3f}"), g(it.r0_cm, "{:.2f}"), it.note])
        w.writerow([])
        w.writerow(["latitud", p.lat])
        w.writerow(["longitud", p.lon])
        w.writerow(["angulo_cenital_satelite_grados", f"{p.theta:.3f}"])
        w.writerow(["Lambda(theta)", f"{LAMBDA_COEF / math.cos(math.radians(p.theta)):.4e}"])
        w.writerow(["z_km", p.z_km])
        w.writerow(["lambda_nm", p.lambda_nm])
        w.writerow(["cuadro_promedio_km", p.box_km])
        w.writerow(["criterio_sol", p.criterion])
        w.writerow(["tendencia", method])
        if footer:
            w.writerow([footer])
