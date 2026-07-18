# P1 GPU Retest Visual Audit

Status: `P1_GPU_RETEST_PASSED`

The migrated RunPod workspace executed real RTMDet-M and RTMPose-M WholeBody inference with CUDA on one NVIDIA GeForce RTX 3090. Exactly ten canonical frames were decoded and inferred again; the court-player selector was then applied to those new raw outputs. No mocks, manual output adjustment, full-rally processing, or Analytics inference were used.

Automated gates report 10 near selections, 10 far selections, 38 rejected person candidates, zero identity switches, 133 keypoints for every selected pose, required wrists/ankles/heels/toes, and five reassociated contacts. Raw and selected results are preserved in the verified local archive `.artifacts/p1-gpu-retest/p1-gpu-retest-results.tar.gz`, SHA-256 `a2e2c138cff1076b9531c24d690a48a44b993a8168e3b52a5d274a50ed11feba`.

- [GPU retest contact sheet](assets/p1_gpu_retest_contact_sheet.jpg)
- [GPU retest before/after sheet](assets/p1_gpu_retest_before_after.jpg)

Human visual approval: **pending**. This result does not declare P1 complete, Analytics integrated, Stage 5B ready, or the project complete.
