FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY constraints.txt requirements-runtime.txt requirements-openmmlab.txt /workspace/containers/player-perception/
RUN python -m pip install --upgrade pip \
    && python -m pip install -c /workspace/containers/player-perception/constraints.txt \
        -r /workspace/containers/player-perception/requirements-runtime.txt \
        -r /workspace/containers/player-perception/requirements-openmmlab.txt

COPY src /workspace/src
COPY scripts /workspace/scripts
COPY config /workspace/config
COPY data/clips/nivel_a2_01/clip_manifest.json /workspace/data/clips/nivel_a2_01/clip_manifest.json

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /input /output /models \
    && chown -R appuser:appuser /workspace /input /output /models
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
    CMD python -m src.player_perception.cli --backend openmmlab --validate-only \
        --model-bundle /workspace/config/player_perception/p1_openmmlab.json || exit 1

ENTRYPOINT ["python", "-m", "src.player_perception.cli"]
