#!/bin/bash
# Firma TurbuLENS.app y crea el .dmg (arrastrar a Aplicaciones).
# Uso: packaging/macos/empaquetar.sh dist/TurbuLENS.app TurbuLENS-v1.2.0-macOS-AppleSilicon.dmg
# Con certificado de Apple (variables APPLE_CERT_P12, APPLE_CERT_PASSWORD, APPLE_ID, APPLE_TEAM_ID,
# APPLE_APP_PASSWORD) firma con «Developer ID» y notariza; sin ellas usa una firma local («ad hoc»).
set -euo pipefail
APP="$1"; DMG="$2"
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
IDENT="-"
if [ -n "${APPLE_CERT_P12:-}" ]; then
  KC="$RUNNER_TEMP/firma.keychain-db"; KP=$(uuidgen)
  echo "$APPLE_CERT_P12" | base64 --decode > "$RUNNER_TEMP/cert.p12"
  security create-keychain -p "$KP" "$KC"
  security set-keychain-settings -lut 21600 "$KC"
  security unlock-keychain -p "$KP" "$KC"
  security import "$RUNNER_TEMP/cert.p12" -P "$APPLE_CERT_PASSWORD" -A -t cert -f pkcs12 -k "$KC"
  security set-key-partition-list -S apple-tool:,apple: -k "$KP" "$KC" >/dev/null
  security list-keychains -d user -s "$KC" $(security list-keychains -d user | tr -d '"')
  IDENT=$(security find-identity -v -p codesigning "$KC" | grep "Developer ID Application" | head -1 | awk -F'"' '{print $2}')
  echo "Firmando con: $IDENT"
  codesign --force --deep --options runtime --timestamp --entitlements "$HERE/entitlements.plist" --sign "$IDENT" "$APP"
else
  echo "Sin certificado de Apple: firma local (ad hoc)."
  codesign --force --deep --sign - "$APP"
fi
codesign --verify --deep --strict "$APP"
STAGE=$(mktemp -d)
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Aplicaciones"
cp "$ROOT/packaging/LEEME.txt" "$STAGE/"
cp "$ROOT/LICENSE" "$STAGE/LICENSE.txt"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$STAGE/"
for i in 1 2 3 4 5; do  # hdiutil a veces falla con «Resource busy» en los equipos de GitHub
  hdiutil create -volname "TurbuLENS" -srcfolder "$STAGE" -ov -format UDZO "$DMG" && break
  echo "hdiutil falló (intento $i), reintentando…"; sleep 10
done
[ -f "$DMG" ]
if [ "$IDENT" != "-" ]; then
  codesign --force --timestamp --sign "$IDENT" "$DMG"
  xcrun notarytool submit "$DMG" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" --wait
  xcrun stapler staple "$DMG"
fi
ls -la "$DMG"
