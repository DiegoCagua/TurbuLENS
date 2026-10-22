# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Clase base de las páginas."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ..widgets import Card, HelpButton, label, scroll


class Page(QWidget):
    """Página con título, subtítulo opcional, botón «!» y contenido desplazable."""

    title = ""
    subtitle = ""
    help_text = ""
    scrollable = True

    def __init__(self, main):
        super().__init__()
        self.main = main
        self._edu_tips = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        body.setObjectName("transparent")
        self.lay = QVBoxLayout(body)
        self.lay.setContentsMargins(26, 20, 26, 22)
        self.lay.setSpacing(14)
        head = QHBoxLayout()
        head.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.h1 = label(self.title, "h1")
        col.addWidget(self.h1)
        self.sub = label(self.subtitle, "muted", wrap=True)
        if self.subtitle:
            col.addWidget(self.sub)
        head.addLayout(col, 1)
        if self.help_text:
            hb = HelpButton(self.help_text)
            head.addWidget(hb)
        self.head = head
        self.lay.addLayout(head)
        if self.scrollable:
            outer.addWidget(scroll(body))
        else:
            outer.addWidget(body)

    # El modo educativo muestra explicaciones adicionales.
    def edu_tip(self, text: str) -> Card:
        c = Card(kind="soft", margins=(14, 10, 14, 10))
        lb = label(text, wrap=True, rich=True)
        c.add(lb)
        c.setVisible(False)
        self._edu_tips.append(c)
        return c

    @property
    def s(self):
        return self.main.session

    @property
    def is_edu(self) -> bool:
        return self.main.mode == "educativo"

    def on_enter(self):
        for c in self._edu_tips:
            c.setVisible(self.is_edu)
        self.refresh()

    def refresh(self):
        pass

    def on_theme(self, pal: dict):
        pass
