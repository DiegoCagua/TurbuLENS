# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Temas claro y oscuro.

Oscuro: grises carbón con acento naranja (borrador 09 «Línea de tiempo»).
Claro: el verde azulado del borrador 04 «Tablero», menos saturado.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

DARK = {
    "name": "dark",
    "bg": "#1C1D21", "panel": "#232429", "panel2": "#2D2F35", "border": "#34363D", "border2": "#4A4C55",
    "text": "#ECEDEF", "muted": "#A5A8B1", "accent": "#F28C28", "accentHover": "#F5A04F", "onAccent": "#1C1D21",
    "accentSoft": "rgba(242,140,40,0.16)", "accentSoftHex": "#3A2E22",
    "accent2": "#6FA8FF", "good": "#5DBB8A", "warn": "#E8B54A", "bad": "#E57A62", "track": "#5A5D66",
    "preview": "#000000", "grid": "#34363D",
}

LIGHT = {
    "name": "light",
    "bg": "#F1F3F2", "panel": "#FFFFFF", "panel2": "#F5F7F6", "border": "#DDE2DF", "border2": "#C2CBC7",
    "text": "#1D2622", "muted": "#55615B", "accent": "#3E7C72", "accentHover": "#356B62", "onAccent": "#FFFFFF",
    "accentSoft": "rgba(62,124,114,0.12)", "accentSoftHex": "#E3EEEC",
    "accent2": "#B4652A", "good": "#2E7D5B", "warn": "#9A6B12", "bad": "#B0452C", "track": "#B9C4BF",
    "preview": "#0C0F0E", "grid": "#E4E8E6",
}


class ThemeManager(QObject):
    changed = Signal(dict)

    def __init__(self):
        super().__init__()
        self.pal = DARK

    @property
    def dark(self) -> bool:
        return self.pal["name"] == "dark"

    def set_dark(self, dark: bool) -> None:
        self.pal = DARK if dark else LIGHT
        self.changed.emit(self.pal)

    def toggle(self) -> None:
        self.set_dark(not self.dark)


theme = ThemeManager()


def qss(p: dict) -> str:
    return f"""
* {{ outline: none; }}
QWidget {{ background: {p['bg']}; color: {p['text']}; font-size: 14px; }}
QWidget#transparent, QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QToolTip {{ background: {p['panel']}; color: {p['text']}; border: 1px solid {p['border2']}; padding: 6px; }}
QFrame[card="true"] {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 14px; }}
QFrame[card="soft"] {{ background: {p['accentSoftHex']}; border: none; border-radius: 12px; }}
QFrame[card="panel2"] {{ background: {p['panel2']}; border: none; border-radius: 10px; }}
QFrame#header, QFrame#sidebar {{ background: {p['panel']}; border: none; }}
QFrame#header {{ border-bottom: 1px solid {p['border']}; }}
QFrame#sidebar {{ border-right: 1px solid {p['border']}; }}
QLabel[role="h1"] {{ font-size: 24px; font-weight: 600; }}
QLabel[role="h2"] {{ font-size: 16px; font-weight: 600; }}
QLabel[role="title"] {{ font-size: 18px; font-weight: 700; }}
QLabel[role="hero"] {{ font-size: 46px; font-weight: 300; }}
QLabel[role="muted"] {{ color: {p['muted']}; }}
QLabel[role="small"] {{ color: {p['muted']}; font-size: 12px; }}
QLabel[role="section"] {{ color: {p['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 2px; padding: 10px 8px 4px 8px; }}
QLabel[role="kpi"] {{ font-size: 26px; font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace; }}
QLabel[role="kpiAccent"] {{ font-size: 30px; color: {p['accent']}; font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace; }}
QLabel[role="mono"] {{ font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace; }}
QLabel[role="chip"] {{ background: {p['accentSoftHex']}; color: {p['accent']}; border-radius: 13px; padding: 5px 12px; font-weight: 600; font-size: 13px; }}
QLabel a {{ color: {p['accent']}; }}

QPushButton {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['border2']}; border-radius: 9px; padding: 8px 14px; min-height: 22px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:disabled {{ color: {p['muted']}; border-color: {p['border']}; }}
QPushButton[kind="primary"] {{ background: {p['accent']}; color: {p['onAccent']}; border: none; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {p['accentHover']}; }}
QPushButton[kind="primary"]:disabled {{ background: {p['border2']}; color: {p['muted']}; }}
QPushButton[kind="chip"] {{ border-radius: 15px; padding: 5px 12px; font-size: 13px; }}
QPushButton[kind="chip"]:checked {{ background: {p['accent']}; color: {p['onAccent']}; border-color: {p['accent']}; }}
QPushButton[kind="nav"] {{ text-align: left; background: transparent; border: 1px solid transparent; padding: 8px 10px; border-radius: 9px; }}
QPushButton[kind="nav"]:hover {{ background: {p['panel2']}; }}
QPushButton[kind="nav"]:checked {{ background: {p['accentSoftHex']}; border-color: {p['accent']}; font-weight: 600; }}
QPushButton[kind="big"] {{ text-align: left; background: {p['panel']}; border: 1px solid {p['border2']}; border-radius: 22px; padding: 26px; }}
QPushButton[kind="big"]:hover {{ border-color: {p['accent']}; }}
QPushButton[kind="drop"] {{ background: {p['panel']}; border: 2px dashed {p['border2']}; border-radius: 22px; font-size: 18px; }}
QPushButton[kind="drop"]:hover {{ border-color: {p['accent']}; }}
QPushButton[kind="transport"] {{ font-family: "Consolas", "Menlo", "DejaVu Sans Mono", monospace; font-weight: 600; padding: 4px 8px; min-width: 30px; }}
QPushButton[kind="transport"]:checked {{ background: {p['accent']}; color: {p['onAccent']}; border-color: {p['accent']}; }}
QPushButton[kind="option"] {{ text-align: left; padding: 10px 14px; }}
QPushButton[kind="option"][state="ok"] {{ border: 2px solid {p['good']}; }}
QPushButton[kind="option"][state="bad"] {{ border: 2px solid {p['bad']}; }}
QToolButton {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['border2']}; border-radius: 9px; padding: 6px; }}
QToolButton:hover {{ border-color: {p['accent']}; }}
QToolButton[kind="help"] {{ background: {p['accentSoftHex']}; color: {p['accent']}; border: 1px solid {p['accent']}; border-radius: 11px; font-weight: 800; padding: 0px; min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; }}
QToolButton[kind="theme"] {{ border-radius: 20px; min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px; padding: 0; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
  background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['border2']}; border-radius: 8px; padding: 6px 8px;
  selection-background-color: {p['accent']}; selection-color: {p['onAccent']}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {p['accent']}; }}
QLineEdit[invalid="true"] {{ border-color: {p['bad']}; }}
QComboBox QAbstractItemView {{ background: {p['panel']}; color: {p['text']}; selection-background-color: {p['accent']}; selection-color: {p['onAccent']}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {p['border2']}; background: {p['panel2']}; }}
QCheckBox::indicator:checked {{ background: {p['accent']}; border-color: {p['accent']}; }}
QSlider::groove:horizontal {{ height: 6px; background: {p['border']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {p['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {p['accent']}; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }}
QProgressBar {{ background: {p['panel2']}; border: none; border-radius: 6px; height: 12px; text-align: center; color: {p['text']}; }}
QProgressBar::chunk {{ background: {p['accent']}; border-radius: 6px; }}
QTableWidget {{ background: {p['panel']}; alternate-background-color: {p['panel2']}; gridline-color: {p['border']}; border: 1px solid {p['border']}; border-radius: 10px; }}
QHeaderView::section {{ background: {p['panel2']}; color: {p['text']}; border: none; border-bottom: 1px solid {p['border']}; padding: 6px 8px; font-weight: 600; }}
QTableWidget::item:selected {{ background: {p['accentSoftHex']}; color: {p['text']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p['border2']}; border-radius: 4px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p['border2']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QFrame#popup {{ background: {p['panel']}; border: 1px solid {p['accent']}; border-radius: 12px; }}
QMessageBox {{ background: {p['panel']}; }}
"""
