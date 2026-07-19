# Validation Framework

## Stage 5A.2 extended ground plane

The automatic calibration gate requires court-line median/p95 <=4/10 px,
homography/camera player disagreement <=1 m (otherwise unresolved), finite
identity-stable positions, and far-Y uncertainty <=1.5 m. The general region allows
the doubles court plus documented lateral margin and 5 m behind either baseline.
Human observations are evaluation references only. Current automatic status is
`PARTIAL`; human approval is pending and XYZ remains blocked.

Regla fuerte: los criterios de exito se escriben antes de iniciar cada etapa. Si un criterio resulta inadecuado, no se mueve la meta silenciosamente; se cierra la etapa y se reabre con criterios nuevos.

## Stage 0 - Validacion

### Criterios de exito

- `scripts/verify_env.py` corre dentro de WSL2 Ubuntu 24.04 y termina con exit code 0.
- La estructura del repositorio existe en la raiz del workspace, sin carpeta contenedora adicional.
- Los ADR-0001 a ADR-0005 existen y estan revisados por el usuario.
- El clip Nivel A y `manual_annotation.json` existen localmente.

### Criterios de falla

- WSL2 Ubuntu 24.04 no puede ser accesible por el agente.
- No se puede generar `uv.lock` en el entorno objetivo.
- Falta informacion para ubicar o anotar el clip de referencia.

### Evidencia que debe acompanar al cierre

- `docs/stages/stage_0/env_report.md`
- `uv.lock`
- Output resumido de `python scripts/verify_env.py`
- `docs/stages/stage_0/exit_report.md`

### Quien valida

Humano. Validacion firmada en `exit_report.md`.

## Stage 1 - Validacion

### Criterios de exito

- Error medio de reproyeccion menor a 5 px sobre 8 puntos de calibracion.
- Error sobre puntos independientes menor a 10 px.
- Render de cancha 2D visualmente coherente.

### Criterios de falla

- No se logra error menor a 10 px tras dos intentos completos.
- El frame de referencia no contiene puntos suficientes o la camara no es fija.

### Evidencia que debe acompanar al cierre

- JSON con matriz H y puntos usados.
- Reporte de error de reproyeccion.
- Imagen renderizada de cancha 2D.

### Quien valida

Humano. Validacion visual firmada en el reporte de cierre.

## Stage 2 - Validacion

### Criterios de exito

- Deteccion mayor o igual a 75% contra 20-50 posiciones manuales.
- Falsos positivos egregios mayores a 100 px por debajo de 5%.
- Inferencia completa del clip en menos de 10 minutos.

### Criterios de falla

- WASB menor a 60% sin ruta clara de mejora plug-and-play.
- Ningun detector supera 50% en Nivel A.

### Evidencia que debe acompanar al cierre

- CSV de detecciones.
- Video con deteccion sobreimpresa.
- Reporte de metricas contra ground truth.

### Quien valida

Humano, con apoyo de metricas.

## Stage 3 - Validacion

### Criterios de exito

- Trayectoria sin discontinuidades visibles.
- Saltos entre frames coherentes con velocidad fisica.
- CSV marca `detected`, `interpolated` y `rejected`.

### Criterios de falla

- La trayectoria suavizada inventa tramos largos sin evidencia.
- El filtro oculta falsos positivos egregios en vez de rechazarlos.

### Evidencia que debe acompanar al cierre

- CSV suavizado.
- Video con trayectoria sobreimpresa.
- Reporte de parametros del filtro.

### Quien valida

Humano.

## Stage 4 - Validacion

### Criterios de exito

- Nivel A: todos los eventos del JSON se convierten sin perdida.
- Nivel B/C: precision y recall mayores o iguales a 90% con tolerancia de +-3 frames.

### Criterios de falla

- En Nivel A se altera la narracion manual.
- En Nivel B/C no se distinguen golpes y botes de forma confiable.

### Evidencia que debe acompanar al cierre

- Archivo de eventos normalizado.
- Reporte de comparacion contra anotacion.
- Timeline y overlay de revision sobre datos reales.
- Confirmacion de que el numero y orden de eventos coincide con `narrative_events`.

### Quien valida

Humano.

## Stage 5 - Validacion

### Criterios de exito

- Botes del lado correcto.
- Trayectorias cruzan la red de forma coherente.
- Nada se sale del rectangulo de cancha.

### Criterios de falla

- Homografia o trayectoria producen puntos fuera de cancha sin explicacion.
- La vista superior contradice eventos manuales.

### Evidencia que debe acompanar al cierre

- PNG/MP4 de vista superior.
- Reporte breve de coherencia visual.

### Quien valida

Humano.

## Stage 6 - Validacion

### Criterios de exito

- Parabolas conectan botes sin discontinuidades.
- Alturas maximas estimadas entre 1 m y 5 m.
- La visualizacion indica que la altura es inferida, no medida.

### Criterios de falla

- Alturas fisicamente imposibles.
- Tramos sin botes suficientes se presentan como medicion real.

### Evidencia que debe acompanar al cierre

- PNG/MP4 de vista lateral.
- Parametros fisicos usados.

### Quien valida

Humano.

## Stage 7 - Validacion

### Criterios de exito

- Reporte final del nivel con metricas y ejemplos visuales.
- Estimacion honesta de generalizacion al siguiente nivel.

### Criterios de falla

- El reporte omite fallas conocidas.
- No hay evidencia suficiente para decidir pasar de nivel.

### Evidencia que debe acompanar al cierre

- `docs/reports/FINAL_REPORT_LEVEL_X.md`
- Tabla de metricas.
- Lista de limitaciones.

### Quien valida

Humano.
