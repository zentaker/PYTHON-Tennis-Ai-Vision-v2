# ROADMAP - TennisAI Core Product

**Version:** 0.3
**Fecha de creacion:** 2026-05-18
**Fecha de reconciliacion:** 2026-07-13
**Estado:** CORE_STAGE2C_WORKER_RUNTIME_FOUNDATION_ACCEPTED

The experimental Stage 5B branch is archived research. The official product path is
the TennisAI Training Session Analyzer and its versioned Analysis Bundle.

Core Stage 2A Session Platform is accepted and its Session API V1 contract is
frozen with gates `STAGE2A_LAYERED_API_ARCHITECTURE_PASSED`,
`STAGE2A_BROWSER_UPLOAD_RUNTIME_AUDIT_PASSED`,
`STAGE2A_PERSISTENCE_FOUNDATION_PASSED`, and
`STAGE2A_FINAL_CONTRACT_PRECISION_PATCH_IMPLEMENTED`.
Release gates are `CHATGPT_CORE_STAGE2A_RELEASE_AUDIT_PASSED`,
`SESSION_PLATFORM_API_V1_FROZEN`, and `CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`.
The additive Core Stage 2B analysis-job orchestration contract is accepted and
frozen. Core Stage 2C adds the production-shaped worker runtime foundation;
its contract fixture is explicit, opt-in and disabled by default, and it does
not connect a real vision processor or execute inference.

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
- [ ] Stage 5B - Reconstrucción física X,Y,Z. v1/v2 rechazados por gate humano; no reabrir sin evidencia.
- [ ] Stage 5C - Vista superior derivada de X,Y. No iniciada.
- [ ] Stage 6 - Vista lateral derivada de distancia,Z. No iniciada.
- [ ] Stage 7 - Metricas y validacion final. No iniciada.
- [x] P1 → Analytics - Cinco contactos aceptados producen cinco registros schema-valid.
- [x] Core Stage 2A - Session Platform foundation (`CORE_STAGE2A_SESSION_PLATFORM_ACCEPTED`).
- [x] Core Stage 2B - Analysis job orchestration (`CORE_STAGE2B_ANALYSIS_ORCHESTRATION_ACCEPTED`).
- [x] Core Stage 2C - Worker runtime foundation (`CORE_STAGE2C_WORKER_RUNTIME_FOUNDATION_ACCEPTED`).

Stage 0 se considera funcionalmente cerrada. Su cierre documental fue reconciliado
retrospectivamente despues de confirmar en Git el avance y los gates posteriores.

### Productización Core — Stage 0B

Estado: cerrada con `STAGE0B_FINAL_HUMAN_GATE_PASSED` y contrato de transporte
congelado como `ANALYSIS_BUNDLE_V1_TRANSPORT_CONTRACT_FROZEN`. El freeze cubre el
layout del bundle, manifest, envelopes de sesión y rallies, estados de packaging,
checksums, fingerprint, perfiles y contrato CLI. Los schemas detallados de rally,
events, ball tracks, player tracks, poses, court map, metrics y tactical patterns
serán contratos versionados independientes y no deben romper Analysis Bundle V1.

### Core Stage 1A — Single Rally Contract & Existing-Output Import

Estado: `CORE_STAGE1A_SYNTHETIC_IMPORT_ACCEPTED`; gates:
`STAGE1A_IMPORTER_IMPLEMENTATION_ACCEPTED`, `STAGE1A_COURT_CONTRACT_CORRECTED`
y `CORE_STAGE1A_SYNTHETIC_IMPORT_GATE_PASSED`.
La capa read-only
convierte outputs existentes en un rally canónico y un Analysis Bundle V1 válido.
El fixture contractual determinista contiene un rally, cinco observaciones, tres
eventos, un contacto y un bote. El video real de referencia y un track Stage 3
versionado no están disponibles localmente (`REAL_REFERENCE_VIDEO_MISSING` y
`REAL_STAGE3_BALL_TRACK_MISSING`), por lo que no se presenta un bundle real ni se
ejecuta inferencia. El gate real es `STAGE1A_REAL_RALLY_GATE_BLOCKED` y la
evidencia real está bloqueada como `REAL_SINGLE_RALLY_EVIDENCE_GATE_BLOCKED`.
Los schemas detallados siguen siendo candidatos hasta una auditoría de assets
reales.

### Core Stage 1B — Real Single Rally Bundle Candidate

Estado: `CORE_STAGE1B_REAL_SINGLE_RALLY_CANDIDATE_READY_FOR_REVIEW`. La referencia
real `nivel_a2_01` (video externo, track Stage 3 ignorado, timestamps VFR, eventos
Stage 4 y calibración 2D existente) quedó alineada mediante 22 checks explícitos,
sin copiar el video ni ejecutar inferencia. El candidato determinista contiene un rally, 527 observaciones (383
visibles, 19 interpoladas y 125 no visibles), 10 eventos (4 contactos, 5 botes y
1 saque), y `surface: unknown`. Los estados de sesión y rally son `partial` para
preservar la ausencia de observaciones. El bundle derivado no contiene video ni
modelos; la auditoría de evidencia, el gate de datos y el release audit están
pasados. El bundle real está aceptado y listo para TennisWebAI Stage 0B; no hay
claim 3D ni ejecución de inferencia.

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

Estado: v1 y v2 `REJECTED_BY_HUMAN_GATE`. No se ejecutará una v3 exclusivamente
matemática; el siguiente trabajo es P1 player-aware tras el gate de proveedor GPU.

### Stage 5C - Vista superior derivada

Renderizar X,Y de la trayectoria 3D aprobada.

Estado: no iniciada.

### Stage 6 - Vista lateral 2D

Renderizar distancia,Z de la trayectoria 3D aprobada.

Estado: no iniciada.

### Stage 7 - Metricas y validacion final

Consolidar metricas, ejemplos, limitaciones y decision sobre el siguiente nivel.

Estado: no iniciada. Gate: aprobacion humana del reporte final.

### Core Stage 2C - Worker runtime foundation

Estado: aceptada y preparada para merge como
`CORE_STAGE2C_WORKER_RUNTIME_FOUNDATION_ACCEPTED`. Los gates aceptados son
`STAGE2C_FAIL_CLOSED_WORKER_RUNTIME_PASSED`,
`STAGE2C_ATTEMPT_SCOPED_PUBLICATION_PASSED`,
`STAGE2C_LEASE_LOSS_RECOVERY_PASSED`,
`STAGE2C_WORKSPACE_BOUNDARY_SECURITY_PASSED`,
`STAGE2C_RUNTIME_EVIDENCE_AUDIT_PASSED`, y
`CHATGPT_CORE_STAGE2C_FINAL_RELEASE_AUDIT_PASSED`.

La evidencia auditada corresponde al head
`c1b6cfdbd78a693b7d2997dd4af5ff959e4b3a81`: 34 tests unitarios, 1 escenario
Compose y 2 escenarios PostgreSQL/MinIO. El runtime es production-shaped,
fail-closed y publica por intento; el fixture contractual es explícito,
opt-in y está deshabilitado por defecto. No hay procesador de visión real,
inferencia, vídeo, GPU, cloud ni gasto.

Deuda no bloqueante:
`STAGE2C_AMBIGUOUS_STORAGE_WRITE_GARBAGE_COLLECTION_DEBT`. Un PUT S3 puede
completarse en servidor aunque el cliente reciba una excepción de transporte;
los namespaces por intento preservan la corrección, y una futura etapa de
garbage collection deberá retirar objetos de intentos no referenciados.

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
