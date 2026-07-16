# Stage 5A.1 — Herramienta de referencia vertical

**Estado:** `TOOL_READY_PENDING_HUMAN_CLICKS`  
**Stage 5A:** `NEEDS_VERTICAL_REFERENCE`  
**Stage 5B:** `NOT_STARTED`

Stage 5A demostró que la homografía de suelo es válida, pero los modelos monoculares
equivalentes divergen hasta 117.5 px en referencias verticales. Esta pasada añade la
intervención humana mínima: cuatro clics sobre el frame canónico aprobado. No se modifica
el anotador de eventos ni Stage 4.

## Uso

```bash
uv run python -m tools.vertical_reference_app --clip-id nivel_a2_01
```

La aplicación abre `http://127.0.0.1:8766/` y carga automáticamente el frame aprobado.
La única secuencia visible es:

1. suelo bajo el centro de la red;
2. parte superior de la red en el centro;
3. base de un poste visible;
4. parte superior del mismo poste;
5. revisar y guardar.

Las alturas reglamentarias están incorporadas: centro `0.914 m`, poste `1.07 m`. La
interfaz no solicita rutas, archivos, matrices, coordenadas ni alturas.

Incluye ajuste a ventana, zoom 100/150/200/300/500 %, pan, lupa de 220×220 px,
crosshair, undo y reset. Las coordenadas se guardan en píxeles canónicos `2746×1536`,
con transformación contain, offset, pan, zoom y `devicePixelRatio` explícitos.

La base del poste se clasifica contra las posiciones reglamentarias y se rechaza si no
es coherente o ambigua. Las validaciones comprueban bounds, duplicados, orden vertical,
coherencia de cada pareja base/top, plano de red y correspondencia del mismo poste.

## Persistencia y recalibración

Cada clic genera el borrador ignorado
`outputs/nivel_a2_01/stage_5a1/vertical_reference_draft.json`. Al guardar se crea
`data/clips/nivel_a2_01/vertical_reference.json`, sin rutas absolutas ni video, y un
backup ignorado con timestamp. El backend prepara una optimización pinhole conjunta con
los ocho puntos de suelo y los cuatro puntos no coplanares. También deja preparados el
modelo refinado, el reporte, el overlay y el readiness bajo `outputs/.../stage_5a1/`.

La referencia no se presenta como exacta: se evalúan errores, degradación del plano,
profundidad positiva y estabilidad ante jitter de ±1/±2/±3 px. Los estados posteriores
permitidos son `READY_FOR_STAGE_5B`, `MARGINAL_VERTICAL_CALIBRATION`,
`STILL_NEEDS_VERTICAL_REFERENCE` e `INVALID_HUMAN_REFERENCE`. Stage 5B no se inicia
automáticamente.

## Self-test

`GET /api/self-test` devuelve `core_self_test=PASS` con 28 comprobaciones antes de
desbloquear la interfaz: inputs, hashes, resolución, homografía, modelo, candidatos, sistema de
coordenadas, transformación de canvas, zoom/pan/DPR, autosave/restore, clasificación,
aislamiento del anotador y ausencia de Stage 5B/GPU.

El `browser_e2e_test` se ejecuta aparte sobre una instancia real de Chrome y una sesión
descartable; solo se considera entrega lista cuando ambos resultados son correctos.

No se usan RunPod, SSH, GPU, CUDA, PyTorch, WASB ni automatización de mouse.
