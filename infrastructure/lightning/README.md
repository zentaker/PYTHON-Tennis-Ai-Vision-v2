# Lightning AI offline SDK gate

This directory contains only a free, offline API-shape gate. It pins the official
`lightning-sdk==2026.7.9.post0` package and inspects the real `Studio`, `Job`,
`Machine`, upload/download, logs/status and stop APIs without authentication,
resource hydration, account setup, cloud calls or credit use.

Run locally in an isolated environment:

```bash
python3 -m venv /tmp/lightning-sdk-gate
/tmp/lightning-sdk-gate/bin/pip install -r infrastructure/lightning/requirements-lightning.txt
/tmp/lightning-sdk-gate/bin/python scripts/lightning_sdk_gate.py
```

The project does not yet implement a Lightning GPU adapter. In particular, it does
not claim that Jobs can execute the validated repository Dockerfile, that CUDA or a
specific GPU is available, or that result transfer/cancellation/recovery works.
