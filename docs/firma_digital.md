# Firma digital de TurbuLENS

Firmar el programa sirve para que Windows y macOS no muestren advertencias como «Windows protegió su PC» o «no se puede verificar el desarrollador». TurbuLENS funciona igual sin firma; la firma solo cambia la confianza del sistema operativo. **Ningún proceso gratuito da esa confianza**: hace falta un certificado emitido a nombre de una persona u organización verificada.

La publicación automática (`.github/workflows/build.yml`) ya tiene los pasos de firma. Se activan solos cuando existen los *secrets* del repositorio (GitHub → Settings → Secrets and variables → Actions). Mientras no existan, el programa se publica sin firmar y todo lo demás funciona igual.

## macOS (lo más directo)

1. Inscribirse en el **Apple Developer Program** (99 USD al año; abierto a personas en Colombia).
2. Crear un certificado **Developer ID Application**, exportarlo como `.p12` desde *Acceso a Llaveros*.
3. Crear una contraseña de app en appleid.apple.com para la notarización.
4. Guardar estos *secrets*:

| Secret | Contenido |
|---|---|
| `APPLE_CERT_P12` | el `.p12` en base64 (`base64 -i cert.p12 \| pbcopy`) |
| `APPLE_CERT_PASSWORD` | la contraseña del `.p12` |
| `APPLE_ID` | el correo de la cuenta de Apple |
| `APPLE_TEAM_ID` | el identificador del equipo (10 caracteres) |
| `APPLE_APP_PASSWORD` | la contraseña de app |

Con eso `packaging/macos/empaquetar.sh` firma con *hardened runtime*, notariza el `.dmg` con Apple y lo «grapa»: el Mac lo abre sin advertencias. Sin certificado, el script usa una firma local (*ad hoc*), suficiente para que la app abra con clic derecho → *Abrir*.

## Windows

Desde 2023 los certificados de firma de código (OV/EV) ya no se entregan como archivo: la clave privada vive en un token USB o en un servicio en la nube. Las opciones realistas son:

- **Certificado de una autoridad (OV) con firma en la nube**, por ejemplo Certum, SSL.com (eSigner) o Sectigo. Lo puede pedir una persona o, mejor, la **Universidad Nacional / el Observatorio** como organización (el nombre de la organización aparece en la firma). Precio orientativo: desde unos 100–130 USD al año. Para firmar desde GitHub Actions sin intervención conviene un servicio que lo permita (por ejemplo SSL.com eSigner con su herramienta CodeSignTool); con Certum SimplySign cada sesión pide un código del celular, así que se firmaría a mano.
- **Azure Artifact Signing** (antes *Trusted Signing*), de Microsoft: 9,99 USD al mes, pero hoy solo acepta personas de EE. UU. y Canadá y organizaciones de EE. UU., Canadá, la Unión Europea y el Reino Unido, así que no aplica a una persona en Colombia.

`packaging/windows/firmar.ps1` firma con `signtool` si existen los *secrets* `WINDOWS_CERT_PFX` (certificado `.pfx` en base64) y `WINDOWS_CERT_PASSWORD`. Sirve para certificados que sí se pueden exportar (por ejemplo uno institucional o uno de prueba). Con un certificado en la nube solo hay que cambiar el comando de ese script por el del proveedor; el resto del proceso (firmar el `.exe`, la versión en carpeta y el instalador) no cambia.

Las propiedades del `.exe` (clic derecho → Propiedades → Detalles) ya muestran el nombre, los autores, el copyright y la versión, firmado o no.
