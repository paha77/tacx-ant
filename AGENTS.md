# AGENTS.md

## Project Overview

This is a simplified Antifier ANT+ broadcaster project. It broadcasts ANT+ FE-C power/cadence data and ANT+ heart-rate data through an ANT+ dongle for apps such as Zwift or TrainerRoad. Power, cadence, and heart rate are set interactively from the keyboard.

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

- `antifier.py`: Main interactive terminal broadcaster. It has one runtime mode and starts the app in `__main__`.
- `ant.py`: ANT+ dongle packet helpers, checksum calculation, channel configuration, reset, and dongle discovery.
- `trainer.py`: Historical Tacx trainer USB helper retained for diagnostics/legacy scripts; not used by `antifier.py`.
- `power_curve.py`: Historical GUI tool for generating custom power curve factors.
- `runoff_calibration.py`: Historical CLI calibration/rolldown helper.
- `tacx_trainer_debug.py`: Historical diagnostic trainer logging helper.
- `reset_usb.py`: Host-side USB reset utility.
- `Dockerfile`: Python 3.14.6 container runtime with `pyserial`, `pyusb`, and `usbutils`.
- `docker-compose.yml`: Interactive broadcaster service definition with USB device passthrough.

## Dependencies

Python packages:
- `pyserial`
- `pyusb`

Host/hardware requirements for real operation:
- ANT+ dongle, commonly Garmin/Suunto hardware IDs `0fcf:1009` or `0fcf:1008`.
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
docker run --rm -v "$PWD:/antifier" -w /antifier tacx-ant-antifier python -c "import usb.core, serial; import ant, antifier; print('imports ok')"
```

Run the interactive broadcaster:

```bash
python3 antifier.py
```

Run Docker service:

```bash
docker compose up antifier
```

## Zwift FE-C Pairing Identity

Zwift does not receive a free-form custom device name from this ANT+ FE-C broadcaster. It typically labels the pairing entry from ANT+ profile metadata such as manufacturer ID, FE-C device number, model/product data, and serial fields. A label like `Peter's ANT+ dongle` is not possible through the current ANT+ FE-C pages unless Zwift itself provides a rename/alias feature.

The current code makes the FE-C identity metadata configurable through environment variables:
- `ANTIFIER_FEC_DEVICE_NUMBER` defaults to `207`.
- `ANTIFIER_FEC_MANUFACTURER_ID` defaults to `89` (Tacx).
- `ANTIFIER_FEC_MODEL_NUMBER` defaults to `33669`.
- `ANTIFIER_FEC_HARDWARE_REVISION` defaults to `1`.
- `ANTIFIER_FEC_SOFTWARE_REVISION` defaults to `1`.
- `ANTIFIER_FEC_SERIAL_NUMBER` defaults to `1`.

`ant.py` uses these values during FE-C channel setup, and `antifier.py` uses the same values while broadcasting manufacturer/product pages. If Zwift still shows an old label, restart Zwift and forget/unpair the cached trainer entry before rescanning.

## Verification Already Performed

During the Python 3 migration, these checks passed:
- `python3 -m compileall .` with local Python 3.12.
- `docker compose config`.
- `docker compose build` using `python:3.14.6`.
- Python 3.14.6 container compile check over the full repo.
- Python 3.14.6 container import check for `usb.core`, `serial`, `ant`, and `antifier`.

During the FE-C identity metadata update, this check passed:
- `PYTHONPYCACHEPREFIX=/tmp/tacx-ant-pycache python3 -m compileall ant.py antifier.py`.

The plain `python3 -m compileall ant.py antifier.py` command could not write bytecode because the existing local `__pycache__` files are not writable in this workspace. That was a cache permission issue, not a syntax failure.

Hardware behavior was not verified because it requires a physical ANT+ dongle and receiver.

## Development Notes

- Do not rewrite the project into a package unless explicitly requested.
- Keep changes scoped and compatible with the existing top-level script workflow.
- Be careful with import-time side effects. `antifier.py` should remain importable without parsing CLI args or opening hardware.
- `old-scripts/` are historical, but should remain syntactically valid Python 3 when possible.
- `ant.pyc` and `trainer.pyc` may exist as ignored legacy artifacts; do not commit bytecode or `__pycache__`.
- Generated files such as logs, calibration pickle files, and packaged `.EXE` binaries are legacy artifacts. Avoid changing or deleting them unless explicitly requested.
- Real USB behavior can differ across Linux, Windows, and macOS because `pyusb`, serial ports, and driver ownership behave differently.
