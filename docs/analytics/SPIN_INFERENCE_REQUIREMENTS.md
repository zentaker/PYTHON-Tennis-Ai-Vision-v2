# Spin inference requirements

Broadcast footage may not visibly resolve actual ball spin. Future output is therefore an estimated
family (`flat`, `topspin`, `slice`, or `unknown`), not measured spin. RPM is out of scope.

Useful evidence may include pose and wrist motion, racket/racket-head detection, swing direction,
contact height, approved 3D trajectory, speed, post-bounce behavior, and temporal context. Bounce
behavior alone cannot establish topspin or slice. Any future classifier requires a human gate and
must preserve `unknown` when evidence is insufficient.
