# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Pantalla de inicio y «Acerca de»."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from ... import (APP_NAME, AUTHOR, AUTHOR_ROLE, AUTHORS, INSTITUTION, LICENSE_NAME, LICENSE_SUMMARY, REPO_URL, __version__,
                 SCALE_LINKS, citation_apa, citation_bibtex)
from ..theme import theme
from ... import i18n
from ...i18n import tr
from ..widgets import Card, ChipGroup, app_icon, button, hbox, label, sun_moon_icon
from .base import Page


class ModeCard(QFrame):
    def __init__(self, title, text, cta, cb):
        super().__init__()
        self.setProperty("card", "true")
        self.setCursor(Qt.PointingHandCursor)
        self.cb = cb
        self.setMinimumSize(380, 210)
        self.setMaximumWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 22)
        lay.setSpacing(10)
        t = label(title, "h1")
        d = label(text, "muted", wrap=True)
        d.setStyleSheet("font-size:15px;")
        lay.addWidget(t)
        lay.addWidget(d)
        lay.addStretch(1)
        b = button(cta, "primary", lambda *_: cb())  # clicked envía «checked»: no pasarlo a cb
        b.setMinimumHeight(42)
        lay.addLayout(hbox(b, "stretch"))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.cb()


class StartPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 20, 30, 24)
        lay.setSpacing(22)
        top = QHBoxLayout()
        top.addStretch(1)
        from PySide6.QtWidgets import QComboBox

        self.lang_c = QComboBox()
        for code, name in i18n.LANGUAGES:
            self.lang_c.addItem(name, code)
        self.lang_c.setCurrentIndex([c for c, _ in i18n.LANGUAGES].index(i18n.lang()))
        self.lang_c.setToolTip("Idioma · Language · Idioma")
        self.lang_c.currentIndexChanged.connect(self._lang_changed)
        top.addWidget(self.lang_c)
        self.theme_b = QToolButton()
        self.theme_b.setProperty("kind", "theme")
        self.theme_b.setCursor(Qt.PointingHandCursor)
        self.theme_b.clicked.connect(theme.toggle)
        top.addWidget(self.theme_b)
        lay.addLayout(top)
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.logo)
        t = label(APP_NAME, "hero")
        t.setAlignment(Qt.AlignCenter)
        lay.addWidget(t)
        i = label(INSTITUTION, "muted")
        i.setAlignment(Qt.AlignCenter)
        lay.addWidget(i)
        d = label("Separa videos de un DIMM en imágenes, mide la imagen doble de una estrella y calcula el seeing de tu cielo.",
                  "muted", wrap=True)
        d.setAlignment(Qt.AlignCenter)
        lay.addWidget(d)
        cards = QHBoxLayout()
        cards.setSpacing(20)
        cards.addStretch(1)
        for title, text, cta, mode in (
            ("Análisis científico", "Para mediciones reales de tu sitio de observación: extracción de cuadros, seeing, "
             "historial y exportación de datos.", "Entrar al modo análisis  →", "analisis"),
            ("Modo educativo", "Aprende estadística con un experimento astronómico real: histogramas, media, desviación "
             "estándar, la campana de Gauss y más. Para colegios y cursos.", "Entrar al modo educativo  →", "educativo"),
        ):
            c = ModeCard(title, text, cta, lambda *_, m=mode: self.main.set_mode(m))
            cards.addWidget(c, 1)
        cards.addStretch(1)
        lay.addLayout(cards)
        n = label("Cada modo guarda sus mediciones por separado: los datos de clase nunca se mezclan con los científicos.", "muted")
        n.setAlignment(Qt.AlignCenter)
        lay.addWidget(n)
        lay.addStretch(1)
        self.about_lbl = label("", "small")
        self.about_lbl.setAlignment(Qt.AlignCenter)
        self.about_lbl.setVisible(False)
        foot = hbox("stretch", label(tr("Uso no comercial · versión {}").format(__version__), "small"),
                    button("Acerca de", slot=self._about), "stretch")
        lay.addLayout(foot)
        lay.addWidget(self.about_lbl)
        theme.changed.connect(self.on_theme)
        self.on_theme(theme.pal)

    def _lang_changed(self, *_):
        code = self.lang_c.currentData()
        if code and code != i18n.lang() and self.main.change_language(code) is False:
            self.lang_c.blockSignals(True)
            self.lang_c.setCurrentIndex([c for c, _ in i18n.LANGUAGES].index(i18n.lang()))
            self.lang_c.blockSignals(False)

    def _about(self):
        autores = "<br>".join(f"<b>{n}</b>" + (f" · {tr(r)}" if r else "") for n, r in AUTHORS)
        self.about_lbl.setText(f"{autores}<br>" + tr("Autores de {}").format(APP_NAME) + "<br>"
                               + tr("Licencia {} (uso no comercial, con crédito a los autores)").format(LICENSE_NAME)
                               + f" · <a href='{REPO_URL}'>{REPO_URL}</a>")
        self.about_lbl.setTextFormat(Qt.RichText)
        self.about_lbl.setOpenExternalLinks(True)
        self.about_lbl.setVisible(not self.about_lbl.isVisible())

    def on_theme(self, pal):
        self.logo.setPixmap(app_icon(84))
        self.theme_b.setIcon(sun_moon_icon(theme.dark, pal["text"]))
        self.theme_b.setToolTip("Tema claro" if theme.dark else "Tema oscuro")


class AboutPage(Page):
    title = f"Acerca de {APP_NAME}"

    def __init__(self, main):
        super().__init__(main)
        lang_card = Card("Idioma · Language · Idioma")
        self.lang = ChipGroup([(code, name) for code, name in i18n.LANGUAGES])
        self.lang.set_value(i18n.lang())
        self.lang.changed.connect(self._lang_changed)
        lang_card.add(label("Cambia el idioma de toda la aplicación. Tus datos y mediciones se conservan.", "muted", wrap=True),
                      self.lang)
        self.lay.addWidget(lang_card)
        c = Card()
        refs = ("<a href='https://arxiv.org/abs/astro-ph/0111022'>Tokovinin (2002), From differential image motion to seeing. "
                "PASP 114, 1156</a><br>" + tr("Protocolo «Determina la nitidez del cielo nocturno», ANDEAN ROAD (2026)") + "<br>"
                + "<br>".join(f"<a href='{u}'>{tr(t)}</a>" for u, t in SCALE_LINKS))
        rows = [
            ("", tr("{} separa videos de un DIMM (monitor de movimiento diferencial de imagen) en imágenes, mide la "
                    "imagen doble de una estrella y estima el seeing del lugar de observación. Tiene un modo científico y un "
                    "modo educativo para aprender estadística.").format(APP_NAME)),
            ("Autores", "<br><br>".join(f"<b>{n}</b>" + (f"<br>{tr(r)}" if r else "") for n, r in AUTHORS)),
            ("Institución", INSTITUTION),
            ("Licencia", f"<b>{LICENSE_NAME}</b>. {tr(LICENSE_SUMMARY)}<br><a href='{REPO_URL}'>{REPO_URL}</a>"),
            ("Referencias", refs),
            ("Tecnología", "Python · NumPy · PySide6 (Qt) · PyAV (FFmpeg) · Pillow · openpyxl"),
            ("Versión", __version__),
        ]
        g = QGridLayout()
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(12)
        for r, (k, v) in enumerate(rows):
            if k:
                g.addWidget(label(k, "muted"), r, 0, Qt.AlignTop)
            lv = label(v, wrap=True, rich=True)
            g.addWidget(lv, r, 1 if k else 0, 1, 1 if k else 2)
        g.setColumnStretch(1, 1)
        c.add(g)
        self.lay.addWidget(c)
        cite = Card("Cómo citar TurbuLENS")
        cite.add(label("Si usas TurbuLENS en un trabajo, informe, clase o publicación, da crédito a los autores con esta referencia:",
                       "muted", wrap=True))
        apa = label(citation_apa(), wrap=True)
        apa.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bib = label(citation_bibtex().replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;"), "mono", wrap=True, rich=True)
        bib.setTextInteractionFlags(Qt.TextSelectableByMouse)
        box = Card(kind="panel2", margins=(12, 10, 12, 10))
        box.add(bib)
        self.copied = label("", "small")
        cite.add(label("APA", "small"), apa, label("BibTeX", "small"), box,
                 hbox(button("Copiar cita APA", slot=lambda: self._copy(citation_apa())),
                      button("Copiar BibTeX", slot=lambda: self._copy(citation_bibtex())), self.copied, "stretch"))
        self.lay.addWidget(cite)
        self.lay.addStretch(1)

    def _lang_changed(self):
        code = self.lang.value()
        if code and code != i18n.lang():
            if self.main.change_language(code) is False:
                self.lang.blockSignals(True)
                self.lang.set_value(i18n.lang())
                self.lang.blockSignals(False)

    def _copy(self, text):
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(text)
        self.copied.setText("Copiado ✓")
