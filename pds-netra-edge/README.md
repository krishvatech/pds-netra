# PDS Netra Edge Node (Base)

This repository contains a minimal yet functional edge node implementation for the **PDS Netra** smart CCTV surveillance system. The edge node connects to RTSP or file-based video sources, performs basic object detection and tracking using Ultralytics YOLO, and publishes structured events and health heartbeats to a central MQTT broker.

For Jetson deployment, auto-start, watchdog, and outbox operations, use the consolidated runbook in `deployment/edge/README.md`.

## Repository layout

The project follows a standard Python package layout:

```
pds-netra-edge/
  app/                # Application package
    config.py         # Configuration loader (YAML + environment)
    logging_config.py # Logging setup helper
    models/           # Pydantic models for events and health
    cv/               # Computer vision pipeline components
    events/           # MQTT client wrapper
    runtime/          # Camera loops and periodic scheduler
    main.py           # CLI entrypoint
  config/
    pds_netra_config.yaml # Sample configuration
    .env.example          # Environment variable overrides
  docker/
    Dockerfile.mac-dev    # Dockerfile for local development (CPU)
    Dockerfile.jetson     # Dockerfile for Jetson deployment (GPU)
    mosquitto.conf        # Mosquitto config used by docker-compose
  docker-compose.yml      # Compose file with edge + Mosquitto services
  requirements.txt        # Python dependencies
  tests/                  # Minimal unit tests
```

## Installation (macOS / CPU)

1. Ensure you have Python 3.10+ and a virtual environment manager installed.
2. Clone this repository and navigate into it:

```bash
git clone <repo-url> pds-netra-edge
cd pds-netra-edge
```

3. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Important for Jetson/Ultralytics compatibility:
- `numpy` is pinned to `numpy==1.26.4` (`numpy<2`) in `requirements.txt`.

Ultralytics will automatically download model weights on first run. For offline environments, download the weights ahead of time and adjust the `model_name` in `YoloDetector` accordingly.

## Running tests

Unit tests use `pytest`. Install it if necessary and run:

```bash
pip install pytest
pytest -q
```

## Running the edge node with a sample video

The edge node can operate on RTSP streams or local video files for development. To run against the sample configuration using local MP4 files:

```bash
python -m app.main --config config/pds_netra_config.yaml --device auto --log-level DEBUG
```

This will start the MQTT client, spawn a processing thread per camera, and emit dummy events to the configured broker. Logs will be printed to the console. Modify `config/pds_netra_config.yaml` or set environment variables (see `.env.example`) to point to your own cameras or broker.

Device options:

- `--device auto` (default)
- `--device cpu`
- `--device cuda:0`
- `--device tensorrt`
- `--device cuda` (alias for `cuda:0`, backward compatible)

If `--device` is not provided, the app auto-selects `cuda:0` when CUDA is available, otherwise falls back to `cpu` with a warning.

## Inference Entrypoints (Current)

Direct model inference paths in this repo:

- `app/cv/yolo_detector.py`
: `YoloDetector.__init__()` -> `YOLO(model_path)` model load
: `YoloDetector.detect()` -> `self.model.predict(...)`
: `YoloDetector.track()` -> `self.model.track(...)`
- `app/cv/fire_detection.py`
: `FireDetectionProcessor.process()` -> `self.detector.detect(frame)` (delegates to `YoloDetector.detect`)
- `app/cv/anpr.py`
: `PlateDetector.detect_plates()` -> `self.detector.detect(frame)` (delegates to `YoloDetector.detect`)

Pipeline/runtime callsites:

- `app/cv/pipeline.py`
: `Pipeline.run()` -> `self.detector.track(frame)`
- `app/runtime/camera_loop.py`
: `_start_camera()` creates `YoloDetector(...)` for general detection
: `_create_anpr_processor_for_camera()` creates ANPR `YoloDetector(...)`

Backend/library notes from scan:

- `torch`: used in `app/main.py` (startup capability logging) and `app/cv/yolo_detector.py` (CUDA model placement checks)
- `onnxruntime`: listed in `requirements.txt`; used indirectly by face/embedding stack, not as a direct detection entrypoint in edge runtime
- `tensorrt`: used through Ultralytics engine export/load path in `app/cv/yolo_detector.py`
- `deepstream`, `triton`, `cv2.dnn`: no direct runtime inference path found in current edge app code
- `gstreamer`: present in Jetson Docker dependencies (`docker/Dockerfile.jp6`), not a direct Python inference path

## Jetson GPU Setup (JetPack 6.2.2 / L4T 36.5.0)

For Jetson host installs (outside Docker), install CUDA-enabled PyTorch wheels first:

```bash
python3 -m pip install --upgrade pip setuptools wheel
python3 -m pip install --extra-index-url https://pypi.ngc.nvidia.com --upgrade torch torchvision torchaudio
python3 -m pip install -r requirements.txt
```

Sanity-check CUDA from Python:

```bash
python3 - <<'PY'
import torch
print("torch:", torch.__version__)
print("cuda_available:", torch.cuda.is_available())
print("gpu0:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A")
PY
```

Run edge on GPU:

```bash
python -m app.main --config config/pds_netra_config.yaml --device auto
python3 -m app.main --config config/pds_netra_config.yaml --device cuda:0
python3 -m app.main --config config/pds_netra_config.yaml --device tensorrt
```

## TensorRT Path

Use TensorRT directly with an engine model:

```bash
python3 -m app.main --config config/pds_netra_config.yaml --device tensorrt
```

If your model is `.pt` and the `.engine` file is missing, the app auto-exports on first run.
You can also export manually:

```bash
python3 scripts/export_engine.py --model models/fire.pt --imgsz 640 --half --dynamic
```

The runtime also supports loading an explicit engine path (for example `animal.engine`) via `EDGE_YOLO_MODEL`.

## Verify GPU Inference

Use the built-in benchmark/check script:

```bash
python3 scripts/check_gpu_inference.py --model animal.pt --device cuda:0 --imgsz 640 --warmup 20 --iters 100
```

It prints average latency, FPS, and `GPU USED: YES/NO`.

While the app runs, confirm GPU activity with tegrastats:

```bash
sudo tegrastats --interval 200
```

Check for non-zero `GR3D_FREQ` while inference is running.

Check which process is touching the GPU device node:

```bash
sudo fuser -v /dev/nvhost-gpu
```

Optional jtop monitoring:

```bash
sudo -H pip3 install -U jetson-stats
sudo jtop
```

In `jtop`, open the GPU tab and confirm utilization/frequency rises during inference.

## Jetson live-lag tuning

If the dashboard live feed is delayed on Jetson (while local works), enable low-latency capture controls in `.env`:

```bash
EDGE_LIVE_LATEST_FRAME_MODE=true
EDGE_RTSP_CAPTURE_BUFFER=1
```

`EDGE_LIVE_LATEST_FRAME_MODE` keeps only the most recent camera frame for processing (drops stale buffered frames), which prevents multi-minute RTSP lag when inference runs slower than camera FPS.

Important deployment note:
- Edge writer and backend reader must point to the same live-frame directory.
- Set one shared path for both services (example below):

```bash
export PDS_LIVE_DIR=/var/lib/pds/live
export EDGE_LIVE_DIR=/var/lib/pds/live
```

Edge runtime also supports legacy `EDGE_LIVE_ANNOTATED_DIR`, but `EDGE_LIVE_DIR` is preferred.

## Using Docker

A `docker-compose.yml` file is provided for local development. It starts a Mosquitto broker and the edge node container. To build and run the stack:

```bash
docker compose up --build
```

The edge node service uses the `Dockerfile.mac-dev` (CPU-only) by default.
Do not use `docker-compose.yml` on Jetson if you need CUDA/ANPR OCR.

For Jetson GPU deployment (JetPack 6), run:

```bash
cd pds-netra-edge
docker compose -f docker-compose.jetson.gpu.yml up --build -d
```

If you run from the repo root, use:

```bash
docker compose -f pds-netra-edge/docker-compose.jetson.gpu.yml up --build -d
```

If you prefer a direct image build, use `docker/Dockerfile.jp6` on the target device:

```bash
docker build -f docker/Dockerfile.jp6 -t pds-netra-edge:jetson .
```

## Next steps

This base project provides the scaffolding for PDS Netra’s edge node. Future enhancements include:

- Implementing proper object tracking (e.g. ByteTrack or DeepSORT).
- Adding rule evaluation and zone logic to generate real events.
- Uploading cropped images/clips to object storage and including their URLs in the event payload.
- Extending health monitoring with camera status detection.

Contributions and refinements are welcome!
