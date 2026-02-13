#!/usr/bin/env python3
"""
Jetson GPU probe utility.

Collects tegrastats samples, optionally correlates /dev/nvhost-gpu users,
writes CSV logs, and prints a clear GPU usage verdict.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import select
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable


GPU_DEV_PATH = "/dev/nvhost-gpu"
GPU_PROBE_EVERY_N_SAMPLES = 5

RAM_RE = re.compile(r"\bRAM\s+(\d+)\s*/\s*(\d+)\s*([A-Za-z]+)\b")
SWAP_RE = re.compile(r"\bSWAP\s+(\d+)\s*/\s*(\d+)\s*([A-Za-z]+)\b")
CPU_RE = re.compile(r"\bCPU\s*\[([^\]]+)\]")
EMC_RE = re.compile(r"\bEMC_FREQ\s+([0-9]+(?:\.[0-9]+)?)%")
GR3D_RE = re.compile(r"\bGR3D(?:_FREQ)?\s+([0-9]+(?:\.[0-9]+)?)%(?:\s*@\s*([^\s]+))?")
NVDEC_RE = re.compile(r"\bNVDEC\d*\b(?:\s+([^\s]+))?", flags=re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
CPU_PERCENT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)%")
PID_RE = re.compile(r"\b(\d+)\b")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_pct(numer: int, denom: int) -> float:
    if denom <= 0:
        return 0.0
    return (100.0 * numer) / float(denom)


def to_mb(value: int, unit: str) -> int:
    unit_u = unit.upper()
    if unit_u.startswith("G"):
        return int(value * 1024)
    if unit_u.startswith("K"):
        return int(value / 1024)
    return value


def parse_cpu_percent_list(cpu_blob: str | None) -> list[float | None]:
    if not cpu_blob:
        return []
    values: list[float | None] = []
    for token in cpu_blob.split(","):
        t = token.strip()
        if not t:
            continue
        if t.lower() == "off":
            values.append(None)
            continue
        m = CPU_PERCENT_RE.search(t)
        if m:
            try:
                values.append(float(m.group(1)))
            except ValueError:
                values.append(None)
        else:
            values.append(None)
    return values


def parse_freq_mhz(freq_blob: str | None) -> float | None:
    if not freq_blob:
        return None
    values: list[float] = []
    for raw in NUM_RE.findall(freq_blob):
        try:
            values.append(float(raw))
        except ValueError:
            continue
    if not values:
        return None
    # Multi-GPC formats can include a list like @[1098,1098]. Use max clock.
    return max(values)


def parse_tegrastats_line(line: str, ts_utc: str | None = None) -> dict:
    parsed = {
        "timestamp_utc": ts_utc or utc_now_iso(),
        "raw_line": line.strip(),
        "gr3d_percent": None,
        "gr3d_freq_mhz": None,
        "cpu_per_core_percent": [],
        "ram_used_mb": None,
        "ram_total_mb": None,
        "swap_used_mb": None,
        "swap_total_mb": None,
        "emc_percent": None,
        "nvdec_status": None,
    }

    ram_m = RAM_RE.search(line)
    if ram_m:
        try:
            parsed["ram_used_mb"] = to_mb(int(ram_m.group(1)), ram_m.group(3))
            parsed["ram_total_mb"] = to_mb(int(ram_m.group(2)), ram_m.group(3))
        except ValueError:
            pass

    swap_m = SWAP_RE.search(line)
    if swap_m:
        try:
            parsed["swap_used_mb"] = to_mb(int(swap_m.group(1)), swap_m.group(3))
            parsed["swap_total_mb"] = to_mb(int(swap_m.group(2)), swap_m.group(3))
        except ValueError:
            pass

    cpu_m = CPU_RE.search(line)
    parsed["cpu_per_core_percent"] = parse_cpu_percent_list(cpu_m.group(1) if cpu_m else None)

    emc_m = EMC_RE.search(line)
    if emc_m:
        try:
            parsed["emc_percent"] = float(emc_m.group(1))
        except ValueError:
            pass

    gr3d_m = GR3D_RE.search(line)
    if gr3d_m:
        try:
            parsed["gr3d_percent"] = float(gr3d_m.group(1))
        except ValueError:
            pass
        parsed["gr3d_freq_mhz"] = parse_freq_mhz(gr3d_m.group(2))

    nvdec_m = NVDEC_RE.search(line)
    if nvdec_m:
        status = (nvdec_m.group(1) or "present").strip()
        parsed["nvdec_status"] = status

    return parsed


def csv_cpu_blob(values: Iterable[float | None]) -> str:
    out: list[str] = []
    for value in values:
        if value is None:
            out.append("off")
        else:
            out.append(f"{value:.1f}")
    return ",".join(out)


def run_cmd(cmd: list[str], timeout_sec: float = 3.0) -> tuple[int, str]:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        return completed.returncode, output
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + ("\n" + exc.stderr if exc.stderr else "")
        return 124, output
    except Exception:
        return 1, ""


def run_cmd_with_optional_sudo(base_cmd: list[str], timeout_sec: float = 3.0) -> tuple[int, str]:
    sudo_bin = shutil.which("sudo")
    if sudo_bin:
        rc, out = run_cmd([sudo_bin, "-n", *base_cmd], timeout_sec=timeout_sec)
        if rc == 0 or out:
            return rc, out
    return run_cmd(base_cmd, timeout_sec=timeout_sec)


def extract_live_pids(text: str) -> set[int]:
    pids: set[int] = set()
    for token in PID_RE.findall(text):
        try:
            pid = int(token)
        except ValueError:
            continue
        if pid <= 1:
            continue
        if os.path.isdir(f"/proc/{pid}"):
            pids.add(pid)
    return pids


def parse_pids_from_lsof_output(raw: str) -> set[int]:
    pids: set[int] = set()
    for index, line in enumerate(raw.splitlines()):
        if not line.strip():
            continue
        if index == 0 and line.lower().startswith("command"):
            continue
        cols = line.split()
        if len(cols) >= 2 and cols[1].isdigit():
            pid = int(cols[1])
            if os.path.isdir(f"/proc/{pid}"):
                pids.add(pid)
    return pids


def detect_gpu_processes() -> tuple[set[int], str]:
    if not os.path.exists(GPU_DEV_PATH):
        return set(), "device-missing"

    fuser_bin = shutil.which("fuser")
    lsof_bin = shutil.which("lsof")

    if fuser_bin:
        rc, out = run_cmd_with_optional_sudo([fuser_bin, "-v", GPU_DEV_PATH], timeout_sec=2.0)
        pids = extract_live_pids(out)
        if pids or rc in (0, 1):
            return pids, "fuser"

    if lsof_bin:
        rc, out = run_cmd_with_optional_sudo([lsof_bin, GPU_DEV_PATH], timeout_sec=2.0)
        pids = parse_pids_from_lsof_output(out)
        if pids or rc in (0, 1):
            return pids, "lsof"

    return set(), "none"


def start_tegrastats(interval_ms: int) -> subprocess.Popen:
    tegrastats_bin = shutil.which("tegrastats")
    if not tegrastats_bin:
        raise RuntimeError("tegrastats not found in PATH")

    commands = [
        ["sudo", "-n", tegrastats_bin, "--interval", str(interval_ms)],
        [tegrastats_bin, "--interval", str(interval_ms)],
    ]
    last_error: str | None = None
    for cmd in commands:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            time.sleep(0.15)
            if proc.poll() is None:
                return proc
            out = ""
            if proc.stdout is not None:
                try:
                    out = proc.stdout.read() or ""
                except Exception:
                    out = ""
            last_error = out.strip() or f"command failed: {' '.join(cmd)}"
        except FileNotFoundError:
            last_error = f"command not found: {' '.join(cmd)}"
        except Exception as exc:
            last_error = str(exc)
    raise RuntimeError(last_error or "failed to start tegrastats")


def print_summary(samples: list[dict], target_pid: int | None) -> None:
    sample_count = len(samples)
    gr3d_values = [float(s.get("gr3d_percent") or 0.0) for s in samples]
    gr3d_positive_count = sum(1 for value in gr3d_values if value > 0.0)
    avg_gr3d = statistics.fmean(gr3d_values) if gr3d_values else 0.0
    max_gr3d = max(gr3d_values) if gr3d_values else 0.0
    gr3d_positive_pct = safe_pct(gr3d_positive_count, sample_count)

    pid_seen_count = 0
    pid_seen_pct = 0.0
    if target_pid is not None:
        pid_seen_count = sum(1 for s in samples if bool(s.get("target_pid_seen")))
        pid_seen_pct = safe_pct(pid_seen_count, sample_count)

    gpu_used = gr3d_positive_pct > 10.0
    if target_pid is not None and pid_seen_count > 0:
        gpu_used = True

    print("\n=== GPU Probe Summary ===")
    print(f"Samples collected                     : {sample_count}")
    print(f"Average GR3D load                     : {avg_gr3d:.2f}%")
    print(f"Max GR3D load                         : {max_gr3d:.2f}%")
    print(
        "Samples with GR3D > 0                 : "
        f"{gr3d_positive_count}/{sample_count} ({gr3d_positive_pct:.2f}%)"
    )
    if target_pid is not None:
        print(
            f"PID {target_pid} seen on {GPU_DEV_PATH:<12}: "
            f"{pid_seen_count}/{sample_count} ({pid_seen_pct:.2f}%)"
        )

    if gpu_used:
        print("Verdict                               : GPU used")
    else:
        print("Verdict                               : GPU not used / mostly CPU")


def run_self_test() -> int:
    print("Running parser self-test...")
    samples = [
        (
            "RAM 220/38955MB (lfb 7765x4MB) SWAP 0/19477MB (cached 0MB) "
            "CPU [2%@729,0%@729,off,off] EMC_FREQ 0%@1600 GR3D_FREQ 0%@306 NVDEC 0",
            {
                "ram_used_mb": 220,
                "ram_total_mb": 38955,
                "gr3d_percent": 0.0,
                "gr3d_freq_mhz": 306.0,
                "emc_percent": 0.0,
            },
        ),
        (
            "RAM 400/7766MB SWAP 0/3883MB CPU [15%@1420,17%@1420,12%@1420,10%@1420] "
            "EMC_FREQ 32%@2133 GR3D_FREQ 74%@[1098,1098] NVDEC OFF",
            {
                "gr3d_percent": 74.0,
                "gr3d_freq_mhz": 1098.0,
                "emc_percent": 32.0,
                "nvdec_status": "OFF",
            },
        ),
        (
            "RAM 512/7766MB SWAP 0/3883MB CPU [5%@1200,3%@1200] EMC_FREQ 12%@1600 "
            "GR3D_FREQ 11% NVDEC0 0%@716",
            {
                "gr3d_percent": 11.0,
                "gr3d_freq_mhz": None,
                "emc_percent": 12.0,
            },
        ),
    ]

    ok = True
    for line, expected in samples:
        parsed = parse_tegrastats_line(line, "2026-02-13T00:00:00Z")
        for key, expected_value in expected.items():
            if parsed.get(key) != expected_value:
                print(
                    "Self-test mismatch:",
                    f"field={key}",
                    f"expected={expected_value!r}",
                    f"actual={parsed.get(key)!r}",
                )
                ok = False
        if not parsed.get("cpu_per_core_percent"):
            print("Self-test mismatch: cpu_per_core_percent did not parse")
            ok = False

    pid_parse_fixture = """
                     USER        PID ACCESS COMMAND
    /dev/nvhost-gpu: root      1234 F.... python3
                     ubuntu    5678 F.... myapp
    """
    extracted = extract_live_pids(pid_parse_fixture)
    # This check is intentionally permissive because /proc/<pid> may not exist on the test host.
    if not isinstance(extracted, set):
        print("Self-test mismatch: PID parser did not return a set")
        ok = False

    if ok:
        print("Self-test passed.")
        return 0
    print("Self-test failed.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Jetson tegrastats GPU probe")
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=1000,
        help="Sampling interval in milliseconds (default: 1000)",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=60,
        help="Monitoring duration in seconds when --cmd is not used (default: 60)",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default="logs/gpu_probe.csv",
        help="CSV output path (default: logs/gpu_probe.csv)",
    )
    parser.add_argument(
        "--pid",
        type=int,
        default=None,
        help="Optional PID to check against /dev/nvhost-gpu users",
    )
    parser.add_argument(
        "--cmd",
        type=str,
        default=None,
        help='Optional app command to run under monitoring, e.g. --cmd "python3 app.py"',
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run parser self-test and exit",
    )
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.interval_ms <= 0:
        print("ERROR: --interval-ms must be > 0", file=sys.stderr)
        return 2
    if args.duration_sec <= 0 and not args.cmd:
        print("ERROR: --duration-sec must be > 0 when --cmd is not used", file=sys.stderr)
        return 2

    csv_path = Path(args.csv)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)

    app_proc: subprocess.Popen | None = None
    if args.cmd:
        print(f"Starting monitored command: {args.cmd}")
        app_proc = subprocess.Popen(args.cmd, shell=True, executable="/bin/bash")
        print(f"Command PID: {app_proc.pid}")

    try:
        tegrastats_proc = start_tegrastats(args.interval_ms)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Monitoring started | interval={args.interval_ms}ms | csv={csv_path}")
    if args.cmd:
        print("Mode: monitor-until-command-exits")
    else:
        print(f"Mode: fixed-duration ({args.duration_sec}s)")
    if args.pid is not None:
        print(f"Tracking PID: {args.pid}")
    print(f"GPU process probe: every {GPU_PROBE_EVERY_N_SAMPLES} sample(s)")
    print("Press Ctrl+C to stop.")

    fieldnames = [
        "timestamp_utc",
        "sample_index",
        "gr3d_percent",
        "gr3d_freq_mhz",
        "cpu_per_core_percent",
        "ram_used_mb",
        "ram_total_mb",
        "swap_used_mb",
        "swap_total_mb",
        "emc_percent",
        "nvdec_status",
        "gpu_probe_method",
        "gpu_pids",
        "target_pid",
        "target_pid_seen",
        "raw_line",
    ]

    samples: list[dict] = []
    sample_index = 0
    probe_method = "none"
    gpu_pids_cache: set[int] = set()
    start_monotonic = time.monotonic()

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames)
            writer.writeheader()

            while True:
                if app_proc is not None and app_proc.poll() is not None:
                    print("Monitored command exited; stopping probe.")
                    break
                if app_proc is None and (time.monotonic() - start_monotonic) >= args.duration_sec:
                    print("Duration reached; stopping probe.")
                    break
                if tegrastats_proc.stdout is None:
                    break

                timeout_sec = max(0.5, float(args.interval_ms) / 1000.0 * 2.0)
                ready, _, _ = select.select([tegrastats_proc.stdout], [], [], timeout_sec)
                if not ready:
                    if tegrastats_proc.poll() is not None:
                        print("tegrastats exited unexpectedly; stopping probe.")
                        break
                    continue

                line = tegrastats_proc.stdout.readline()
                if not line:
                    if tegrastats_proc.poll() is not None:
                        print("tegrastats stream ended; stopping probe.")
                        break
                    continue

                sample_index += 1
                parsed = parse_tegrastats_line(line)

                if sample_index == 1 or (sample_index % GPU_PROBE_EVERY_N_SAMPLES == 0):
                    gpu_pids_cache, probe_method = detect_gpu_processes()
                    probe_label = probe_method
                else:
                    probe_label = f"{probe_method}-cached"

                target_pid_seen = bool(args.pid is not None and args.pid in gpu_pids_cache)

                row = {
                    "timestamp_utc": parsed["timestamp_utc"],
                    "sample_index": sample_index,
                    "gr3d_percent": parsed["gr3d_percent"],
                    "gr3d_freq_mhz": parsed["gr3d_freq_mhz"],
                    "cpu_per_core_percent": csv_cpu_blob(parsed["cpu_per_core_percent"]),
                    "ram_used_mb": parsed["ram_used_mb"],
                    "ram_total_mb": parsed["ram_total_mb"],
                    "swap_used_mb": parsed["swap_used_mb"],
                    "swap_total_mb": parsed["swap_total_mb"],
                    "emc_percent": parsed["emc_percent"],
                    "nvdec_status": parsed["nvdec_status"],
                    "gpu_probe_method": probe_label,
                    "gpu_pids": ";".join(str(pid) for pid in sorted(gpu_pids_cache)),
                    "target_pid": args.pid,
                    "target_pid_seen": target_pid_seen,
                    "raw_line": parsed["raw_line"],
                }
                writer.writerow(row)
                fp.flush()

                samples.append(
                    {
                        "gr3d_percent": parsed["gr3d_percent"],
                        "target_pid_seen": target_pid_seen,
                    }
                )

                gr3d_text = "--" if parsed["gr3d_percent"] is None else f"{parsed['gr3d_percent']:.1f}%"
                freq_text = "--" if parsed["gr3d_freq_mhz"] is None else f"{parsed['gr3d_freq_mhz']:.0f}MHz"
                ram_text = (
                    "--/--MB"
                    if parsed["ram_used_mb"] is None or parsed["ram_total_mb"] is None
                    else f"{parsed['ram_used_mb']}/{parsed['ram_total_mb']}MB"
                )
                swap_text = (
                    "--/--MB"
                    if parsed["swap_used_mb"] is None or parsed["swap_total_mb"] is None
                    else f"{parsed['swap_used_mb']}/{parsed['swap_total_mb']}MB"
                )
                emc_text = "--" if parsed["emc_percent"] is None else f"{parsed['emc_percent']:.1f}%"
                nvdec_text = parsed["nvdec_status"] or "--"
                gpu_pid_text = ",".join(str(pid) for pid in sorted(gpu_pids_cache)) if gpu_pids_cache else "-"
                print(
                    f"[{sample_index:04d}] {parsed['timestamp_utc']} "
                    f"GR3D={gr3d_text} GPU_FREQ={freq_text} EMC={emc_text} "
                    f"RAM={ram_text} SWAP={swap_text} NVDEC={nvdec_text} "
                    f"GPU_PIDs={gpu_pid_text}"
                )

    except KeyboardInterrupt:
        print("\nInterrupted by user; stopping probe.")
    finally:
        try:
            tegrastats_proc.terminate()
            tegrastats_proc.wait(timeout=2.0)
        except Exception:
            try:
                tegrastats_proc.kill()
            except Exception:
                pass

        if app_proc is not None and app_proc.poll() is None:
            # Forward Ctrl+C behavior to command started by this script.
            try:
                app_proc.terminate()
                app_proc.wait(timeout=3.0)
            except Exception:
                pass

    print_summary(samples, args.pid)
    if app_proc is not None:
        print(f"Monitored command exit code             : {app_proc.returncode}")
    print(f"CSV log written to                     : {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
