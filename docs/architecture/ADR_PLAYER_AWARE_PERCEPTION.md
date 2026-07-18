# ADR — Player-Aware Perception Foundation

**Status:** Accepted for P1 preparation; real model execution not started.

## Decision

Player context becomes an independent reusable layer around the approved ball tracking
and court calibration. The pipeline is detector → temporal identity tracker → pose
backend → foot anchor → court projector → contact auditor → biomechanics features.
The backend contract supports OpenMMLab components compatible with RTMDet, ByteTrack
and RTMPose/RTMW without pinning a model weight or version in application code.

The primary identity evidence is temporal track continuity plus foot support projected
through the approved homography. The sign of metric Y assigns near/far, with UNKNOWN
when evidence is insufficient. Human observations are future evaluation gates; they are
not encoded as model inputs. The mock backend is deterministic and is the only backend
used during this preparation.

## Consequences

Detector, tracker, pose, racket, projection and audit components can be replaced without
rewriting output schemas or renderers. Feet use heel/toe, ankle, then bbox fallback and
mark airborne uncertainty. Biomechanics remains geometric and confidence-aware; it does
not estimate force, torque, injury or clinical risk. Real weights, GPU dependencies and
provider decisions remain external to the Mac development environment.
