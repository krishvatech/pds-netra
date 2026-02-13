# Jetson GPU Probe

`jetson_gpu_probe.py` helps you verify whether inference is using GPU on Jetson by reading `tegrastats` and checking `/dev/nvhost-gpu` users.

It logs each sample to CSV and prints a final verdict:
- `GPU used` when GR3D activity is seen (`GR3D > 0` in more than 10% of samples), or when the tracked PID is seen on `/dev/nvhost-gpu`.
- `GPU not used / mostly CPU` otherwise.

## Usage

1. Monitor while app is already running:

```bash
sudo python3 scripts/diagnostics/jetson_gpu_probe.py --duration-sec 120
```

2. Monitor a specific PID:

```bash
sudo python3 scripts/diagnostics/jetson_gpu_probe.py --pid <PID> --duration-sec 60
```

3. Run app under monitoring:

```bash
sudo python3 scripts/diagnostics/jetson_gpu_probe.py --cmd "python3 your_entrypoint.py --your-args"
```

## Notes

- `GR3D_FREQ` is the main Jetson GPU load indicator for 3D/compute activity.
- GUI processes such as `Xorg` or `gnome-shell` can also appear on `/dev/nvhost-gpu`; this is normal.
- Default CSV output is `logs/gpu_probe.csv`.
- Run parser checks with:

```bash
python3 scripts/diagnostics/jetson_gpu_probe.py --self-test
```
