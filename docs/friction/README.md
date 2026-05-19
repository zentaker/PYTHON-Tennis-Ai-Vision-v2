# Friccion

La friccion es cualquier obstaculo que consume mas de 15 minutos, revela un supuesto tecnico incorrecto o fuerza un pivote dentro de una etapa.

## Categorias

- `DEP`: dependencias, instalacion, versiones.
- `MOD`: comportamiento de modelo, pesos, inferencia.
- `INT`: integracion entre componentes.
- `VAL`: validacion, metricas, ground truth.
- `DOM`: concepto de dominio o supuesto incorrecto.
- `ENV`: entorno, OS, paths, GPU.
- `DOC`: documentacion faltante o erronea.
- `AGT`: comportamiento del agente, loop improductivo o mala interpretacion.

## Salud por etapa

```text
ratio_friccion = horas_friccion_etapa / horas_totales_etapa

< 0.2: saludable
0.2-0.5: friccion moderada
> 0.5: fragil, reevaluar enfoque
```
