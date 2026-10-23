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
from ..i18n import tr

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
    def __init__(self, data_root: str | None = None, sessions: dict | None = None):
        super().__init__()
        self.data_root = data_root
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path("assets", "turbulens_256.png")))
        self.resize(1400, 880)
        # Tamaño mínimo pequeño: si es mayor que la pantalla, algunos escritorios ocultan el botón de maximizar.
        self.setMinimumSize(880, 560)
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint
                            | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.settings = QSettings("TurbuLENS", "TurbuLENS")
        # Al cambiar de idioma se rehace la interfaz pero se conservan los datos de trabajo de cada modo.
        self.sessions = sessions or {"analisis": Session("analisis", data_root), "educativo": Session("educativo", data_root)}
        self.mode = "analisis"
        self.current = None
        self._busy = False

        self._build_ui()
        for s in self.sessions.values():
            s.result_changed.connect(self._on_result)

        from PySide6.QtGui import QKeySequence, QShortcut

        QShortcut(QKeySequence(Qt.Key_F11), self, activated=self.toggle_fullscreen)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=lambda: self.isFullScreen() and self.toggle_fullscreen())
        theme.changed.connect(self.apply_theme)
        dark = self.settings.value("dark", True, type=bool)
        theme.set_dark(dark)
        self.apply_theme(theme.pal)

    def _build_ui(self):
        """Crea toda la interfaz (también al cambiar de idioma, en la misma ventana)."""
        self.root = QStackedWidget()
        self.setCentralWidget(self.root)
        from .widgets import scroll as _scroll

        self.start = misc.StartPage(self)
        start_sa = _scroll(self.start)  # con desplazamiento: en pantallas bajas nada se monta encima de nada
        start_sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.root.addWidget(start_sa)

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
        sa = _scroll(inner)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sbl.addWidget(sa)
        body.addWidget(self.sidebar)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        sl.addLayout(body, 1)
        self.root.addWidget(shell)
        self.root.addWidget(misc.StartAbout(self))  # «Acerca de» desde la pantalla de inicio
        if getattr(self, "toast_lbl", None) is None:  # el aviso breve se crea una sola vez
            self.toast_lbl = QLabel(self)
            self.toast_lbl.setVisible(False)
            self.toast_lbl.setWordWrap(True)

        self.page_by_key = {}
        self.nav_buttons = {}
        for key, cls in [("video", analysis.VideoPage), ("region", analysis.RegionPage),
                         ("parametros", analysis.ParamsPage), ("procesar", analysis.ProcessPage),
                         ("resultados", analysis.ResultsPage), ("historial", analysis.HistoryPage),
                         ("acerca", misc.AboutPage), ("bienvenida", edu.Welcome), ("quiz", edu.QuizPage),
                         ("titilan", edu.AstroTitilan), ("dimm", edu.AstroDimm), ("simulador", edu.AstroSim)]:
            self._add_page(key, cls(self))
        for i, cls in enumerate(edu.LESSONS, start=1):
            self._add_page(f"l{i}", cls(self))

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
        self._loading_tick()

    def _loading_tick(self):
        """Mientras se rehace la interfaz, deja que el logo de la pantalla de carga siga girando."""
        import time

        ov = getattr(self, "_loading", None)
        if ov is None or time.monotonic() - getattr(self, "_last_tick", 0.0) < 0.025:
            return
        self._last_tick = time.monotonic()
        ov.raise_()
        from PySide6.QtCore import QEventLoop

        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

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
                b = button(f"{i}   {tr(text)}" if title.startswith(("FLUJO", "TU VIDEO", "ESTAD")) else text, "nav",
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
        self.side_lay.addWidget(label(tr("Versión {}").format(__version__), "small"))
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

    def show_start_about(self):
        self.root.setCurrentIndex(2)

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
        lb = self.toast_lbl
        QTimer.singleShot(3800, lb, lambda: lb.setVisible(False))  # se cancela solo si la ventana se cierra

    # ------------------------------------------------------------------ tema
    def apply_theme(self, pal: dict):
        app = QApplication.instance()
        css = qss(pal)
        if app.styleSheet() != css:  # volver a poner la misma hoja de estilo repinta toda la app (lento)
            app.setStyleSheet(css)
        from PySide6.QtGui import QColor, QPalette

        qp = app.palette()  # enlaces legibles en los dos temas
        qp.setColor(QPalette.Link, QColor(pal["accent"]))
        qp.setColor(QPalette.LinkVisited, QColor(pal["accent"]))
        app.setPalette(qp)
        # Los textos con enlaces guardan el color con que se crearon: se vuelven a poner para que tomen el del tema.
        for lb in self.findChildren(QLabel):
            t = lb.text()
            if "<a " in t:
                lb.clear()  # con el mismo texto Qt no lo vuelve a dibujar
                lb.setText(t)
        self.logo.setPixmap(app_icon(34))
        self.theme_b.setIcon(sun_moon_icon(theme.dark, pal["text"]))
        self.theme_b.setToolTip("Cambiar a tema claro" if theme.dark else "Cambiar a tema oscuro")
        self.settings.setValue("dark", theme.dark)
        for p in self.page_by_key.values():
            p.on_theme(pal)
            p.update()

    # ---------------------------------------------------------------- idioma
    LOADING = {"es": "Cambiando el idioma…", "en": "Changing the language…", "pt": "Mudando o idioma…"}

    def change_language(self, code: str):
        """Cambia el idioma de toda la interfaz en la misma ventana, conservando los datos y la pantalla."""
        from .. import i18n

        if code == i18n.lang() or getattr(self, "_switching", False):
            return
        if self._busy:
            self.toast("Espera a que termine el procesamiento o cancélalo.")
            return False
        self._switching = True  # una sola reconstrucción aunque la señal llegue dos veces
        self.settings.setValue("lang", code)
        self._show_loading(self.LOADING.get(code, self.LOADING["es"]))
        QTimer.singleShot(40, lambda: self._apply_language(code))
        return True

    def _show_loading(self, text: str):
        """Pantalla de carga: se ve de inmediato y tapa la ventana mientras se rehace la interfaz."""
        pal = theme.pal
        ov = QFrame(self)
        ov.setObjectName("loading")
        ov.setStyleSheet(f"QFrame#loading {{ background: {pal['bg']}; }}")
        lay = QVBoxLayout(ov)
        lay.addStretch(1)
        from .widgets import SpinningLogo

        lay.addWidget(SpinningLogo(96), 0, Qt.AlignHCenter)
        t = QLabel()
        t.setText(text)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet(f"font-size: 22px; font-weight: 600; color: {pal['text']}; background: transparent;")
        lay.addWidget(t)
        lay.addStretch(1)
        ov.setGeometry(self.rect())
        ov.show()
        ov.raise_()
        self._loading = ov
        from . import widgets as _w

        _w.LOADING_TICK = self._loading_tick
        ov.repaint()
        QApplication.processEvents()

    def _apply_language(self, code: str):
        from .. import i18n
        from . import i18n_qt

        try:
            i18n.load(code)
            i18n_qt.load_qt_translations(QApplication.instance())
            idx, mode, cur = self.root.currentIndex(), self.mode, self.current
            self._build_ui()
            self.apply_theme(theme.pal)
            if idx == 1:
                self.set_mode(mode)
                if cur:
                    self.go(cur)
            else:
                self.root.setCurrentIndex(idx)
        finally:
            self._switching = False
            from . import widgets as _w

            _w.LOADING_TICK = None
            ov = getattr(self, "_loading", None)
            if ov is not None:
                ov.raise_()
                QTimer.singleShot(150, ov.deleteLater)  # deja ver la interfaz nueva ya dibujada
                self._loading = None

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        ov = getattr(self, "_loading", None)
        if ov is not None:
            ov.setGeometry(self.rect())

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
    from .. import i18n
    from . import i18n_qt

    i18n_qt.install()  # todos los textos de Qt pasan por la traducción
    i18n.load(QSettings("TurbuLENS", "TurbuLENS").value("lang", "es", type=str) or "es")
    if sys.platform == "win32":  # icono y nombre propios en la barra de tareas (no los de Python)
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DiegoCagua.TurbuLENS")
        except Exception:
            pass
    app = QApplication(argv)
    i18n_qt.load_qt_translations(app)
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
