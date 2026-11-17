# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Calibración guiada por cabeceras: cada luz recibe los darks y flats de su exposición, filtro y tamaño."""

import os

import numpy as np
import pytest

from turbulens.core import calframes as cf
from turbulens.core.imageio import read_stack, write_fits

SHAPE = (30, 40)


def _scene(tmp, rng):
    """Una noche de observación: luces de 30 s y 60 s en dos filtros, darks de 30 s y 120 s, bias y flats."""
    yy, xx = np.mgrid[0:SHAPE[0], 0:SHAPE[1]]
    vign = {"R": 1 - 0.3 * (((xx - 20) / 20) ** 2 + ((yy - 15) / 15) ** 2),
            "V": 1 - 0.2 * (((xx - 10) / 20) ** 2 + ((yy - 15) / 15) ** 2)}
    bias, rate = 300.0, 2.0  # cuentas y cuentas/s de corriente oscura
    hot = np.zeros(SHAPE)
    hot[4, 6] = 50.0  # un píxel caliente: cuentas/s
    sky = 100 + 500 * np.exp(-((xx - 30) ** 2 + (yy - 10) ** 2) / 6)

    def put(folder, name, a, **hdr):
        os.makedirs(os.path.join(tmp, folder), exist_ok=True)
        p = os.path.join(tmp, folder, name)
        write_fits(p, a.astype(np.float32), hdr)
        return p

    def dark(t):
        return bias + (rate + hot) * t + rng.normal(0, 1.0, SHAPE)

    for i in range(5):
        put("bias", f"b{i}.fits", bias + rng.normal(0, 1.0, SHAPE), IMAGETYP="Bias Frame", EXPTIME=0.0, GAIN=100)
        put("darks", f"d30_{i}.fits", dark(30), IMAGETYP="Dark Frame", EXPTIME=30.0, GAIN=100, **{"CCD-TEMP": -10.0})
        put("darks", f"d120_{i}.fits", dark(120), IMAGETYP="Dark Frame", EXPTIME=120.0, GAIN=100, **{"CCD-TEMP": -10.0})
        for f in ("R", "V"):
            put("flats", f"flat_{f}_{i}.fits", bias + 20000 * vign[f] + rng.normal(0, 5, SHAPE),
                IMAGETYP="Flat Field", EXPTIME=0.5, FILTER=f, GAIN=100)
    lights = {}
    for t in (30.0, 60.0):
        for f in ("R", "V"):
            # sin IMAGETYP: se clasifica por la carpeta «luces»
            lights[(t, f)] = put("luces", f"m42_{f}_{int(t)}s.fits", sky * vign[f] * t / 30 + dark(t),
                                 EXPTIME=t, FILTER=f, GAIN=100, **{"CCD-TEMP": -10.0})
    put("otros", "raro_64.fits", np.ones((8, 8)), IMAGETYP="Light Frame", EXPTIME=30.0)  # otro tamaño: sin darks
    return lights, sky


def test_classification_from_header_name_and_folder(tmp_path):
    assert cf.kind_from_header_text("Dark Frame") == "dark"
    assert cf.kind_from_header_text("FLAT") == "flat"
    assert cf.kind_from_header_text("Bias Frame") == "bias" and cf.kind_from_header_text("zero") == "bias"
    assert cf.kind_from_header_text("Light Frame") == "light" and cf.kind_from_header_text("OBJECT") == "light"
    assert cf.kind_from_header_text("DarkFlat") == "darkflat"
    assert cf.kind_from_name("Flats_R") == "flat" and cf.kind_from_name("dark_flat_001") == "darkflat"
    assert cf.kind_from_name("luces") == "light" and cf.kind_from_name("M42_001") is None
    p = tmp_path / "Darks" / "img_0001.fits"
    p.parent.mkdir()
    write_fits(str(p), np.zeros((4, 5), np.float32), {"EXPTIME": 12.5, "XBINNING": 2, "YBINNING": 2, "CCD-TEMP": -5.0})
    info = cf.read_info(str(p))
    assert (info.kind, info.kind_source) == ("dark", "carpeta")
    assert info.exptime == 12.5 and info.binning == (2, 2) and info.temp == -5.0 and info.size == (5, 4)


def test_plan_matches_exposure_filter_and_scales_darks(tmp_path):
    rng = np.random.default_rng(0)
    _scene(str(tmp_path), rng)
    frames = cf.scan([str(tmp_path)])
    assert len(frames) == 5 * 5 + 4 + 1
    plan = cf.build_plan(frames)
    assert plan.counts == {"light": 5, "dark": 10, "flat": 10, "darkflat": 0, "bias": 5}
    g = {(p.exptime, p.filter): p for p in plan.groups}
    assert g[(30.0, "R")].dark.mode == "igual" and len(g[(30.0, "R")].dark.paths) == 5
    # 60 s: no hay darks de 60 s → se escala el de 120 s (más largo) con el bias
    d60 = g[(60.0, "R")].dark
    assert d60.mode == "escalado" and d60.exptime == 120.0 and d60.scale == pytest.approx(0.5)
    assert all("flat_R" in os.path.basename(p) for p in g[(30.0, "R")].flat.paths)
    assert all("flat_V" in os.path.basename(p) for p in g[(30.0, "V")].flat.paths)
    # flats de 0,5 s: sin darks de 0,5 s → solo el bias
    assert g[(30.0, "R")].flat.darks[0][0].mode in ("bias", "escalado")
    odd = [p for p in plan.groups if p.size == (8, 8)][0]
    assert not odd.dark.any and odd.warnings


def test_calibration_removes_dark_hot_pixel_and_vignetting(tmp_path):
    rng = np.random.default_rng(1)
    lights, sky = _scene(str(tmp_path / "noche"), rng)
    frames = cf.scan([str(tmp_path / "noche")])
    res = cf.Calibrator(str(tmp_path / "salida")).run(cf.build_plan(frames), frames)
    assert len(res.outputs) == 5 and any("maestro_dark_120s" in k for k in res.masters)
    for (t, f), p in lights.items():
        out = read_stack([q for q in res.outputs if os.path.basename(p)[:-5] in q][0])
        expected = sky * t / 30
        out = out * np.median(expected / out)  # el flat se normaliza a mediana 1: queda una escala global
        err = np.abs(out - expected) / expected.max()
        assert err.max() < 0.03, (t, f, err.max())  # sin viñeteo ni píxel caliente, también en 60 s (dark escalado)
    hdr = cf.read_info([q for q in res.outputs if "60s" in q][0]).header
    assert hdr.get("EXPTIME") == 60.0
    assert res.first["flat"] and os.path.isfile(res.first["flat"])


def test_masters_only_and_big_series_out_of_core(tmp_path):
    rng = np.random.default_rng(2)
    for i in range(7):
        write_fits(str(tmp_path / f"dark_{i}.fits"), (100 + rng.normal(0, 1, SHAPE)).astype(np.float32), {"EXPTIME": 5.0})
    frames = cf.scan([str(tmp_path)])
    plan = cf.build_plan(frames)
    assert not plan.groups and plan.masters_only[0][0] == "dark"
    res = cf.Calibrator(str(tmp_path / "s")).run(plan, frames)
    assert len(res.masters) == 1
    # combinación por franjas con archivo temporal (memoria limitada)
    imgs = [rng.normal(10, 1, (50, 60)).astype(np.float32) for _ in range(9)]
    imgs[4][7, 7] = 1e5  # rayo cósmico
    a = cf.combine_frames(iter(imgs), 9, "mediana", max_bytes=9 * 50 * 60 * 4 // 3)
    b = cf.combine_frames(iter(imgs), 9, "mediana")
    np.testing.assert_allclose(a, b)
    assert a[7, 7] < 20


def test_oan_devices_plate_scale():
    """Escalas de placa de los equipos del OAN (Nikon en video: píxel efectivo = sensor ÷ ancho del video)."""
    from turbulens.core import devices as dv

    se = dv.by_key(dv.TELESCOPES, "8se")
    nikon = dv.by_key(dv.CAMERAS, "d5600")
    qhy = dv.by_key(dv.CAMERAS, "qhy174")
    assert dv.plate_scale(se, nikon, 1920) == pytest.approx(1.242, abs=0.002)
    assert dv.plate_scale(se, nikon, as_video=False) == pytest.approx(0.398, abs=0.002)  # la escala que se había usado
    assert dv.plate_scale(se, qhy) == pytest.approx(0.595, abs=0.002)
    assert dv.by_key(dv.MASKS, "grupo8").D_cm == 4.2 and dv.by_key(dv.MASKS, "grupo8").B_cm == 14.4
