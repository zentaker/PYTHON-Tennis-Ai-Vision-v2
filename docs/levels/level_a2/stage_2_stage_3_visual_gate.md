# Gate visual humano — Stage 2 y Stage 3 A2

**Fecha de preparación:** 2026-07-15

## Veredicto humano definitivo

- Stage 2: `A — APROBADA`; estado final `CLOSED_SUCCESSFULLY`.
- Stage 3: `A — APROBADA`; estado final `CLOSED_SUCCESSFULLY`.
- Commit usado para preparar este paquete:
  `bbd6429203f40c3d98902f4f6d3be815ade27995`.
- Commit publicado del paquete de gate:
  `618cf54eb00fc9cf082fb21c95f7a4719fa8a379`.
- Fecha del veredicto: `2026-07-15`.

> El usuario revisó el video comparativo y confirmó que el tracking de la pelota es
> correcto y que Stage 2 obtuvo su objetivo.

El usuario también confirmó que la trayectoria suavizada es visualmente correcta y
usable para continuar. Los gaps y métricas documentados permanecen visibles y no se
interpretan como cobertura total. No se recalculó Stage 3, no se cambiaron parámetros y
no se ejecutó WASB para registrar el veredicto.

## Material que debe revisarse

1. Comparación completa:
   `outputs/nivel_a2_01/review/stage_2_vs_stage_3_comparison.mp4`.
2. Casos críticos:
   `outputs/nivel_a2_01/review/critical_cases/`.
3. Overlay Stage 2 completo:
   `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.
4. Overlay Stage 3 normal:
   `outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4`.
5. Overlay Stage 3 debug:
   `outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4`.

La comparación presenta Stage 2 raw a la izquierda y Stage 3 debug a la derecha. Tiene
`527` frames, resolución `1920x634`, orientación canónica, timestamps VFR y duración
`10.471668 s`. Los tres overlays fuente también fueron verificados con `527` frames,
`2746x1536`, duración `10.471668 s`, y primer/último frame legibles.

## Métricas baseline Stage 3

- Frames: `527`.
- Detected: `383`.
- Rejected: `0`.
- Interpolated: `19`.
- Missing: `125`.
- Cobertura: `402/527` (`76.2808%`).
- Gaps interpolados: `8`.
- Gap missing máximo: `81` frames / `1.588333 s`.
- Velocidad raw máxima: `4550.819943 px/s`.
- Velocidad smooth máxima: `4689.589387 px/s`.

## Puntos de atención obligatorios

- La cobertura es `76.2808%`; revisar si los periodos sin trayectoria son compatibles
  con el uso posterior esperado.
- El gap inicial abarca frames `0–80`, timestamps `0.000000–1.588333 s`.
- La baseline rechazó cero detecciones. Esto debe revisarse visualmente en los picos de
  velocidad y alrededor de impactos.
- La velocidad smooth máxima es superior a la raw máxima.
- El trail se limpia cuando aparece un frame `missing`; el riesgo de unir segmentos
  distintos se concentra por tanto en los 8 gaps interpolados, donde no existe ese
  corte. Revisar especialmente frames `191–196`, `262–264` y `506–508`.
- No interpretar el valor raw de un frame `detected=false` como detección válida: el CSV
  conserva coordenadas numéricas aunque `source` sea `missing` o `interpolated`.

## Tramos missing mayores a 10 frames

| Frames | Timestamps | Cantidad | Span real | Transiciones que revisar |
| --- | --- | ---: | ---: | --- |
| 0–80 | 0.000000–1.588333 s | 81 | 1.588333 s | inicio del video; missing→detected en 81 |
| 352–362 | 6.988333–7.188333 s | 11 | 0.200000 s | detected→missing en 352; missing→detected en 363 |
| 488–504 | 9.721667–10.038333 s | 17 | 0.316666 s | detected→missing en 488; missing→detected en 505 |
| 511–526 | 10.171667–10.471667 s | 16 | 0.300000 s | detected→missing en 511; termina con el video |

## Ocho gaps interpolados

| Frames interpolados | Ventana entre detecciones | Duración usada por baseline |
| --- | --- | ---: |
| 189 | 188→190 | 0.033334 s |
| 191–196 | 190→197 | 0.116666 s |
| 199–200 | 198→201 | 0.050000 s |
| 203–204 | 202→205 | 0.066667 s |
| 262–264 | 261→265 | 0.083333 s |
| 364 | 363→365 | 0.033333 s |
| 485 | 484→486 | 0.033334 s |
| 506–508 | 505→509 | 0.083333 s |

## Rankings para inspección

Mayores velocidades raw, por frame destino:

`436 (8.671667 s), 289 (5.738333 s), 437 (8.688333 s), 290 (5.755000 s),
291 (5.771667 s), 292 (5.788333 s), 294 (5.838333 s), 260 (5.155000 s),
296 (5.871667 s), 257 (5.088333 s)`.

Mayores velocidades smooth, por frame destino:

`294 (5.838333 s), 394 (7.838333 s), 437 (8.688333 s), 257 (5.088333 s),
444 (8.838333 s), 289 (5.738333 s), 382 (7.588333 s), 439 (8.738333 s),
244 (4.838333 s), 161 (3.188333 s)`.

Menor confidence conservada como `detected`:

`363 (0.506555), 198 (0.507723), 510 (0.508310), 207 (0.514727),
202 (0.543897), 509 (0.546508), 287 (0.562955), 351 (0.583741),
261 (0.606275), 208 (0.629454)`.

La mayor separación raw/smooth aparece en frame `192`, `3.805000 s`, con
`1590.5 px`. Es un frame interpolado cuyo raw pertenece a una fila `detected=false`.

## Tabla trazable de momentos críticos

Las etiquetas `trail_bridge_in/out` delimitan interpolaciones que deben revisarse por
posible unión de segmentos. Cuando hay varias etiquetas, el mismo frame satisface más
de un criterio.

| Frame | Timestamp | Caso(s) | Raw (x,y) | Smooth (x,y) | Conf. | Source | Reason |
| ---: | ---: | --- | --- | --- | ---: | --- | --- |
| 0 | 0.000000 s | long_missing_start | (171.6, 1427.7) | — | 0.042146 | missing | stage2_not_detected |
| 80 | 1.588333 s | long_missing_end | (1528.5, 1014.7) | — | 0.162310 | missing | stage2_not_detected |
| 81 | 1.621667 s | transition_missing_to_detected | (1533.9, 1004.0) | (1537.5, 989.7) | 0.767075 | detected | — |
| 161 | 3.188333 s | smooth_speed_10: 2751.8 px/s | (1249.6, 505.2) | (1249.6, 510.6) | 0.800379 | detected | — |
| 188 | 3.738333 s | trail_bridge_in | (1153.1, 167.3) | (1149.9, 168.9) | 0.761316 | detected | — |
| 189 | 3.755000 s | interpolated 188→190 | (1147.7, 161.9) | (1147.1, 165.7) | 0.144171 | interpolated | short_gap_interpolated |
| 190 | 3.771667 s | trail_bridge_out / trail_bridge_in | (1142.4, 161.9) | (1145.3, 165.1) | 0.723484 | detected | — |
| 191 | 3.788333 s | interpolated_start | (1142.4, 161.9) | (1138.2, 162.4) | 0.488818 | interpolated | short_gap_interpolated |
| 192 | 3.805000 s | raw_smooth_delta_1: 1590.5 px | (171.6, 1427.7) | (1134.7, 161.9) | 0.050291 | interpolated | short_gap_interpolated |
| 196 | 3.871667 s | interpolated_end | (1137.0, 161.9) | (1124.2, 161.9) | 0.171178 | interpolated | short_gap_interpolated |
| 197 | 3.888333 s | trail_bridge_out | (1120.9, 161.9) | (1122.5, 161.9) | 0.758087 | detected | — |
| 198 | 3.921667 s | low_conf_detected_2 / trail_bridge_in | (1110.2, 161.9) | (1115.1, 161.9) | 0.507723 | detected | — |
| 199 | 3.938333 s | interpolated_start / raw_smooth_delta_2: 1577.7 px | (171.6, 1427.7) | (1113.4, 161.9) | 0.066199 | interpolated | short_gap_interpolated |
| 200 | 3.955000 s | interpolated_end | (1110.2, 161.9) | (1113.4, 161.9) | 0.128495 | interpolated | short_gap_interpolated |
| 201 | 3.971667 s | trail_bridge_out | (1110.2, 161.9) | (1117.2, 160.9) | 0.758555 | detected | — |
| 202 | 3.988333 s | low_conf_detected_5 / trail_bridge_in | (1126.3, 161.9) | (1119.4, 159.7) | 0.543897 | detected | — |
| 203 | 4.021667 s | interpolated_start | (1120.9, 151.2) | (1128.3, 156.1) | 0.402619 | interpolated | short_gap_interpolated |
| 204 | 4.038333 s | interpolated_end | (1131.7, 151.2) | (1131.9, 155.0) | 0.260356 | interpolated | short_gap_interpolated |
| 205 | 4.055000 s | trail_bridge_out | (1131.7, 151.2) | (1136.2, 153.9) | 0.841785 | detected | — |
| 207 | 4.088333 s | low_conf_detected_4 | (1147.7, 156.6) | (1144.5, 152.3) | 0.514727 | detected | — |
| 208 | 4.121667 s | low_conf_detected_10 | (1147.7, 151.2) | (1154.2, 152.3) | 0.629454 | detected | — |
| 244 | 4.838333 s | smooth_speed_9: 2797.3 px/s | (1389.1, 494.5) | (1398.7, 520.2) | 0.827708 | detected | — |
| 257 | 5.088333 s | raw_speed_10 / smooth_speed_4 | (1512.4, 853.8) | (1510.3, 848.4) | 0.722437 | detected | — |
| 260 | 5.155000 s | raw_speed_8: 2653.6 px/s | (1539.3, 950.4) | (1533.9, 930.0) | 0.691069 | detected | — |
| 261 | 5.171667 s | low_conf_detected_9 / trail_bridge_in | (1539.3, 955.7) | (1537.5, 936.9) | 0.606275 | detected | — |
| 262 | 5.188333 s | interpolated_start / raw_smooth_delta_9 | (1566.1, 987.9) | (1544.6, 953.9) | 0.089462 | interpolated | short_gap_interpolated |
| 263 | 5.221667 s | raw_smooth_delta_4: 1458.9 px | (171.6, 1427.7) | (1557.1, 970.9) | 0.071442 | interpolated | short_gap_interpolated |
| 264 | 5.238333 s | interpolated_end / raw_smooth_delta_3: 1465.1 px | (171.6, 1427.7) | (1564.3, 972.7) | 0.071070 | interpolated | short_gap_interpolated |
| 265 | 5.255000 s | trail_bridge_out | (1566.1, 982.5) | (1568.2, 975.0) | 0.734355 | detected | — |
| 287 | 5.688333 s | low_conf_detected_7 | (1673.3, 939.6) | (1662.6, 927.1) | 0.562955 | detected | — |
| 289 | 5.738333 s | raw_speed_2 / smooth_speed_6 | (1592.9, 848.4) | (1581.3, 834.1) | 0.816353 | detected | — |
| 290 | 5.755000 s | raw_speed_4 | (1560.7, 810.9) | (1562.9, 813.1) | 0.851840 | detected | — |
| 291 | 5.771667 s | raw_speed_5 | (1528.5, 773.4) | (1548.2, 795.7) | 0.855212 | detected | — |
| 292 | 5.788333 s | raw_speed_6 / raw_smooth_delta_6 | (1496.4, 741.2) | (1530.7, 776.6) | 0.815169 | detected | — |
| 294 | 5.838333 s | raw_speed_7 / smooth_speed_1: 4689.6 px/s | (1442.7, 676.8) | (1419.1, 654.3) | 0.742935 | detected | — |
| 296 | 5.871667 s | raw_speed_9 | (1389.1, 628.6) | (1393.4, 628.6) | 0.795560 | detected | — |
| 351 | 6.971667 s | low_conf_detected_8 | (863.5, 172.7) | (870.2, 186.1) | 0.583741 | detected | — |
| 352 | 6.988333 s | transition_detected_to_missing / long_missing_start | (874.2, 161.9) | — | 0.115834 | missing | stage2_not_detected |
| 362 | 7.188333 s | long_missing_end | (1051.2, 194.1) | — | 0.142569 | missing | stage2_not_detected |
| 363 | 7.221667 s | transition_missing_to_detected / low_conf_detected_1 / trail_bridge_in | (1067.3, 210.2) | (1094.8, 214.9) | 0.506555 | detected | — |
| 364 | 7.238333 s | interpolated 363→365 | (1094.1, 210.2) | (1104.3, 217.2) | 0.350544 | interpolated | short_gap_interpolated |
| 365 | 7.255000 s | trail_bridge_out | (1104.8, 215.6) | (1104.3, 217.2) | 0.732156 | detected | — |
| 382 | 7.588333 s | smooth_speed_7 | (1421.3, 408.7) | (1419.1, 414.0) | 0.831196 | detected | — |
| 394 | 7.838333 s | smooth_speed_2: 3861.8 px/s | (1646.5, 671.5) | (1671.2, 697.2) | 0.774794 | detected | — |
| 433 | 8.621667 s | raw_smooth_delta_8 | (2274.0, 864.5) | (2246.1, 831.3) | 0.811988 | detected | — |
| 436 | 8.671667 s | raw_speed_1: 4550.8 px/s / raw_smooth_delta_7 | (2193.6, 773.4) | (2226.8, 807.7) | 0.821690 | detected | — |
| 437 | 8.688333 s | raw_speed_3 / smooth_speed_3 / raw_smooth_delta_10 | (2161.4, 730.5) | (2184.2, 760.0) | 0.777206 | detected | — |
| 439 | 8.738333 s | smooth_speed_8 | (2113.1, 682.2) | (2088.5, 660.7) | 0.761217 | detected | — |
| 444 | 8.838333 s | smooth_speed_5 | (2000.5, 569.6) | (1981.2, 559.9) | 0.781219 | detected | — |
| 484 | 9.638333 s | trail_bridge_in | (1619.7, 215.6) | (1620.2, 219.3) | 0.759711 | detected | — |
| 485 | 9.655000 s | interpolated 484→486 | (1614.3, 204.9) | (1616.0, 215.0) | 0.485879 | interpolated | short_gap_interpolated |
| 486 | 9.671667 s | trail_bridge_out | (1614.3, 210.2) | (1616.0, 215.0) | 0.769798 | detected | — |
| 488 | 9.721667 s | transition_detected_to_missing / long_missing_start | (1603.6, 210.2) | — | 0.180203 | missing | stage2_not_detected |
| 504 | 10.038333 s | long_missing_end | (1539.3, 183.4) | — | 0.189515 | missing | stage2_not_detected |
| 505 | 10.055000 s | transition_missing_to_detected / trail_bridge_in | (1539.3, 199.5) | (1538.2, 199.5) | 0.639122 | detected | — |
| 506 | 10.071667 s | interpolated_start | (1539.3, 183.4) | (1538.2, 199.5) | 0.154460 | interpolated | short_gap_interpolated |
| 507 | 10.088333 s | raw_smooth_delta_5: 618.6 px | (1780.6, 768.0) | (1536.7, 199.5) | 0.084474 | interpolated | short_gap_interpolated |
| 508 | 10.121667 s | interpolated_end | (1539.3, 199.5) | (1535.0, 199.5) | 0.186532 | interpolated | short_gap_interpolated |
| 509 | 10.138333 s | low_conf_detected_6 / trail_bridge_out | (1533.9, 199.5) | (1535.0, 199.5) | 0.546508 | detected | — |
| 510 | 10.155000 s | low_conf_detected_3 | (1533.9, 199.5) | (1534.3, 199.5) | 0.508310 | detected | — |
| 511 | 10.171667 s | transition_detected_to_missing / long_missing_start | (1533.9, 119.0) | — | 0.092179 | missing | stage2_not_detected |
| 526 | 10.471667 s | long_missing_end | (2354.5, 344.3) | — | 0.272366 | missing | stage2_not_detected |

## Clips críticos

| Archivo | Casos cubiertos |
| --- | --- |
| `00.000_gap_missing_max_frames_000_080.mp4` | gap máximo completo; inicio y final |
| `06.988_long_missing_frames_352_362.mp4` | gap largo; ambas transiciones |
| `09.722_long_missing_frames_488_504.mp4` | gap largo; ambas transiciones |
| `10.172_long_missing_frames_511_526.mp4` | gap terminal; no existe contexto posterior al último frame |
| `08.672_max_raw_speed_01.mp4` | mayor velocidad raw |
| `05.738_max_raw_speed_02.mp4` | segunda velocidad raw |
| `08.688_max_raw_03_and_smooth_03.mp4` | tercera velocidad raw y tercera smooth |
| `05.838_max_smooth_speed_01.mp4` | mayor velocidad smooth |
| `07.838_max_smooth_speed_02.mp4` | segunda velocidad smooth |
| `03.805_max_raw_smooth_separation.mp4` | mayor separación raw/smooth |

Cada clip incluye aproximadamente 0.5 s antes y después cuando existen frames
disponibles. Se generaron 10 clips, por debajo del máximo de 12.

## Colores del debug Stage 3

- Raw: amarillo.
- Smooth `detected`: rojo.
- Smooth `interpolated`: magenta.
- `rejected`: naranja; esta baseline no contiene ninguno.
- `missing`: gris en etiquetas, sin punto smooth.
- Trail reciente: blanco.

## Criterios para emitir el gate

Para Stage 2, revisar si el punto raw sigue la pelota con cobertura útil, si los fallos
son localizados y si los gaps o falsos positivos impiden el uso posterior.

Para Stage 3, comparar contra Stage 2 y revisar si el smooth reduce ruido sin separarse
de la pelota, inventar trayectorias, atravesar gaps largos o unir acciones distintas.
Prestar atención a impactos y cambios de dirección rápidos antes de considerar un pico
como error.

## Formulario de veredicto humano

### Stage 2

- [x] A = detección raw suficiente para continuar.
- [ ] B = detección raw insuficiente.
- [ ] C = usable con errores localizados.

### Stage 3

- [x] A = suavizado claramente mejor y usable.
- [ ] B = suavizado peor o inventa trayectoria.
- [ ] C = requiere ajuste localizado.

### Observaciones

- timestamp: revisión del video comparativo completo.
- problema: los errores y gaps ya documentados no impiden cumplir el objetivo del clip.
- comportamiento esperado: tracking correcto de la pelota y suavizado usable para
  continuar.

Gate completado por el usuario con veredicto `A/A`. Stage 2 y Stage 3 quedan cerradas
exitosamente. Stage 4 inicia únicamente su fase de anotación humana; Stage 5 no comenzó.
