<p align="center"><img src="turbulens/assets/turbulens_256.png" width="110" alt="TurbuLENS"></p>

<h1 align="center">TurbuLENS</h1>

<p align="center"><b>Separa videos de un DIMM en imágenes, mide el seeing de tu cielo y aprende estadística con una estrella.</b><br>
Observatorio Astronómico Nacional · Universidad Nacional de Colombia</p>

<p align="center"><img src="docs/capturas/01_analisis_resultados_oscuro.png" width="860" alt="Resultados en TurbuLENS"></p>

## Descarga

**Versión actual: 1.5.0.** Descarga el archivo de tu sistema, descomprímelo y abre TurbuLENS: **no hay que instalar Python ni nada más**. Funciona en **español, inglés y portugués**.

| Sistema | Descarga directa | Se abre con |
|---|---|---|
| Windows 10/11 | [TurbuLENS-v1.5.0-Windows-x64.zip](https://github.com/DiegoCagua/TurbuLENS/releases/download/v1.5.0/TurbuLENS-v1.5.0-Windows-x64.zip) | `TurbuLENS.exe` |
| Mac con Apple Silicon | [TurbuLENS-v1.5.0-macOS-AppleSilicon.zip](https://github.com/DiegoCagua/TurbuLENS/releases/download/v1.5.0/TurbuLENS-v1.5.0-macOS-AppleSilicon.zip) | `TurbuLENS.app` |
| Mac con Intel | [TurbuLENS-v1.5.0-macOS-Intel.zip](https://github.com/DiegoCagua/TurbuLENS/releases/download/v1.5.0/TurbuLENS-v1.5.0-macOS-Intel.zip) | `TurbuLENS.app` |
| Linux | [TurbuLENS-v1.5.0-Linux-x64.tar.gz](https://github.com/DiegoCagua/TurbuLENS/releases/download/v1.5.0/TurbuLENS-v1.5.0-Linux-x64.tar.gz) | `TurbuLENS` |

Las notas de cada versión y las versiones anteriores están en **[Releases](https://github.com/DiegoCagua/TurbuLENS/releases)**.

> La primera vez, Windows puede mostrar «Windows protegió su PC»: pulsa *Más información → Ejecutar de todas formas*. En Mac, abre la app con clic derecho → *Abrir*.

## Qué hace

📘 **Manual completo** (uso paso a paso, medir con tu propio equipo, fundamentos y código): [docs/Manual_TurbuLENS_v1.5.0.pdf](docs/Manual_TurbuLENS_v1.5.0.pdf). También viene dentro de cada descarga.

**Medición del seeing** (mediciones reales con un DIMM)

1. **Video**: abre cientos de formatos (MOV, MP4, AVI, MKV, WMV, MTS, WebM, SER, FITS, …) con FFmpeg incluido, también de cámaras astronómicas de 16 bits. Arrastra el archivo a la ventana o búscalo.
2. **Recorte y tramo**: dibuja la región de la estrella **como en Paint** (arrastrar, mover, cuadritos para cambiar el tamaño, zoom con la rueda) o pulsa *Ajustar a la estrella*. Elige el tramo con una línea de tiempo: `<<` `>>` reproducen a velocidad constante (0.25× a 32× respecto al video real), `<` `>` mueven un cuadro, `[ Entrada` y `Salida ]` marcan el tramo, *Ir a* salta a un cuadro o a un minuto.
3. **Parámetros**: botón **Dispositivos (OAN y propios)** con los telescopios, cámaras y máscaras del observatorio y **los tuyos** (se agregan con *+ Propio…* y quedan guardados); diámetro y separación de los orificios y longitud de onda (con unidades y el rango permitido a la vista), escala de placa (con calculadora y el píxel efectivo del video), altura de la estrella, calibración opcional con **dark y flat** y **perfiles de equipo** para no escribir nada dos veces. Si cambias estos valores después de procesar, el seeing se recalcula al instante.
4. **Procesar**: no empieza sin escala de placa (lo avisa). Separa el video en imágenes recortadas y **seguidas** (la región encuentra a la estrella, se recentra en cada cuadro y ajusta su tamaño al de los spots), en PNG, TIFF 16 bits, JPG, un cubo NumPy o un cubo FITS, y mide los dos puntos en cada cuadro.
5. **Resultados**: seeing (longitudinal, transversal y promedio), r₀, corrección al cenit, animación de los centroides, histograma con la curva normal, σ segundo a segundo, diagrama del movimiento diferencial y las **correlaciones r** que dicen si los datos se comportan como turbulencia. Las gráficas leen el valor bajo el cursor y se guardan con clic derecho. Si no se detectó la estrella, las gráficas quedan vacías con un aviso.
6. **Historial**: base de datos local para comparar noches y épocas del año, con etiquetas y notas; es el mismo en los modos medición y educativo. Al salir o al cambiar de video, TurbuLENS pregunta si quieres guardar el análisis.

**Exportación** en dos pasos desde Resultados y desde el Historial: eliges los formatos y la carpeta y pulsas **Generar**. Datos en **CSV, Excel, JSON, NumPy y tabla FITS**; gráficas en **PDF, PNG y SVG**; e **informe PDF** completo. El nombre de los archivos es automático y nunca se sobrescribe nada.

> **Escala de placa con cámaras de fotos (Nikon, Canon) o celulares.** Al grabar video, la cámara reduce la imagen del sensor: el píxel que vale es el **efectivo**, ancho del sensor ÷ ancho del video (Nikon D5600: 23,5 mm ÷ 1920 px = 12,2 µm, no los 3,9 µm del sensor). Con el píxel del sensor la escala sale unas 3 veces menor y el seeing, unas 4 veces mejor de lo real. La calculadora de *Parámetros* y *Dispositivos* lo hacen solas.

**Modo educativo** (colegios y cursos): el eje es **aprender estadística** con datos reales de una estrella.

| Lección | Tema |
|---|---|
| 1 | Datos y mediciones: cada cuadro es un dato |
| 2 | El histograma: intervalos y frecuencias |
| 3 | Media y mediana: el valor típico y la robustez |
| 4 | Varianza y desviación estándar: σ mide la turbulencia |
| 5 | La distribución normal y la regla 68–95–99,7 |
| 6 | Muestras y error de la media (σ/√n, límite central) |
| 7 | Datos atípicos |
| 8 | Correlación entre dos variables y cómo leer *r* en un DIMM |
| 9 | Laboratorio libre |
| 10 | Prueba final de 11 preguntas |

Cada lección tiene controles interactivos, fórmulas en LaTeX, una pregunta que se responde una sola vez por sesión, guarda sus datos en **CSV o Excel** y puede usar los datos de ejemplo (Altair) o **el video que procese la clase**. La parte astronómica se explica en tres pantallas con **animaciones** (por qué titilan las estrellas, el truco de los dos huequitos y un simulador).

**Modo Imágenes**: agrega imágenes sueltas o **carpetas completas** (también arrastrándolas); TurbuLENS lee la cabecera de cada archivo (FITS o EXIF), las clasifica en luces, darks, flats, darks de flat y bias, y empareja cada luz con los darks de su misma **exposición**, ganancia, temperatura y binning, y con los flats de su **filtro**. Muestra el plan antes de calibrar, informa cuánto corrige cada flat (y si los flats están saturados) y deja **comparar antes y después** con los mismos límites de brillo. Su **visor de píxeles** funciona como SAOImage DS9: valor del píxel bajo el cursor, escalas y límites (también manuales, con histograma), mapas de color, regiones rectangulares, circulares o elípticas con su estadística, y la **medición de una estrella**: gaussiana 2D, radio al primer sigma, FWHM y, con la escala de placa, el seeing en segundos de arco, con su perfil radial.

**Modo Satélite**: para saber si había nubes y estimar el seeing de una noche. Eliges la fecha, *Desde* y *Hasta* (cada 30 o 60 minutos), las coordenadas (por defecto el OAN) y los canales del ABI; TurbuLENS busca las imágenes de **disco completo** de GOES-16 o GOES-19 más cercanas a cada hora en el repositorio abierto de NOAA, **lee solo la zona** de tu recorte (≈2 MB por canal), muestra cada canal con un **mapa** (costas, países y departamentos) y, con los canales 9, 13 y 16, calcula el **seeing hora por hora** con el método de Cavazzani et al. (2012), dejando fuera las horas de día según la altura del Sol. Cada evaluación queda en su propia subcarpeta `evaluadas_dia_…` con la serie, los valores, las gráficas y los recortes.

<p align="center">
<img src="docs/capturas/40_imagenes_visor_oscuro.png" width="420" alt="Visor de píxeles">
<img src="docs/capturas/50_satelite_goes_claro.png" width="420" alt="Modo satélite GOES">
</p>

La ventana se abre maximizada (F11 para pantalla completa sin bordes, Esc para salir). Todos los modos tienen tema **claro y oscuro** (sol / luna), botones **!** que explican cada control y tres idiomas (**español, English, Português**).

<p align="center">
<img src="docs/capturas/01_analisis_region_oscuro.png" width="420" alt="Recorte y tramo">
<img src="docs/capturas/11_edu_l5_claro.png" width="420" alt="Lección de la campana de Gauss">
</p>

### Medir con tu propio equipo

TurbuLENS no está atado a los equipos del OAN. En *Parámetros → Dispositivos (OAN y propios)* pulsa **+ Propio…** y agrega tu telescopio (apertura y focal), tu cámara (ancho del sensor en mm y en píxeles; si es una cámara de fotos o un celular, también el ancho del video) y tu máscara (D y B). Quedan guardados y marcados con ★. Después, en *Perfil*, pulsa **Guardar…** para guardar el montaje completo y cargarlo con un clic la próxima vez. También puedes escribir D, B y la escala directamente y usar la calculadora *Calcular…*.

## Cómo funciona

1. Cada cuadro se decodifica con **PyAV/FFmpeg** directamente a un arreglo de **NumPy** en escala de grises (8 o 16 bits), sin guardar el video completo en memoria.
2. Se recorta la región; si *Seguir a la estrella* está activo, la región se recentra con los últimos cuadros válidos y se vuelve a buscar la estrella si se pierde.
3. Los cuadros se procesan **en bloques vectorizados** `(n, alto, ancho)`: fondo por mediana y ruido por MAD; los píxeles con luz se separan en **dos grupos** (k-medias ponderado por intensidad, que empieza en el píxel más brillante y en el píxel con luz más lejano) y el centro de cada grupo es su **centroide**, recortado alrededor del spot (precisión de centésimas de píxel). Así funciona con spots pequeños, grandes, en anillo o partidos. Un cuadro solo cuenta si los dos spots están bien separados, tienen suficiente señal y hay una caída de luz entre ellos.
4. Las mediciones van a un **arreglo estructurado de NumPy reservado de antemano** (sin listas ni archivos intermedios).
5. Los vectores se orientan con el eje principal (los puntos pueden intercambiarse entre cuadros), se proyectan sobre la línea de base (longitudinal) y su perpendicular (transversal) y se descartan los atípicos a más de 5 σ robustas.
6. El seeing sale del modelo de **Tokovinin (2002)**: σ²ₗ,ₜ = Kₗ,ₜ λ² r₀^(−5/3) D^(−1/3), con Kₗ = 0,364 (1 − 0,532 b^(−1/3) − 0,024 b^(−7/3)), Kₜ = 0,364 (1 − 0,798 b^(−1/3) + 0,018 b^(−7/3)), b = B/D y ε = 0,98 λ/r₀.

Con el video de prueba de Altair (1920 × 1080, 59,94 cuadros/s, 8.484 cuadros) TurbuLENS mide los 8.484 cuadros en unos 12 s, guarda las 8.484 imágenes recortadas en unos 5 MB (el programa original generaba ~900 MB de JPG) y obtiene σ = 0,716 px. Con 1″/px, D = 2,5 cm y B = 14 cm eso da un seeing de 1,14″. Más detalles en [docs/metodo.md](docs/metodo.md) y en el [análisis de los códigos originales](docs/analisis_codigos_originales.md).

## Desde el código fuente

```bash
git clone https://github.com/DiegoCagua/TurbuLENS
cd TurbuLENS
pip install -r requirements.txt
python -m turbulens                      # abre la aplicación
python -m turbulens --autoprueba         # prueba sin ventana
python -m pytest                         # pruebas del motor
pyinstaller packaging/turbulens.spec     # ejecutable para tu sistema
```

Cada `git push` ejecuta las pruebas en GitHub Actions y compila y prueba los ejecutables de Windows, macOS y Linux. Cuando llega a `main` una versión nueva (`python scripts/nueva_version.py X.Y.Z`), se publica sola en *Releases* con los archivos de Windows, Mac y Linux.

Los textos de la interfaz están en español en el código; las traducciones están en `turbulens/locales/en.json` y `pt.json` (clave = texto en español).

```
turbulens/
  core/        motor sin interfaz: video, detección, DIMM, estadística, FITS, calibración, GOES y seeing satelital,
               ajuste de estrellas, mapas, exportación, historial
  gui/         interfaz PySide6 (páginas de los cuatro modos, visor de imágenes, animaciones, temas, idiomas)
  _vendor/     pyfive (lector de NetCDF4/HDF5 en Python puro, BSD-3) para el modo Satélite
  locales/     traducciones al inglés y al portugués
  charts.py    gráficas dibujadas con Qt (pantalla, PNG, SVG, PDF)
  reports.py   gráficas e informes de un análisis o del historial
tests/         pruebas con videos sintéticos de valores conocidos
docs/          método, análisis de los códigos originales, capturas y diseños de la interfaz
packaging/     PyInstaller y notas de versión
```

## Diseño

El diseño de la interfaz partió de 10 borradores y tres versiones preliminares interactivas, guardados en [docs/diseno](docs/diseno).

## Créditos

**Autores:** Diego Fernando Cagua Lozada, Fredy Esteban Cruz Ospina y Saray Juliana Pinto Sanabria (coautora y pruebas), estudiantes del pregrado de Física, Departamento de Física, Universidad Nacional de Colombia, Bogotá D.C.

TurbuLENS se desarrolló para la asignatura **Técnicas Observacionales** de la Maestría en Astronomía del Observatorio Astronómico Nacional, Universidad Nacional de Colombia, Bogotá D.C.

Basado en el protocolo *Determina la nitidez del cielo nocturno en tu lugar de observación* (ANDEAN ROAD, Oficina Regional Andina de la Astronomía para el Desarrollo, 2026) y en A. Tokovinin, *From differential image motion to seeing*, PASP 114, 1156 (2002), [arXiv:astro-ph/0111022](https://arxiv.org/abs/astro-ph/0111022).

El seeing desde el satélite sigue a S. Cavazzani, S. Ortolani y V. Zitelli, *Site testing at astronomical sites: seeing evaluation from satellite based data* (2012), [arXiv:1112.3497](https://arxiv.org/abs/1112.3497).

Construido con Python, NumPy, PySide6 (Qt), PyAV (FFmpeg), Pillow, openpyxl y pyfive. Las imágenes del modo Satélite son de NOAA (GOES-R Series, producto ABI L2 CMIPF, NOAA Open Data Dissemination) y los mapas, de Natural Earth (dominio público).

## Cómo citar

Si usas TurbuLENS en un trabajo, informe, clase o publicación, da crédito a los autores:

> Cagua Lozada, D. F., Cruz Ospina, F. E., & Pinto Sanabria, S. J. (2026). *TurbuLENS* (versión 1.5.0) [Software]. Observatorio Astronómico Nacional, Universidad Nacional de Colombia. https://github.com/DiegoCagua/TurbuLENS

```bibtex
@software{cagua_lozada_turbulens_2026,
  author    = {Cagua Lozada, Diego Fernando and Cruz Ospina, Fredy Esteban and Pinto Sanabria, Saray Juliana},
  title     = {TurbuLENS: medición del seeing con un DIMM y enseñanza de la estadística},
  year      = {2026},
  version   = {1.5.0},
  publisher = {Observatorio Astronómico Nacional, Universidad Nacional de Colombia},
  url       = {https://github.com/DiegoCagua/TurbuLENS}
}
```

GitHub también ofrece el botón *Cite this repository* a partir de [`CITATION.cff`](CITATION.cff). La app muestra estas citas en *Acerca de*, con botones para copiarlas, y cada informe, gráfica o exportación lleva una línea de crédito.

## Licencia

TurbuLENS se distribuye bajo la licencia **[PolyForm Noncommercial 1.0.0](LICENSE)**:

- ✅ Puedes usarlo, estudiarlo, modificarlo y compartirlo para **fines no comerciales**: estudio personal, investigación, enseñanza, colegios, universidades, organizaciones sin ánimo de lucro y entidades públicas.
- ✅ Toda copia o versión modificada debe incluir la licencia y las líneas **`Required Notice`** que dan crédito a los autores.
- ❌ **No se permite el uso comercial** (venderlo, cobrar por usarlo o usarlo para obtener ganancias) sin permiso escrito de los autores.

Por no permitir el uso comercial, TurbuLENS es software de **código fuente disponible**, no «código abierto» en el sentido de la OSI. Las versiones hasta la 1.0.0 se publicaron con licencia MIT; desde la 1.1.0 rige PolyForm Noncommercial. Los componentes de terceros conservan sus licencias: ver [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
