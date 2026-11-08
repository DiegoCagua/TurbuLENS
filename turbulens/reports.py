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


def correlation_explanation(rec: dict) -> tuple[str, str]:
    """Título y texto de la sección «Cómo leer la correlación r» del informe, con los valores del análisis."""
    def f(key, d=2):
        v = rec.get(key)
        return num(v, d) if isinstance(v, (int, float)) and math.isfinite(v) else "—"

    r_lt = rec.get("corr_lt")
    ratio, exp = rec.get("sigma_ratio"), rec.get("sigma_ratio_expected")
    issues = []
    if isinstance(r_lt, (int, float)) and math.isfinite(r_lt) and abs(r_lt) >= 0.2:
        issues.append(tr("|r| longitudinal–transversal alto ({})").format(f("corr_lt")))
    if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (ratio, exp)) and exp > 0 and abs(ratio / exp - 1) > 0.25:
        issues.append(tr("σt/σl lejos del valor teórico ({} frente a {})").format(f("sigma_ratio"), f("sigma_ratio_expected")))
    verdict = (tr("los datos son coherentes con turbulencia atmosférica.") if not issues else
               tr("revisa el tramo: ") + "; ".join(issues) + ".")
    B, D = rec.get("B_cm"), rec.get("D_cm")
    bd = num(B / D, 2) if B and D else "—"
    text = "\n\n".join([
        tr("Qué es r. En cada cuadro el DIMM mide el vector que une los dos spots, y su movimiento se separa en una "
           "componente longitudinal (a lo largo de la línea que une los orificios) y una transversal (perpendicular). "
           "El coeficiente de correlación de Pearson, r = Σ(xᵢ − x̄)(yᵢ − ȳ) / √[Σ(xᵢ − x̄)² · Σ(yᵢ − ȳ)²], va de −1 a 1 y "
           "dice si dos movimientos tienden a variar juntos (r > 0), en sentidos opuestos (r < 0) o sin relación (r ≈ 0)."),
        tr("r longitudinal–transversal = {}. La turbulencia mueve las dos componentes de forma independiente, así que lo "
           "esperado es un valor cercano a 0 (|r| < 0,2). Un |r| grande, positivo o negativo, delata un efecto que no es "
           "turbulencia: vibración o viento en una sola dirección, cambios de foco, una línea de base mal estimada o spots "
           "confundidos. El signo solo depende de cómo quedaron orientados los ejes; lo que importa es su tamaño.").format(f("corr_lt")),
        tr("r entre los dos spots = {} (longitudinal) y {} (transversal), tras quitar la deriva lenta. Mide cuánto se mueven "
           "juntas las dos imágenes. Cerca de 1: domina el movimiento común (vibración del telescopio o seguimiento); el DIMM "
           "lo cancela al medir la diferencia, así que el seeing sigue siendo válido, pero si es muy grande puede emborronar los "
           "spots. Entre 0 y 1: lo normal, porque los dos orificios ven parte de la misma turbulencia. Cerca de 0: cada orificio "
           "ve turbulencia independiente. Negativo: los spots se acercan y se alejan de forma opuesta (cambios de foco o de "
           "escala) o hubo errores de detección.").format(f("corr_spots_l"), f("corr_spots_t")),
        tr("Comprobación adicional: el cociente σt/σl medido es {} y el teórico para esta máscara (B/D = {}) es √(Kt/Kl) = {}. "
           "Si se parecen, la turbulencia se comporta como predice el modelo de Tokovinin.").format(
            f("sigma_ratio"), bd, f("sigma_ratio_expected")),
        tr("Diagnóstico: ") + verdict,
    ])
    return tr("Cómo leer la correlación r"), text


def write_report_pdf(path: str, title: str, rows: list[tuple[str, str]], specs: list[ChartSpec], notes: str = "",
                     sections: list[tuple[str, str]] | None = None) -> None:
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
        r = p.boundingRect(QRectF(0, y, W, 2000), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, notes)
        p.drawText(QRectF(0, y, W, r.height() + 4), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, notes)
        y += r.height() + 8
    bottom = page.height() - 60
    for head, body in sections or []:
        fb = QFont(f)
        fb.setPointSizeF(12)
        fb.setBold(True)
        fn = QFont(f)
        fn.setPointSizeF(9)
        p.setFont(fn)
        rb = p.boundingRect(QRectF(0, 0, W, 5000), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, body)
        if y + 50 + rb.height() > bottom:  # no cabe: a una página nueva
            w.newPage()
            _footer(p, w)
            y = 0
        y += 18
        p.setFont(fb)
        p.setPen(QColor(PRINT_PALETTE["text"]))
        p.drawText(QRectF(0, y, W, 36), Qt.AlignLeft | Qt.AlignVCenter, head)
        y += 40
        p.setFont(fn)
        p.drawText(QRectF(0, y, W, rb.height() + 6), Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop, body)
        y += rb.height() + 8
        p.setFont(f)
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
        write_report_pdf(pth, tr("Informe de seeing"), summary_rows(rec), specs, notes, sections=[correlation_explanation(rec)])
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
