# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Calibración guiada por las cabeceras: cada luz se corrige con los darks y flats que le corresponden.

El dark depende del tiempo de exposición, la ganancia (o ISO), la temperatura del sensor, el binning y el
tamaño de la imagen; el flat depende del filtro, el binning y el tamaño. Este módulo:

1. Lee la cabecera de cada archivo (FITS, o los datos EXIF de TIFF/JPG/PNG) **sin cargar la imagen**
   (:func:`read_info`) y la clasifica como luz, dark, flat, dark de flat o bias: primero por la cabecera
   (``IMAGETYP`` y similares), luego por el nombre del archivo y de la carpeta.
2. Arma un **plan** (:func:`build_plan`): agrupa las luces que comparten características y elige para cada
   grupo sus darks y flats. Si no hay darks de la misma exposición pero sí bias, escala el dark:
   ``(dark − bias) · t_luz / t_dark + bias``.
3. Ejecuta el plan (:class:`Calibrator`): crea los maestros una sola vez, los guarda en FITS y escribe cada
   luz calibrada como ``(luz − dark) / flat``.

Las series grandes se combinan por franjas con un archivo temporal, para no llenar la memoria.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import numpy as np

from . import calibration as cal
from .imageio import FITS_EXTS, IMAGE_EXTS, read_fits_header, read_stack, write_fits

KINDS = ("light", "dark", "flat", "darkflat", "bias")
KIND_NAMES = {"light": "Luz", "dark": "Dark", "flat": "Flat", "darkflat": "Dark de flat", "bias": "Bias"}
SOURCE_NAMES = {"cabecera": "según la cabecera", "nombre": "según el nombre del archivo",
                "carpeta": "según el nombre de la carpeta", "manual": "elegido a mano",
                "supuesto": "supuesto (no se pudo saber): cámbialo si no es una luz"}

_TYPE_KEYS = ("IMAGETYP", "IMGTYPE", "FRAMETYP", "FRAME", "OBSTYPE", "IMAGE-TY")
_EXP_KEYS = ("EXPTIME", "EXPOSURE", "EXP_TIME", "EXPTIM", "ITIME")
_GAIN_KEYS = ("GAIN", "ISOSPEED", "ISO", "GAINRAW")
_TEMP_KEYS = ("CCD-TEMP", "CCDTEMP", "SENSTEMP", "TEMPERAT", "DET-TEMP")
_FILTER_KEYS = ("FILTER", "FILTER1", "FILTNAME")
_CAMERA_KEYS = ("INSTRUME", "CAMERA", "DETECTOR")
COPY_KEYS = ("OBJECT", "EXPTIME", "GAIN", "OFFSET", "CCD-TEMP", "XBINNING", "YBINNING", "FILTER", "DATE-OBS", "INSTRUME",
             "TELESCOP", "OBSERVER", "FOCALLEN", "XPIXSZ", "YPIXSZ", "RA", "DEC", "AIRMASS")


@dataclass
class FrameInfo:
    path: str
    kind: str = "light"
    kind_source: str = "supuesto"
    exptime: Optional[float] = None  # segundos
    gain: Optional[float] = None  # ganancia o ISO
    temp: Optional[float] = None  # °C
    binning: Optional[tuple] = None
    filter: str = ""
    width: int = 0
    height: int = 0
    frames: int = 1
    date: str = ""
    camera: str = ""
    type_text: str = ""  # el texto de la cabecera que dio el tipo
    error: str = ""
    header: dict = field(default_factory=dict)  # tarjetas que se copian a la imagen calibrada

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def folder(self) -> str:
        return os.path.basename(os.path.dirname(self.path))

    @property
    def size(self) -> tuple:
        return (self.width, self.height)


# ------------------------------------------------------------- clasificación
def kind_from_header_text(text: str) -> Optional[str]:
    """Tipo de imagen a partir del valor de IMAGETYP y similares («Dark Frame», «FLAT», «Light», «zero»…)."""
    t = str(text).strip().lower()
    if not t:
        return None
    if re.search(r"dark[\s_\-]*flat|flat[\s_\-]*dark", t):
        return "darkflat"
    if "dark" in t or "oscur" in t:
        return "dark"
    if "flat" in t or "plano" in t:
        return "flat"
    if "bias" in t or "zero" in t or "offset" in t:
        return "bias"
    if any(w in t for w in ("light", "object", "science", "sci", "luz", "luces", "target")):
        return "light"
    return None


def kind_from_name(name: str) -> Optional[str]:
    """Tipo según las palabras de un nombre de archivo o carpeta («Darks», «flat_R_001», «luces»…)."""
    tokens = [t for t in re.split(r"[^a-záéíóúñ]+", name.lower()) if t]
    has = lambda *pre: any(t.startswith(pre) for t in tokens)  # noqa: E731
    if has("darkflat", "flatdark") or (has("dark") and has("flat")):
        return "darkflat"
    if has("dark", "oscuro"):
        return "dark"
    if has("flat", "plano"):
        return "flat"
    if has("bias", "offset", "zero"):
        return "bias"
    if has("light", "luz", "luces", "science", "ciencia", "object"):
        return "light"
    return None


def _exposure_from_name(name: str) -> Optional[float]:
    m = re.search(r"(?<![\d.])(\d+(?:[.,]\d+)?)\s*(ms|s|sec|seg)(?![a-z])", name.lower())
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v / 1000.0 if m.group(2) == "ms" else v


def _num(v) -> Optional[float]:
    try:
        f = float(v)
        return f if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _first(hdr: dict, keys) -> object:
    for k in keys:
        if k in hdr and hdr[k] not in ("", None):
            return hdr[k]
    return None


def _info_from_fits(info: FrameInfo, hdr: dict) -> None:
    naxis = int(hdr.get("NAXIS", 0))
    info.width = int(hdr.get("NAXIS1", 0))
    info.height = int(hdr.get("NAXIS2", 0))
    n = 1
    for i in range(3, naxis + 1):
        n *= int(hdr.get(f"NAXIS{i}", 1))
    info.frames = max(1, n)
    info.exptime = _num(_first(hdr, _EXP_KEYS))
    if info.exptime is None and _num(hdr.get("EXPOINUS")) is not None:  # ZWO ASICap: microsegundos
        info.exptime = float(hdr["EXPOINUS"]) / 1e6
    info.gain = _num(_first(hdr, _GAIN_KEYS))
    info.temp = _num(_first(hdr, _TEMP_KEYS))
    bx, by = _num(hdr.get("XBINNING")), _num(hdr.get("YBINNING"))
    if bx:
        info.binning = (int(bx), int(by or bx))
    else:
        m = re.match(r"\s*(\d+)\s*[xX ]\s*(\d+)", str(hdr.get("BINNING", hdr.get("CCDSUM", ""))))
        if m:
            info.binning = (int(m.group(1)), int(m.group(2)))
    f = _first(hdr, _FILTER_KEYS)
    info.filter = str(f).strip() if f is not None else ""
    info.date = str(hdr.get("DATE-OBS", "") or "")
    c = _first(hdr, _CAMERA_KEYS)
    info.camera = str(c).strip() if c is not None else ""
    t = _first(hdr, _TYPE_KEYS)
    if t is not None:
        info.type_text = str(t).strip()
        k = kind_from_header_text(info.type_text)
        if k:
            info.kind, info.kind_source = k, "cabecera"
    info.header = {k: hdr[k] for k in COPY_KEYS if k in hdr and isinstance(hdr[k], (int, float, str, bool))}


def _info_from_pillow(info: FrameInfo) -> None:
    from PIL import Image

    with Image.open(info.path) as im:
        info.width, info.height = im.size
        info.frames = int(getattr(im, "n_frames", 1) or 1)
        try:
            exif = im.getexif()
        except Exception:
            exif = None
        if exif:
            sub = {}
            try:
                sub = exif.get_ifd(0x8769)
            except Exception:
                pass
            info.exptime = _num(sub.get(0x829A))  # ExposureTime
            iso = sub.get(0x8827)  # ISOSpeedRatings
            if isinstance(iso, (tuple, list)):
                iso = iso[0] if iso else None
            info.gain = _num(iso)
            info.date = str(sub.get(0x9003, "") or exif.get(0x0132, "") or "")
            info.camera = str(exif.get(0x0110, "") or "").strip()
    if info.exptime is not None:
        info.header["EXPTIME"] = float(info.exptime)
    if info.gain is not None:
        info.header["GAIN"] = float(info.gain)
    if info.camera:
        info.header["INSTRUME"] = info.camera[:60]


def read_info(path: str) -> FrameInfo:
    """Características de una imagen leídas de su cabecera (no carga los píxeles)."""
    info = FrameInfo(path)
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in FITS_EXTS:
            _info_from_fits(info, read_fits_header(path))
        elif ext in (".npy", ".npz"):
            a = np.load(path, mmap_mode="r") if ext == ".npy" else None
            if a is None:
                z = np.load(path)
                a = z["frames" if "frames" in z else list(z.keys())[0]]
            info.height, info.width = int(a.shape[-2]), int(a.shape[-1])
            info.frames = int(a.shape[0]) if a.ndim == 3 else 1
        else:
            _info_from_pillow(info)
    except Exception as exc:
        info.error = str(exc) or exc.__class__.__name__
        return info
    if info.kind_source != "cabecera":
        k = kind_from_name(os.path.splitext(info.name)[0])
        if k:
            info.kind, info.kind_source = k, "nombre"
        else:
            folder = os.path.dirname(os.path.abspath(path))
            for _ in range(2):  # la carpeta y la que la contiene
                k = kind_from_name(os.path.basename(folder))
                if k:
                    info.kind, info.kind_source = k, "carpeta"
                    break
                folder = os.path.dirname(folder)
    if info.kind_source == "supuesto" and info.exptime is not None and info.exptime == 0:
        info.kind, info.kind_source = "bias", "cabecera"  # exposición nula
    if info.exptime is None:
        e = _exposure_from_name(os.path.splitext(info.name)[0])
        if e is not None:
            info.exptime = e
    return info


def scan(paths: Iterable[str], progress: Optional[Callable[[int, int], None]] = None) -> list[FrameInfo]:
    """Archivos sueltos y carpetas (se recorren con sus subcarpetas) → lista de imágenes con sus características."""
    files: list[str] = []
    seen = set()
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs.sort()
                for n in sorted(names):
                    if os.path.splitext(n)[1].lower() in IMAGE_EXTS and not n.startswith("."):
                        files.append(os.path.join(root, n))
        elif os.path.isfile(p):
            files.append(p)
    out = []
    uniq = [f for f in files if not (os.path.abspath(f) in seen or seen.add(os.path.abspath(f)))]
    for i, f in enumerate(uniq):
        out.append(read_info(f))
        if progress and (i % 25 == 0 or i == len(uniq) - 1):
            progress(i + 1, len(uniq))
    return out


# ------------------------------------------------------------------- el plan
@dataclass
class MatchOptions:
    exp_tol: float = 0.02  # tolerancia relativa del tiempo de exposición
    temp_tol: float = 5.0  # °C
    scale_darks: bool = True
    method: str = "mediana"


@dataclass
class DarkChoice:
    """Qué se resta. ``mode``: igual, escalado, bias, sin_escalar o ninguno."""

    mode: str = "ninguno"
    paths: list = field(default_factory=list)
    exptime: Optional[float] = None
    scale: float = 1.0
    bias_paths: list = field(default_factory=list)
    warning: str = ""
    warning_args: tuple = ()

    @property
    def any(self) -> bool:
        return self.mode != "ninguno"


@dataclass
class FlatChoice:
    paths: list = field(default_factory=list)
    filter: str = ""
    darks: list = field(default_factory=list)  # [(DarkChoice, [rutas de flats])] por exposición del flat
    warning: str = ""
    warning_args: tuple = ()


@dataclass
class GroupPlan:
    lights: list
    exptime: Optional[float]
    gain: Optional[float]
    temp: Optional[float]
    filter: str
    size: tuple
    binning: Optional[tuple]
    dark: DarkChoice
    flat: Optional[FlatChoice]
    warnings: list = field(default_factory=list)  # [(plantilla, args)]


@dataclass
class Plan:
    groups: list
    masters_only: list  # [(tipo, etiqueta, DarkChoice | FlatChoice)] cuando no hay luces
    counts: dict
    unreadable: list
    options: MatchOptions


def _close(a, b, rel=0.0, absolute=0.0) -> bool:
    """Dos valores coinciden; si falta alguno en la cabecera no se puede descartar: se acepta."""
    if a is None or b is None:
        return True
    return abs(a - b) <= max(absolute, rel * max(abs(a), abs(b)))


def _compatible(f: FrameInfo, size, binning, gain=None, check_gain=True) -> bool:
    if f.size != size:
        return False
    if f.binning is not None and binning is not None and tuple(f.binning) != tuple(binning):
        return False
    return (not check_gain) or _close(f.gain, gain, rel=0.01)


def _exp_match(e, t, tol) -> bool:
    return e is not None and t is not None and abs(e - t) <= max(tol * max(t, e), 1e-4)


def _median(vals):
    v = [x for x in vals if x is not None]
    return float(np.median(v)) if v else None


def choose_dark(exptime, gain, temp, size, binning, darks: list, biases: list, opts: MatchOptions,
                preferred: Optional[list] = None) -> DarkChoice:
    """El dark de una imagen (luz o flat) con estas características."""
    bias = [b.path for b in biases if _compatible(b, size, binning, gain)]
    warn, wargs = "", ()
    for pool in ([preferred] if preferred else []) + [darks]:
        cands = [d for d in pool if _compatible(d, size, binning, gain)]
        if not cands:
            continue
        if temp is not None and any(d.temp is not None for d in cands):
            near = [d for d in cands if d.temp is None or abs(d.temp - temp) <= opts.temp_tol]
            if near:
                cands = near
            else:
                dt = min(abs(d.temp - temp) for d in cands if d.temp is not None)
                warn, wargs = "los darks están a otra temperatura (diferencia de {} °C)", (round(dt, 1),)
        if exptime is None:
            exps = sorted({round(d.exptime, 4) for d in cands if d.exptime is not None})
            if len(exps) <= 1:
                return DarkChoice("igual", [d.path for d in cands], exps[0] if exps else None, 1.0, bias,
                                  "la imagen no tiene el tiempo de exposición en la cabecera", ())
            continue
        same = [d for d in cands if _exp_match(d.exptime, exptime, opts.exp_tol)]
        if same:
            return DarkChoice("igual", [d.path for d in same], exptime, 1.0, bias, warn, wargs)
    # Sin darks de la misma exposición
    pool = [d for d in (preferred or []) + darks if _compatible(d, size, binning, gain)]
    with_exp = [d for d in pool if d.exptime is not None and d.exptime > 0]
    if exptime is not None and with_exp:
        longer = sorted({round(d.exptime, 4) for d in with_exp if d.exptime >= exptime})
        shorter = sorted({round(d.exptime, 4) for d in with_exp if d.exptime < exptime})
        e = longer[0] if longer else shorter[-1]  # mejor uno más largo: al escalar hacia abajo el ruido no crece
        chosen = [d.path for d in with_exp if round(d.exptime, 4) == e]
        if opts.scale_darks and bias:
            return DarkChoice("escalado", chosen, e, exptime / e, bias,
                              "no hay darks de {} s: se escala el de {} s con el bias", (exptime, e))
        if bias:
            return DarkChoice("bias", [], None, 1.0, bias, "no hay darks de {} s: solo se resta el bias", (exptime,))
        return DarkChoice("sin_escalar", chosen, e, 1.0, [],
                          "no hay darks de {} s ni bias para escalar: se usa el de {} s sin escalar", (exptime, e))
    if exptime is None and with_exp:
        if bias:
            return DarkChoice("bias", [], None, 1.0, bias,
                              "la imagen no indica su exposición y hay darks de varias: solo se resta el bias", ())
        return DarkChoice("ninguno", warning="la imagen no indica su exposición y hay darks de varias: no se resta dark")
    no_exp = [d.path for d in pool if d.exptime is None]
    if no_exp:
        return DarkChoice("igual", no_exp, None, 1.0, bias, "los darks no tienen el tiempo de exposición en la cabecera", ())
    if bias:
        return DarkChoice("bias", [], None, 1.0, bias, "no hay darks compatibles: solo se resta el bias", ())
    return DarkChoice("ninguno", warning="no hay darks ni bias compatibles (tamaño, binning o ganancia distintos)"
                      if (darks or biases) else "")


def choose_flat(filt: str, size, binning, flats: list, darkflats: list, darks: list, biases: list,
                opts: MatchOptions) -> Optional[FlatChoice]:
    cands = [f for f in flats if _compatible(f, size, binning, check_gain=False)]
    if not cands:
        if flats:
            return FlatChoice(warning="no hay flats del mismo tamaño y binning")
        return None
    norm = lambda s: s.strip().lower()  # noqa: E731
    warn, wargs = "", ()
    if filt:
        same = [f for f in cands if norm(f.filter) == norm(filt)]
        if same:
            cands = same
        else:
            unknown = [f for f in cands if not f.filter]
            if not unknown:
                return FlatChoice(warning="no hay flats del filtro {}", warning_args=(filt,))
            cands, warn, wargs = unknown, "los flats no indican el filtro: comprueba que sean del filtro {}", (filt,)
    else:
        names = {norm(f.filter) for f in cands}
        if len(names) > 1:
            return FlatChoice(warning="la luz no indica el filtro y hay flats de varios filtros: no se aplica flat")
    choice = FlatChoice([f.path for f in cands], filt or (cands[0].filter if cands else ""), warning=warn, warning_args=wargs)
    by_exp: dict = {}
    for f in cands:
        by_exp.setdefault(None if f.exptime is None else round(f.exptime, 4), []).append(f)
    for e, group in by_exp.items():
        d = choose_dark(e, _median([f.gain for f in group]), _median([f.temp for f in group]), size, binning,
                        darks, biases, opts, preferred=darkflats)
        choice.darks.append((d, [f.path for f in group]))
    return choice


def build_plan(frames: list, opts: Optional[MatchOptions] = None) -> Plan:
    """Agrupa las luces por sus características y elige los darks y flats de cada grupo."""
    opts = opts or MatchOptions()
    ok = [f for f in frames if not f.error and f.width > 0]
    by = {k: [f for f in ok if f.kind == k] for k in KINDS}
    groups: dict = {}
    for f in by["light"]:
        key = (f.size, f.binning, None if f.gain is None else round(f.gain, 3),
               None if f.exptime is None else round(f.exptime, 4), f.filter.strip().lower())
        groups.setdefault(key, []).append(f)
    plans = []
    for (size, binning, gain, exptime, _filt), lights in groups.items():
        temp = _median([f.temp for f in lights])
        dark = choose_dark(exptime, gain, temp, size, binning, by["dark"], by["bias"], opts)
        flat = choose_flat(lights[0].filter, size, binning, by["flat"], by["darkflat"], by["dark"], by["bias"], opts)
        g = GroupPlan(lights, exptime, gain, temp, lights[0].filter, size, binning, dark, flat)
        if dark.warning:
            g.warnings.append((dark.warning, dark.warning_args))
        if not dark.any and not (by["dark"] or by["bias"]):
            g.warnings.append(("sin darks ni bias: no se resta nada", ()))
        if flat is None:
            g.warnings.append(("sin flats: no se corrige el viñeteo ni el polvo", ()))
        elif flat.warning:
            g.warnings.append((flat.warning, flat.warning_args))
        if flat is not None and flat.paths and any(dc.mode == "ninguno" for dc, _ in flat.darks):
            g.warnings.append(("a los flats no se les resta dark ni bias (no hay compatibles)", ()))
        plans.append(g)
    plans.sort(key=lambda g: (g.size, g.filter, g.exptime or 0))
    masters = []
    if not by["light"]:  # solo crear maestros
        def split(items, keyf):
            d: dict = {}
            for f in items:
                d.setdefault(keyf(f), []).append(f)
            return d

        gkey = lambda f: None if f.gain is None else round(f.gain, 3)  # noqa: E731
        ekey = lambda f: None if f.exptime is None else round(f.exptime, 4)  # noqa: E731
        for (size, binning, gain), fs in split(by["bias"], lambda f: (f.size, f.binning, gkey(f))).items():
            masters.append(("bias", fs[0], DarkChoice("bias", [], None, 1.0, [f.path for f in fs])))
        for kind in ("dark", "darkflat"):
            for (size, binning, gain, e), fs in split(by[kind], lambda f: (f.size, f.binning, gkey(f), ekey(f))).items():
                masters.append((kind, fs[0], DarkChoice("igual", [f.path for f in fs], e, 1.0, [])))
        for (size, binning, filt), fs in split(by["flat"], lambda f: (f.size, f.binning, f.filter.strip().lower())).items():
            fc = choose_flat(fs[0].filter, size, binning, fs, by["darkflat"], by["dark"], by["bias"], opts)
            if fc and fc.paths:
                masters.append(("flat", fs[0], fc))
    return Plan(plans, masters, {k: len(v) for k, v in by.items()}, [f for f in frames if f.error or f.width <= 0], opts)


# ----------------------------------------------------------------- ejecución
def _frames_of(path: str):
    a = read_stack(path)
    if a.ndim == 3:
        for fr in a:
            yield fr
    else:
        yield a


def combine_frames(frames: Iterable[np.ndarray], n: int, method: str = "mediana", sigma: float = 3.0,
                   max_bytes: int = 768 * 1024 * 1024, tick: Optional[Callable[[], None]] = None) -> np.ndarray:
    """Combina ``n`` imágenes del mismo tamaño. Si no caben en memoria, usa un archivo temporal y trabaja por franjas."""
    it = iter(frames)
    first = np.asarray(next(it), dtype=np.float32)
    if first.ndim != 2:
        raise ValueError("se espera una imagen 2D")
    h, w = first.shape

    def rest():
        yield first
        for fr in it:
            fr = np.asarray(fr, dtype=np.float32)
            if fr.shape != (h, w):
                raise ValueError(f"imágenes de tamaños distintos: {fr.shape[1]} × {fr.shape[0]} y {w} × {h} px")
            yield fr

    if n <= 1:
        return first.copy()
    if method == "media":
        acc = np.zeros((h, w), np.float64)
        k = 0
        for fr in rest():
            acc += fr
            k += 1
            tick and tick()
        return (acc / max(1, k)).astype(np.float32)
    need = n * h * w * 4
    tmp = None
    if need <= max_bytes:
        stack = np.empty((n, h, w), np.float32)
    else:
        fd, tmp = tempfile.mkstemp(prefix="turbulens_comb_", suffix=".dat")
        os.close(fd)
        stack = np.memmap(tmp, dtype=np.float32, mode="w+", shape=(n, h, w))
    try:
        k = 0
        for fr in rest():
            if k >= n:
                break
            stack[k] = fr
            k += 1
            tick and tick()
        if k < n:
            stack = stack[:k]
        if tmp is None:
            return cal.combine_stack(stack, method, sigma)
        out = np.empty((h, w), np.float32)
        rows = max(1, int(max_bytes // 3 // max(1, k * w * 4)))
        for r0 in range(0, h, rows):
            out[r0:r0 + rows] = cal.combine_stack(np.array(stack[:, r0:r0 + rows]), method, sigma)
            tick and tick()
        return out
    finally:
        if tmp is not None:
            del stack
            try:
                os.remove(tmp)
            except OSError:
                pass


def _fmt_exp(e) -> str:
    if e is None:
        return "x"
    return (f"{e:.4f}".rstrip("0").rstrip(".") or "0").replace(".", "p") + "s"


@dataclass
class CalResult:
    outputs: list = field(default_factory=list)
    masters: dict = field(default_factory=dict)  # etiqueta → ruta
    first: dict = field(default_factory=dict)  # dark/flat/bias del primer grupo, para el análisis de video
    cancelled: bool = False


class Calibrator:
    """Ejecuta un plan: crea cada maestro una sola vez y calibra las luces."""

    def __init__(self, out_dir: str, opts: Optional[MatchOptions] = None,
                 progress: Optional[Callable[[str, tuple, int, int], None]] = None,
                 cancelled: Optional[Callable[[], bool]] = None):
        self.out_dir = out_dir
        self.opts = opts or MatchOptions()
        self.progress = progress or (lambda text, args, a, b: None)
        self.cancelled = cancelled or (lambda: False)
        self._cache: dict = {}
        self.result = CalResult()
        self._done = 0
        self._total = 1
        self.master_dir = os.path.join(out_dir, "maestros")
        self.cal_dir = os.path.join(out_dir, "calibradas")

    # ---- utilidades
    def _tick(self):
        self._done += 1
        if self.cancelled():
            raise InterruptedError("cancelado")

    def _say(self, text: str, *args):
        self.progress(text, args, min(self._done, self._total), self._total)

    def _free(self, folder: str, name: str) -> str:
        os.makedirs(folder, exist_ok=True)
        base, ext = os.path.splitext(name)
        p, i = os.path.join(folder, name), 2
        while os.path.exists(p):
            p = os.path.join(folder, f"{base}_{i}{ext}")
            i += 1
        return p

    def _count(self, paths) -> int:
        return sum(self.infos[p].frames if p in self.infos else 1 for p in paths)

    def _save_master(self, kind: str, label: str, a: np.ndarray, n: int, extra: Optional[dict] = None) -> str:
        p = self._free(self.master_dir, f"maestro_{kind}_{label}.fits")
        hdr = {"IMAGETYP": f"Master {kind.capitalize()}", "NCOMBINE": int(n), "COMBINE": self.opts.method}
        hdr.update(extra or {})
        write_fits(p, a, hdr)
        self.result.masters[os.path.basename(p)] = p
        return p

    def _label(self, ref: Optional[FrameInfo], e=None, filt: str = "") -> str:
        parts = []
        if filt:
            parts.append(re.sub(r"[^A-Za-z0-9]+", "", filt)[:12] or "f")
        if e is not None:
            parts.append(_fmt_exp(e))
        if ref is not None:
            if ref.gain is not None:
                parts.append(f"g{ref.gain:g}")
            parts.append(f"{ref.width}x{ref.height}")
        return "_".join(parts) or "x"

    # ---- maestros
    def bias(self, paths: list) -> Optional[np.ndarray]:
        if not paths:
            return None
        key = ("bias", tuple(sorted(paths)))
        if key not in self._cache:
            self._say("Combinando {} bias…", len(paths))
            n = self._count(paths)
            a = combine_frames((fr for p in paths for fr in _frames_of(p)), n, self.opts.method, tick=self._tick)
            ref = self.infos.get(paths[0])
            path = self._save_master("bias", self._label(ref), a, n)
            self._cache[key] = (a, path)
        return self._cache[key][0]

    def raw_dark(self, paths: list, e=None) -> Optional[np.ndarray]:
        if not paths:
            return None
        key = ("dark", tuple(sorted(paths)))
        if key not in self._cache:
            self._say("Combinando {} darks de {} s…", len(paths), "?" if e is None else f"{e:g}")
            n = self._count(paths)
            a = combine_frames((fr for p in paths for fr in _frames_of(p)), n, self.opts.method, tick=self._tick)
            ref = self.infos.get(paths[0])
            extra = {"EXPTIME": float(e)} if e is not None else {}
            path = self._save_master("dark", self._label(ref, e), a, n, extra)
            self._cache[key] = (a, path)
        return self._cache[key][0]

    def dark_for(self, c: DarkChoice) -> Optional[np.ndarray]:
        """La imagen que se resta, según el modo elegido en el plan."""
        if c.mode == "ninguno":
            return None
        if c.mode == "bias":
            return self.bias(c.bias_paths)
        d = self.raw_dark(c.paths, c.exptime)
        if c.mode == "escalado":
            b = self.bias(c.bias_paths)
            return ((d - b) * np.float32(c.scale) + b).astype(np.float32)
        return d

    def flat(self, c: Optional[FlatChoice]) -> Optional[np.ndarray]:
        if c is None or not c.paths:
            return None
        key = ("flat", tuple(sorted(c.paths)))
        if key not in self._cache:
            def gen():
                for dc, paths in c.darks:
                    d = self.dark_for(dc)
                    for p in paths:
                        for fr in _frames_of(p):
                            fr = np.asarray(fr, np.float32)
                            if d is not None:
                                if d.shape != fr.shape:
                                    raise ValueError("el dark del flat no tiene el tamaño del flat")
                                fr = fr - d
                            med = float(np.median(fr))
                            yield fr / med if med > 0 else fr  # cada flat se nivela antes de combinar

            for dc, _ in c.darks:  # los darks de los flats se combinan antes (para que el avance sea claro)
                self.dark_for(dc)
            self._say("Combinando {} flats{}…", len(c.paths), f" ({c.filter})" if c.filter else "")
            n = self._count(c.paths)
            m = combine_frames(gen(), n, self.opts.method, tick=self._tick)
            med = float(np.median(m[m > 0])) if np.any(m > 0) else 1.0
            m = m / (med if med > 0 else 1.0)
            m[~np.isfinite(m) | (m < 0.05)] = 1.0  # píxeles muertos o sin luz: no se dividen
            ref = self.infos.get(c.paths[0])
            path = self._save_master("flat", self._label(ref, None, c.filter), m.astype(np.float32), n,
                                     {"FILTER": c.filter} if c.filter else {})
            self._cache[key] = (m.astype(np.float32), path)
        return self._cache[key][0]

    def _path_of(self, kind: str, paths: list) -> str:
        v = self._cache.get((kind, tuple(sorted(paths))))
        return v[1] if v else ""

    # ---- ejecución
    def run(self, plan: Plan, frames: list) -> CalResult:
        self.infos = {f.path: f for f in frames}
        used = set()
        for g in plan.groups:
            used.update(g.dark.paths, g.dark.bias_paths)
            if g.flat:
                used.update(g.flat.paths)
                for dc, _ in g.flat.darks:
                    used.update(dc.paths, dc.bias_paths)
        for _kind, _ref, ch in plan.masters_only:
            used.update(getattr(ch, "paths", []), getattr(ch, "bias_paths", []))
            for dc, _ in getattr(ch, "darks", []):
                used.update(dc.paths, dc.bias_paths)
        self._total = max(1, self._count(used) + sum(f.frames for g in plan.groups for f in g.lights))
        try:
            for kind, _ref, ch in plan.masters_only:
                if kind == "flat":
                    self.flat(ch)
                else:
                    self.dark_for(ch)
            main = max(plan.groups, key=lambda g: (len(g.lights), g.dark.any, bool(g.flat and g.flat.paths)), default=None)
            for g in plan.groups:
                dark = self.dark_for(g.dark)
                flat = self.flat(g.flat)
                if g is main:  # el grupo principal: sus maestros se pueden usar en el análisis de video
                    self.result.first = {"dark": self._path_of("dark", g.dark.paths) if g.dark.mode == "igual" else "",
                                         "bias": self._path_of("bias", g.dark.bias_paths),
                                         "flat": self._path_of("flat", g.flat.paths) if g.flat else ""}
                stat = ("B" if g.dark.mode in ("bias", "escalado") else "") + \
                       ("D" if g.dark.mode in ("igual", "escalado", "sin_escalar") else "") + ("F" if flat is not None else "")
                for f in g.lights:
                    self._say("Calibrando {}…", f.name)
                    frames_ = list(_frames_of(f.path))
                    for j, img in enumerate(frames_):
                        out = cal.apply_calibration(img, dark, flat, None)
                        suf = f"_{j + 1:04d}" if len(frames_) > 1 else ""
                        q = self._free(self.cal_dir, os.path.splitext(f.name)[0] + suf + "_calibrada.fits")
                        hdr = dict(f.header)
                        hdr.update({"IMAGETYP": "Light Frame", "CALSTAT": stat or "NONE", "NDARK": len(g.dark.paths),
                                    "NBIAS": len(g.dark.bias_paths), "NFLAT": len(g.flat.paths) if g.flat else 0})
                        if g.dark.mode == "escalado":
                            hdr["DARKSCAL"] = round(float(g.dark.scale), 6)
                            hdr["DARKEXP"] = float(g.dark.exptime)
                        write_fits(q, out, hdr)
                        self.result.outputs.append(q)
                        self._tick()
        except InterruptedError:
            self.result.cancelled = True
        self._say("Listo", )
        return self.result
