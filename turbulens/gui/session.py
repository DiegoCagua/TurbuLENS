# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Estado de trabajo de cada modo (análisis y educativo). El historial y los perfiles de equipo se comparten."""

from __future__ import annotations

import os
from typing import Optional

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..core import pipeline
from ..core.dimm import DimmParams, DimmResult, analyze
from ..core.history import History
from ..core.video import VideoReader


def resource_path(*parts: str) -> str:
    import sys

    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


class Session(QObject):
    video_changed = Signal()
    roi_changed = Signal()
    params_changed = Signal()
    result_changed = Signal()
    history_changed = Signal()

    def __init__(self, mode: str, data_root: Optional[str] = None):
        super().__init__()
        self.mode = mode
        # Respuestas de las preguntas (una sola vez por sesión; se conservan si se cambia el idioma)
        self.answers: dict = {}
        self.reader: Optional[VideoReader] = None
        self.info = None
        self.roi = (0, 0, 64, 64)
        self.roi_frame = 0
        self.tin = 0
        self.tout = 0
        self.frame = 0
        self.params = DimmParams()
        self.track = True
        self.save_images = True
        self.fmt = "PNG"
        self.every_n = 1
        self.out_dir = ""
        self.result: Optional[pipeline.ProcessResult] = None
        self.dimm: Optional[DimmResult] = None
        self.saved_id: Optional[int] = None
        self.history = History(mode, root=data_root)

    # ------------------------------------------------------------ video
    def open_video(self, path: str) -> None:
        reader = VideoReader(path)
        if self.reader is not None:
            self.reader.close()
        self.reader = reader
        self.info = reader.info
        n = self.info.n_frames
        self.tin, self.tout, self.frame = 0, n - 1, 0
        self.roi_frame = 0
        first = reader.frame_at(0)
        try:
            self.roi = pipeline.fit_roi(first)
        except Exception:
            w = min(128, self.info.width)
            h = min(128, self.info.height)
            self.roi = ((self.info.width - w) // 2, (self.info.height - h) // 2, w, h)
        stem = os.path.splitext(os.path.basename(path))[0]
        self.out_dir = os.path.join(os.path.dirname(path), f"{stem}_TurbuLENS")
        self.result = None
        self.dimm = None
        self.saved_id = None
        self.video_changed.emit()
        self.roi_changed.emit()
        self.result_changed.emit()

    def frame_image(self, idx: int) -> Optional[np.ndarray]:
        if self.reader is None:
            return None
        return self.reader.frame_at(idx)

    def set_roi(self, roi: tuple, frame: Optional[int] = None) -> None:
        self.roi = tuple(int(v) for v in roi)
        if frame is not None:
            self.roi_frame = int(frame)
        self.roi_changed.emit()

    def tracked_roi_at(self, frame: int) -> Optional[tuple]:
        """Región seguida en ``frame`` según el último procesamiento (si existe)."""
        if self.result is None or self.result.meas.size == 0:
            return None
        m = self.result.meas
        i = int(np.searchsorted(m["frame"], frame))
        if i >= m.size or m["frame"][i] != frame:
            return None
        w, h = self.result.options.roi[2], self.result.options.roi[3]
        return (int(m["roi_x"][i]), int(m["roi_y"][i]), int(w), int(h))

    # ---------------------------------------------------------- análisis
    def reanalyze(self) -> None:
        if self.result is not None and self.result.meas.size:
            self.dimm = analyze(self.result.meas, self.params)
            self.saved_id = None
        self.result_changed.emit()

    def set_result(self, res: pipeline.ProcessResult) -> None:
        self.result = res
        self.dimm = analyze(res.meas, self.params) if res.meas.size else None
        self.saved_id = None
        try:
            if self.dimm is not None:
                pipeline.write_outputs(res, self.dimm, self.params)
        except Exception:
            pass
        self.result_changed.emit()

    def record(self) -> dict:
        from ..core.export import summary_record

        return summary_record(self.result, self.dimm, self.params)

    def save_to_history(self, label: str = "", notes: str = "") -> int:
        res, d, prm = self.result, self.dimm, self.params
        rec = {
            "label": label, "notes": notes, "video_name": res.video.get("name"), "video_path": res.video.get("path"),
            "start": res.options.start, "stop": res.options.stop, "fps": res.video.get("fps"),
            "n_frames": d.n_frames, "n_detected": d.n_detected, "n_used": d.n_used,
            "mean_sep_px": d.mean_sep_px, "median_sep_px": d.median_sep_px, "std_sep_px": d.std_sep_px,
            "sigma_l_px": d.sigma_l_px, "sigma_t_px": d.sigma_t_px, "eps_l": d.eps_l, "eps_t": d.eps_t,
            "eps": d.eps, "eps_zenith": d.eps_zenith, "r0_cm": d.r0_cm, "D_cm": prm.D_cm, "B_cm": prm.B_cm,
            "lambda_nm": prm.lambda_nm, "scale": prm.scale_arcsec_px, "altitude": prm.altitude_deg,
            "roi": list(res.options.roi), "out_dir": res.out_dir,
        }
        arrays = {k: v for k, v in d.arrays.items()}
        if res.preview_frames is not None:
            # Hasta 300 recortes para poder ver la animación desde el historial.
            k = res.preview_frames.shape[0]
            sel = np.linspace(0, k - 1, min(k, 300)).astype(int)
            arrays["preview_frames"] = res.preview_frames[sel]
            arrays["preview_rows"] = res.preview_rows[sel]
        rid = self.history.add(rec, meas=res.meas, arrays=arrays)
        self.saved_id = rid
        self.history_changed.emit()
        return rid
