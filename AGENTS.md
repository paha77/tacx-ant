# AGENTS.md

## Project Overview

This is a legacy Antifier/Tacx ANT+ bridge project. It reads data from a Tacx trainer over USB and broadcasts ANT+ FE-C, heart-rate, cadence, and power-style data through an ANT+ dongle for apps such as Zwift or TrainerRoad.

Keep the existing script-oriented structure. The project is intentionally flat and legacy: top-level scripts are the main entry points, `classes/` contains a small helper package, and `old-scripts/` plus `T1942/` contain historical/diagnostic scripts.

## Python Runtime

The project has been migrated from Python 2 to Python 3. The target runtime is Python 3.14.6.

Important migration details:
- Use `python3` in docs and shell commands.
- `Tkinter` is now `tkinter`.
- USB/serial packets must be bytes, not text strings. Prefer `bytes([...])` for byte-int arrays and `binascii.unhexlify(...)` for hex packet strings.
- Decode `binascii.hexlify(...)` results to ASCII before string slicing/comparison.
- Avoid reintroducing Python 2 syntax such as `print ...`, `except Exception, e`, `raw_input`, or `dict.iterkeys()`.

## Main Files

- `antifier.py`: Main GUI/headless application. Parses CLI arguments at import time and starts the app in `__main__`.
- `ant.py`: ANT+ dongle packet helpers, checksum calculation, channel configuration, reset, and dongle discovery.
- `trainer.py`: Tacx trainer USB discovery, initialization, read/write, and power curve parsing.
- `power_curve.py`: GUI tool for generating custom power curve factors.
- `runoff_calibration.py`: CLI calibration/rolldown helper.
- `tacx_trainer_debug.py`: Diagnostic trainer logging helper.
- `reset_usb.py`: Host-side USB reset utility.
- `power_calc_factors_*.txt`: Power curve calibration data files.
- `Dockerfile`: Python 3.14.6 container runtime with `pyserial`, `pyusb`, `numpy`, and `usbutils`.
- `docker-compose.yml`: Headless simulation-oriented service definition with USB device passthrough.

## Dependencies

Python packages:
- `pyserial`
- `pyusb`
- `numpy`

GUI mode also needs `tkinter`. The official `python:3.14.6` image used here imports `tkinter` successfully.

Host/hardware requirements for real operation:
- ANT+ dongle, commonly Garmin/Suunto hardware IDs `0fcf:1009` or `0fcf:1008`.
- Tacx trainer USB head unit, historically tested with `0x1932` and `0x1942`.
- Linux serial device mapping for ANT+ dongles, usually `/dev/ttyUSB*`.
- Docker operation uses privileged mode and device passthrough.

## Common Commands

Syntax check all Python files with the local Python 3:

```bash
python3 -m compileall .
```

Build the Docker image:

```bash
docker compose build
```

Validate Docker Compose configuration:

```bash
docker compose config
```

Compile inside the target Python 3.14.6 image:

```bash
docker run --rm -v "$PWD:/antifier" -w /antifier tacx-ant-antifier python -m compileall .
```

Check target-image imports:

```bash
docker run --rm -v "$PWD:/antifier" -w /antifier tacx-ant-antifier python -c "import usb.core, serial, numpy, tkinter; import ant, trainer; print('imports ok')"
```

Run headless simulation:

```bash
python3 antifier.py -l -c power_calc_factors_fortius.txt -s
```

Run Docker service:

```bash
docker compose up antifier
```

## Verification Already Performed

During the Python 3 migration, these checks passed:
- `python3 -m compileall .` with local Python 3.12.
- `docker compose config`.
- `docker compose build` using `python:3.14.6`.
- Python 3.14.6 container compile check over the full repo.
- Python 3.14.6 container import check for `usb.core`, `serial`, `numpy`, `tkinter`, `ant`, and `trainer`.

Hardware behavior was not verified because it requires physical trainer and ANT+ devices.

## Development Notes

- Do not rewrite the project into a package unless explicitly requested.
- Keep changes scoped and compatible with the existing top-level script workflow.
- Be careful with import-time side effects. Some scripts parse CLI args or initialize globals at import time.
- `old-scripts/` are historical, but should remain syntactically valid Python 3 when possible.
- `ant.pyc` and `trainer.pyc` may exist as ignored legacy artifacts; do not commit bytecode or `__pycache__`.
- Generated files such as logs, calibration pickle files, and packaged `.EXE` binaries are legacy artifacts. Avoid changing or deleting them unless explicitly requested.
- Real USB behavior can differ across Linux, Windows, and macOS because `pyusb`, serial ports, and driver ownership behave differently.

