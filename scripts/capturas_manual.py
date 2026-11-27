# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Capturas del manual (tema claro, ventana de 1440 × 900) en docs/manual/img/.

Uso:  python scripts/capturas_manual.py

Usa un video sintético, una imagen de estrellas sintética y una noche de GOES armada en memoria (sin internet), así
que las capturas se pueden repetir en cualquier computador.
"""
import datetime as dt
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import numpy as np  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

OUT = os.path.join(ROOT, "docs", "manual", "img")


def pump(app, n=25):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.01)


def fake_night():
    """Una noche de GOES-19 (18:00–23:00, cada hora) con los canales 9, 13 y 16, sin descargar nada."""
    import test_modes

    from turbulens.core import goes
    from turbulens.core import satseeing as ss

    rng = np.random.default_rng(4)
    tz = dt.timezone(dt.timedelta(hours=-5))
    out = []
    base = {9: 1250, 13: 1780, 16: 1380}  # en cuentas: 0,05 K por cuenta + 180 K
    wobble = [0, 14, -9, 11, -6, 4]
    for k in range(6):
        local = dt.datetime(2026, 10, 19, 18 + k, 0, tzinfo=tz)
        utc = local.astimezone(dt.timezone.utc)
        it = ss.SatInstant(local=local, utc=utc)
        for ch, b in base.items():
            f = test_modes._FakeGoesFile()
            n = f["CMI"].shape[0]
            yy, xx = np.mgrid[0:n, 0:n]
            clouds = 160 * np.exp(-((xx - 260 - 6 * k) ** 2 + (yy - 250) ** 2) / 900.0)
            raw = (b + (wobble[k] if ch == 9 else 0) + 40 * np.sin(xx / 30) * np.cos(yy / 24)
                   - (clouds if ch != 9 else 0) + rng.normal(0, 3, (n, n))).astype(np.int16)
            f["CMI"].data = raw
            f["band_id"].data = np.array([ch], np.int8)
            stamp = utc.strftime("%Y%j%H%M%S")
            f.filename = f"OR_ABI-L2-CMIPF-M6C{ch:02d}_G19_s{stamp}0_e{stamp}0_c{stamp}0.nc"
            it.readings[ch] = goes.read_point(f, goes.OAN_LAT, goes.OAN_LON, 300, box_km=111)
        out.append(it)
    return out


def star_field(path):
    from turbulens.core.imageio import write_fits

    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:600, 0:800]
    img = 1000 + rng.normal(0, 12, yy.shape) + 250 * (1 - ((xx - 400) ** 2 + (yy - 300) ** 2) / 500 ** 2)
    for _ in range(45):
        x, y, a = rng.uniform(20, 780), rng.uniform(20, 580), rng.uniform(300, 20000)
        img += a * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * 2.3 ** 2))
    img += 26000 * np.exp(-((xx - 420) ** 2 + (yy - 310) ** 2) / (2 * 2.6 ** 2))
    write_fits(path, img.astype(np.float32), {"OBJECT": "Campo de prueba", "EXPTIME": 30.0})


def main():
    QSettings.setDefaultFormat(QSettings.IniFormat)
    # Con TURBULENS_CAPTURAS_DIR las rutas que salen en las capturas son legibles (p. ej. /home/observador/Observaciones).
    tmp = os.environ.get("TURBULENS_CAPTURAS_DIR") or tempfile.mkdtemp()
    if os.path.isdir(tmp) and os.listdir(tmp):
        import shutil

        shutil.rmtree(tmp)
    os.makedirs(tmp, exist_ok=True)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, tmp)
    from turbulens import i18n
    from turbulens.gui import i18n_qt

    i18n_qt.install()
    i18n.load("es")
    app = QApplication.instance() or QApplication([])
    i18n_qt.load_qt_translations(app)
    from PySide6.QtGui import QFont

    f = QFont()
    f.setFamilies(["Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(14)
    app.setFont(f)
    from turbulens.gui import widgets
    from turbulens.gui.app import MainWindow
    from turbulens.gui.theme import theme

    widgets.ask_save = lambda *a, **k: "descartar"
    os.makedirs(OUT, exist_ok=True)
    w = MainWindow(data_root=os.path.join(tmp, "datos"))
    theme.set_dark(False)
    w.resize(1440, 900)
    w.show()
    pump(app, 40)

    def shot(name, widget=None):
        pump(app)
        (widget or w).grab().save(os.path.join(OUT, name + ".png"))
        print("captura", name, flush=True)

    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QAbstractButton

    def find(ref, text):
        for b in ref.findChildren(QAbstractButton):
            if b.isVisible() and b.text().strip().startswith(text):
                return b
        return None

    def marks(name, ref, items):
        """Guarda las marcas numeradas de una captura en img/<name>_marcas.tex (coordenadas relativas)."""
        pump(app)
        W, H = ref.width(), ref.height()
        out = []
        for num, wid, *where in items:
            if isinstance(wid, str):
                wid = find(ref, wid)
            if wid is None or not wid.isVisible():
                print("  sin marca", name, num, flush=True)
                continue
            p = wid.mapTo(ref, QPoint(0, 0))
            w_, h_ = wid.width(), wid.height()
            pos = where[0] if where else "tl"
            x, y = {"tl": (p.x() + 4, p.y() + 4), "l": (p.x() - 12, p.y() + h_ / 2),
                    "r": (p.x() + w_ + 12, p.y() + h_ / 2), "t": (p.x() + w_ / 2, p.y() - 10),
                    "c": (p.x() + w_ / 2, p.y() + h_ / 2), "tr": (p.x() + w_ - 4, p.y() + 4),
                    "in": (p.x() + 40, p.y() + 40)}[pos]
            if not (0 <= x <= W and 0 <= y <= H):
                print("  fuera", name, num, flush=True)
                continue
            out.append(f"\\marca{{{x / W:.4f}}}{{{1 - y / H:.4f}}}{{{num}}}")
        with open(os.path.join(OUT, name + "_marcas.tex"), "w", encoding="utf-8") as fh:
            fh.write("% Generado por scripts/capturas_manual.py\n" + "\n".join(out) + "\n")

    def scroll_to(page, frac):
        sa = page.findChild(QScrollArea)
        if sa is not None:
            bar = sa.verticalScrollBar()
            bar.setValue(int(bar.maximum() * frac))
        pump(app)

    from synthetic import make_video

    shot("inicio")
    video = os.path.join(tmp, "altair_dimm.mkv")
    make_video(video, n=600, w=960, h=540)
    w.set_mode("analisis")
    shot("video_vacio")
    vp = w.page_by_key["video"]
    vp.open(video)
    s = w.session
    s.out_dir = os.path.join(tmp, "altair_dimm_TurbuLENS")
    shot("video")
    marks("video", w, [(1, vp.preview, "in"), (2, vp.info_card), (3, "Cambiar video"), (4, "Siguiente")])
    w.go("region")
    rg = w.page_by_key["region"]
    shot("region")
    marks("region", w, [(1, rg.canvas, "in"), (2, "◎ Ajustar"), (3, rg.track), (4, rg.auto_size), (5, rg.zoom_chips),
                        (6, rg.zoomview), (7, rg.timeline), (8, "[ Entrada"), (9, rg.speed)])
    w.go("parametros")
    pp = w.page_by_key["parametros"]
    shot("parametros_vacio")
    w.go("procesar")
    shot("procesar_sin_escala")
    # Equipos: los del OAN y uno propio
    from turbulens.core import devices as dv
    from turbulens.gui import oan

    oan.save_custom([dv.Telescope("u:1", "Refractor 80 mm f/6", 80, 480, "Telescopio propio.")],
                    [dv.Camera("u:1", "ZWO ASI120MM", 4.8, 3.6, 1280, 960, False, (), "Cámara propia.")],
                    [dv.Mask("u:1", "Máscara del club · 2 / 7 cm", 2.0, 7.0, "Máscara propia.")])
    dlg = oan.OanDevicesDialog(w, 960, "8se,d5600,grupo8,1")
    dlg.show()
    pump(app)
    dlg.adjustSize()
    shot("oan", dlg)
    dlg.rows["tel"]["chips"].set_value("u:1")
    dlg.rows["cam"]["chips"].set_value("u:1")
    dlg.rows["mask"]["chips"].set_value("u:1")
    dlg._update()
    shot("oan_propio", dlg)
    marks("oan_propio", dlg, [(1, dlg.rows["tel"]["chips"]), (2, dlg.rows["tel"]["add"]), (3, dlg.rows["tel"]["del"]),
                              (4, dlg.as_video), (5, dlg.res_lbl), (6, dlg.ok_b)])
    dlg.close()
    cd = oan.CustomDeviceDialog(w, "cam")
    cd.name.setText("ZWO ASI120MM")
    cd.sw.setValue(4.8)
    cd.wpx.setValue(1280)
    cd.video.setChecked(False)
    cd.show()
    pump(app)
    cd.adjustSize()
    shot("dispositivo_propio", cd)
    marks("dispositivo_propio", cd, [(1, cd.name, "tl"), (2, cd.sw, "tl"), (3, cd.wpx, "tl"), (4, cd.video, "tl"),
                                     (5, cd.vw, "tl")])
    cd.close()
    # Escala y máscara del grupo (8SE + Nikon D5600 en video)
    pp.D.setValue(4.2)
    pp.B.setValue(14.4)
    pp.scale.setText("1,242")
    w.go("parametros")
    shot("parametros")
    marks("parametros", w, [(1, pp.oan_b), (2, pp.D, "l"), (3, pp.lam, "l"), (4, pp.calc_b), (5, pp.alt_on),
                            (6, pp.prof), (7, pp.save_on), (8, pp.fmt), (9, pp.out), (10, pp.cal_on)])
    pp.calc_b.setChecked(True)
    shot("parametros_calculadora")
    pp.calc_b.setChecked(False)
    w.go("procesar")
    pg = w.page_by_key["procesar"]
    shot("procesar")
    pg.start()
    t0 = time.time()
    while pg.thread is not None and time.time() - t0 < 300:
        pump(app, 5)
    w.go("resultados")
    rp = w.page_by_key["resultados"]
    rp.labelEdit.setText("Altair, noche 1")
    shot("resultados")
    marks("resultados", w, [(1, rp.k_eps), (2, rp.k_l), (3, rp.k_r0), (4, rp.k_n), (5, rp.player, "in"),
                            (6, rp.c_hist, "in"), (7, rp.labelEdit, "l"), (8, rp.save_b)])
    from PySide6.QtCore import QPointF

    ch = rp.c_hist
    ch._hover = ch._nearest(QPointF(ch.width() * 0.33, ch.height() * 0.62))
    ch.update()
    shot("grafica_cursor", ch)
    ch._hover = None
    scroll_to(rp, 1.0)
    shot("resultados_abajo")
    marks("resultados_abajo", w, [(1, rp.c_t, "in"), (2, rp.c_sc, "in"), (3, rp.corr_lbl)])
    rp.exp.set_folder(os.path.join(tmp, "altair_dimm_TurbuLENS"))
    find(rp.exp, "Generar").click()
    pump(app, 40)
    shot("exportar", rp.exp)
    marks("exportar", rp.exp, [(1, rp.exp.chips["Datos"], "l"), (2, rp.exp.chips["Gráficas"], "l"),
                               (3, rp.exp.chips["Informe"], "l"), (4, "Cambiar carpeta"), (5, "Generar"),
                               (6, "Ver archivos")])
    rp.save()
    w.go("historial")
    shot("historial")
    w.go("acerca")
    shot("acerca")
    # Video sin la estrella: gráficas vacías
    empty = os.path.join(tmp, "sin_estrella.mkv")
    import av

    c = av.open(empty, "w")
    st = c.add_stream("ffv1", rate=30)
    st.width, st.height, st.pix_fmt = 320, 240, "gray"
    rng = np.random.default_rng(1)
    for _ in range(60):
        fr = av.VideoFrame.from_ndarray(np.clip(10 + 3 * rng.standard_normal((240, 320)), 0, 255).astype(np.uint8),
                                        format="gray")
        for p in st.encode(fr):
            c.mux(p)
    for p in st.encode():
        c.mux(p)
    c.close()
    w.set_mode("educativo")
    w.page_by_key["video"].open(empty)
    w.session.params.scale_arcsec_px = 1.0
    w.go("procesar")
    pg = w.page_by_key["procesar"]
    pg.start()
    t0 = time.time()
    while pg.thread is not None and time.time() - t0 < 120:
        pump(app, 5)
    w.go("resultados")
    shot("resultados_sin_datos")
    # Educativo
    for key, name in (("bienvenida", "edu_bienvenida"), ("titilan", "edu_titilan"), ("dimm", "edu_dimm"),
                      ("l3", "edu_l3"), ("l5", "edu_l5")):
        w.go(key)
        pump(app, 60)
        shot(name)
    w.go("l8")
    lp = w.page_by_key["l8"]
    scroll_to(lp, 1.0)
    shot("edu_correlacion", lp.dimm_lbl.parentWidget())
    # Imágenes
    fits = os.path.join(tmp, "campo_estrellas.fits")
    star_field(fits)
    w.set_mode("imagenes")
    v = w.page_by_key["img_ver"]
    v.open(fits)
    v.view.set_region(330, 230, 470, 370)
    shot("visor")
    marks("visor", w, [(1, v.stretch_c), (2, v.limits_c), (3, v.cmap_c), (4, v.shape_c), (5, v.view, "in"),
                       (6, v.pix), (7, v.reg_box), (8, v.hdr)])
    v.shape_c.setCurrentIndex(1)
    v.view.set_region(406, 296, 434, 324)
    v.scale_s.setValue(1.242)
    v.measure_star()
    v.view.center_on(420, 310, 5.0)
    scroll_to(v, 1.0)
    shot("visor_estrella")
    marks("visor_estrella", w, [(1, v.c_hist, "in"), (2, v.lo_s, "l"), (3, v.lock_cb), (4, v.scale_s, "l"),
                                (5, "Medir la estrella"), (6, v.fit_lbl), (7, v.plot_c), (8, v.c_plot, "in")])
    # Calibración: una noche con luces de 30 y 60 s en dos filtros
    from turbulens.core.imageio import write_fits

    night = os.path.join(tmp, "noche")
    rng = np.random.default_rng(7)
    yy, xx = np.mgrid[0:120, 0:160]
    vign = 1 - 0.25 * (((xx - 80) / 80) ** 2 + ((yy - 60) / 60) ** 2)
    for sub, kind, n, exp, filt, level in (("Luces", "Light Frame", 4, 30.0, "R", 900), ("Luces", "Light Frame", 3, 60.0, "V", 1500),
                                           ("Darks", "Dark Frame", 4, 30.0, "", 0), ("Darks", "Dark Frame", 4, 120.0, "", 0),
                                           ("Bias", "Bias Frame", 6, 0.0, "", 0), ("Flats", "Flat Field", 4, 2.0, "R", 20000),
                                           ("Flats", "Flat Field", 4, 2.0, "V", 22000)):
        os.makedirs(os.path.join(night, sub), exist_ok=True)
        for i in range(n):
            img = 300 + rng.normal(0, 4, yy.shape) + 0.5 * exp
            if level:
                img += level * vign
            hdr = {"IMAGETYP": kind, "EXPTIME": exp, "CCD-TEMP": -10.0}
            if filt:
                hdr["FILTER"] = filt
            write_fits(os.path.join(night, sub, f"{sub.lower()}_{filt or 'x'}_{int(exp)}s_{i:02d}.fits"),
                       img.astype(np.float32), hdr)
    w.go("img_cal")
    cal = w.page_by_key["img_cal"]
    cal._add([night])
    cal.out_dir = os.path.join(tmp, "calibracion")
    cal.out_lbl.setText("Carpeta de salida: " + cal.out_dir)
    shot("calibracion_plan")
    marks("calibracion_plan", w, [(1, "Agregar carpeta"), (2, cal.table, "in"), (3, cal.kind_c), (4, cal.method),
                                  (5, cal.scale_chk), (6, cal.plan_lbl), (7, cal.run_b)])
    cal.run()
    t0 = time.time()
    while cal.thread is not None and time.time() - t0 < 120:
        pump(app, 5)
    scroll_to(cal, 1.0)
    shot("calibracion_resultado")
    # Satélite
    w.set_mode("satelite")
    g = w.page_by_key["goes"]
    g.folder = os.path.join(tmp, "satelite")
    os.makedirs(g.folder, exist_ok=True)
    g._update_folder()
    from PySide6.QtCore import QDate, QTime

    g.date.setDate(QDate(2026, 10, 19))
    g.t0.setTime(QTime(18, 0))
    g.t1.setTime(QTime(23, 0))
    g.step.setCurrentIndex(2)
    g.seeing_cb.setChecked(True)
    shot("satelite")
    marks("satelite", w, [(1, g.date, "l"), (2, g.t0, "l"), (3, g.step, "l"), (4, g.lat, "l"), (5, g.half, "l"),
                          (6, g.seeing_cb), (7, g.lam, "l"), (8, g.crit, "l"), (9, g.mode, "l"), (10, g.run_b)])
    g.show_instants(fake_night())
    g.stable.selectRow(3)
    pump(app)
    g.table.selectRow(1)
    shot("satelite_serie", g.series_card)
    marks("satelite_serie", g.series_card, [(1, g.c_seeing, "in"), (2, g.c_f, "in"), (3, g.stable, "in"), (4, g.series_msg, "l")])
    shot("satelite_mapa", g.prev_card)
    marks("satelite_mapa", g.prev_card, [(1, g.preview, "in"), (2, g.map_cb), (3, "Ver completo"), (4, g.prev_lbl)])
    w.go("goes_info")
    shot("satelite_info")
    print("listo", flush=True)
    w.close()


if __name__ == "__main__":
    main()
