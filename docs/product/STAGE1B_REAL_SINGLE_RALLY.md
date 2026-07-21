# Stage 1B — Real Single Rally Bundle Candidate

This candidate documents a read-only import of existing local reference assets.
It is evidence for audit, not a human acceptance decision and not a new
inference run.

## Aligned references

- Selected external video: `nivel_a2_01/source.mp4` (10.488333 seconds,
  1536×2746 source pixels, 527 frames).
- Existing Stage 3 trajectory: `nivel_a2_01/smoothed_trajectory.csv`, with
  527 frame rows: 383 visible, 19 interpolated and 125 missing/non-visible.
- Existing VFR timestamps cover frames 0–526; Stage 4 manual events cover the
  same rally; existing 2D calibration is approved and non-synthetic.
- No source video, model, or personal filesystem path is copied into the
  versioned fixture.

## Candidate contents

The deterministic derived fixture contains one rally, 527 ball observations,
and 10 events: 4 contacts, 5 bounces and 1 serve. No out or unknown event is
introduced. The source surface is not declared by the available metadata, so it
remains `unknown`. `manifest.status` is `complete`; `session.status` and
`rallies.status` are `partial` because the source track preserves non-visible
observations rather than fabricating positions.

The bundle uses image-pixel observations and an existing 2D pixel-to-court
calibration with `calibration_status: approved`; it makes no 3D or Stage 5B
claim. Two independent builds have the same fingerprint and source verification
passes. SVG previews show the track/court and event timeline without embedding
video frames.

## Gate

`REAL_REFERENCE_ASSET_ALIGNMENT_PASSED` confirms correspondence of the selected
assets. The product gate remains
`REAL_SINGLE_RALLY_BUNDLE_CANDIDATE_PENDING_HUMAN_AUDIT`. Human review of the
derived evidence is the next gate; this document must not be read as approval.
