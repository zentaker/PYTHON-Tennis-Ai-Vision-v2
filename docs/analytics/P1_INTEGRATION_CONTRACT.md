# P1 read-only integration contract

Analytics does not assume these outputs currently exist and does not import Player Perception.

| Input | Expected fields | Dependency |
|---|---|---|
| `player_tracks.csv` | frame_id, track_id, identity, bbox, confidence | EXPECTED_FROM_P1 |
| `player_pose.jsonl` | frame_id, track_id, keypoints, confidence | EXPECTED_FROM_P1 |
| `player_court_positions.csv` | frame_id, track_id, x_m, y_m, confidence | EXPECTED_FROM_P1 |
| `contact_audit.json` | event_id, expected_player, track_id, frame_id, ball_pixel, wrist_pixels, ball_wrist_distance_px, confidence, warnings | EXPECTED_FROM_P1 |
| Stage 4 events | event ID, VFR timing, legacy manual shot type | AVAILABLE_NOW |
| approved XYZ trajectory | timestamped metric coordinates | EXPECTED_FROM_STAGE5B, BLOCKING for 3D speed |
| P2 refined temporal contact | refined contact evidence | EXPECTED_FROM_P2 |

Optional future P1 fields are `hitting_hand`, `racket_head_pixel`, `racket_velocity_vector`,
`refined_contact_frame`, `contact_height`, `swing_direction`, and
`pose_window_before_after_contact`. They are OPTIONAL and are not requested as upstream changes here.
