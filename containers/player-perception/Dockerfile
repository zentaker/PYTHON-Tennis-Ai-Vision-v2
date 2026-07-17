FROM python:3.11-slim
WORKDIR /workspace
COPY requirements-gpu.txt /workspace/requirements-gpu.txt
RUN pip install --no-cache-dir -r /workspace/requirements-gpu.txt
ENTRYPOINT ["python", "-m", "src.player_perception.cli"]
