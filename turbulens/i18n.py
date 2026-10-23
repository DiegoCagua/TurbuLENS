# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Idiomas de TurbuLENS: español (original), inglés y portugués.

Los textos del programa están escritos en español. ``tr(texto)`` devuelve la
traducción del idioma activo usando los diccionarios ``locales/en.json`` y
``locales/pt.json`` (clave = texto en español). Para textos con partes que cambian
(números, nombres), las claves pueden tener ``{}``: «Muestra de {} cuadros».
Si un texto no tiene traducción se muestra en español.
"""
from __future__ import annotations

import json
import os
import re
import sys

LANGUAGES = [("es", "Español"), ("en", "English"), ("pt", "Português")]
_lang = "es"
_exact: dict[str, str] = {}
_templates: list = []
_cache: dict[str, str] = {}


def _dir() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "locales")
    if not os.path.isdir(d):
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
    return d


def load(lang: str) -> None:
    global _lang, _exact, _templates, _cache
    _lang = lang if lang in dict(LANGUAGES) else "es"
    _exact, _templates, _cache = {}, [], {}
    if _lang == "es":
        return
    path = os.path.join(_dir(), f"{_lang}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    for k, v in data.items():
        if not v:
            continue
        if "{}" in k:
            parts = [re.escape(p) for p in k.split("{}")]
            rx = re.compile("^" + "(.+?)".join(parts) + "$", re.S)
            _templates.append((rx, v))
        else:
            _exact[k] = v
    _templates.sort(key=lambda t: -len(t[0].pattern))


def lang() -> str:
    return _lang


def tr(text):
    """Traduce ``text`` al idioma activo (o lo devuelve igual)."""
    if _lang == "es" or not isinstance(text, str) or not text:
        return text
    if text in _cache:
        return _cache[text]
    out = _exact.get(text)
    if out is None:
        for rx, tpl in _templates:
            m = rx.match(text)
            if m:
                vals = [tr(g) for g in m.groups()]
                try:
                    out = tpl.replace("{}", "\x00").replace("\x00", "{}").format(*vals)
                except Exception:
                    out = None
                if out is not None:
                    break
    if out is None:
        out = text
    _cache[text] = out
    return out


def decimal_point() -> str:
    return "." if _lang == "en" else ","


def num(v, d: int = 2) -> str:
    """Número con decimales según el idioma: 1,25 (es, pt) o 1.25 (en)."""
    s = f"{v:.{d}f}"
    return s if _lang == "en" else s.replace(".", ",")


def integer(n) -> str:
    """Entero con separador de miles: 8.484 (es, pt) o 8,484 (en)."""
    s = f"{int(n):,}"
    return s if _lang == "en" else s.replace(",", ".")


def localize_number_text(s: str) -> str:
    """Cambia los puntos decimales de un texto ya formateado («1.25») al idioma activo."""
    return s if _lang == "en" else s.replace(".", ",")
