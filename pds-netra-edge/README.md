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
python -m app.main --config config/pds_netra_config.yaml --device cpu --log-level DEBUG
```

This will start the MQTT client, spawn a processing thread per camera, and emit dummy events to the configured broker. Logs will be printed to the console. Modify `config/pds_netra_config.yaml` or set environment variables (see `.env.example`) to point to your own cameras or broker.

## Using Docker

A `docker-compose.yml` file is provided for local development. It starts a Mosquitto broker and the edge node container. To build and run the stack:

```bash
docker compose up --build
```

The edge node service uses the `Dockerfile.mac-dev` by default. For Jetson deployment build using `Dockerfile.jetson` on the target device instead:

```bash
docker build -f docker/Dockerfile.jetson -t pds-netra-edge:jetson .
```

## Next steps

This base project provides the scaffolding for PDS Netra’s edge node. Future enhancements include:

- Implementing proper object tracking (e.g. ByteTrack or DeepSORT).
- Adding rule evaluation and zone logic to generate real events.
- Uploading cropped images/clips to object storage and including their URLs in the event payload.
- Extending health monitoring with camera status detection.

Contributions and refinements are welcome!
