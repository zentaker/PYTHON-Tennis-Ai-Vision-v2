# Scripts

Utilitarios operativos del proyecto. No colocar scripts sueltos en la raiz.

- `verify_env.py`: valida el entorno base de Stage 0.
- `replit_smoke_test.py`: smoke test ligero archivado; valida imports de Stage 4 sin
  tracker, video ni checkpoints.
- `stage2_a2_preflight.py`: valida video, manifest, homografia, VFR y orientacion canonica
  de Nivel A2 sin importar PyTorch ni ejecutar WASB.
- `gpu/runpod_bootstrap.sh`: prepara y valida un Pod Ubuntu/CUDA sin iniciar inferencia.
- `gpu/verify_runpod_environment.sh`: reporta runtime GPU y activos Stage 2 A2.
- `gpu/run_stage2_a2_remote.sh`: fija un commit y ejecuta Stage 2 A2 remotamente.
- `gpu/download_stage2_results.sh`: recupera resultados con backup y SHA-256.
