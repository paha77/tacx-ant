# AGENTS.md

## Project Overview

This is a simplified Antifier ANT+/Bluetooth broadcaster project. It broadcasts ANT+ FE-C power/cadence data and ANT+ heart-rate data through an ANT+ dongle, or Bluetooth FTMS trainer data plus Bluetooth heart-rate data through BlueZ, for apps such as Zwift or TrainerRoad. Power, cadence, heart rate, and resistance are set interactively from the keyboard.

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
- `ble.py`: Bluetooth Low Energy FTMS/heart-rate broadcaster implemented as a BlueZ GATT peripheral using `dbus-next`.
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
- `dbus-next`

Host/hardware requirements for real operation:
- ANT+ dongle, commonly Garmin/Suunto hardware IDs `0fcf:1009` or `0fcf:1008`.
- Linux serial device mapping for ANT+ dongles, usually `/dev/ttyUSB*`.
- Bluetooth mode requires Linux BlueZ, a running system D-Bus, and a Bluetooth adapter that supports BLE peripheral advertising.
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

Run Bluetooth mode:

```bash
python3 antifier.py --transport bluetooth
ANTIFIER_TRANSPORT=bluetooth python3 antifier.py
```

## Bluetooth FTMS Status

Bluetooth support is implemented in `ble.py` using BlueZ GATT peripheral APIs through `dbus-next`. `antifier.py` selects it with `--transport bluetooth`, `--transport ble`, or `ANTIFIER_TRANSPORT=bluetooth`.

Current Bluetooth behavior:
- Advertises Fitness Machine Service (`0x1826`) and Heart Rate Service (`0x180d`).
- Notifies FTMS Indoor Bike Data (`0x2ad2`) with instantaneous speed placeholder, cadence, resistance level, power, and heart rate.
- Notifies Bluetooth Heart Rate Measurement (`0x2a37`).
- Exposes FTMS Fitness Machine Feature (`0x2acc`), Supported Resistance Level Range (`0x2ad6`), Fitness Machine Control Point (`0x2ad9`), and Fitness Machine Status (`0x2ada`).
- Accepts Fitness Machine Control Point writes for request control, reset, set target resistance level, set target power, start/resume, and stop/pause.
- Resistance defaults to a 0-100 range in 1-step increments and can be configured with `ANTIFIER_BLUETOOTH_MIN_RESISTANCE`, `ANTIFIER_BLUETOOTH_MAX_RESISTANCE`, and `ANTIFIER_BLUETOOTH_RESISTANCE_INCREMENT`.
- The advertised Bluetooth local name defaults to `Antifier` and can be changed with `ANTIFIER_BLUETOOTH_NAME`; adapter path defaults to `/org/bluez/hci0` and can be changed with `ANTIFIER_BLUETOOTH_ADAPTER`.

Known limitations:
- Bluetooth FTMS behavior has only been syntax-checked and locally smoke-tested for byte encoding/control-point handling.
- Real pairing/control behavior with Zwift, TrainerRoad, and other receiver apps has not been verified because it requires BLE-capable hardware, BlueZ runtime access, and target apps.
- The Bluetooth implementation is a software GATT peripheral. It does not directly control Tacx brake hardware; incoming resistance/power target commands update the broadcast state used by the interactive simulator.
- App compatibility can vary even when the FTMS GATT surface is present.

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

During the Bluetooth FTMS controllable trainer update, these checks passed:
- `PYTHONPYCACHEPREFIX=/tmp/tacx-ant-pycache python3 -m compileall antifier.py ble.py`.
- Local smoke test of FTMS Indoor Bike Data encoding, Fitness Machine Feature encoding, request-control response, and target-resistance control-point handling.

The plain `python3 -m compileall ant.py antifier.py` command could not write bytecode because the existing local `__pycache__` files are not writable in this workspace. That was a cache permission issue, not a syntax failure.

Hardware behavior was not verified because it requires a physical ANT+ dongle and receiver.

## Development Notes

- Do not rewrite the project into a package unless explicitly requested.
- Keep changes scoped and compatible with the existing top-level script workflow.
- When implementing or adding major behavior, update both `README.md` and `AGENTS.md` in the same change so user-facing docs and agent working context stay current.
- Be careful with import-time side effects. `antifier.py` should remain importable without parsing CLI args or opening hardware.
- `old-scripts/` are historical, but should remain syntactically valid Python 3 when possible.
- `ant.pyc` and `trainer.pyc` may exist as ignored legacy artifacts; do not commit bytecode or `__pycache__`.
- Generated files such as logs, calibration pickle files, and packaged `.EXE` binaries are legacy artifacts. Avoid changing or deleting them unless explicitly requested.
- Real USB behavior can differ across Linux, Windows, and macOS because `pyusb`, serial ports, and driver ownership behave differently.
