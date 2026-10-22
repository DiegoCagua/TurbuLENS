"""Escritura mínima de archivos FITS (sin dependencias externas).

FITS es el formato estándar de la astronomía: lo abren DS9, Astropy, SAOImage,
IRAF, etc. Aquí se implementan dos casos:

* Un cubo de imágenes (``NAXIS3`` = número de cuadros), escrito por partes
  para no cargar todo el video en memoria.
* Una tabla binaria (``BINTABLE``) con las mediciones por cuadro.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable

import numpy as np

BLOCK = 2880


def _card(key: str, value=None, comment: str = "") -> str:
    key = key.upper()[:8]
    if value is None:
        s = key.ljust(80)
        return s[:80]
    if isinstance(value, bool):
        v = ("T" if value else "F").rjust(20)
    elif isinstance(value, (int, np.integer)):
        v = str(int(value)).rjust(20)
    elif isinstance(value, (float, np.floating)):
        v = (f"{float(value):.10G}").rjust(20)
    else:
        txt = str(value).replace("'", "''")
        v = ("'" + txt.ljust(8) + "'").ljust(20)
    s = f"{key:<8}= {v}"
    if comment:
        s += " / " + comment
    return s[:80].ljust(80)


def _header(cards: Iterable[str]) -> bytes:
    body = "".join(cards) + "END".ljust(80)
    pad = (-len(body)) % BLOCK
    return (body + " " * pad).encode("ascii", errors="replace")


def _common_cards(extra: dict | None) -> list[str]:
    cards = [
        _card("ORIGIN", "TurbuLENS"),
        _card("DATE", _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")),
    ]
    for k, v in (extra or {}).items():
        if v is None:
            continue
        cards.append(_card(k, v))
    return cards


class FitsCubeWriter:
    """Escribe un cubo FITS cuadro por cuadro."""

    def __init__(self, path: str, n_frames: int, height: int, width: int, dtype, extra: dict | None = None):
        self.path = path
        self.n_expected = int(n_frames)
        self.h, self.w = int(height), int(width)
        self.is16 = np.dtype(dtype).itemsize > 1
        self.extra = extra or {}
        self.n = 0
        self._f = open(path, "wb")
        self._hdr_len = 0
        self._write_header(self.n_expected)

    def _cards(self, n: int) -> list[str]:
        cards = [
            _card("SIMPLE", True, "archivo FITS estandar"),
            _card("BITPIX", 16 if self.is16 else 8, "bits por pixel"),
            _card("NAXIS", 3),
            _card("NAXIS1", self.w, "ancho (px)"),
            _card("NAXIS2", self.h, "alto (px)"),
            _card("NAXIS3", n, "numero de cuadros"),
        ]
        if self.is16:
            cards += [_card("BZERO", 32768), _card("BSCALE", 1)]
        return cards + _common_cards(self.extra)

    def _write_header(self, n: int) -> None:
        hdr = _header(self._cards(n))
        self._f.seek(0)
        self._f.write(hdr)
        self._hdr_len = len(hdr)

    def write(self, frame: np.ndarray) -> None:
        a = np.flipud(np.asarray(frame))  # FITS: la primera fila es la de abajo
        if self.is16:
            data = (a.astype(np.int32) - 32768).astype(">i2")
        else:
            data = a.astype(np.uint8)
        self._f.write(data.tobytes())
        self.n += 1

    def close(self) -> None:
        if self._f.closed:
            return
        nbytes = self.n * self.h * self.w * (2 if self.is16 else 1)
        self._f.write(b"\x00" * ((-nbytes) % BLOCK))
        if self.n != self.n_expected:
            pos = self._f.tell()
            hdr = _header(self._cards(self.n))
            if len(hdr) == self._hdr_len:
                self._f.seek(0)
                self._f.write(hdr)
            self._f.seek(pos)
        self._f.close()


def write_table(path: str, columns: dict, units: dict | None = None, extra: dict | None = None) -> None:
    """Escribe una tabla binaria FITS con columnas numéricas (float64 / int32 / bool)."""
    units = units or {}
    names = list(columns)
    arrays = []
    forms = []
    for name in names:
        a = np.asarray(columns[name])
        if a.dtype == bool:
            arrays.append(a.astype(">i4"))
            forms.append("J")
        elif np.issubdtype(a.dtype, np.integer):
            arrays.append(a.astype(">i4"))
            forms.append("J")
        else:
            arrays.append(a.astype(">f8"))
            forms.append("D")
    nrows = len(arrays[0]) if arrays else 0
    rec = np.empty(nrows, dtype=[(n, a.dtype) for n, a in zip(names, arrays)])
    for n, a in zip(names, arrays):
        rec[n] = a
    rowbytes = rec.dtype.itemsize

    primary = _header([
        _card("SIMPLE", True), _card("BITPIX", 8), _card("NAXIS", 0), _card("EXTEND", True),
    ] + _common_cards(extra))
    cards = [
        _card("XTENSION", "BINTABLE"), _card("BITPIX", 8), _card("NAXIS", 2),
        _card("NAXIS1", rowbytes), _card("NAXIS2", nrows), _card("PCOUNT", 0), _card("GCOUNT", 1),
        _card("TFIELDS", len(names)),
    ]
    for i, (n, f) in enumerate(zip(names, forms), start=1):
        cards.append(_card(f"TTYPE{i}", n))
        cards.append(_card(f"TFORM{i}", f))
        if n in units:
            cards.append(_card(f"TUNIT{i}", units[n]))
    cards.append(_card("EXTNAME", "MEDICIONES"))
    data = rec.tobytes()
    with open(path, "wb") as f:
        f.write(primary)
        f.write(_header(cards))
        f.write(data)
        f.write(b"\x00" * ((-len(data)) % BLOCK))
