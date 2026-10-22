# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: pyinstaller packaging/turbulens.spec
import os, sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ONEFILE = os.environ.get("TURBULENS_ONEFILE", "1") == "1" and sys.platform != "darwin"

a = Analysis(
    [os.path.join(ROOT, "packaging", "turbulens_app.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "turbulens", "assets"), "assets"),
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
                     info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0.0"})
