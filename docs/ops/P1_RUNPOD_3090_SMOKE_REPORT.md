# P1 RunPod RTX 3090 Smoke Report

Status: `P1_GPU_SMOKE_PARTIAL`

The validated integration source `9c80d548f3222436fd70b0aa14fcb08b9813214b` ran on Pod `jhvv98pfxdndz6`, one NVIDIA GeForce RTX 3090, using real CUDA inference over exactly frames 138, 139, 140, 199, 200, 201, 286, 287, 351, and 434. The inference runtime was 34 seconds. The environment used PyTorch 2.1.2+cu121, MMEngine 0.10.4, MMCV 2.1.0, MMDetection 3.2.0, and MMPose 1.3.2.

The first attempt stopped before inference because Setuptools no longer provided `pkg_resources`. The single permitted correction pinned Setuptools 70.3.0; the one full retry completed. Both model checkpoints matched their declared SHA-256 values. No mocks were used.

Outputs contain 58 track rows, a 133-keypoint pose for every detected person, projected court positions, five contact-audit rows, ten individual overlays, a contact sheet, manifests, diagnostics, and logs. The runtime reported no near/far identity-switch flags. However, the detector returned five or six persons per frame because spectators were included. The exactly-two-relevant-player criterion and visual quality therefore remain unvalidated. Human evaluation is pending; no outputs were manually adjusted.

The verified local archive is `.artifacts/p1-runpod-3090-smoke/p1-runpod-3090-smoke-results.tar.gz` (6,910,962 bytes), SHA-256 `b872f8c3aa586cf7111afc717e4d25f45d65f6e917aa05eafa294437b168bd17`.

Additional compute observed during this operation is approximately US$0.12 at the displayed US$0.46/hour rate. No RunPod API credential was available, so provider-level automatic STOP and final provider state verification were technically unavailable. Remote inference processes finished; this does not prove billing stopped.
