# Agent Protocol

## Raiz de trabajo activa

El agente resuelve la raiz desde el checkout Git y no crea una carpeta contenedora. El
checkout activo reconciliado es:

```text
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2
```

La ruta historica WSL de la maquina usada para WASB fue:

```text
/mnt/c/Users/MSI/Desktop/TennisAI
```

Esa ruta se conserva como evidencia historica, no como requisito para desarrollo ligero
en macOS. WSL/Linux sigue siendo el entorno de inferencia pesada.

## Reglas de operacion

- Una etapa, un artefacto, un gate.
- No avanzar a vision computacional durante Stage 0.
- No pivotar sin aprobacion explicita del usuario.
- No escribir secretos en archivos del repositorio.
- Registrar friccion si un bloqueo consume mas de 15 minutos o revela un supuesto incorrecto.
- Mantener ADRs como `Propuesta` hasta aprobacion humana.

## Cuando detenerse

El agente se detiene y pide validacion cuando:

- Un gate requiere juicio humano.
- Un ADR debe aceptarse antes de continuar.
- Hay un pivote tecnico con impacto en roadmap.
- El entorno requerido no esta disponible.
- Se requieren credenciales o permisos administrativos.

## Credenciales

Las credenciales compartidas en chat se tratan como sensibles. No se escriben en archivos, logs, scripts, README, comandos persistidos ni historial git.

## Commits

Stage 0 pide estructura commiteada. Antes de commitear:

1. Revisar `git status`.
2. Confirmar que no se agregan `data/`, `models/`, `outputs/`, `.venv/` ni secretos.
3. Ejecutar las verificaciones posibles.
4. Crear commit con mensaje claro de etapa.
