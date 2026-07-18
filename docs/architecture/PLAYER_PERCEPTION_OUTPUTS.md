# Player perception output contracts

Future Stage P1 output directory: `outputs/nivel_a2_01/stage_p1/`.

- `player_tracks.csv`: frame, stable track id, identity, bbox and confidence.
- `player_pose.jsonl`: frame, track id, semantic keypoints and confidence.
- `player_court_positions.csv`: X/Y metres, distance to both baselines, region flags
  and confidence.
- `contact_audit.json`: expected event player, assigned track, feet, wrists, ball pixel,
  distances, warnings and confidence. It never asserts 3-D contact.
- `perception_report.json`: versioned run summary and frame-level contract.
- `player_pose_overlay.mp4`, `contact_audit_contact_sheet.png`: generated only after a
  real backend gate; mock tests use temporary directories and do not populate stage_p1.
