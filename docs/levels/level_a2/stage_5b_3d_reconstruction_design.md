# Stage 5B A2 — Diseño de reconstrucción 3D

Stage 5B está `IN_PROGRESS`; la referencia vertical de Stage 5A.1 está cerrada y el
baseline ejecutado queda pendiente del gate humano 3D.
Cada vuelo tendrá estado `(X0,Y0,Z0,Vx0,Vy0,Vz0)` y el baseline balístico será:

```text
X(t) = X0 + Vx0*t
Y(t) = Y0 + Vy0*t
Z(t) = Z0 + Vz0*t - 0.5*9.80665*t²
```

El coste futuro combinará error de reproyección 2D, restricciones `Z=0` en los cinco
botes, continuidad temporal, altura/velocidad plausibles, clearance sobre la red y
regularización. No se impondrá que el ápice coincida con la red, ni que todos los vuelos
tengan igual altura, ni se usará una recta entre eventos.

Las extensiones posteriores pueden incorporar drag, topspin, slice, fuerza de Magnus y
estimación de spin. No se implementan en Stage 5A.

La implementación vive en `src/reconstruction3d/` y `scripts/stage5b_a2.py`. Usa eventos
compartidos, optimización robusta `scipy.least_squares`, pesos source-aware y timestamps
VFR. Los cinco botes se parametrizan con `Z=0`; hits y serve dejan la altura libre dentro
de límites amplios. El frame gate conserva las 24 combinaciones posibles y no altera la
anotación humana.
