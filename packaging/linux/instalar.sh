#!/bin/sh
# Instala TurbuLENS para tu usuario: aparece en el menú de aplicaciones con su icono.
# Uso:  sh instalar.sh        (para quitarlo:  sh instalar.sh --desinstalar)
set -e
DIR=$(cd "$(dirname "$0")" && pwd)
APP="$HOME/.local/share/TurbuLENS"
BIN="$HOME/.local/bin"
ICON="$HOME/.local/share/icons/hicolor/256x256/apps"
DESK="$HOME/.local/share/applications"

if [ "$1" = "--desinstalar" ]; then
  rm -rf "$APP" "$BIN/turbulens" "$ICON/turbulens.png" "$DESK/turbulens.desktop"
  command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESK" || true
  echo "TurbuLENS se desinstaló."
  exit 0
fi

mkdir -p "$APP" "$BIN" "$ICON" "$DESK"
cp "$DIR/TurbuLENS" "$APP/TurbuLENS"
chmod +x "$APP/TurbuLENS"
cp "$DIR/turbulens.png" "$ICON/turbulens.png"
for f in LICENSE.txt THIRD_PARTY_NOTICES.md LEEME.txt; do [ -f "$DIR/$f" ] && cp "$DIR/$f" "$APP/"; done
ln -sf "$APP/TurbuLENS" "$BIN/turbulens"
cat > "$DESK/turbulens.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TurbuLENS
GenericName=DIMM seeing monitor
Comment=Seeing con un DIMM y estadística con una estrella
Comment[en]=DIMM seeing and statistics with a star
Comment[pt]=Seeing com um DIMM e estatística com uma estrela
Exec="$APP/TurbuLENS" %f
Icon=turbulens
Terminal=false
Categories=Education;Science;Astronomy;
StartupWMClass=TurbuLENS
DESKTOP
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DESK" || true
echo "Listo: busca «TurbuLENS» en el menú de aplicaciones (o escribe «turbulens» en la terminal)."
