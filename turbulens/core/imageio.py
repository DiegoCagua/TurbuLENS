# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Lectura y escritura de imágenes astronómicas sin dependencias externas pesadas.

* FITS (``.fits``, ``.fit``, ``.fts``): imagen 2D o cubo 3D del HDU primario (o de la
  primera extensión de imagen), con ``BZERO``/``BSCALE``. Se lee también la cabecera.
* PNG, TIFF, JPG, BMP (con Pillow): en color se convierten a luminancia; se respetan 16 bits.
* NumPy (``.npy``, ``.npz``).

Las imágenes se devuelven en ``float32`` con la fila 0 arriba (como se ven en pantalla).
"""

from __future__ import annotations

import os
from typing import Optional

import numpy as np

from .fits import BLOCK, _card, _common_cards, _header

IMAGE_EXTS = (".fits", ".fit", ".fts", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp", ".npy", ".npz")
FITS_EXTS = (".fits", ".fit", ".fts")

_BITPIX = {8: ">u1", 16: ">i2", 32: ">i4", 64: ">i8", -32: ">f4", -64: ">f8"}


def _parse_header(f) -> tuple[dict, list[str]]:
    cards, hdr = [], {}
    while True:
        block = f.read(BLOCK)
        if len(block) < BLOCK:
            raise ValueError("cabecera FITS incompleta")
        txt = block.decode("ascii", errors="replace")
        end = False
        for i in range(0, BLOCK, 80):
            c = txt[i:i + 80]
            key = c[:8].strip()
            if key == "END":
                end = True
                break
            cards.append(c.rstrip())
            if c[8:10] == "= ":
                v = c[10:].split(" /")[0].strip()
                if v.startswith("'"):
                    v = v.strip("'").rstrip()
                elif v in ("T", "F"):
                    v = v == "T"
                else:
                    try:
                        v = int(v)
                    except ValueError:
                        try:
                            v = float(v.replace("D", "E"))
                        except ValueError:
                            pass
                hdr[key] = v
        if end:
            return hdr, cards


def read_fits(path: str) -> tuple[np.ndarray, dict, list[str]]:
    """Datos (2D o 3D, float32, fila 0 arriba), cabecera y tarjetas del primer HDU con imagen."""
    with open(path, "rb") as f:
        while True:
            hdr, cards = _parse_header(f)
            naxis = int(hdr.get("NAXIS", 0))
            bitpix = int(hdr.get("BITPIX", 8))
            dims = [int(hdr.get(f"NAXIS{i}", 0)) for i in range(1, naxis + 1)]
            n = int(np.prod(dims)) if dims else 0
            nbytes = n * abs(bitpix) // 8
            if naxis >= 2 and n > 0 and hdr.get("XTENSION", "IMAGE") in ("IMAGE", "IMAGE   ") or (naxis >= 2 and "SIMPLE" in hdr and n):
                raw = f.read(nbytes)
                a = np.frombuffer(raw, dtype=_BITPIX[bitpix]).reshape(dims[::-1]).astype(np.float64)
                a = a * float(hdr.get("BSCALE", 1.0)) + float(hdr.get("BZERO", 0.0))
                if a.ndim > 3:
                    a = a.reshape((-1,) + a.shape[-2:])
                a = np.flip(a, axis=-2)  # FITS guarda la fila de abajo primero
                return np.ascontiguousarray(a, dtype=np.float32), hdr, cards
            # sin datos de imagen: saltar al siguiente HDU
            f.seek(nbytes + ((-nbytes) % BLOCK), 1)
            if f.tell() >= os.path.getsize(path):
                raise ValueError("el archivo FITS no tiene una imagen")


def read_image(path: str, frame: int = 0) -> np.ndarray:
    """Una imagen 2D (float32). En cubos o videos de imágenes se toma ``frame``."""
    a = read_stack(path)
    return a[min(frame, len(a) - 1)] if a.ndim == 3 else a


def read_stack(path: str) -> np.ndarray:
    """Imagen 2D o cubo 3D (float32)."""
    ext = os.path.splitext(path)[1].lower()
    if ext in FITS_EXTS:
        return read_fits(path)[0]
    if ext == ".npy":
        return np.asarray(np.load(path), dtype=np.float32)
    if ext == ".npz":
        z = np.load(path)
        key = "frames" if "frames" in z else list(z.keys())[0]
        return np.asarray(z[key], dtype=np.float32)
    from PIL import Image

    im = Image.open(path)
    if im.mode in ("I;16", "I;16B", "I;16L", "I"):
        a = np.asarray(im, dtype=np.float32)
    elif im.mode == "F":
        a = np.asarray(im, dtype=np.float32)
    else:
        rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
        if im.mode in ("L", "P", "1", "LA"):
            a = np.asarray(im.convert("L"), dtype=np.float32)
        else:
            a = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    return a


def header_text(path: str) -> str:
    """Cabecera FITS legible (vacío para otros formatos)."""
    if os.path.splitext(path)[1].lower() not in FITS_EXTS:
        return ""
    try:
        return "\n".join(read_fits(path)[2])
    except Exception as exc:
        return str(exc)


def write_fits(path: str, a: np.ndarray, extra: Optional[dict] = None) -> None:
    """Imagen 2D en FITS de 32 bits en coma flotante (lo abre DS9, Astropy, SAOImage)."""
    a = np.asarray(a, dtype=np.float32)
    if a.ndim != 2:
        raise ValueError("se espera una imagen 2D")
    cards = [_card("SIMPLE", True, "archivo FITS estandar"), _card("BITPIX", -32, "coma flotante 32 bits"),
             _card("NAXIS", 2), _card("NAXIS1", a.shape[1], "ancho (px)"), _card("NAXIS2", a.shape[0], "alto (px)")]
    cards += _common_cards(extra)
    data = np.flipud(a).astype(">f4").tobytes()
    with open(path, "wb") as f:
        f.write(_header(cards))
        f.write(data)
        f.write(b"\x00" * ((-len(data)) % BLOCK))


def write_png16(path: str, a: np.ndarray, lo: Optional[float] = None, hi: Optional[float] = None) -> None:
    """PNG de 16 bits escalado entre ``lo`` y ``hi`` (por defecto, mínimo y máximo)."""
    from PIL import Image

    a = np.asarray(a, dtype=np.float64)
    lo = float(np.nanmin(a)) if lo is None else lo
    hi = float(np.nanmax(a)) if hi is None else hi
    u = np.clip((a - lo) / max(hi - lo, 1e-12), 0, 1) * 65535
    Image.fromarray(u.astype(np.uint16)).save(path)
