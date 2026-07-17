FROM pytorch/pytorch:2.3.1-cuda12.1-cudnn8-runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace

ARG MMDET_REF=v3.2.0
ARG MMPOSE_REF=v1.3.2

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
RUN git clone --depth 1 --branch ${MMDET_REF} https://github.com/open-mmlab/mmdetection.git /opt/openmmlab/mmdetection \
    && git clone --depth 1 --branch ${MMPOSE_REF} https://github.com/open-mmlab/mmpose.git /opt/openmmlab/mmpose
ENV P1_CONFIG_ROOT=/opt/openmmlab
COPY containers/player-perception/constraints.txt containers/player-perception/requirements-runtime.txt containers/player-perception/requirements-openmmlab.txt /workspace/containers/player-perception/
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --only-binary=mmcv --no-deps \
        --find-links https://download.openmmlab.com/mmcv/dist/cu121/torch2.3/index.html \
        mmcv==2.2.0 \
    && python -m pip install -c /workspace/containers/player-perception/constraints.txt \
        -r /workspace/containers/player-perception/requirements-runtime.txt \
    && python -m pip install --no-deps -r /workspace/containers/player-perception/requirements-openmmlab.txt

COPY src /workspace/src
COPY scripts /workspace/scripts
COPY config /workspace/config
COPY data/clips/nivel_a2_01/clip_manifest.json /workspace/data/clips/nivel_a2_01/clip_manifest.json
COPY data/clips/nivel_a2_01/homography.json /workspace/data/clips/nivel_a2_01/homography.json

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /input /output /models \
    && chown -R appuser:appuser /workspace /input /output /models
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s \
    CMD python -m src.player_perception.cli --backend openmmlab --validate-only \
        --model-bundle /workspace/config/player_perception/p1_openmmlab.json || exit 1

ENTRYPOINT ["python", "-m", "src.player_perception.cli"]
