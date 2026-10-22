# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Pruebas de la interfaz simulando clics reales (sin pantalla)."""

import os
import sys
import time
import traceback

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def errors():
    errs = []
    old = sys.excepthook
    sys.excepthook = lambda t, v, tb: errs.append("".join(traceback.format_exception(t, v, tb)))
    yield errs
    sys.excepthook = old


def make_window(tmp_path):
    from turbulens.gui.app import MainWindow

    w = MainWindow(data_root=str(tmp_path / "datos"))
    w.resize(1400, 880)
    w.show()
    QApplication.processEvents()
    return w


@pytest.mark.parametrize("idx,mode", [(0, "analisis"), (1, "educativo")])
@pytest.mark.parametrize("where", ["boton", "tarjeta"])
def test_enter_mode_from_start_screen(app, errors, tmp_path, idx, mode, where):
    from turbulens.gui.pages.misc import ModeCard

    w = make_window(tmp_path)
    card = w.start.findChildren(ModeCard)[idx]
    if where == "boton":
        QTest.mouseClick(card.findChildren(QPushButton)[0], Qt.LeftButton)
    else:
        QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(30, 30))
    QApplication.processEvents()
    assert w.mode == mode
    assert w.root.currentIndex() == 1
    # Recorrer todo el menú del modo con clics
    for b in list(w.nav_buttons.values()):
        QTest.mouseClick(b, Qt.LeftButton)
        QApplication.processEvents()
    assert not errors, errors[0]
    w.close()


def test_open_and_process_video_in_each_mode(app, errors, tmp_path):
    from synthetic import make_video

    vid = str(tmp_path / "v.mkv")
    make_video(vid, n=180, w=480, h=320)
    w = make_window(tmp_path)
    for mode in ("analisis", "educativo"):
        w.set_mode(mode)
        w.go("video")
        w.page_by_key["video"].open(vid)
        s = w.session
        assert s.info is not None and s.info.n_frames == 180
        s.out_dir = str(tmp_path / f"out_{mode}")
        for key in ("region", "parametros", "procesar"):
            w.go(key)
        pg = w.page_by_key["procesar"]
        pg.start()
        t0 = time.time()
        while pg.thread is not None and time.time() - t0 < 120:
            QApplication.processEvents()
            time.sleep(0.02)
        assert s.result is not None and s.dimm.n_detected > 150
        w.go("resultados")
        w.page_by_key["resultados"].save()
        w.go("historial")
        assert len(s.history.list()) == 1
    # Modos separados
    assert len(w.sessions["analisis"].history.list()) == 1
    assert len(w.sessions["educativo"].history.list()) == 1
    w.go_start()
    assert not errors, errors[0]
    w.close()
