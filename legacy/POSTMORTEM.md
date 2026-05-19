# Postmortem del sistema legacy

## Proposito

Este documento resume fallas anteriores como referencia negativa. El codigo legacy no se reutiliza.

## Fallas observadas

- Se empezo por vision computacional sin fijar primero entorno y versiones.
- No habia criterios de exito escritos antes de ejecutar etapas.
- No se midio friccion, por lo que los bloqueos se acumularon sin decision clara.
- La homografia y la referencia de cancha no quedaron aisladas como primer problema.
- No estaba separado que era dato local, modelo, salida, codigo y documentacion.
- Las anotaciones manuales no tenian rol claro entre ground truth y entrenamiento.

## Lecciones aplicadas en v2

- Stage 0 crea fundamento antes de cualquier modelo.
- Stage 1 resuelve homografia antes de tracking.
- Stage 2 mide detectores contra ground truth minimo antes de considerar fine-tuning.
- Las decisiones viven en ADRs.
- La friccion se registra y se usa para decidir cierres o pivotes.
