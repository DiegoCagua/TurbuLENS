# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Diego Fernando Cagua Lozada — TurbuLENS (https://github.com/DiegoCagua/TurbuLENS)
"""Punto de entrada para el ejecutable empaquetado."""
import multiprocessing
import sys

def _linux_platform_fallback():
    """En Linux, si el usuario no eligió plataforma, probar X11 y luego Wayland."""
    import os

    if "--autoprueba" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        return
    if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM"):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return  # sin escritorio: que Qt muestre su mensaje normal
        if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY"):
            os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
        else:
            os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _linux_platform_fallback()
    if "--prueba-ventana" in sys.argv:
        from turbulens.selftest import window_test

        sys.exit(window_test())
    if "--autoprueba" in sys.argv:
        from turbulens.selftest import run

        sys.exit(run(sys.argv[1:]))
    from turbulens.gui.app import main

    sys.exit(main())
