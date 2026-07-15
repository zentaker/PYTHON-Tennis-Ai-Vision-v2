# Entorno temporal RunPod para pruebas GPU de Stage 2 A2

**Última auditoría:** 2026-07-14

## Alcance y fuente de verdad

RunPod se usa solamente como runner Linux/CUDA temporal para preflight e inferencia WASB.
No se despliega una API, no se deja un servicio permanente y no se configura todavía un
self-hosted runner de GitHub Actions. El Mac sigue siendo el entorno principal de
desarrollo y GitHub es la fuente de verdad del código.

El flujo está limitado a Stage 2 del clip `nivel_a2_01`. No ejecuta Stage 3 ni Stage 5.
Los videos, checkpoints, `third_party`, outputs y logs siguen ignorados por Git.

## Pod recomendado

- GPU inicial: **RTX A5000, 24 GB VRAM**.
- Fallback: **RTX 3090, 24 GB VRAM**.
- Imagen: plantilla oficial RunPod PyTorch basada en Ubuntu, con acceso SSH completo.
- Container disk: 20–30 GB para el sistema y cachés temporales.
- Volume disk en `/workspace`: 50 GB como punto de partida para repo, `.venv`, MP4,
  checkpoint, WASB-SBDT, frames temporales del overlay y resultados.
- Red: habilitar IP pública y TCP 22 si se usarán `scp`/`rsync`.
- No abrir puertos HTTP ni desplegar endpoints.

RunPod distingue el SSH básico por proxy del SSH completo por IP pública: el primero no
soporta SCP/SFTP, mientras que el segundo sí. La guía oficial explica ambas opciones:
[Connect to a Pod with SSH](https://docs.runpod.io/pods/configuration/use-ssh).

Los tamaños son deliberadamente moderados para esta primera pasada. Si el bootstrap se
queda sin espacio, aumentar el volumen; RunPod permite aumentarlo, pero no reducirlo. La
documentación de tipos y persistencia está en
[Storage options](https://docs.runpod.io/pods/storage/types).

## 1. Crear y asegurar el Pod

1. En RunPod, abrir **Pods → Deploy**.
2. Elegir una RTX A5000; usar RTX 3090 solo si la primera no está disponible.
3. Seleccionar una plantilla oficial PyTorch/Ubuntu compatible con SSH.
4. Configurar el almacenamiento indicado arriba con `/workspace` persistente.
5. Añadir únicamente la **clave pública** SSH a RunPod. La clave privada permanece en el
   Mac.
6. Para transferencias, habilitar IP pública y TCP 22 y copiar de la consola el host y
   puerto asignados.
7. Conectar y ejecutar `nvidia-smi` antes de copiar activos.

No guardar host, puerto, tokens ni claves en Git. Copiar el ejemplo a una ubicación
privada fuera del repositorio:

```bash
mkdir -p "$HOME/.config/tennis-vision-ai"
cp config/runpod/stage2_a2.env.example \
  "$HOME/.config/tennis-vision-ai/stage2_a2.env"
chmod 600 "$HOME/.config/tennis-vision-ai/stage2_a2.env"
```

Completar ese archivo y cargarlo solo en la shell local:

```bash
set -a
source "$HOME/.config/tennis-vision-ai/stage2_a2.env"
set +a
```

## 2. Publicar y clonar el código

El commit usado debe contener los scripts GPU y estar disponible en GitHub. Antes de
usar RunPod, revisar, hacer commit y push explícitamente desde el Mac; este procedimiento
no hace push por sí solo. Obtener siempre el SHA completo:

```bash
git status --short
git rev-parse HEAD
git ls-remote origin "$(git rev-parse HEAD)"
```

En el Pod:

```bash
cd /workspace
git clone https://github.com/zentaker/PYTHON-Tennis-Ai-Vision-v2.git
cd /workspace/PYTHON-Tennis-Ai-Vision-v2
```

El runner ejecuta `git fetch origin --prune` y `git checkout --detach <SHA>`. Rechaza
cambios rastreados antes del checkout y nunca ejecuta `git clean`, por lo que no elimina
los activos ignorados colocados en el Pod.

## 3. Subir los activos ignorados

Se requieren exactamente estas entradas remotas:

```text
data/clips/nivel_a2_01/source.mp4
data/clips/nivel_a2_01/clip_manifest.json
data/clips/nivel_a2_01/homography.json
data/clips/nivel_a2_01/court_corners_pixel.json
models/wasb/wasb_tennis_best.pth.tar
third_party/WASB-SBDT
```

Los tres JSON pequeños pueden venir del checkout, pero se incluyen en el inventario para
que el gate remoto compruebe su presencia. El MP4, checkpoint y WASB-SBDT se transfieren
fuera de Git. Desde el Mac, usando el host/puerto público que muestra RunPod:

```bash
ssh -p "$RUNPOD_SSH_PORT" -i "$RUNPOD_SSH_KEY" \
  "$RUNPOD_SSH_USER@$RUNPOD_HOST" \
  "mkdir -p /workspace/PYTHON-Tennis-Ai-Vision-v2/data/clips/nivel_a2_01 \
    /workspace/PYTHON-Tennis-Ai-Vision-v2/models/wasb \
    /workspace/PYTHON-Tennis-Ai-Vision-v2/third_party"

scp -P "$RUNPOD_SSH_PORT" -i "$RUNPOD_SSH_KEY" \
  data/clips/nivel_a2_01/source.mp4 \
  "$RUNPOD_SSH_USER@$RUNPOD_HOST:/workspace/PYTHON-Tennis-Ai-Vision-v2/data/clips/nivel_a2_01/"

scp -P "$RUNPOD_SSH_PORT" -i "$RUNPOD_SSH_KEY" \
  models/wasb/wasb_tennis_best.pth.tar \
  "$RUNPOD_SSH_USER@$RUNPOD_HOST:/workspace/PYTHON-Tennis-Ai-Vision-v2/models/wasb/"

rsync -az --delete -e "ssh -p $RUNPOD_SSH_PORT -i $RUNPOD_SSH_KEY" \
  third_party/WASB-SBDT/ \
  "$RUNPOD_SSH_USER@$RUNPOD_HOST:/workspace/PYTHON-Tennis-Ai-Vision-v2/third_party/WASB-SBDT/"
```

`--delete` queda limitado al destino `third_party/WASB-SBDT/`; no usarlo sobre el repo
completo. Si los activos solo existen en otra máquina autorizada, transferirlos desde esa
máquina y verificar sus checksums antes del bootstrap.

## 4. Bootstrap reproducible, sin inferencia

Dentro del Pod:

```bash
cd /workspace/PYTHON-Tennis-Ai-Vision-v2
bash scripts/gpu/runpod_bootstrap.sh
```

El bootstrap:

- exige Linux Ubuntu, NVIDIA y capacidad CUDA informada por el driver;
- instala `uv` solo si falta e instala Python 3.11 mediante `uv`;
- ejecuta `uv sync --frozen --extra dev --extra tracker` y comprueba que `uv.lock` no
  cambió;
- verifica FFmpeg/FFprobe, PyTorch CUDA y todos los activos;
- ejecuta tests ligeros y el preflight A2 con decodificación de los 527 frames;
- guarda `outputs/nivel_a2_01/stage_2/logs/bootstrap_preflight.json`;
- **no invoca `wasb_runner` y no inicia inferencia**.

La verificación puede repetirse en cualquier momento:

```bash
bash scripts/gpu/verify_runpod_environment.sh
```

## 5. Ejecutar Stage 2 desde el Mac

Con el bootstrap en verde y el commit publicado en GitHub:

```bash
cd /Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2
./scripts/gpu/run_stage2_a2_remote.sh "$RUNPOD_HOST" "$RUNPOD_COMMIT_SHA"
```

El script local abre una sesión SSH y ejecuta el modo remoto. En el Pod, ese modo:

1. rechaza cambios Git rastreados;
2. hace fetch y checkout detached del SHA completo;
3. conserva los activos ignorados;
4. verifica el entorno y ejecuta el preflight con `--require-runtime`;
5. ejecuta una sola vez la CLI real `src.tracker.wasb_runner` con `--device cuda`;
6. genera CSV, overlay VFR, reporte y log;
7. registra el commit en `inference_report.json`;
8. exige 527 filas/IDs, 527 frames reportados y 527 frames en el overlay;
9. imprime SHA-256 de cada resultado;
10. no ejecuta Stage 3.

Resultados remotos:

```text
data/clips/nivel_a2_01/wasb_detections.csv
outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4
outputs/nivel_a2_01/stage_2/inference_report.json
outputs/nivel_a2_01/stage_2/logs/stage2_<UTC>_<SHA>.log
```

## 6. Recuperar y verificar resultados

Desde el Mac:

```bash
./scripts/gpu/download_stage2_results.sh "$RUNPOD_HOST"
```

El downloader consulta el SHA-256 remoto, descarga únicamente CSV, MP4, JSON y logs a
un archivo temporal, compara el checksum y solo entonces lo instala localmente. Si ya
existe un resultado, primero lo mueve a:

```text
outputs/nivel_a2_01/stage_2/backups/<UTC>/<ruta_relativa>
```

El gate visual del overlay sigue siendo humano. Descargar resultados no autoriza ni
inicia Stage 3.

## 7. Detener o terminar el Pod

1. Confirmar que los cuatro tipos de artefacto llegaron al Mac y que los checksums
   pasaron.
2. Revisar `inference_report.json` y conservar el log.
3. En la consola RunPod, detener el Pod si se reutilizará en breve o terminarlo si la
   prueba terminó y ya existe backup externo.
4. Verificar en la consola que no queda compute ejecutándose y revisar Billing.

La página oficial de precios listaba, durante esta auditoría, A5000 desde USD 0.27/h y
RTX 3090 desde USD 0.46/h, pero disponibilidad y precio deben confirmarse al desplegar:
[RunPod GPU pricing](https://www.runpod.io/pricing). La facturación es por uso y dejar el
Pod ejecutándose consume saldo. Además, detener un Pod no elimina el costo de su volumen:
el almacenamiento persistente sigue facturándose y puede costar más mientras está
detenido. Consultar las tarifas vigentes en
[Billing overview](https://docs.runpod.io/accounts-billing/billing).

RunPod no debe tratarse como backup permanente. La documentación recomienda respaldar
datos críticos externamente; si la cuenta se queda sin fondos, el almacenamiento puede
perderse. Por eso esta pasada termina descargando resultados y apagando/terminando el
Pod.

## Límites de seguridad

- No colocar tokens, contraseñas, IPs, hosts ni claves privadas en Git.
- No subir el MP4, checkpoint, WASB-SBDT ni outputs a GitHub.
- No ejecutar el runner si bootstrap o preflight fallan.
- No cambiar el modelo para esconder una incompatibilidad CUDA/checkpoint.
- No iniciar Stage 3 ni Stage 5 desde estos scripts.
- No dejar un Pod encendido después de recuperar los resultados.
