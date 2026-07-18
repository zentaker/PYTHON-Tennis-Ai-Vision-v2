# Stage 5B v2 — Rechazo final

**Estado:** `REJECTED_BY_HUMAN_GATE`

Aunque la parametrización ancló endpoints y satisfizo `ev_003` en el límite
(`Y=11.8851 m`), no comprendió la profundidad monocular: el jugador visual estaba
claramente detrás de la baseline y `ev_001` también recibió una profundidad incoherente.
La pelota, la cámara y la física balística no bastan para resolver esa ambigüedad.

No se intentará Stage 5B v3 exclusivamente matemática. El siguiente enfoque autorizado
es player-aware, usando detección/tracking de jugadores, pies, pose, homografía y
auditoría de contactos. Los outputs y el código V1/V2 se conservan; Stage 5C y Stage 6
siguen sin iniciar.
