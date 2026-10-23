# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Idiomas: diccionarios coherentes, cambio de idioma sin ventanas extra y preguntas de una sola respuesta."""

import json
import os
import re
import sys
import traceback

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES = os.path.join(ROOT, "turbulens", "locales")
TAG = re.compile(r"</?[a-z]+[^>]*>")


def _load(lang):
    with open(os.path.join(LOCALES, f"{lang}.json"), encoding="utf-8") as f:
        return json.load(f)


def test_dictionaries_match():
    en, pt = _load("en"), _load("pt")
    assert set(en) == set(pt)
    assert len(en) > 500
    for d in (en, pt):
        for k, v in d.items():
            assert v, k
            assert v.count("{}") == k.count("{}"), k
            assert TAG.findall(v) == TAG.findall(k), k


def test_tr_templates_and_numbers():
    from turbulens import i18n

    try:
        i18n.load("en")
        assert i18n.tr("Resultados") == "Results"
        assert i18n.tr("Guardado ✓ (#7)") == "Saved ✓ (#7)"
        assert i18n.num(1.25) == "1.25" and i18n.integer(8484) == "8,484"
        i18n.load("pt")
        assert i18n.tr("Resultados") == "Resultados" and i18n.tr("Historial") == "Histórico"
        assert i18n.num(1.25) == "1,25" and i18n.integer(8484) == "8.484"
        assert "versão" in __import__("turbulens").citation_apa()
    finally:
        i18n.load("es")
    assert i18n.tr("Resultados") == "Resultados" and i18n.num(1.25) == "1,25"


QtWidgets = pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "config"))
    from turbulens.gui import i18n_qt

    i18n_qt.install()
    a = QApplication.instance() or QApplication([])
    _drop_old_windows()  # las ventanas de otras pruebas harían lento cada cambio de tema/estilo
    yield a
    from turbulens import i18n

    i18n.load("es")


def _drop_old_windows():
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QMainWindow

    for w in QApplication.topLevelWidgets():
        if isinstance(w, QMainWindow):
            w.hide()
            w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def _pump(ms=120):
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _visible_tops():
    from PySide6.QtWidgets import QApplication

    return [w for w in QApplication.topLevelWidgets() if w.isVisible()]


def test_language_switch_in_same_window_keeps_answers(app, tmp_path):
    from turbulens import i18n
    from turbulens.gui.app import MainWindow

    errs = []
    old_hook = sys.excepthook
    sys.excepthook = lambda t, v, tb: errs.append("".join(traceback.format_exception(t, v, tb)))
    try:
        w = MainWindow(data_root=str(tmp_path / "datos"))
        w.show()
        w.set_mode("educativo")
        w.go("quiz")
        quiz = w.page_by_key["quiz"]
        quiz.pick(0, 1)
        quiz.pick(0, 2)  # no se puede cambiar
        assert quiz.items[0]["ans"] == 1
        # Cambio desde «Acerca de»: la ficha emite dos señales y solo debe rehacerse una vez la interfaz
        w.go("acerca")
        import time

        old_page = w.page_by_key["resultados"]
        t0 = time.time()
        w.page_by_key["acerca"].lang.set_value("en")
        assert w._loading is not None and w._loading.isVisible()  # pantalla de carga inmediata
        _pump(500)
        assert time.time() - t0 < 20
        assert i18n.lang() == "en" and w.page_by_key["resultados"] is not old_page
        assert w.current == "acerca" and w.mode == "educativo"  # misma pantalla y mismo modo
        assert w.page_by_key["resultados"].h1.text() == "Results"
        assert w.page_by_key["quiz"].items[0]["ans"] == 1  # la respuesta sigue registrada
        assert w._loading is None
        w.change_language("pt")
        _pump(500)
        assert w.page_by_key["historial"].h1.text() == "Histórico"
        w.go_start()
        w.start.lang_c.setCurrentIndex(0)  # desde el inicio, de vuelta al español
        _pump(500)
        assert i18n.lang() == "es" and w.root.currentIndex() == 0
        assert _visible_tops() == [w]
        w.close()
    finally:
        sys.excepthook = old_hook
    assert not errs, errs[0]


def test_no_popup_windows_while_processing(app, tmp_path):
    import time

    sys.path.insert(0, os.path.dirname(__file__))
    from synthetic import make_video
    from turbulens.gui.app import MainWindow

    vid = str(tmp_path / "v.mkv")
    make_video(vid, n=120, w=400, h=300)
    w = MainWindow(data_root=str(tmp_path / "datos"))
    w.show()
    w.set_mode("analisis")
    w.page_by_key["video"].open(vid)
    w.session.out_dir = str(tmp_path / "out")
    for k in ("region", "parametros", "procesar"):
        w.go(k)
        _pump(50)
    pg = w.page_by_key["procesar"]
    pg.start()
    t0 = time.time()
    while pg.thread is not None and time.time() - t0 < 120:
        _pump(50)
    for k in ("resultados", "historial", "acerca"):
        w.go(k)
        _pump(150)
        assert _visible_tops() == [w], [type(t).__name__ for t in _visible_tops()]
    w.close()
