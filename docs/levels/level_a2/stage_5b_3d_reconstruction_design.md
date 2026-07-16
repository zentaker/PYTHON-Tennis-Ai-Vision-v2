# Stage 5B A2 — Diseño de reconstrucción 3D (no implementado)

Stage 5B permanece `NOT_STARTED` hasta resolver la referencia vertical de Stage 5A.
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
