# Stage 5A.2B temporal ground track

- Stage 5A.2 human gate: rejected, evidence insufficient.
- Inputs: canonical real video plus accepted P1 contacts/poses/tracks.
- Compute: CPU optical flow and classical image geometry; no inference/GPU/cloud.
- Geometry sources: correlated; calibration family ensemble used for dispersion.
- Far distance: not forced and no 5 m gate.
- Contact visual gate: passed 5/5; identities correct and zero visible switches.
- Temporal gate: rejected; status `STAGE5A2B_REJECTED_BY_HUMAN_GATE_TRACKER_INVALID`.
- Blocker: 143.144 m/s is invalid tracker drift, not real player motion.
- Next gate: ChatGPT visual audit after artifact publication.
