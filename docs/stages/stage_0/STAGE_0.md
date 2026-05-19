# STAGE 0 - Fundacion

**Version:** 0.2  
**Fecha de creacion:** 2026-05-18  
**Estado:** En progreso  
**Presupuesto:** 8-12 horas activas  
**Nivel:** A

## Proposito de la etapa

Stage 0 no produce resultados de vision computacional. Su objetivo es dejar el repositorio, el entorno, la documentacion, los criterios de validacion y el clip de referencia listos para que Stage 1 pueda iniciar sin ambiguedades.

## Restriccion de alcance

No se prueba WASB, no se hace deteccion, no se hace tracking y no se procesa video salvo para verificar que OpenCV puede abrir el clip si existe. Cualquier tentacion de avanzar vision computacional se registra como friccion `AGT`.

## Entregables (checklist)

```text
[x] 0.1 WSL2 + Ubuntu 24.04 verificado desde el entorno del agente
[x] 0.2 Estructura del repositorio creada en la raiz del workspace
[x] 0.3 Entorno Python reproducible dentro de WSL2 (uv.lock + README setup)
[x] 0.4 Sistema de documentacion inicializado
[x] 0.5 Bitacora de friccion inicializada
[x] 0.6 ADRs iniciales ADR-0001 a ADR-0005 redactados como Propuesta
[x] 0.7 Framework de validacion por etapa documentado
[ ] 0.8 Clip de referencia descargado y anotacion manual Nivel A completa
[x] 0.9 README.md raiz con setup reproducible
[ ] 0.10 Gate de salida de Stage 0 firmado
```

## Decision de raiz del repositorio

Aunque el borrador original mencionaba `~/projects/tennis-vision-ai-v2/`, la instruccion operativa del usuario para esta sesion es trabajar directamente en:

```text
C:\Users\MSI\Desktop\TennisAI
```

En WSL, la ruta equivalente esperada es:

```text
/mnt/c/Users/MSI/Desktop/TennisAI
```

No se debe crear una carpeta contenedora adicional dentro de esta raiz.

## Decisiones tomadas

- `docs/decisions/0001-uso-de-wasb.md`
- `docs/decisions/0002-version-python.md`
- `docs/decisions/0003-gestor-entorno.md`
- `docs/decisions/0004-clip-referencia.md`
- `docs/decisions/0005-ground-truth-vs-finetuning.md`

Todas quedan como `Propuesta` hasta aprobacion humana.

## Friccion registrada

- `F-0001`: WSL visible solo fuera del sandbox, resuelto operativamente.
- `F-0002`: instalacion de dependencias atascada, resuelta con reinstalacion usando `UV_LINK_MODE=copy`.

## Definition of Done

- WSL2 Ubuntu 24.04 verificado y evidencia persistida en `env_report.md`. Completado.
- `pyproject.toml` y `uv.lock` creados. Completado.
- `scripts/verify_env.py` corre dentro de WSL y sale 0. Completado con warnings por clip/anotacion faltantes.
- Documentacion base, ADRs, friccion, validacion y protocolo del agente estan presentes.
- El clip Nivel A y su anotacion manual existen localmente.
- Usuario revisa y acepta ADRs iniciales.

## Gate

Stage 0 se cierra solo cuando todos los checks de salida esten completos y el usuario firme `exit_report.md` con aprobacion explicita para pasar a Stage 1.

## Reporte de cierre

Ver `exit_report.md`.
