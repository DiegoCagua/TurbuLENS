# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Imágenes del satélite GOES-Este (GOES-16 o GOES-19) para revisar el cielo de una noche de observación.

Se usan los productos ``ABI-L2-CMIPF`` (imagen de disco completo de cada canal, ya calibrada:
reflectancia en los canales 1–6 y temperatura de brillo en kelvin en los canales 7–16) que NOAA
publica gratis en los repositorios abiertos de Amazon (``noaa-goes16`` y ``noaa-goes19``).

* GOES-19 reemplazó a GOES-16 como GOES-Este el 4 de abril de 2025 hacia las 15:10 UTC; para fechas
  anteriores se usa GOES-16. Si el archivo no está en el repositorio esperado se prueba en el otro.
* Los archivos NetCDF4 se leen con ``pyfive`` (Python puro, incluido en ``turbulens._vendor``) y solo
  se descomprimen los bloques del recorte pedido.
* La conversión latitud/longitud → píxel sigue la proyección geoestacionaria de la guía de usuario
  de GOES-R (PUG, vol. 3, sección 5.1.2.8).
"""

from __future__ import annotations

import datetime as dt
import math
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

PRODUCT = "ABI-L2-CMIPF"
SWITCH_G19 = dt.datetime(2025, 4, 4, 15, 10, tzinfo=dt.timezone.utc)
BUCKET_URL = "https://noaa-goes{sat}.s3.amazonaws.com"
OAN_LAT, OAN_LON = 4.6386, -74.0846  # Observatorio Astronómico Nacional, Bogotá

# canal: (longitud de onda µm, nombre, resolución km, tamaño aproximado del archivo en MB)
CHANNELS = {
    1: (0.47, "Azul", 1.0, 90),
    2: (0.64, "Rojo", 0.5, 330),
    3: (0.86, "Vegetación", 1.0, 90),
    4: (1.37, "Cirros", 2.0, 15),
    5: (1.61, "Nieve y hielo", 1.0, 70),
    6: (2.24, "Partículas de nube", 2.0, 15),
    7: (3.9, "IR onda corta", 2.0, 25),
    8: (6.2, "Vapor de agua alto", 2.0, 25),
    9: (6.9, "Vapor de agua medio", 2.0, 25),
    10: (7.3, "Vapor de agua bajo", 2.0, 25),
    11: (8.4, "Fase de nubes", 2.0, 25),
    12: (9.6, "Ozono", 2.0, 25),
    13: (10.3, "IR limpio (nubes)", 2.0, 25),
    14: (11.2, "IR", 2.0, 25),
    15: (12.3, "IR sucio", 2.0, 25),
    16: (13.3, "CO₂ (altura de nubes)", 2.0, 25),
}
CHANNEL_INFO = {
    1: "Visible azul: aerosoles y humo, de día.",
    2: "Visible rojo: la imagen más nítida de las nubes de día (0,5 km).",
    3: "Infrarrojo cercano: vegetación, quemas y nubes de día.",
    4: "Detecta cirros delgados y altos, de día.",
    5: "Distingue nubes de hielo de nieve en el suelo, de día.",
    6: "Tamaño de las partículas de las nubes, de día.",
    7: "Infrarrojo de onda corta: nubes bajas y niebla de noche, incendios.",
    8: "Vapor de agua en la troposfera alta.",
    9: "Vapor de agua en la troposfera media.",
    10: "Vapor de agua en la troposfera baja.",
    11: "Fase de las nubes (agua o hielo) y polvo.",
    12: "Ozono total y corrientes en chorro.",
    13: "Infrarrojo «limpio»: nubes de día y de noche. Entre más fría, más alta la nube.",
    14: "Infrarrojo: nubes y temperatura de la superficie.",
    15: "Infrarrojo «sucio»: humedad baja, polvo y ceniza volcánica.",
    16: "Dióxido de carbono: altura de los topes de las nubes.",
}
DEFAULT_CHANNELS = (13,)

_NAME_RE = re.compile(r"OR_ABI-L2-CMIPF-M(\d)C(\d\d)_G(\d\d)_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})(\d)_e\d+_c\d+\.nc$")


def channel_unit(ch: int) -> str:
    return "reflectancia" if ch <= 6 else "K"


def satellite_for(when: dt.datetime) -> int:
    """16 o 19 según la fecha (en UTC)."""
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return 19 if when >= SWITCH_G19 else 16


@dataclass
class RemoteFile:
    key: str
    size: int
    sat: int
    channel: int
    start: dt.datetime

    @property
    def name(self) -> str:
        return self.key.rsplit("/", 1)[-1]

    @property
    def url(self) -> str:
        return f"{BUCKET_URL.format(sat=self.sat)}/{self.key}"


def parse_name(name: str) -> Optional[dict]:
    m = _NAME_RE.search(os.path.basename(name))
    if not m:
        return None
    mode, ch, sat, y, doy, hh, mm, ss, _ = m.groups()
    start = dt.datetime(int(y), 1, 1, int(hh), int(mm), int(ss), tzinfo=dt.timezone.utc) + dt.timedelta(days=int(doy) - 1)
    return {"mode": int(mode), "channel": int(ch), "sat": int(sat), "start": start}


def _open_url(url: str, timeout: float = 30, headers: Optional[dict] = None):
    req = urllib.request.Request(url, headers={"User-Agent": "TurbuLENS", **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def list_hour(sat: int, when: dt.datetime, opener=_open_url) -> list[RemoteFile]:
    """Archivos CMIPF de una hora (todas las bandas) en el repositorio del satélite."""
    when = when.astimezone(dt.timezone.utc)
    prefix = f"{PRODUCT}/{when:%Y}/{when.timetuple().tm_yday:03d}/{when:%H}/"
    out, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix}
        if token:
            q["continuation-token"] = token
        url = f"{BUCKET_URL.format(sat=sat)}/?{urllib.parse.urlencode(q)}"
        with opener(url) as r:
            root = ET.fromstring(r.read())
        ns = {"s3": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
        pre = "s3:" if ns else ""
        for c in root.findall(f"{pre}Contents", ns):
            key = c.find(f"{pre}Key", ns).text
            size = int(c.find(f"{pre}Size", ns).text)
            info = parse_name(key)
            if info:
                out.append(RemoteFile(key, size, info["sat"], info["channel"], info["start"]))
        trunc = root.find(f"{pre}IsTruncated", ns)
        nxt = root.find(f"{pre}NextContinuationToken", ns)
        if trunc is not None and trunc.text == "true" and nxt is not None:
            token = nxt.text
        else:
            return out


def find_files(when: dt.datetime, channels, sat: Optional[int] = None, opener=_open_url,
               log: Callable[[str], None] = lambda s: None) -> tuple[int, list[RemoteFile]]:
    """La imagen más cercana a ``when`` para cada canal. Devuelve (satélite usado, archivos)."""
    when = when.astimezone(dt.timezone.utc)
    sats = [sat] if sat else [satellite_for(when)]
    sats += [s for s in (16, 19) if s not in sats]
    for s in sats:
        files: list[RemoteFile] = []
        for h in (when - dt.timedelta(hours=1), when, when + dt.timedelta(hours=1)):
            try:
                files += list_hour(s, h, opener)
            except Exception as exc:  # una hora sin datos o sin conexión
                log(f"GOES-{s} {h:%Y-%m-%d %H} h: {exc}")
        chosen = []
        for ch in channels:
            cands = [f for f in files if f.channel == ch]
            if cands:
                chosen.append(min(cands, key=lambda f: abs((f.start - when).total_seconds())))
        if chosen:
            return s, chosen
    return sats[0], []


def download(rf: RemoteFile, folder: str, progress: Callable[[int, int], bool] = lambda a, b: True,
             opener=_open_url) -> str:
    """Descarga un archivo a ``folder`` (si ya está completo, lo reutiliza). ``progress`` devuelve False para cancelar."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, rf.name)
    if os.path.exists(path) and os.path.getsize(path) == rf.size:
        progress(rf.size, rf.size)
        return path
    tmp = path + ".part"
    done = 0
    with opener(rf.url, timeout=60) as r, open(tmp, "wb") as fh:
        while True:
            buf = r.read(1 << 20)
            if not buf:
                break
            fh.write(buf)
            done += len(buf)
            if not progress(done, rf.size):
                fh.close()
                os.remove(tmp)
                raise InterruptedError("descarga cancelada")
    os.replace(tmp, path)
    return path


# ------------------------------------------------------------------ geometría
@dataclass
class Projection:
    h: float  # altura del satélite sobre el centro de la Tierra (m)
    r_eq: float
    r_pol: float
    lon0: float  # grados
    x0: float  # radianes del primer píxel
    dx: float
    y0: float
    dy: float
    nx: int
    ny: int

    def scan_angles(self, lat: float, lon: float) -> tuple[float, float, bool]:
        """Ángulos de barrido (x, y) en radianes y si el punto es visible desde el satélite."""
        phi = math.radians(lat)
        lam = math.radians(lon - self.lon0)
        e2 = (self.r_eq ** 2 - self.r_pol ** 2) / self.r_eq ** 2
        phic = math.atan((self.r_pol ** 2 / self.r_eq ** 2) * math.tan(phi))
        rc = self.r_pol / math.sqrt(1 - e2 * math.cos(phic) ** 2)
        sx = self.h - rc * math.cos(phic) * math.cos(lam)
        sy = -rc * math.cos(phic) * math.sin(lam)
        sz = rc * math.sin(phic)
        visible = self.h * (self.h - sx) >= sy ** 2 + (self.r_eq ** 2 / self.r_pol ** 2) * sz ** 2
        y = math.atan(sz / sx)
        x = math.asin(-sy / math.sqrt(sx ** 2 + sy ** 2 + sz ** 2))
        return x, y, visible

    def latlon(self, x: float, y: float) -> tuple[float, float]:
        """Inversa: ángulos de barrido → latitud y longitud (grados). NaN fuera del disco."""
        a = math.sin(x) ** 2 + math.cos(x) ** 2 * (math.cos(y) ** 2 + (self.r_eq ** 2 / self.r_pol ** 2) * math.sin(y) ** 2)
        b = -2 * self.h * math.cos(x) * math.cos(y)
        c = self.h ** 2 - self.r_eq ** 2
        disc = b * b - 4 * a * c
        if disc < 0:
            return float("nan"), float("nan")
        rs = (-b - math.sqrt(disc)) / (2 * a)
        sx = rs * math.cos(x) * math.cos(y)
        sy = -rs * math.sin(x)
        sz = rs * math.cos(x) * math.sin(y)
        lat = math.degrees(math.atan((self.r_eq ** 2 / self.r_pol ** 2) * sz / math.sqrt((self.h - sx) ** 2 + sy ** 2)))
        lon = self.lon0 - math.degrees(math.atan(sy / (self.h - sx)))
        return lat, lon

    def pixel(self, lat: float, lon: float) -> tuple[float, float, bool]:
        """Columna y fila (fraccionarias) del punto; ``False`` si no se ve o cae fuera de la imagen."""
        x, y, vis = self.scan_angles(lat, lon)
        col = (x - self.x0) / self.dx
        row = (y - self.y0) / self.dy
        inside = vis and -0.5 <= col < self.nx - 0.5 and -0.5 <= row < self.ny - 0.5
        return col, row, inside

    @property
    def pixel_km(self) -> float:
        return abs(self.dx) * (self.h - self.r_eq) / 1000


def _attr(obj, name, default=None):
    v = obj.attrs.get(name, default) if hasattr(obj.attrs, "get") else default
    if isinstance(v, (bytes, np.bytes_)):
        return v.decode("utf-8", "replace")
    if isinstance(v, np.ndarray):
        if v.dtype.kind in "SO":
            return v.ravel()[0].decode() if v.size and isinstance(v.ravel()[0], bytes) else v
        return v.ravel()[0].item() if v.size == 1 else v
    if isinstance(v, np.generic):
        return v.item()
    return v


def projection_of(f) -> Projection:
    p = f["goes_imager_projection"]
    r_eq = float(_attr(p, "semi_major_axis"))
    xv, yv = f["x"], f["y"]
    xs, xo = float(_attr(xv, "scale_factor", 1.0)), float(_attr(xv, "add_offset", 0.0))
    ys, yo = float(_attr(yv, "scale_factor", 1.0)), float(_attr(yv, "add_offset", 0.0))
    x_raw = np.asarray(xv[0:2], dtype=np.float64)
    y_raw = np.asarray(yv[0:2], dtype=np.float64)
    x0, x1 = x_raw * xs + xo
    y0, y1 = y_raw * ys + yo
    return Projection(h=float(_attr(p, "perspective_point_height")) + r_eq, r_eq=r_eq,
                      r_pol=float(_attr(p, "semi_minor_axis")), lon0=float(_attr(p, "longitude_of_projection_origin")),
                      x0=float(x0), dx=float(x1 - x0), y0=float(y0), dy=float(y1 - y0),
                      nx=int(xv.shape[0]), ny=int(yv.shape[0]))


def decode_cmi(var, raw: np.ndarray) -> np.ndarray:
    """Valores físicos (float64, NaN donde no hay dato) a partir de los enteros guardados."""
    raw = np.asarray(raw)
    fill = _attr(var, "_FillValue")
    unsigned = str(_attr(var, "_Unsigned", "false")).lower() == "true"
    if unsigned and raw.dtype.kind == "i":
        raw = raw.view(raw.dtype.str.replace("i", "u"))
        if fill is not None:
            fill = int(np.array(fill).astype(raw.dtype.str.replace("u", "i")).view(raw.dtype))
    out = raw.astype(np.float64)
    bad = np.zeros(raw.shape, bool)
    if fill is not None:
        bad |= raw == fill
    vr = _attr(var, "valid_range")
    if isinstance(vr, np.ndarray) and vr.size == 2:
        lo, hi = vr.astype(np.float64)
        if unsigned and lo < 0:
            lo, hi = lo % 65536, hi % 65536
        bad |= (out < lo) | (out > hi)
    out = out * float(_attr(var, "scale_factor", 1.0)) + float(_attr(var, "add_offset", 0.0))
    out[bad] = np.nan
    return out


@dataclass
class ChannelReading:
    channel: int
    path: str
    sat: int
    start: Optional[dt.datetime]
    lat: float
    lon: float
    col: float
    row: float
    visible: bool
    value: float = float("nan")  # en el píxel del punto
    mean3: float = float("nan")  # promedio 3×3
    unit: str = ""
    pixel_km: float = float("nan")
    cutout: Optional[np.ndarray] = None  # recorte (fila 0 = norte)
    cut_origin: tuple[int, int] = (0, 0)  # (fila, columna) del primer píxel del recorte
    notes: list = field(default_factory=list)


def read_point(path, lat: float, lon: float, half_km: float = 150.0) -> ChannelReading:
    """Valor en (lat, lon) y un recorte cuadrado de ±``half_km`` alrededor, de un archivo CMIP de GOES.

    ``path`` es la ruta del archivo NetCDF o un objeto ya abierto con la interfaz de h5py/pyfive.
    """
    if isinstance(path, (str, os.PathLike)):
        from .._vendor import pyfive

        f = pyfive.File(str(path))
    else:
        f, path = path, getattr(path, "filename", "")
    info = parse_name(str(path)) or {}
    try:
        cmi = f["CMI"]
        proj = projection_of(f)
        ch = int(info.get("channel") or np.asarray(f["band_id"][()]).ravel()[0])
        sat = int(info.get("sat") or 0)
        col, row, ok = proj.pixel(lat, lon)
        res = ChannelReading(ch, path, sat, info.get("start"), lat, lon, col, row, ok, unit=channel_unit(ch),
                             pixel_km=proj.pixel_km)
        if not ok:
            res.notes.append("El punto no se ve desde el satélite o cae fuera de la imagen.")
            return res
        r, c = int(round(row)), int(round(col))
        half = max(2, int(round(half_km / max(proj.pixel_km, 1e-3))))
        r0, r1 = max(0, r - half), min(proj.ny, r + half + 1)
        c0, c1 = max(0, c - half), min(proj.nx, c + half + 1)
        cut = decode_cmi(cmi, cmi[r0:r1, c0:c1])
        res.cutout = cut
        res.cut_origin = (r0, c0)
        res.value = float(cut[r - r0, c - c0])
        win = cut[max(0, r - r0 - 1):r - r0 + 2, max(0, c - c0 - 1):c - c0 + 2]
        res.mean3 = float(np.nanmean(win)) if np.isfinite(win).any() else float("nan")
        return res
    finally:
        fh = getattr(f, "_fh", None)
        if fh is not None and getattr(f, "_close", False):
            fh.close()


def describe_value(ch: int, v: float) -> tuple[str, float]:
    """Lectura sencilla del valor para una noche de observación: (plantilla con «{}» para °C, °C)."""
    if not math.isfinite(v):
        return "sin dato", float("nan")
    if ch <= 6:
        return ("muy brillante: nubes o superficie clara" if v > 0.4 else
                "brillo medio" if v > 0.15 else "oscuro: despejado o de noche"), float("nan")
    c = v - 273.15
    if ch in (13, 14, 15):
        if c < -40:
            return "{} °C: topes de nubes altas y frías", c
        if c < -10:
            return "{} °C: nubes medias o altas", c
        if c < 5:
            return "{} °C: posibles nubes bajas o neblina", c
        return "{} °C: probablemente despejado (superficie)", c
    return "{} °C", c
