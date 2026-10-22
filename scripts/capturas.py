# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Recorre la interfaz y guarda capturas de cada pantalla (prueba de humo).

Uso:  python scripts/capturas.py [video] [carpeta_salida]
Sin video, genera uno sintético.
"""
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from PySide6.QtCore import QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from turbulens.gui.app import MainWindow  # noqa: E402
from turbulens.gui.theme import theme  # noqa: E402


def pump(ms=150):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main():
    video = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "capturas")
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp()
    if video is None:
        from synthetic import make_video

        video = os.path.join(tmp, "sintetico.mkv")
        make_video(video, n=900, w=960, h=540)
    app = QApplication.instance() or QApplication([])
    w = MainWindow(data_root=os.path.join(tmp, "datos"))
    w.resize(1440, 900)
    w.show()
    pump(300)

    def shot(name):
        pump(200)
        w.grab().save(os.path.join(out, name + ".png"))
        print("captura", name, flush=True)

    for dark in (True, False):
        theme.set_dark(dark)
        tag = "oscuro" if dark else "claro"
        w.root.setCurrentIndex(0)
        shot(f"00_inicio_{tag}")
        for mode in ("analisis", "educativo"):
            w.set_mode(mode)
            s = w.session
            if s.info is None:
                w.page_by_key["video"].open(video)
            s.out_dir = os.path.join(tmp, f"salida_{mode}")
            s.params.scale_arcsec_px = 1.0
            if mode == "educativo":
                shot(f"10_edu_bienvenida_{tag}")
            for key in ("video", "region", "parametros"):
                w.go(key)
                shot(f"{'20' if mode == 'educativo' else '01'}_{mode}_{key}_{tag}")
            if s.result is None:
                w.go("procesar")
                pg = w.page_by_key["procesar"]
                pg.start()
                t0 = time.time()
                while pg.thread is not None and time.time() - t0 < 600:
                    pump(200)
                shot(f"{'20' if mode == 'educativo' else '01'}_{mode}_procesar_{tag}")
            w.go("resultados")
            shot(f"{'20' if mode == 'educativo' else '01'}_{mode}_resultados_{tag}")
            if not w.session.history.list():
                w.page_by_key["resultados"].save()
            w.go("historial")
            shot(f"{'20' if mode == 'educativo' else '01'}_{mode}_historial_{tag}")
            if mode == "educativo":
                for key in ["l%d" % i for i in range(1, 10)] + ["quiz", "titilan", "dimm", "simulador"]:
                    w.go(key)
                    if key == "simulador":
                        pump(1500)
                    shot(f"11_edu_{key}_{tag}")
        w.go("acerca")
        shot(f"30_acerca_{tag}")

    # Exportaciones (sin diálogos)
    from turbulens import reports
    from turbulens.core.export import export_analysis, export_history_table

    s = w.sessions["analisis"]
    rec = s.record()
    exp = os.path.join(out, "_exportacion")
    files = export_analysis(rec, s.result.meas, s.dimm, ["csv", "xlsx", "json", "npz", "fits"], exp, "prueba")
    files += reports.export_analysis_charts(w.page_by_key["resultados"].specs, ["png", "svg", "pdfg", "pdf"], exp, "prueba", rec)
    hist = s.history.list()
    files += export_history_table(hist, ["csv", "xlsx"], exp, "historial")
    files += reports.export_history_charts(hist, ["pdfg", "png", "pdf"], exp, "historial")
    print("exportados", len(files), flush=True)
    w.close()


if __name__ == "__main__":
    main()
