# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pyinstaller packaging/turbulens.spec
import os, sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ONEFILE = os.environ.get("TURBULENS_ONEFILE", "1") == "1" and sys.platform != "darwin"

# Linux: Qt 6.5+ necesita libxcb-cursor0 y otras bibliotecas xcb-util que muchas
# instalaciones de escritorio no traen. Se empaquetan junto al programa.
extra_bins = []
if sys.platform.startswith("linux"):
    import glob

    LINUX_LIBS = ["libxcb-cursor.so.0", "libxcb-icccm.so.4", "libxcb-image.so.0", "libxcb-keysyms.so.1",
                  "libxcb-render-util.so.0", "libxcb-util.so.1", "libxcb-xkb.so.1", "libxkbcommon-x11.so.0",
                  "libxcb-xinerama.so.0", "libxcb-randr.so.0", "libxcb-shape.so.0", "libxcb-xfixes.so.0",
                  "libxcb-sync.so.1", "libxcb-shm.so.0", "libxcb-render.so.0"]
    faltan = []
    for lib in LINUX_LIBS:
        hits = glob.glob(f"/usr/lib/x86_64-linux-gnu/{lib}*") + glob.glob(f"/lib/x86_64-linux-gnu/{lib}*") + \
            glob.glob(f"/usr/lib64/{lib}*")
        hits = [h for h in hits if h.endswith(lib) or h.split(lib)[-1].startswith(".")]
        if hits:
            extra_bins.append((sorted(hits, key=len)[0], "."))
        else:
            faltan.append(lib)
    if "libxcb-cursor.so.0" in faltan and os.environ.get("TURBULENS_REQUIRE_XCB", "0") == "1":
        raise SystemExit("Falta libxcb-cursor0 en el equipo de compilación: sudo apt install libxcb-cursor0")
    print("Bibliotecas xcb empaquetadas:", [b[0] for b in extra_bins], "faltan:", faltan)

a = Analysis(
    [os.path.join(ROOT, "packaging", "turbulens_app.py")],
    pathex=[ROOT],
    binaries=extra_bins,
    datas=[(os.path.join(ROOT, "LICENSE"), "."), (os.path.join(ROOT, "THIRD_PARTY_NOTICES.md"), "."),
           (os.path.join(ROOT, "turbulens", "assets"), "assets"),
           (os.path.join(ROOT, "turbulens", "data"), "data")],
    hiddenimports=["PySide6.QtSvg", "openpyxl", "PIL.Image", "PIL.TiffImagePlugin", "PIL.PngImagePlugin",
                   "PIL.JpegImagePlugin"],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest", "cv2",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtBluetooth", "PySide6.QtCharts"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = os.path.join(ROOT, "turbulens", "assets", "turbulens.ico" if sys.platform == "win32" else "turbulens.png")
common = dict(name="TurbuLENS", debug=False, strip=False, upx=False, console=False, icon=icon)
if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **common)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **common)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="TurbuLENS")
    if sys.platform == "darwin":
        app = BUNDLE(coll, name="TurbuLENS.app", icon=os.path.join(ROOT, "turbulens", "assets", "turbulens.icns")
                     if os.path.exists(os.path.join(ROOT, "turbulens", "assets", "turbulens.icns")) else None,
                     bundle_identifier="co.edu.unal.oan.turbulens",
                     info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.1.1"})
