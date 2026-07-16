# Stage 5A / 5A.1 — Exit report A2

**Estado:** `CLOSED_SUCCESSFULLY`
**Readiness entregado:** `READY_FOR_STAGE_5B`

Stage 5A auditó la homografía y Stage 5A.1 refinó la cámara con las cuatro referencias
verticales humanas preservadas byte a byte. La referencia es
`data/clips/nivel_a2_01/vertical_reference.json`, SHA-256
`e33512a98b0e1acad00ae7eef2c4e5fc820a0538c8f7b06e8e6ea0ca04644b73`; sus respaldos
están bajo `outputs/nivel_a2_01/stage_5a1/backups/`. El modelo refinado es
`outputs/nivel_a2_01/stage_5a1/camera_model_refined.json`.

La cámara usa `fx=4816.903`, `fy=4473.611`, `cx=1407.815`, `cy=2074.312` y centro
`[-0.046,-39.859,10.512] m`. El error de suelo es media/máximo `4.416/8.913 px` y el
vertical `3.946/7.633 px`. El jitter real (200 muestras por nivel) alcanzó p95 de
`5.85 px` a 3 m y `12.72 px` a 5 m con perturbación ±2 px; la sensibilidad mejoró
`69.61%` (`117.5` a `35.713 px`). Los 13 criterios de readiness pasaron.

La cámara es monocular y basada en supuestos: las alturas no son ground truth. Se
autoriza Stage 5B como baseline balístico con `g=9.80665 m/s²`, sin drag, spin ni
Magnus. No se recalcularon Stage 2/3, no se modificó Stage 4 y no se usó RunPod, SSH,
GPU, PyTorch o WASB.
