# ROADMAP - Tennis Vision AI v2

**Version:** 0.2  
**Fecha de creacion:** 2026-05-18  
**Estado:** Borrador inicial - revisar antes de cerrar Stage 0

## 1. Objetivo del proyecto

Construir un sistema que, dado un video de broadcast de tenis con camara fija, genere dos representaciones 2D del rally:

- Vista superior: trayectoria de la pelota proyectada sobre el plano de la cancha.
- Vista lateral: trayectoria con altura inferida fisicamente entre botes consecutivos.

El sistema opera sobre clips reales de torneos ATP/WTA y se valida en tres niveles progresivos de generalizacion.

## 2. Modelo operativo: agente + usuario

### Rol del agente

- Operacion de consola y filesystem dentro del entorno de trabajo.
- Instalacion de dependencias mediante gestores de paquetes.
- Edicion de archivos, commits, estructura de repositorio.
- Ejecucion de scripts y tests.
- Llenado de plantillas de documentacion.
- Reporte al usuario al final de cada subseccion con evidencia.

### Rol del usuario

- Pasos one-off que requieran GUI nativo o privilegios de administrador.
- Validacion humana en cada gate.
- Decision final en cualquier pivote.
- Anotacion manual y conocimiento de dominio.
- Aprobar ADRs antes de marcarlos como `Aceptada`.

## 3. Principios operativos

1. Una etapa, un artefacto, un gate.
2. Validacion humana explicita en cada gate.
3. Friccion se mide, no se padece.
4. Modelos plug-and-play o nada.
5. El sistema legacy es referencia negativa.
6. El usuario es persona de dominio, no ingeniero de ML.
7. Validacion en tres niveles de generalizacion: A, B, C.
8. Agente conduce, usuario valida.

## 4. Niveles de generalizacion

### Nivel A - Sandbox supervisado

- Clip: Madrid Open, rally R1.
- Inputs: narracion completa del rally.
- Prueba: tracking, proyeccion y render cuando los eventos son dados como input.

### Nivel B - Generalizacion dentro de escena

- Clip: Madrid Open, rally R2.
- Inputs: ninguno adicional.
- Prueba: deteccion automatica de eventos y generalizacion a rally no visto.

### Nivel C - Generalizacion a escena distinta

- Clip: Hamburg Open.
- Inputs: court corners nuevos.
- Prueba: generalizacion real a camara, iluminacion y fondo distintos.

## 5. Etapas

### Stage 0 - Fundacion

Entorno reproducible, documentacion viva, dataset de prueba con ground truth, bitacoras y modelo operativo.

Gate: `scripts/verify_env.py` corre sin fallas criticas y el usuario puede reabrir el repo sin mirar el chat.

### Stage 1 - Calibracion de cancha

Calcular homografia H desde pixeles de cancha a coordenadas reales en metros.

Gate: inspeccion visual humana del render y error de reproyeccion dentro de tolerancia.

### Stage 2 - Deteccion de pelota

Instalar y correr WASB-SBDT con pesos preentrenados de tenis.

Gate: video con deteccion sobreimpresa y metricas contra ground truth.

### Stage 3 - Trayectoria temporalmente suavizada

Convertir detecciones por frame en trayectoria continua con Kalman, rechazo de outliers e interpolacion corta.

Gate: validacion visual de trayectoria sin discontinuidades.

### Stage 4 - Deteccion de eventos

Nivel A lee `narrative_events`; niveles B/C detectan botes y golpes automaticamente.

Gate: eventos generados sin perdida en Nivel A; precision/recall en B/C.

### Stage 5 - Vista superior 2D

Proyectar la trayectoria a cancha y renderizar.

Gate: validacion visual de lado correcto, cruces de red coherentes y trayectoria dentro de cancha.

### Stage 6 - Vista lateral 2D con altura inferida

Renderizar parabolas entre botes usando fisica basica.

Gate: parabolas conectan botes y alturas fisicas plausibles.

### Stage 7 - Metricas y validacion final del nivel

Reporte final del nivel contra ground truth y estimacion honesta de generalizacion.

Gate: lectura humana y decision de pasar al siguiente nivel.

## 6. Gobernanza de cambios

Cualquier modificacion al roadmap requiere ADR, incremento de version y registro de friccion si fue forzada por blocker.

## 7. Criterios de fracaso del proyecto completo

- Friccion acumulada mayor a 40 horas sin completar Stage 2 en Nivel A.
- Ningun detector de pelota alcanza tasa mayor o igual a 50% en Stage 2 Nivel A.
- Stage 1 no logra homografia con error menor a 10 px tras dos intentos completos.

## 8. Referencias rapidas

- Stage 0: `docs/stages/stage_0/STAGE_0.md`
- Friccion: `docs/friction/FRICTION_LOG.md`
- Decisiones: `docs/decisions/`
- Legacy: `legacy/POSTMORTEM.md`
