# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada y Fredy Esteban Cruz Ospina — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Historial de análisis en SQLite, compartido por los dos modos.

Los análisis del modo análisis y del modo educativo se guardan en la misma base
(``historial.sqlite``); la columna ``modo`` dice en cuál se hizo cada uno. Las
mediciones por cuadro van en ``datos_historial``. La primera vez se copian los
análisis de las versiones anteriores, que tenían una base por modo.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
import sys
from typing import Optional

import numpy as np

FIELDS = [
    ("created", "TEXT"), ("label", "TEXT"), ("video_name", "TEXT"), ("video_path", "TEXT"),
    ("start", "INTEGER"), ("stop", "INTEGER"), ("fps", "REAL"),
    ("n_frames", "INTEGER"), ("n_detected", "INTEGER"), ("n_used", "INTEGER"),
    ("mean_sep_px", "REAL"), ("median_sep_px", "REAL"), ("std_sep_px", "REAL"),
    ("sigma_l_px", "REAL"), ("sigma_t_px", "REAL"),
    ("eps_l", "REAL"), ("eps_t", "REAL"), ("eps", "REAL"), ("eps_zenith", "REAL"), ("r0_cm", "REAL"),
    ("D_cm", "REAL"), ("B_cm", "REAL"), ("lambda_nm", "REAL"), ("scale", "REAL"), ("altitude", "REAL"),
    ("roi", "TEXT"), ("out_dir", "TEXT"), ("notes", "TEXT"), ("data_file", "TEXT"), ("modo", "TEXT"),
]
MODES = ("analisis", "educativo")


def app_data_dir() -> str:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    d = os.path.join(base, "TurbuLENS")
    os.makedirs(d, exist_ok=True)
    return d


class History:
    """Historial compartido. ``mode`` es el modo con que se guardan los análisis nuevos."""

    def __init__(self, mode: str = "analisis", root: Optional[str] = None):
        if mode not in MODES:
            raise ValueError("modo inválido")
        self.mode = mode
        self.root = root or app_data_dir()
        self.data_dir = os.path.join(self.root, "datos_historial")
        os.makedirs(self.data_dir, exist_ok=True)
        self.path = os.path.join(self.root, "historial.sqlite")
        self._con = sqlite3.connect(self.path)
        self._con.row_factory = sqlite3.Row
        cols = ", ".join(f"{n} {t}" for n, t in FIELDS)
        self._con.execute(f"CREATE TABLE IF NOT EXISTS analyses (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
        self._con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        existing = {r[1] for r in self._con.execute("PRAGMA table_info(analyses)")}
        for n, t in FIELDS:
            if n not in existing:
                self._con.execute(f"ALTER TABLE analyses ADD COLUMN {n} {t}")
        self._con.commit()
        self._migrate_old()

    def _migrate_old(self) -> None:
        """Copia una sola vez los análisis de las bases por modo de versiones anteriores."""
        if self._con.execute("SELECT value FROM meta WHERE key='migrado'").fetchone():
            return
        names = [n for n, _ in FIELDS]
        for mode in MODES:
            old = os.path.join(self.root, f"{mode}.sqlite")
            if not os.path.isfile(old):
                continue
            try:
                con = sqlite3.connect(old)
                con.row_factory = sqlite3.Row
                for r in con.execute("SELECT * FROM analyses ORDER BY id"):
                    r = dict(r)
                    rec = {k: r.get(k) for k in names}
                    rec["modo"] = mode
                    q = ", ".join("?" for _ in rec)
                    self._con.execute(f"INSERT INTO analyses ({', '.join(rec)}) VALUES ({q})", list(rec.values()))
                con.close()
            except sqlite3.Error:
                pass
        self._con.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('migrado', '1')")
        self._con.commit()

    def add(self, record: dict, meas: Optional[np.ndarray] = None, arrays: Optional[dict] = None) -> int:
        rec = {k: record.get(k) for k, _ in FIELDS}
        rec["created"] = rec.get("created") or _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        rec["modo"] = rec.get("modo") or self.mode
        if isinstance(rec.get("roi"), (list, tuple)):
            rec["roi"] = json.dumps(list(rec["roi"]))
        for k, v in list(rec.items()):
            if isinstance(v, (np.floating,)):
                rec[k] = float(v)
            if isinstance(v, float) and not np.isfinite(v):
                rec[k] = None
        names = ", ".join(rec)
        q = ", ".join("?" for _ in rec)
        cur = self._con.execute(f"INSERT INTO analyses ({names}) VALUES ({q})", list(rec.values()))
        rid = int(cur.lastrowid)
        if meas is not None:
            fn = os.path.join(self.data_dir, f"analisis_{rid:05d}.npz")
            np.savez_compressed(fn, mediciones=meas, **{k: np.asarray(v) for k, v in (arrays or {}).items()})
            self._con.execute("UPDATE analyses SET data_file=? WHERE id=?", (fn, rid))
        self._con.commit()
        return rid

    def list(self) -> list[dict]:
        return [dict(r) for r in self._con.execute("SELECT * FROM analyses ORDER BY id DESC")]

    def get(self, rid: int) -> Optional[dict]:
        r = self._con.execute("SELECT * FROM analyses WHERE id=?", (rid,)).fetchone()
        return dict(r) if r else None

    def load_arrays(self, rid: int) -> Optional[dict]:
        r = self.get(rid)
        if not r or not r.get("data_file") or not os.path.isfile(r["data_file"]):
            return None
        with np.load(r["data_file"], allow_pickle=False) as z:
            return {k: z[k] for k in z.files}

    def update_notes(self, rid: int, notes: str, label: Optional[str] = None) -> None:
        if label is None:
            self._con.execute("UPDATE analyses SET notes=? WHERE id=?", (notes, rid))
        else:
            self._con.execute("UPDATE analyses SET notes=?, label=? WHERE id=?", (notes, label, rid))
        self._con.commit()

    def delete(self, rid: int) -> None:
        r = self.get(rid)
        if r and r.get("data_file") and os.path.isfile(r["data_file"]):
            try:
                os.remove(r["data_file"])
            except OSError:
                pass
        self._con.execute("DELETE FROM analyses WHERE id=?", (rid,))
        self._con.commit()

    def close(self) -> None:
        self._con.close()
