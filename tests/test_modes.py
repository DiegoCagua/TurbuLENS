# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Pruebas de los modos «Imágenes» (calibración y visor) y «Satélite» (GOES), sin conexión a internet."""

import datetime as dt
import io
import os
import pathlib

import numpy as np
import pytest

from turbulens.core import calibration as cal
from turbulens.core import goes
from turbulens.core.imageio import read_fits, read_stack, write_fits

DATA = pathlib.Path(__file__).parent / "data"
UTC = dt.timezone.utc


# ------------------------------------------------------------------ GOES
def test_projection_matches_goes_r_pug_example():
    """Ejemplo numérico de la guía de usuario de GOES-R (PUG vol. 3, 5.1.2.8.1)."""
    p = goes.Projection(h=42164160.0, r_eq=6378137.0, r_pol=6356752.31414, lon0=-75.0, x0=-0.151844, dx=5.6e-5,
                        y0=0.151844, dy=-5.6e-5, nx=5424, ny=5424)
    x, y, vis = p.scan_angles(33.846162, -84.690932)
    assert vis and x == pytest.approx(-0.024052, abs=2e-6) and y == pytest.approx(0.095340, abs=2e-6)
    lat, lon = p.latlon(x, y)
    assert lat == pytest.approx(33.846162, abs=1e-6) and lon == pytest.approx(-84.690932, abs=1e-6)
    assert not p.scan_angles(10, 120)[2]  # al otro lado de la Tierra
    assert p.pixel_km == pytest.approx(2.0, rel=0.01)


def test_satellite_by_date():
    assert goes.satellite_for(dt.datetime(2024, 6, 1, tzinfo=UTC)) == 16
    assert goes.satellite_for(dt.datetime(2025, 4, 4, 15, 0, tzinfo=UTC)) == 16
    assert goes.satellite_for(dt.datetime(2025, 4, 4, 15, 20, tzinfo=UTC)) == 19
    assert goes.satellite_for(dt.datetime(2026, 10, 31, 4, 0)) == 19


def _name(ch, sat, t):
    return (f"OR_ABI-L2-CMIPF-M6C{ch:02d}_G{sat}_s{t:%Y}{t.timetuple().tm_yday:03d}{t:%H%M%S}0_"
            f"e{t:%Y}{t.timetuple().tm_yday:03d}{t:%H%M%S}9_c{t:%Y}{t.timetuple().tm_yday:03d}{t:%H%M%S}9.nc")


def _fake_bucket(sat_files: dict):
    """Simula el listado XML de S3 y la descarga de los archivos."""
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.close()

    def opener(url, timeout=30, headers=None):
        from urllib.parse import parse_qs, urlparse

        u = urlparse(url)
        sat = int(u.netloc.split(".")[0].replace("noaa-goes", ""))
        if u.query:
            prefix = parse_qs(u.query)["prefix"][0]
            keys = [k for k in sat_files.get(sat, {}) if k.startswith(prefix)]
            body = "".join(f"<Contents><Key>{k}</Key><Size>{len(sat_files[sat][k])}</Size></Contents>" for k in keys)
            xml = ('<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                   f"{body}<IsTruncated>false</IsTruncated></ListBucketResult>")
            return Resp(xml.encode())
        return Resp(sat_files[sat][u.path.lstrip("/")])

    return opener


def test_find_nearest_scan_and_download(tmp_path):
    t0 = dt.datetime(2026, 10, 31, 4, 0, 21, tzinfo=UTC)
    files = {}
    for k in range(6):
        t = t0 + dt.timedelta(minutes=10 * k)
        for ch in (2, 13):
            key = f"ABI-L2-CMIPF/{t:%Y}/{t.timetuple().tm_yday:03d}/{t:%H}/" + _name(ch, 19, t)
            files[key] = bytes([ch]) * (100 + k)
    opener = _fake_bucket({19: files})
    sat, found = goes.find_files(dt.datetime(2026, 10, 31, 4, 33, tzinfo=UTC), [13, 2], opener=opener)
    assert sat == 19 and [f.channel for f in found] == [13, 2]
    assert all(f.start.minute == 30 for f in found)
    p = goes.download(found[0], str(tmp_path), opener=opener)
    assert os.path.getsize(p) == found[0].size and p.endswith(".nc")
    # Ya descargado: no se vuelve a pedir
    assert goes.download(found[0], str(tmp_path), opener=lambda *a, **k: 1 / 0) == p


def test_falls_back_to_other_satellite():
    t = dt.datetime(2025, 4, 5, 3, 0, 20, tzinfo=UTC)  # GOES-19 por fecha, pero solo hay datos de GOES-16
    key = f"ABI-L2-CMIPF/{t:%Y}/{t.timetuple().tm_yday:03d}/{t:%H}/" + _name(13, 16, t)
    sat, found = goes.find_files(t, [13], opener=_fake_bucket({16: {key: b"x"}}))
    assert sat == 16 and found and found[0].sat == 16


class _Var:
    def __init__(self, data, attrs=None):
        self.data = np.asarray(data)
        self.attrs = attrs or {}
        self.shape = self.data.shape

    def __getitem__(self, k):
        return self.data[k]


class _FakeGoesFile(dict):
    """Imagen de disco completo pequeña (2 km → 54 px) con la geometría real de GOES-19."""

    filename = "OR_ABI-L2-CMIPF-M6C13_G19_s20263040400210_e20263040409529_c20263040410000.nc"

    def __init__(self, n=541):
        super().__init__()
        scale = 0.151844 * 2 / (n - 1)
        xs = np.arange(n, dtype=np.int16)
        self["x"] = _Var(xs, {"scale_factor": np.float32(scale), "add_offset": np.float32(-0.151844)})
        self["y"] = _Var(xs, {"scale_factor": np.float32(-scale), "add_offset": np.float32(0.151844)})
        self["goes_imager_projection"] = _Var(0, {
            "perspective_point_height": 35786023.0, "semi_major_axis": 6378137.0, "semi_minor_axis": 6356752.31414,
            "longitude_of_projection_origin": -75.0})
        raw = np.full((n, n), 2000, np.int16)  # 2000·0.05 + 180 = 280 K
        self.proj = goes.projection_of(self)
        c, r, _ = self.proj.pixel(goes.OAN_LAT, goes.OAN_LON)
        raw[int(round(r)), int(round(c))] = 1000  # 230 K justo en el OAN
        raw[0, 0] = -1  # sin dato (fuera del disco)
        self["CMI"] = _Var(raw, {"scale_factor": np.float32(0.05), "add_offset": np.float32(180.0),
                                 "_FillValue": np.int16(-1), "_Unsigned": "true",
                                 "valid_range": np.array([0, 4095], np.int16)})
        self["band_id"] = _Var(np.array([13], np.int8))


def test_read_point_value_and_cutout():
    f = _FakeGoesFile()
    r = goes.read_point(f, goes.OAN_LAT, goes.OAN_LON, half_km=200)
    assert r.visible and r.channel == 13 and r.sat == 19 and r.unit == "K"
    assert r.value == pytest.approx(230.0, abs=0.01)
    assert 230 < r.mean3 < 280
    rr, cc = int(round(r.row)) - r.cut_origin[0], int(round(r.col)) - r.cut_origin[1]
    assert r.cutout[rr, cc] == pytest.approx(230.0, abs=0.01)
    assert r.start == dt.datetime(2026, 10, 31, 4, 0, 21, tzinfo=UTC)
    tmpl, c = goes.describe_value(13, r.value)
    assert "nubes" in tmpl and c == pytest.approx(-43.15, abs=0.01)
    far = goes.read_point(f, 10, 120)
    assert not far.visible and far.cutout is None
    assert np.isnan(goes.decode_cmi(f["CMI"], f["CMI"][0:1, 0:1])[0, 0])


def test_vendored_hdf5_reader_reads_compressed_chunks():
    from turbulens._vendor import pyfive

    f = pyfive.File(str(DATA / "pyfive_compressed.hdf5"))
    d = f["dataset1"]
    assert d.shape == (21, 16) and d.compression == "gzip"
    np.testing.assert_array_equal(d[1:3, 2:5], [[18, 19, 20], [34, 35, 36]])


# ------------------------------------------------------------ calibración
def _frames(n, base, noise, rng, shape=(40, 60)):
    return [base + rng.normal(0, noise, shape) for _ in range(n)]


def test_calibration_recovers_the_sky(tmp_path):
    rng = np.random.default_rng(0)
    shape = (40, 60)
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    vignette = 1 - 0.3 * (((xx - 30) / 30) ** 2 + ((yy - 20) / 20) ** 2)
    hot = np.zeros(shape)
    hot[5, 7] = 500
    dark_level = 100 + hot
    sky = 50 + 400 * np.exp(-((xx - 40) ** 2 + (yy - 12) ** 2) / 8)
    lights = [sky * vignette + dark_level + rng.normal(0, 2, shape) for _ in range(5)]
    darks = _frames(9, dark_level, 2, rng)
    flats = [3000 * vignette + 20 + rng.normal(0, 5, shape) for _ in range(9)]
    dflats = _frames(9, np.full(shape, 20.0), 1, rng)
    md = cal.combine(darks, "mediana")
    mf = cal.master_flat(flats, cal.combine(dflats), None)
    assert np.median(mf) == pytest.approx(1.0, abs=0.01)
    out = cal.apply_calibration(np.mean(lights, 0), md, mf)
    k = sky.mean() / out.mean()
    assert np.abs(out * k - sky).max() < 0.05 * sky.max()  # sin viñeteo y sin el píxel caliente
    # FITS de ida y vuelta (32 bits, fila 0 arriba)
    p = tmp_path / "m.fits"
    write_fits(str(p), out, {"OBJECT": "Cúmulo ñandú"})
    back, hdr, cards = read_fits(str(p))
    np.testing.assert_allclose(back, out, rtol=1e-6)
    assert hdr["OBJECT"] == "Cumulo nandu"  # FITS solo admite ASCII
    s = cal.stats(out[10:15, 35:45])
    assert s["n"] == 50 and s["max"] >= s["mediana"] >= s["min"]


def test_sigma_clip_rejects_cosmic_rays():
    rng = np.random.default_rng(1)
    fr = [np.full((10, 10), 100.0) + rng.normal(0, 1, (10, 10)) for _ in range(7)]
    fr[3][4, 4] = 60000
    assert cal.combine(fr, "sigma")[4, 4] == pytest.approx(100, abs=3)
    assert cal.combine(fr, "media")[4, 4] > 1000


# ------------------------------------------------------------------ GUI
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _window(tmp_path):
    from turbulens.gui.app import MainWindow

    w = MainWindow(data_root=str(tmp_path / "datos"))
    w.resize(1300, 850)
    w.show()
    return w


def test_images_mode_calibrate_and_view(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication

    from turbulens.gui.pages import images

    rng = np.random.default_rng(2)
    shape = (30, 50)
    paths = {}
    for k, base in (("darks", 100.0), ("flats", 2000.0), ("luces", 400.0)):
        paths[k] = []
        for i in range(3):
            p = tmp_path / f"{k}_{i}.fits"
            write_fits(str(p), (base + rng.normal(0, 3, shape)).astype(np.float32))
            paths[k].append(str(p))
    w = _window(tmp_path)
    w.set_mode("imagenes")
    assert w.current == "img_ver"
    pg = w.page_by_key["img_cal"]
    w.go("img_cal")
    for k, ps in paths.items():
        pg.files[k] = list(ps)
        pg._sync(k)
    pg.out_dir = str(tmp_path / "salida")
    os.makedirs(pg.out_dir)
    pg.run()
    assert set(pg.masters) == {"dark", "flat"} and len(pg.outputs) == 3
    calib = read_stack(pg.outputs[0])
    assert calib.shape == shape and abs(float(np.median(calib)) - 300) < 10
    pg.use_in_analysis()
    assert w.sessions["analisis"].cal["on"] and w.sessions["analisis"].cal["dark"].endswith("_dark.fits")
    # Visor: abrir, leer un píxel, estadística de región y exportar la región a CSV
    pg.open_in_viewer(pg.outputs[0])
    v = w.page_by_key["img_ver"]
    assert w.current == "img_ver" and v.view.data.shape == shape
    v._hover(4, 2, float(v.view.data[2, 4]))
    assert "x = 5" in v.pix.text() and "y = 3" in v.pix.text()
    v.view.set_region(10, 5, 19, 14)
    assert v.reg_vals["n"].text() == "100"
    monkeypatch.setattr(images, "choose_folder", lambda *a, **k: str(tmp_path))
    v.export_region()
    csvs = list(tmp_path.glob("*_region_*.csv"))
    assert csvs and len(csvs[0].read_text(encoding="utf-8").splitlines()) >= 101
    for mode in ("lineal", "log", "raiz", "asinh", "histeq"):
        v.view.set_display(stretch_kind=mode)
    v.view.set_display(limit_mode="minmax", cmap="calor")
    QApplication.processEvents()
    w.close()


def test_satellite_page_shows_readings(app, tmp_path):
    w = _window(tmp_path)
    w.set_mode("satelite")
    pg = w.page_by_key["goes"]
    assert w.current == "goes"
    pg.folder = str(tmp_path)
    r = goes.read_point(_FakeGoesFile(), goes.OAN_LAT, goes.OAN_LON, half_km=150)
    pg.show_readings([r])
    assert pg.table.rowCount() == 1 and pg.table.item(0, 2).text().startswith("230")
    assert list(tmp_path.glob("turbulens_goes_*_valores.csv")) and list(tmp_path.glob("*_C13_recorte.fits"))
    pg.open_viewer()
    assert w.current == "img_ver" and w.page_by_key["img_ver"].view.marker is not None
    # Fecha local de Colombia → UTC y satélite automático
    from PySide6.QtCore import QDate, QTime

    pg.zone.setCurrentIndex(0)
    pg.date.setDate(QDate(2025, 4, 4))
    pg.time.setTime(QTime(10, 0))
    assert pg.when_utc() == dt.datetime(2025, 4, 4, 15, 0, tzinfo=UTC)
    assert "GOES-16" in pg.sat_lbl.text()
    pg.time.setTime(QTime(10, 30))
    assert "GOES-19" in pg.sat_lbl.text()
    w.close()
