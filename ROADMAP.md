# ROADMAP - Tennis Vision AI v2

**Version:** 0.3
**Fecha de creacion:** 2026-05-18
**Fecha de reconciliacion:** 2026-07-13
**Estado:** Activo - Stage 5B v3 rechazado; v3.1 corrección parcial

La pasada de datos activa es Nivel A2. Stage 1–4 están cerradas con gates aprobados y la
la auditoría de cámara Stage 5A terminó con `READY_FOR_STAGE_5B` tras evaluar Stage 5A.1.
La pasada Madrid R1
permanece cerrada como evidencia histórica.

## 1. Objetivo

Construir un sistema que, dado un video de broadcast de tenis con camara fija, genere:

- una vista superior con la trayectoria proyectada sobre la cancha;
- una vista lateral con altura inferida fisicamente entre botes consecutivos.

## 2. Progreso

- [x] Stage 0 - Fundacion y entorno reproducible.
- [x] Stage 1 - Calibracion de cancha.
- [x] Stage 2 - Deteccion de pelota con WASB, con limitaciones conocidas.
- [x] Stage 3 - Trayectoria suavizada y gate visual.
- [x] Stage 4 - Eventos. A2 cerrada exitosamente con gate humano A.
- [x] Stage 5A - Calibración de cámara 3D y observabilidad. Cerrada con referencia refinada.
- [x] Stage 5A.1 - Referencia vertical de red. Cuatro clics y evaluación cerrados.
- [ ] Stage 5B - V3 rechazado; v3.1 PARTIAL por p95 y coordenadas far.
- [ ] Stage 5C - Vista superior derivada de X,Y. No iniciada.
- [ ] Stage 6 - Vista lateral derivada de distancia,Z. No iniciada.
- [ ] Stage 7 - Metricas y validacion final. No iniciada.
- [x] P1 → Analytics - Cinco contactos aceptados producen cinco registros schema-valid.

Stage 0 se considera funcionalmente cerrada. Su cierre documental fue reconciliado
retrospectivamente despues de confirmar en Git el avance y los gates posteriores.

## 3. Niveles de generalizacion

### Nivel A - Sandbox supervisado

- Clip: Madrid Open, rally R1.
- Inputs: narracion y eventos anotados manualmente.
- Prueba: tracking, proyeccion y render con eventos dados como input.
- Stage 4: normaliza `narrative_events`; no detecta eventos automaticamente.

### Nivel B - Generalizacion dentro de escena

- Clip: Madrid Open, rally R2.
- Inputs adicionales: ninguno.
- Prueba: deteccion automatica de eventos y generalizacion a rally no visto.
- Stage 4: debe detectar golpes y botes automaticamente.

### Nivel C - Generalizacion a escena distinta

- Clip: Hamburg Open.
- Inputs adicionales: nuevos court corners.
- Prueba: generalizacion a otra camara, iluminacion y fondo.
- Stage 4: debe conservar la deteccion automatica de eventos.

## 4. Etapas y gates

### Stage 0 - Fundacion

Entorno, estructura, documentacion, ADRs, bitacora y modelo operativo reproducibles.

Estado: cerrada funcionalmente; reconciliacion documental completada en v0.3.

### Stage 1 - Calibracion de cancha

Homografia pixel -> coordenadas reales obtenida mediante UI web de clic directo.

Estado: cerrada. Gate numerico y visual aprobado.

### Stage 2 - Deteccion de pelota

WASB-SBDT con pesos preentrenados produjo detecciones y overlay del clip Nivel A.

Estado: cerrada con limitaciones conocidas y validacion visual humana.

### Stage 3 - Trayectoria temporalmente suavizada

Rechazo de outliers, interpolacion corta y media movil sobre detecciones 2D.

Estado: cerrada y taggeada como `v1.3.0`. Gate visual aprobado.

### Stage 4 - Deteccion y normalizacion de eventos

Nivel A lee y valida `narrative_events` de `manual_annotation.json`, sin inventar ni
detectar eventos. Niveles B/C incorporaran deteccion automatica de botes y golpes.

Estado: cerrada exitosamente para A2. Gate humano final: A.

### Stage 5A - Calibración y observabilidad de cámara 3D

Auditar la homografía, construir un modelo pinhole assumption-based, medir sensibilidad
vertical y segmentar vuelos. No reconstruye todavía la pelota en 3D.

Estado: cerrada con calibración vertical refinada; readiness `READY_FOR_STAGE_5B`.

### Stage 5B - Reconstrucción física X,Y,Z

Ajustar por segmento X,Y,Z con reproyección, restricciones Z=0 en botes y dinámica
balística. El diseño está documentado, pero la implementación aún no comenzó.

Estado: v1 y v2 `REJECTED_BY_HUMAN_GATE`. V3 player-aware produjo un candidato con
cinco contactos P1, nueve vuelos, cinco botes, tres hipótesis e incertidumbre explícita.
V3.1 fue `STAGE5B_V31_REJECTED_BY_HUMAN_GATE`: contactos y coordenadas far no
plausibles, p95 fuera de gate, homografía audit-only y métrica de ambigüedad incompleta.
Stage 5A.2 debe corregir el plano de suelo antes de otra reconstrucción XYZ.
Analytics y velocidad 3D real continúan bloqueados.

Stage 5A.2 fue `STAGE5A2_REJECTED_BY_HUMAN_GATE_EVIDENCE_INSUFFICIENT`: la evidencia
recortaba eventos far, confundía líneas modelo con detecciones, usaba geometría
correlacionada e incertidumbre incompleta, y carecía de soporte temporal sobre frames
reales. Stage 5A.2B debe validar temporalmente sin imponer un límite de 5 m. XYZ no se
reejecutó.

Stage 5A.2B procesó frames reales y quedó
`STAGE5A2B_REJECTED_BY_HUMAN_GATE_TRACKER_INVALID`. El gate visual de los cinco frames
de contacto pasó, incluidas posiciones far de 6–8 m; el tracker temporal fue rechazado
por drift imposible. Stage 5A.2C debe usar flujo secuencial entre frames adyacentes.

Stage 5A.2C ajustó 15 familias con 61 segmentos reales y rastreó secuencialmente frames
adyacentes. Produjo cinco anchors; ev_001/005/007 están accepted y ev_003/009 unresolved
por p95 local. Estado `STAGE5A2C_CONTACT_GROUND_ANCHORS_PARTIAL`; XYZ sigue bloqueado.

El gate humano posterior aprobó los cinco anchors estáticos y mantuvo la validación de
movimiento temporal como parcial. Stage 5B v3.2 puede consumir coordenadas estáticas e
incertidumbre total, nunca trayectorias temporales del jugador.

Stage 5B v3.2 consumió los cinco anchors v4 y 314 observaciones en CPU. El resultado
es `STAGE5B_V32_PARTIAL`: mediana 7.0635 px, p95 27.4726 px, residual máximo de
contacto 8.3071 m y de bote 0.01782 m. El gate humano está pendiente y Analytics
continúa bloqueado.

El gate humano rechazó v3.2 como `EVENT_TO_SEGMENT_CONTACT_CONSTRAINT_FAILED`:
el residual de contacto máximo fue 8.3071 m y la evidencia omitió los peores frames.
V3.3 debe pasar primero topología y factibilidad de endpoints; no puede compensar un
fallo topológico mediante el ajuste físico.

### Stage 5C - Vista superior derivada

Renderizar X,Y de la trayectoria 3D aprobada.

Estado: no iniciada.

### Stage 6 - Vista lateral 2D

Renderizar distancia,Z de la trayectoria 3D aprobada.

Estado: no iniciada.

### Stage 7 - Metricas y validacion final

Consolidar metricas, ejemplos, limitaciones y decision sobre el siguiente nivel.

Estado: no iniciada. Gate: aprobacion humana del reporte final.

### P1 → Analytics

El adaptador read-only consume los resultados P1 aceptados mediante archivos
serializados. La ejecución real asoció cinco contactos con timestamps, tracks, poses,
posiciones y evidencia de muñeca, y produjo cinco registros válidos. Solo una etiqueta
manual Stage 4 es informativa; las dimensiones restantes conservan `unknown`.
Kinematics permanece bloqueado por `APPROVED_STAGE5B_XYZ_REQUIRED`; no se validó el
rally completo ni velocidad real de pelota. GPU, cloud y gasto: cero.

## 5. Modelo operativo

El agente implementa, valida y documenta. El usuario aporta conocimiento de dominio,
anotacion manual, artefactos no versionados y la decision en cada gate humano.

Principios:

1. Una etapa, un artefacto, un gate.
2. No mover criterios silenciosamente.
3. No inventar datos para completar evidencia.
4. Modelos plug-and-play o decision explicita de pivote.
5. Friccion mayor a 15 minutos se registra.
6. Stage 5 no comienza hasta cerrar el gate de Stage 4.

## 6. Gobernanza

Los cambios de alcance o tecnologia requieren ADR. Los artefactos pesados permanecen
fuera de Git y deben transferirse con un inventario verificable entre maquinas.

## 7. Referencias

- Stage 0: `docs/stages/stage_0/exit_report.md`
- Stage 3: `docs/stages/stage_3/exit_report.md`
- Stage 4: `docs/stages/stage_4/STAGE_4.md`
- Validacion: `docs/validation/VALIDATION_FRAMEWORK.md`
- Friccion: `docs/friction/FRICTION_LOG.md`
- Decisiones: `docs/decisions/`
