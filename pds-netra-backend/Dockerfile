FROM python:3.10-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /opt/app
RUN apt-get update && apt-get install -y \
    g++ \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
    numpy \
    opencv-python-headless \
    insightface \
    onnxruntime
COPY . .
RUN pip install --no-cache-dir .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
