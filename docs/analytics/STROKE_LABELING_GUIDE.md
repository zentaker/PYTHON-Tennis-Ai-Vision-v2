# Stroke labeling guide

Annotate a frame range plus VFR timestamp range and cite visible evidence. Human observation is not
ground truth unless the dataset explicitly declares it as such; never relabel inference as observation.

- Forehand/backhand describes the hitting side, not spin. Use `unknown` when contact side is hidden.
- Groundstroke follows a bounce; volley is struck before a bounce; half-volley is near-immediate after
  bounce. Do not decide from player location alone.
- Flat/topspin/slice describes estimated spin family. Motion blur or bounce alone is insufficient.
- Drop/lob/drive describes tactical shape independently of side and spin.
- Use `unknown` for occlusion, conflicting cues, inadequate temporal context, or uncertain contact.

Include frames before and after contact. Preserve source timestamps rather than deriving constant-FPS
times. Record ambiguity in warnings. The example JSON is structural only and is not a real-rally label.
