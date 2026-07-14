# New Video Candidates

## a2_candidate_01

- **candidate_id:** `a2_candidate_01`
- **source:** `data/candidates/a2_candidate_01.mp4`
- **extension:** `.mp4`
- **classification:** **B - utilizable con riesgos**
- **SHA-256:** `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`
- **size:** `24,944,366 bytes`

### Estabilidad de la fuente

El archivo todavia estaba terminando de copiarse durante la primera lectura y cambio de
tamanio/SHA. Esa medicion fue descartada. La auditoria final se hizo despues de comprobar
que tamanio, mtime y SHA permanecian estables y que ningun proceso mantenia el archivo
abierto. La copia canonica coincide con el SHA estable.

### Metadata final

| Campo | Valor |
| --- | --- |
| Contenedor | MPEG-4 / `public.mpeg-4` con metadata QuickTime |
| Codec video | HEVC (`hevc`) |
| Codec audio | MPEG-4 AAC, 2 canales |
| Resolucion declarada | `2746x1536` |
| Resolucion entregada por OpenCV | `1536x2746`, lateral por rotacion del contenedor |
| Aspect ratio canonico | `1.788:1`, aproximadamente 16:9 |
| Rotacion declarada | `270°` |
| FPS nominal/promedio | `50.24630541871921` |
| FPS calculado por timestamps | `50.17488076311605` |
| Cadence | Variable: intervalos de `0.016667` y `0.033333` s |
| Frames reportados/decodificados | `527 / 527` |
| Duracion | `10.48833333333333 s` |
| Bitrate total | `19015 kb/s` por metadata macOS (`19026 kb/s` por OpenCV) |
| Bitrate video | `18887 kb/s` |
| Bitrate audio | `128 kb/s` |
| Errores de lectura | `0` |
| Frame inicial/final | Ambos legibles |

`ffprobe` no estaba instalado. La metadata se cruzo con OpenCV/FFmpeg embebido, `mdls`,
`file`, timestamps decodificados y lectura secuencial completa.

### Evaluacion visual y programatica

- Camara fija: si. Homografias ORB/RANSAC contra el frame inicial, evaluadas en ocho
  muestras, dieron desplazamiento medio maximo de esquina de `0.218 px` a media
  resolucion y maximo absoluto de `0.381 px` (`<0.8 px` a resolucion completa).
- Cambio de plano: no detectado.
- Replay/transicion: no detectado.
- Rally continuo: si, durante todo el clip.
- Cancha completa: visible.
- Lineas de doubles, baselines, service lines y red: visibles.
- Overlays: marcador abajo a la izquierda y watermark arriba a la derecha; no cubren
  intersecciones principales de calibracion.
- Resolucion: alta y suficiente para Stage 1.
- Blur: sin frame global fuertemente borroso; los tres candidatos seleccionados tienen
  nitidez alta dentro del clip.
- Diferencia consecutiva maxima baja y correlacion de histogramas minima `0.99898`, sin
  evidencia programatica de corte.

### Riesgos

**Calibracion: medio.** El encuadre es favorable, pero la metadata rota el contenido. Los
PNG derivados se corrigieron 90° en sentido antihorario. Los puntos humanos y cualquier
deteccion futura deben compartir esa orientacion canonica.

**WASB: medio-alto.** HEVC, cadence variable, resolucion no estandar y rotacion requieren
validacion en Linux/GPU. La pelota es pequena en la vista completa. No se intento
inferencia en macOS.

### Recomendacion

Aceptar provisionalmente como Nivel A2 y avanzar solo al gate humano del frame de
referencia. Antes de Stage 2 se debe aprobar ADR-0010 y definir en Linux una lectura que
aplique la misma rotacion antihoraria sin recomprimir la fuente.

Evidencia visual local:

```text
outputs/candidate_review/a2_candidate_01/contact_sheet.png
outputs/candidate_review/a2_candidate_01/frame_start.png
outputs/candidate_review/a2_candidate_01/frame_middle.png
outputs/candidate_review/a2_candidate_01/frame_end.png
```
