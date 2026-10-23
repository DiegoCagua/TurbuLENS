# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Gráficas e informes de un análisis o del historial (PNG, SVG, PDF)."""

from __future__ import annotations

import math
import os
from typing import Iterable

import numpy as np
from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter

from . import APP_NAME, INSTITUTION, __version__, citation_apa
from .charts import PRINT_PALETTE, ChartSpec, Series, draw_chart, histogram_spec, render_png, render_svg
from .core import stats
from .core.dimm import DimmResult, quality_label
from .core.export import SUMMARY_LABELS
from .i18n import num, tr


def analysis_charts(dimm: DimmResult, t: np.ndarray, fps: float = 30.0) -> list[ChartSpec]:
    a = dimm.arrays
    used = a["used"]
    sep = a["sep"][used]
    specs = [histogram_spec(sep, title="Histograma de la separación entre los dos spots",
                            xlabel="Separación (px)", ylabel="Cuadros", normal=True)]
    tt = np.asarray(t, dtype=float)
    sep_all = np.where(used, a["sep"], np.nan)
    ok = np.isfinite(sep_all)
    if ok.sum() > 4:
        mids, sd, _ = stats.running_std(tt[ok], sep_all[ok], 1.0)
        specs.append(ChartSpec(title="Dispersión (σ) de la separación, segundo a segundo",
                               xlabel="Tiempo del video (s)", ylabel="σ (px)",
                               series=[Series("line", x=mids, y=sd, color="accent", width=2, label="σ por segundo"),
                                       Series("hline", y=[float(np.nanmedian(sd))], color="muted", dash=True, width=1.5,
                                              label="Mediana")],
                               ymin_zero=True))
    lon = a["lon"][used] - np.nanmean(a["lon"][used])
    tra = a["tra"][used] - np.nanmean(a["tra"][used])
    step = max(1, lon.size // 3000)
    lim = float(np.nanmax(np.abs(np.concatenate([lon, tra])))) * 1.05 if lon.size else 1.0
    specs.append(ChartSpec(title="Movimiento diferencial: longitudinal vs. transversal",
                           xlabel="Δ longitudinal (px)", ylabel="Δ transversal (px)",
                           series=[Series("scatter", x=lon[::step], y=tra[::step], color="accent", alpha=0.35, size=1.8)],
                           xlim=(-lim, lim), ylim=(-lim, lim), legend=False,
                           note=tr("Correlación r = {}").format(num(dimm.corr_lt, 2))))
    return specs


def history_charts(records: list[dict]) -> list[ChartSpec]:
    recs = list(reversed(records))
    labels = [r.get("label") or f"#{r['id']}" for r in recs]
    seeing = [r.get("eps") if r.get("eps") is not None else float("nan") for r in recs]
    sig = [r.get("std_sep_px") if r.get("std_sep_px") is not None else float("nan") for r in recs]
    specs = []
    if any(math.isfinite(v) for v in seeing):
        cols = []
        for v in seeing:
            cols.append("good" if math.isfinite(v) and v <= 1.5 else ("warn" if math.isfinite(v) and v <= 3 else "bad"))
        specs.append(ChartSpec(title="Seeing por análisis", ylabel="Seeing (″)", categorical=True, legend=False,
                               series=[Series("hbars", y=seeing, labels=labels, colors=cols, values_on_top=True)],
                               ymin_zero=True))
    specs.append(ChartSpec(title="Desviación estándar de la separación por análisis", ylabel="σ (px)", categorical=True,
                           legend=False, series=[Series("hbars", y=sig, labels=labels, values_on_top=True)], ymin_zero=True))
    return specs


def _pdf(path: str) -> QPdfWriter:
    w = QPdfWriter(path)
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageOrientation(QPageLayout.Portrait)
    w.setPageMargins(QMarginsF(14, 14, 14, 14), QPageLayout.Millimeter)
    w.setResolution(150)
    w.setTitle(APP_NAME)
    w.setCreator(f"{APP_NAME} {__version__}")
    return w


def _footer(p: QPainter, writer: QPdfWriter) -> None:
    page = writer.pageLayout().paintRectPixels(writer.resolution())
    f = QFont()
    f.setPointSizeF(7.5)
    p.save()
    p.setFont(f)
    p.setPen(QColor(PRINT_PALETTE["muted"]))
    p.drawText(QRectF(0, page.height() - 46, page.width(), 44), Qt.AlignLeft | Qt.AlignBottom | Qt.TextWordWrap,
               tr("Generado con TurbuLENS · ") + citation_apa())
    p.restore()


def _charts_pages(p: QPainter, writer: QPdfWriter, specs: list[ChartSpec], first_new_page: bool) -> None:
    page = writer.pageLayout().paintRectPixels(writer.resolution())
    W, H = page.width(), page.height() - 50
    per = 2
    for i, spec in enumerate(specs):
        if i % per == 0 and (i > 0 or first_new_page):
            writer.newPage()
            _footer(p, writer)
        elif i == 0:
            _footer(p, writer)
        slot = i % per
        r = QRectF(0, slot * H / per + 10, W, H / per - 30)
        draw_chart(p, r, spec, PRINT_PALETTE, scale=W / 1000)


def write_charts_pdf(path: str, specs: list[ChartSpec]) -> None:
    w = _pdf(path)
    p = QPainter(w)
    _charts_pages(p, w, specs, first_new_page=False)
    p.end()


def write_report_pdf(path: str, title: str, rows: list[tuple[str, str]], specs: list[ChartSpec], notes: str = "") -> None:
    w = _pdf(path)
    p = QPainter(w)
    page = w.pageLayout().paintRectPixels(w.resolution())
    W = page.width()
    f = QFont()
    f.setPointSizeF(18)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(PRINT_PALETTE["text"]))
    p.drawText(QRectF(0, 0, W, 60), Qt.AlignLeft | Qt.AlignVCenter, title)
    f.setPointSizeF(10)
    f.setBold(False)
    p.setFont(f)
    p.setPen(QColor(PRINT_PALETTE["muted"]))
    p.drawText(QRectF(0, 60, W, 30), Qt.AlignLeft | Qt.AlignVCenter, f"{APP_NAME} {__version__} · {INSTITUTION}")
    _footer(p, w)
    y = 110
    rh = 34
    for i, (k, v) in enumerate(rows):
        if i % 2 == 0:
            p.fillRect(QRectF(0, y, W, rh), QColor("#F2F5F4"))
        p.setPen(QColor(PRINT_PALETTE["muted"]))
        p.drawText(QRectF(12, y, W * 0.55, rh), Qt.AlignLeft | Qt.AlignVCenter, str(k))
        p.setPen(QColor(PRINT_PALETTE["text"]))
        p.drawText(QRectF(W * 0.55, y, W * 0.45 - 12, rh), Qt.AlignRight | Qt.AlignVCenter, str(v))
        y += rh
    if notes:
        y += 16
        p.setPen(QColor(PRINT_PALETTE["muted"]))
        p.drawText(QRectF(0, y, W, 200), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, notes)
    _charts_pages(p, w, specs, first_new_page=True)
    p.end()


def _fmt_val(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "—"
        return num(v, 3)
    return str(v)


def summary_rows(rec: dict) -> list[tuple[str, str]]:
    rows = []
    for key, label in SUMMARY_LABELS:
        if key in rec:
            rows.append((label, _fmt_val(rec[key])))
    return rows


def export_analysis_charts(specs: list[ChartSpec], formats: Iterable[str], folder: str, base: str,
                           rec: dict | None = None) -> list[str]:
    os.makedirs(folder, exist_ok=True)
    formats = set(formats)
    out = []
    names = ["histograma", "sigma_tiempo", "movimiento_diferencial", "grafica4", "grafica5"]
    if "png" in formats:
        for s, n in zip(specs, names):
            pth = os.path.join(folder, f"{base}_{n}.png")
            render_png(s, pth)
            out.append(pth)
    if "svg" in formats:
        for s, n in zip(specs, names):
            pth = os.path.join(folder, f"{base}_{n}.svg")
            render_svg(s, pth)
            out.append(pth)
    if "pdfg" in formats:
        pth = os.path.join(folder, f"{base}_graficas.pdf")
        write_charts_pdf(pth, specs)
        out.append(pth)
    if "pdf" in formats and rec is not None:
        pth = os.path.join(folder, f"{base}_informe.pdf")
        q = rec.get("calidad") or quality_label(rec.get("eps") or float("nan"))
        notes = tr("Seeing calculado con el modelo de Tokovinin (2002) a partir de la varianza del movimiento diferencial. "
                   "Calidad del cielo: {}.").format(tr(q))
        write_report_pdf(pth, tr("Informe de seeing"), summary_rows(rec), specs, notes)
        out.append(pth)
    return out


def export_history_charts(records: list[dict], formats: Iterable[str], folder: str, base: str = "historial") -> list[str]:
    specs = history_charts(records)
    os.makedirs(folder, exist_ok=True)
    formats = set(formats)
    out = []
    names = ["seeing", "sigma"] if len(specs) == 2 else ["sigma"]
    if "png" in formats:
        for s, n in zip(specs, names):
            pth = os.path.join(folder, f"{base}_{n}.png")
            render_png(s, pth)
            out.append(pth)
    if "svg" in formats:
        for s, n in zip(specs, names):
            pth = os.path.join(folder, f"{base}_{n}.svg")
            render_svg(s, pth)
            out.append(pth)
    if "pdfg" in formats:
        pth = os.path.join(folder, f"{base}_graficas.pdf")
        write_charts_pdf(pth, specs)
        out.append(pth)
    if "pdf" in formats:
        pth = os.path.join(folder, f"{base}_informe.pdf")
        rows = [(f"#{r['id']} · {r.get('label') or r.get('video_name') or ''}"[:60],
                 f"seeing {_fmt_val(r.get('eps'))}″ · σ {_fmt_val(r.get('std_sep_px'))} px") for r in records]
        write_report_pdf(pth, tr("Historial de seeing"), rows, specs)
        out.append(pth)
    return out
