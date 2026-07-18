# P1 GPU runtime compatibility

This is a provider-neutral Linux/CUDA image. It is intentionally not built or run on
the Intel Mac during this task.

| Component | Pin | Rationale/source |
|---|---|---|
| Base OS | `pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime` | Official PyTorch image tag; CUDA 12.1 runtime and Python 3.10 are supplied by the image. |
| CUDA | 12.1 | Matches the pinned PyTorch image and common NVIDIA driver compatibility policy. |
| PyTorch | 2.1.2 | Official CUDA 12.1 base paired with the available MMCV 2.1 wheel. |
| MMEngine | 0.10.4 | OpenMMLab 0.10 compatibility line for the pinned 2.x stack. |
| MMCV | 2.1.0 | The exact official `cu121/torch2.1` wheel available from OpenMMLab. |
| MMDetection | 3.2.0 | Matches the pinned manifest and MMPose 1.3.2 `mim` compatibility range; CI must prove runtime compatibility with the available wheel. |
| MMPose | 1.3.2 | Stable 1.x top-down inference API used by the pose adapter. |
| FFmpeg | Ubuntu package | Required for video inspection and VFR assets. |

Sources consulted: the official PyTorch Docker image tags, the official OpenMMLab
`cu121/torch2.1` wheel index, and the pinned package metadata/compatibility ranges for
MMEngine, MMCV, MMDetection and MMPose.

The exact MMCV wheel index used by the Dockerfile is
`https://download.openmmlab.com/mmcv/dist/cu121/torch2.1/index.html`; pip is passed this
index explicitly with `--only-binary=mmcv`, so it cannot silently compile MMCV from source.
MMDetection 3.2.0 asserts `mmcv<2.2.0` at import time, so the otherwise attractive
PyTorch 2.3/ CUDA 12.1 + MMCV 2.2 candidate is rejected by official runtime behavior.
The CUDA 12.1/PyTorch 2.1 index provides the compatible MMCV 2.1.0 wheel; `pip check`
and the real CPU inference gate remain mandatory compatibility evidence.
MMPose's official runtime requirements include `chumpy==0.70`; its legacy build setup
requires the already-installed environment and therefore is installed once with
`--no-build-isolation` before the normal dependency-resolving requirements install.
Versions were recorded on 2026-07-17. The image must be rebuilt and smoke-tested on the
target NVIDIA runtime before any provider is accepted. No weights are downloaded by the
Docker build; model assets are mounted at `/models` and checked by their manifest.
