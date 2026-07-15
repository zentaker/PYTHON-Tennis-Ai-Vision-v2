# Reporte de ejecución RunPod — Stage 2 A2

**Fecha:** 2026-07-15  
**Estado:** `BLOCKED_CONNECTION` / `BLOCKED_TRANSFER`

## Alcance de esta pasada

Se auditó y preparó la integración Mac → RunPod para el Pod temporal con RTX A4500 y
SSH proxy básico. No se ejecutó inferencia, Stage 3 ni Stage 5.

## Estado local

- Git limpio al inicio, `main` y `origin/main` en
  `e9fe90822c1d87d1530bf7b56c40943ce13e6842`.
- Baseline: 111 tests, Ruff y compileall correctos; smoke test correcto.
- Video: `data/clips/nivel_a2_01/source.mp4`, 24,944,366 bytes.
- SHA-256 local:
  `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- Sidecar: 527 timestamps válidos, rango `0.000000–10.471667 s`, estrictamente
  monótonos.

## Conexión

La conexión proxy llegó al endpoint SSH, pero no pudo autenticarse porque la ruta de
llave configurada no existe en este Mac. Solo existe `known_hosts` bajo `~/.ssh`; no se
leyó contenido de ninguna llave ni se probaron identidades alternativas.

Por ello permanecen sin verificar directamente:

- GPU, VRAM, driver y CUDA del Pod;
- escritura en `/workspace`;
- checkout remoto;
- presencia remota de WASB-SBDT y checkpoint;
- SHA-256 remoto del video.

## Transferencia

`runpodctl` no estaba instalado. El intento autorizado de instalación con Homebrew se
detuvo porque macOS exige aceptar primero la licencia de Xcode mediante una acción
administrativa interactiva. No se usó un binario alternativo, API key, SCP ni rsync.

## Cambios preparados localmente

- Helper `scripts/gpu/runpod_ssh.sh` para `proxy` y `exposed_tcp`.
- Configuración privada proxy con permisos `600`, fuera del repositorio.
- Downloader con rutas separadas `runpodctl` y SCP, backups y SHA-256.
- Bootstrap/environment gate explícito para 527 timestamps VFR.
- Tests del proxy sin puerto, TCP con puerto, configuración incompleta y garantía de que
  proxy no invoca SCP.

Estos cambios no se han commiteado ni publicado. El Pod continúa fijado conceptualmente
al SHA publicado anterior hasta que exista autorización para commit/push.

## Gate

No se cumplen las condiciones de `READY_FOR_INFERENCE`. La próxima pasada debe:

1. crear o restaurar la llave privada correspondiente y registrar su clave pública en
   RunPod;
2. aceptar la licencia de Xcode e instalar/verificar `runpodctl` en el Mac;
3. repetir SSH, verificar `runpodctl` remoto y continuar con checkout/activos/bootstrap.

No se produjo CSV, overlay, reporte de inferencia ni bundle de resultados.
