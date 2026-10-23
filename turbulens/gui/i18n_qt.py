# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Traducción automática de los textos de la interfaz.

Se envuelven los métodos de Qt que muestran texto (setText, setToolTip,
addItem, setHorizontalHeaderLabels, …) para que pasen por ``i18n.tr``.
Así cada texto en español del programa se muestra en el idioma activo sin
tener que marcarlo a mano. También carga las traducciones propias de Qt
(botones de los diálogos estándar).
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QTableWidget, QWidget,
)

from ..i18n import lang, tr

_installed = False
_qt_translator = None


def _wrap(cls, name, kind):
    orig = getattr(cls, name)

    if kind == "first":
        def f(self, text, *a, **k):
            return orig(self, tr(text) if isinstance(text, str) else text, *a, **k)
    elif kind == "list":
        def f(self, items, *a, **k):
            return orig(self, [tr(t) if isinstance(t, str) else t for t in items], *a, **k)
    elif kind == "last":
        def f(self, *a, **k):
            if a and isinstance(a[-1], str):
                a = a[:-1] + (tr(a[-1]),)
            return orig(self, *a, **k)
    elif kind == "additem":
        def f(self, *a, **k):
            a = list(a)
            for i, v in enumerate(a):
                if isinstance(v, str):
                    a[i] = tr(v)
                    break
            return orig(self, *a, **k)
    f.__name__ = name
    setattr(cls, name, f)


def install():
    """Activa la traducción automática (una sola vez por proceso)."""
    global _installed
    if _installed:
        return
    _installed = True
    _wrap(QLabel, "setText", "first")
    _wrap(QAbstractButton, "setText", "first")
    _wrap(QWidget, "setToolTip", "first")
    _wrap(QWidget, "setWindowTitle", "first")
    _wrap(QWidget, "setAccessibleName", "first")
    _wrap(QLineEdit, "setPlaceholderText", "first")
    _wrap(QGroupBox, "setTitle", "first")
    _wrap(QComboBox, "addItem", "additem")
    _wrap(QComboBox, "addItems", "list")
    _wrap(QTableWidget, "setHorizontalHeaderLabels", "list")
    _wrap(QPainter, "drawText", "last")  # textos de las gráficas y de los informes PDF


def _translations_dir() -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base and os.path.isdir(os.path.join(base, "translations")):
        return os.path.join(base, "translations")
    return QLibraryInfo.path(QLibraryInfo.TranslationsPath)


def load_qt_translations(app) -> None:
    """Traducciones de Qt (diálogos de archivo, botones estándar) para el idioma activo."""
    global _qt_translator
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    code = {"es": "es", "pt": "pt_BR", "en": None}.get(lang())
    loc = {"es": QLocale(QLocale.Spanish, QLocale.Colombia), "pt": QLocale(QLocale.Portuguese, QLocale.Brazil),
           "en": QLocale(QLocale.English, QLocale.UnitedStates)}[lang()]
    QLocale.setDefault(loc)
    if code:
        t = QTranslator(app)
        if t.load(f"qtbase_{code}", _translations_dir()):
            app.installTranslator(t)
            _qt_translator = t
