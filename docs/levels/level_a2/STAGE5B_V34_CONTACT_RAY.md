# Stage 5B v3.4 — contact rays and shared nodes

Phase A derives five contact nodes from reconciled raw/smoothed/P1 pixels, camera
rays, both wrist rays, pose, approved anchor uncertainty, racket reach, and height.
It independently derives five bounce nodes from camera-ground and homography evidence.
No previous XYZ is a dependency. A deterministic graph search selects one candidate
per shared node across nine analytically feasible flights.

Phase A passed 5/5 contact nodes, 5/5 bounce nodes, 9/9 flight edges and 10/10 shared
nodes. Phase B executed on 314 observations with structural contact/shared-node
constraints. Its median/p95/maximum reprojection errors are 17.6898/53.9555/86.1965
px, so the result is `STAGE5B_V34_OPTIMIZATION_PARTIAL`. Analytics remains blocked.
