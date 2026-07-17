# P1 GPU runtime compatibility

This is a provider-neutral Linux/CUDA image. It is intentionally not built or run on
the Intel Mac during this task.

| Component | Pin | Rationale/source |
|---|---|---|
| Base OS | `pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime` | Official PyTorch image tag; CUDA 12.1 runtime and Python 3.11 are supplied by the image. |
| CUDA | 12.1 | Matches the pinned PyTorch image and common NVIDIA driver compatibility policy. |
| PyTorch | 2.3.1 | Matches the official base image and avoids installing a second torch build. |
| MMEngine | 0.10.4 | OpenMMLab 0.10 compatibility line for the pinned 2.x stack. |
| MMCV | 2.2.0 | The exact official `cu121/torch2.3` wheel available from OpenMMLab. |
| MMDetection | 3.3.0 | Candidate paired with the available MMCV wheel; CI must prove runtime compatibility. |
| MMPose | 1.3.2 | Stable 1.x top-down inference API used by the pose adapter. |
| FFmpeg | Ubuntu package | Required for video inspection and VFR assets. |

Sources consulted: the official PyTorch Docker image tags, the official OpenMMLab
`cu121/torch2.3` wheel index, and the pinned package metadata/compatibility ranges for
MMEngine, MMCV, MMDetection and MMPose.

The exact MMCV wheel index used by the Dockerfile is
`https://download.openmmlab.com/mmcv/dist/cu121/torch2.3/index.html`; pip is passed this
index explicitly with `--only-binary=mmcv`, so it cannot silently compile MMCV from source.
The upstream package metadata advertises a narrow MMDetection/MMCV range; this candidate
is intentionally verified by the free CI gate before any readiness promotion.
Versions were recorded on 2026-07-17. The image must be rebuilt and smoke-tested on the
target NVIDIA runtime before any provider is accepted. No weights are downloaded by the
Docker build; model assets are mounted at `/models` and checked by their manifest.
