FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip git build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip && python3.11 -m pip install -r requirements.txt

COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
