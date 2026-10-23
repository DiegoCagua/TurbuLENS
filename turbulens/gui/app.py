# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Ventana principal de TurbuLENS."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)

from .. import APP_NAME, INSTITUTION, __version__
from .pages import analysis, edu, misc
from .session import Session, resource_path
from .theme import qss, theme
from .widgets import app_icon, button, label, sun_moon_icon

NAV_ANALISIS = [
    ("FLUJO DE ANÁLISIS", [("video", "Video"), ("region", "Recorte y tramo"), ("parametros", "Parámetros"),
                            ("procesar", "Procesar"), ("resultados", "Resultados")]),
    ("DATOS", [("historial", "Historial")]),
]
NAV_EDU = [
    ("EMPIEZA AQUÍ", [("bienvenida", "Bienvenida")]),
    ("ESTADÍSTICA", [("l1", "Datos y mediciones"), ("l2", "El histograma"), ("l3", "Media y mediana"),
                                      ("l4", "Desviación estándar"), ("l5", "La campana de Gauss"),
                                      ("l6", "Muestras y error"), ("l7", "Datos atípicos"), ("l8", "Correlación"),
                                      ("l9", "Laboratorio libre"), ("quiz", "Ponte a prueba")]),
    ("LA ESTRELLA", [("titilan", "¿Por qué titilan?"), ("dimm", "Los dos huequitos"),
                                  ("simulador", "Simulador")]),
    ("TU VIDEO", [("video", "Video"), ("region", "Recorte y tramo"), ("parametros", "Parámetros"),
                         ("procesar", "Procesar"), ("resultados", "Resultados"), ("historial", "Mis mediciones")]),
]


class MainWindow(QMainWindow):
    def __init__(self, data_root: str | None = None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path("assets", "turbulens_256.png")))
        self.resize(1400, 880)
        # Tamaño mínimo pequeño: si es mayor que la pantalla, algunos escritorios ocultan el botón de maximizar.
        self.setMinimumSize(880, 560)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint
                            | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.settings = QSettings("TurbuLENS", "TurbuLENS")
        self.sessions = {"analisis": Session("analisis", data_root), "educativo": Session("educativo", data_root)}
        self.mode = "analisis"
        self.current = None
        self._busy = False

        self.root = QStackedWidget()
        self.setCentralWidget(self.root)
        self.start = misc.StartPage(self)
        self.root.addWidget(self.start)

        shell = QWidget()
        sl = QVBoxLayout(shell)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)
        sl.addWidget(self._header())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(232)
        sbl = QVBoxLayout(self.sidebar)
        sbl.setContentsMargins(0, 0, 0, 0)
        inner = QWidget()
        inner.setObjectName("transparent")
        self.side_lay = QVBoxLayout(inner)
        self.side_lay.setContentsMargins(10, 8, 10, 10)
        self.side_lay.setSpacing(2)
        from .widgets import scroll as _scroll
        sa = _scroll(inner)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sbl.addWidget(sa)
        body.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        sl.addLayout(body, 1)
        self.root.addWidget(shell)
        self.toast_lbl = QLabel(self)
        self.toast_lbl.setVisible(False)
        self.toast_lbl.setWordWrap(True)

        self.page_by_key = {}
        for key, cls in [("video", analysis.VideoPage), ("region", analysis.RegionPage),
                         ("parametros", analysis.ParamsPage), ("procesar", analysis.ProcessPage),
                         ("resultados", analysis.ResultsPage), ("historial", analysis.HistoryPage),
                         ("acerca", misc.AboutPage), ("bienvenida", edu.Welcome), ("quiz", edu.QuizPage),
                         ("titilan", edu.AstroTitilan), ("dimm", edu.AstroDimm), ("simulador", edu.AstroSim)]:
            self._add_page(key, cls(self))
        for i, cls in enumerate(edu.LESSONS, start=1):
            self._add_page(f"l{i}", cls(self))
        for s in self.sessions.values():
            s.result_changed.connect(self._on_result)

        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=lambda: self.isFullScreen() and self.toggle_fullscreen())
        theme.changed.connect(self.apply_theme)
        dark = self.settings.value("dark", True, type=bool)
        theme.set_dark(dark)
        self.apply_theme(theme.pal)

    # --------------------------------------------------------------- partes
    def _header(self):
        h = QFrame()
        h.setObjectName("header")
        lay = QHBoxLayout(h)
        lay.setContentsMargins(18, 10, 18, 10)
        lay.setSpacing(12)
        self.logo = QLabel()
        lay.addWidget(self.logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(APP_NAME, "title"))
        col.addWidget(label(INSTITUTION, "small"))
        lay.addLayout(col)
        lay.addStretch(1)
        self.mode_chip = label("", "chip")
        lay.addWidget(self.mode_chip)
        lay.addWidget(button("Cambiar de modo", slot=self.go_start))
        self.theme_b = QToolButton()
        self.theme_b.setProperty("kind", "theme")
        self.theme_b.setCursor(Qt.PointingHandCursor)
        self.theme_b.clicked.connect(theme.toggle)
        lay.addWidget(self.theme_b)
        return h

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()


    def _add_page(self, key, page):
        self.page_by_key[key] = page
        self.pages.addWidget(page)

    def _build_nav(self):
        while self.side_lay.count():
            it = self.side_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.nav_buttons = {}
        group = QButtonGroup(self.sidebar)
        group.setExclusive(True)
        nav = NAV_EDU if self.mode == "educativo" else NAV_ANALISIS
        for title, items in nav:
            self.side_lay.addWidget(label(title, "section"))
            for i, (key, text) in enumerate(items, start=1):
                b = button(f"{i}   {text}" if title.startswith(("FLUJO", "TU VIDEO", "ESTAD")) else text, "nav",
                           checkable=True)
                b.clicked.connect(lambda _=False, k=key: self.go(k))
                group.addButton(b)
                self.side_lay.addWidget(b)
                self.nav_buttons[key] = b
        self.side_lay.addStretch(1)
        ab = button("Acerca de", "nav", checkable=True)
        ab.clicked.connect(lambda: self.go("acerca"))
        group.addButton(ab)
        self.nav_buttons["acerca"] = ab
        self.side_lay.addWidget(ab)
        self.side_lay.addWidget(label(f"Versión {__version__}", "small"))
        self._nav_group = group

    # ------------------------------------------------------------ navegación
    @property
    def session(self) -> Session:
        return self.sessions[self.mode]

    def set_mode(self, mode: str):
        if mode not in self.sessions:  # protección: nunca quedar en un modo inválido
            return
        self.mode = mode
        self.mode_chip.setText("Modo educativo" if mode == "educativo" else "Modo análisis")
        self._build_nav()
        self.root.setCurrentIndex(1)
        self.go("bienvenida" if mode == "educativo" else "video")

    def go_start(self):
        if self._busy:
            self.toast("Espera a que termine el procesamiento o cancélalo.")
            return
        self.root.setCurrentIndex(0)

    def go(self, key: str):
        page = self.page_by_key.get(key)
        if page is None:
            return
        self.current = key
        self.pages.setCurrentWidget(page)
        if key in getattr(self, "nav_buttons", {}):
            self.nav_buttons[key].setChecked(True)
        page.on_enter()
        page.on_theme(theme.pal)

    def set_busy(self, busy: bool):
        self._busy = busy

    def _on_result(self):
        page = self.pages.currentWidget()
        if page in (self.page_by_key["resultados"],):
            page.refresh()

    def toast(self, text: str):
        pal = theme.pal
        self.toast_lbl.setText(text)
        self.toast_lbl.setStyleSheet(f"background:{pal['panel']}; color:{pal['text']}; border:1px solid {pal['accent']};"
                                     "border-radius:10px; padding:10px 14px;")
        self.toast_lbl.adjustSize()
        self.toast_lbl.setFixedWidth(min(520, self.width() - 40))
        self.toast_lbl.adjustSize()
        self.toast_lbl.move((self.width() - self.toast_lbl.width()) // 2, self.height() - self.toast_lbl.height() - 24)
        self.toast_lbl.raise_()
        self.toast_lbl.setVisible(True)
        QTimer.singleShot(3800, lambda: self.toast_lbl.setVisible(False))

    # ------------------------------------------------------------------ tema
    def apply_theme(self, pal: dict):
        QApplication.instance().setStyleSheet(qss(pal))
        self.logo.setPixmap(app_icon(34))
        self.theme_b.setIcon(sun_moon_icon(theme.dark, pal["text"]))
        self.theme_b.setToolTip("Cambiar a tema claro" if theme.dark else "Cambiar a tema oscuro")
        self.settings.setValue("dark", theme.dark)
        for p in self.page_by_key.values():
            p.on_theme(pal)
            p.update()

    def closeEvent(self, ev):
        pg = self.page_by_key.get("procesar")
        if pg is not None and pg.worker is not None:
            pg.cancel()
            if pg.thread is not None:
                pg.thread.quit()
                pg.thread.wait(3000)
        super().closeEvent(ev)


def main(argv=None) -> int:
    argv = sys.argv if argv is None else argv
    from PySide6.QtCore import QLocale

    QLocale.setDefault(QLocale(QLocale.Spanish, QLocale.Colombia))
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName("TurbuLENS")
    app.setWindowIcon(QIcon(resource_path("assets", "turbulens_256.png")))
    f = QFont()
    f.setFamilies(["Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Noto Sans", "DejaVu Sans", "Arial"])
    f.setPointSizeF(10)
    app.setFont(f)
    w = MainWindow()
    w.showMaximized()  # abre ocupando toda la pantalla
    if len(argv) > 1 and os.path.isfile(argv[1]):
        w.set_mode("analisis")
        w.page_by_key["video"].open(argv[1])
    return app.exec()
