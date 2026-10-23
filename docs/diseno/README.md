# Diseño de la interfaz

El diseño de TurbuLENS se hizo en tres etapas, en un lienzo de diseño de Claude. Los archivos `.dc.html` son la fuente de cada pantalla (HTML con plantillas del formato *Design Component*). Para verlos con todo su estilo e interacción se abren en ese lienzo; como HTML plano sin el entorno se ven sin datos.

## 1. Diez borradores (`borradores/`)

| # | Archivo | Idea |
|---|---|---|
| 01 | `01_Main.dc.html` | Asistente por pasos |
| 02 | `02_Oscuro.dc.html` | Panel científico oscuro |
| 03 | `03_Nocturno.dc.html` | Modo nocturno rojo (adaptación a la oscuridad) |
| 04 | `04_Tarjetas.dc.html` | Tablero de tarjetas |
| 05 | `05_Instrumento.dc.html` | Panel de instrumento tipo osciloscopio |
| 06 | `06_Lotes.dc.html` | Cola de lotes de varios videos |
| 07 | `07_Minimal.dc.html` | Minimalista |
| 08 | `08_Pestanas.dc.html` | Pestañas clásicas de escritorio |
| 09 | `09_Timeline.dc.html` | Línea de tiempo tipo editor de video |
| 10 | `10_Bitacora.dc.html` | Bitácora de observación |

Los elegidos para continuar fueron **02, 04, 07 y 09**. El tema oscuro de la app usa los colores del 09 y el claro los del 04, menos saturados.

## 2. Versiones preliminares interactivas (`preliminar/`)

- **0.1:** mezcla de 02, 04, 07 y 09; modos análisis y educativo; tema claro y oscuro; cálculo de seeing con los parámetros del usuario; historial.
- **0.2:** pantalla de inicio que separa los modos; región libre; laboratorio de estadística; exportación en varios formatos; nombre DIMMension.
- **0.3** (`v0.3_TurbuLENS.dc.html`): nombre **TurbuLENS**; región que se dibuja y ajusta como en Paint; línea de tiempo simple con `<<` `<` `>` `>>` y marcas de entrada y salida; iconos de sol y luna; PNG recortado como opción predeterminada.

Las versiones 0.1 y 0.2 evolucionaron dentro del mismo archivo, así que aquí solo queda la 0.3, que contiene los cambios de las anteriores.

## 3. Versión 1.0 (la aplicación)

Cambios de la versión 1.0 respecto a la 0.3: el modo educativo gira alrededor de la estrella pero enseña **estadística**, en 9 lecciones y una prueba; la astronomía se explica en tres pantallas sencillas; `<<` y `>>` son más rápidos (2× a 32×); los controles de recorte y tramo ocupan menos espacio; y las explicaciones de cada control quedan en botones **!**. Las capturas están en [../capturas](../capturas).

## 4. Versión 1.1

Animación de los centroides en Resultados, corrección del arranque en Linux y licencia PolyForm Noncommercial con crédito obligatorio a los autores.

## 5. Versión 1.1.2

Fredy Esteban Cruz Ospina se suma como coautor en la aplicación, la licencia, la cita y la documentación.

## 6. Versión 1.2.0

Tres idiomas (español, inglés y portugués) que se cambian desde *Acerca de* o la pantalla de inicio; los mismos botones `<<` `<` `>` `>>` y las mismas velocidades (0.25× a 32×) en toda la app; fórmulas en LaTeX en las lecciones; y botón de maximizar en la barra de título.

## 7. Versión 1.2.1

«Acerca de» del inicio abre una página completa (antes el texto se montaba sobre la pantalla), pantalla de carga al cambiar de idioma, la ficha «Mi video» de las lecciones funciona con el video procesado en cualquiera de los dos modos y se quitó el botón de video de ejemplo.

## 8. Versión 1.2.2

Un solo selector de archivos y carpetas en toda la app (el propio, con el tema y el idioma de TurbuLENS); exportar pide solo la carpeta y nombra los archivos solo; historial y perfiles de equipo compartidos entre los dos modos; en la pantalla de carga del idioma gira el logo; y Recorte y tramo se desplaza en ventanas bajas en vez de montar los textos sobre el video.
