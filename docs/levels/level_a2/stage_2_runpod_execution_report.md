# Reporte de ejecución RunPod — Stage 2 A2

**Fecha:** 2026-07-15  
**Estado:** `BLOCKED_CONNECTION`

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

Se recuperó la identidad histórica cuya pública coincide con el fingerprint esperado
`SHA256:LSId5ppgJuAlLK24MjEqHvEIqT05118sFnO7DCFW9gg`. El servidor reconoció esa pública,
pero la privada está cifrada con una passphrase que no existe en el agente ni en
Keychain. El original cifrado fue preservado sin mostrar su contenido.

Se generó una identidad Ed25519 específica en `~/.ssh/runpod_tennis_ai`, con permisos
`600`; su pública tiene fingerprint
`SHA256:VlyYRggSyC1rFBopP2/0MykiwLdx+3ujt6Tk8w5i80E`. La conexión queda pendiente de
registrar esa pública en la cuenta/Pod mediante la interfaz web de RunPod.

Por ello permanecen sin verificar directamente:

- GPU, VRAM, driver y CUDA del Pod;
- escritura en `/workspace`;
- checkout remoto;
- presencia remota de WASB-SBDT y checkpoint;
- SHA-256 remoto del video.

## Transferencia

`runpodctl 2.7.1-06a0a26` quedó instalado en `~/.local/bin` desde el release oficial de
`runpod/runpodctl`. El binario Intel macOS se verificó contra el checksum oficial; SHA-256
`150566e84157d78fc25e39d73520aed0a879d24023a67a9d3fc41776dd34c1b3`. No se configuró
API key, ni se usaron SCP o rsync.

## Cambios preparados localmente

- Helper `scripts/gpu/runpod_ssh.sh` para `proxy` y `exposed_tcp`.
- Configuración privada proxy con permisos `600`, fuera del repositorio.
- Downloader con rutas separadas `runpodctl` y SCP, backups y SHA-256.
- Bootstrap/environment gate explícito para 527 timestamps VFR.
- Tests del proxy sin puerto, TCP con puerto, configuración incompleta y garantía de que
  proxy no invoca SCP.

El soporte proxy/runpodctl fue publicado en GitHub. El ajuste posterior para aceptar el
alias privado `tennis-runpod-a2` se publicó en
`0ac9a8afcf23afe651bf817454365f34f08473c1`.

## Gate

No se cumplen las condiciones de `READY_FOR_INFERENCE`. La próxima pasada debe:

1. registrar en RunPod la pública de `~/.ssh/runpod_tennis_ai.pub`;
2. repetir SSH, verificar `runpodctl` remoto y continuar con checkout/activos/bootstrap.

No se produjo CSV, overlay, reporte de inferencia ni bundle de resultados.
