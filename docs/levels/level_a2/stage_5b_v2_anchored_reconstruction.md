# Stage 5B v2 — Reconstrucción anclada a eventos

V1 fue `REJECTED_BY_HUMAN_GATE`; V2 se implementa en `src/reconstruction3d_v2/` sin
modificar ni sobrescribir `outputs/nivel_a2_01/stage_5b/`.

Cada evento usa el píxel observado del frame candidato y permanece sobre su rayo de
cámara. Los botes intersectan exactamente `Z=0`. Serve y hits tienen una sola variable
de altura; X/Y se derivan del rayo. Las velocidades se derivan exclusivamente de los
endpoints y del intervalo VFR, por lo que `P(0)=P_start`, `P(T)=P_end` y los eventos
compartidos son espacialmente continuos por construcción.

Se resuelven las 24 combinaciones reales con 16 starts deterministas por combinación,
`scipy.optimize.least_squares`, pérdida `soft_l1`, `max_nfev=800` y bounds físicos. No
se reutilizan costes ni resultados entre combinaciones. La restricción humana versionada
en `data/clips/nivel_a2_01/semantic_constraints.json` exige `ev_003.Y > +11.885 m`.

Los renderers V2 conservan proporción métrica, escala isotrópica, FAR arriba/NEAR abajo
en top view y NEAR izquierda/FAR derecha en side view. Las baselines, red, exteriores y
service lines se dibujan en metros; no hay clamps visuales.
