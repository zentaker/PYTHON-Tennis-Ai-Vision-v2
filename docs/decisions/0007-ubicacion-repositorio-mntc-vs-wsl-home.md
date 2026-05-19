# ADR-0007: Ubicación del repositorio: /mnt/c vs WSL home

- **Status:** Aceptada
- **Fecha:** 2026-05-18
- **Stage:** 1

## Contexto

El repositorio fue fundado en Stage 0 directamente en la carpeta Windows `C:\Users\MSI\Desktop\TennisAI`, accesible desde WSL como `/mnt/c/Users/MSI/Desktop/TennisAI`. Los prompts anteriores mencionaban `~/projects/tennis-vision-ai-v2/`, pero el usuario confirmó que esa ruta era ilustrativa y que la ubicación canónica del proyecto es la ruta actual en `/mnt/c`.

## Decisión

Mantener el repositorio en `/mnt/c/Users/MSI/Desktop/TennisAI` por continuidad del trabajo de Stage 0 y facilidad de acceso cross-OS.

## Alternativas consideradas

- Migrar ahora a WSL home - descartada por fricción temprana y porque Stage 1 es principalmente geometría, documentación e imágenes puntuales.
- Mantener una copia duplicada entre Windows y WSL - descartada porque introduce riesgo de divergencia y errores de sincronización.

## Consecuencias

- Positivas: el usuario puede acceder al repositorio desde Windows y WSL sin pasos extra; se preserva la historia Git ya creada en Stage 0.
- Negativas / riesgos: operaciones con muchos archivos pequeños pueden ser significativamente más lentas en `/mnt/c` que en el filesystem nativo de WSL2. Estimación informal: 5-10x más lento para installs, lectura intensiva de frames o inferencia con muchos accesos a disco.

## Mitigación

Antes de iniciar Stage 2 se hará un review obligatorio del impacto de I/O. Si la inferencia de WASB sobre el clip de referencia corre en tiempo aceptable, definido por el DoD de Stage 2 como menos de 10 minutos, esta decisión podrá aceptarse. Si no, se migrará el repositorio a WSL home antes de continuar.

## Aceptación

Aceptada por el usuario el 2026-05-19. El usuario priorizó accesibilidad directa desde Windows Explorer sobre performance de I/O. La fricción de install/inferencia en /mnt/c se acepta como trade-off conocido y documentado. Cualquier intento previo de migración fuera de /mnt/c queda revertido.
