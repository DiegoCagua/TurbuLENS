# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Autoprueba sin ventana: ``TurbuLENS --autoprueba [video] [carpeta]``.

Comprueba que el ejecutable empaquetado puede leer video (FFmpeg), procesar,
calcular el seeing, exportar todos los formatos y dibujar las gráficas.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile


def run(argv: list[str]) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from . import __version__, reports
    from .core import dimm, export, pipeline
    from .core.video import VideoReader

    app = QApplication.instance() or QApplication([])
    args = [a for a in argv if not a.startswith("--")]
    out = args[1] if len(args) > 1 else tempfile.mkdtemp(prefix="turbulens_")
    video = args[0] if args else None
    if video is None:
        import av
        import numpy as np

        video = os.path.join(out, "sintetico.mp4")
        rng = np.random.default_rng(0)
        yy, xx = np.mgrid[0:240, 0:320]
        with av.open(video, "w") as o:
            st = o.add_stream("mpeg4", rate=30)
            st.width, st.height, st.pix_fmt = 320, 240, "yuv420p"
            for i in range(150):
                d = 13 + 0.7 * rng.standard_normal()
                img = 4 + 200 * np.exp(-((xx - 150) ** 2 + (yy - 120) ** 2) / 3.4) \
                    + 170 * np.exp(-((xx - 150 - d) ** 2 + (yy - 120) ** 2) / 3.4)
                g = np.clip(img, 0, 255).astype("uint8")
                for p in st.encode(av.VideoFrame.from_ndarray(np.stack([g] * 3, -1), format="rgb24")):
                    o.mux(p)
            for p in st.encode():
                o.mux(p)
    r = VideoReader(video)
    roi = pipeline.fit_roi(r.frame_at(0))
    opts = pipeline.ProcessOptions(roi=roi, start=0, stop=r.info.n_frames - 1, out_dir=os.path.join(out, "cuadros"))
    res = pipeline.run(r, opts)
    prm = dimm.DimmParams(scale_arcsec_px=1.0)
    d = dimm.analyze(res.meas, prm)
    pipeline.write_outputs(res, d, prm)
    rec = export.summary_record(res, d, prm)
    files = export.export_analysis(rec, res.meas, d, list(export.DATA_FORMATS), os.path.join(out, "export"), "autoprueba")
    files += reports.export_analysis_charts(reports.analysis_charts(d, res.meas["t"]), ["png", "svg", "pdfg", "pdf"],
                                            os.path.join(out, "export"), "autoprueba", rec)
    summary = {"version": __version__, "video": r.info.name, "codec": r.info.codec, "frames": int(res.meas.size),
               "detected": d.n_detected, "saved_images": res.n_saved, "sigma_px": round(d.std_sep_px, 4),
               "seeing_arcsec": round(d.eps, 3), "exported_files": len(files), "out": out}
    print(json.dumps(summary, ensure_ascii=False))
    ok = d.n_detected > 0.9 * res.meas.size and len(files) >= 10
    print("AUTOPRUEBA OK" if ok else "AUTOPRUEBA FALLÓ")
    return 0 if ok else 1


def window_test(seconds: float = 3.0) -> int:
    """Abre la ventana real con la plataforma gráfica del sistema y la cierra (``--prueba-ventana``)."""
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    from .gui.app import MainWindow

    app = QApplication.instance() or QApplication([])
    w = MainWindow(data_root=tempfile.mkdtemp(prefix="turbulens_ventana_"))
    w.show()
    w.set_mode("analisis")
    w.go("resultados")
    w.set_mode("educativo")
    w.go("l5")
    ok = {"v": False}

    def done():
        ok["v"] = w.isVisible()
        print(json.dumps({"plataforma": QGuiApplication.platformName(), "ventana_visible": ok["v"]}))
        app.quit()

    QTimer.singleShot(int(seconds * 1000), done)
    app.exec()
    print("VENTANA OK" if ok["v"] else "VENTANA FALLÓ")
    return 0 if ok["v"] else 1
