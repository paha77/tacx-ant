# Antifier

> **Legacy project:** This repository is the old Antifier codebase and is kept for reference. New development will continue in the Trainercast repository: <https://github.com/paha77/trainercast>.

Antifier is a small interactive broadcaster for indoor cycling apps. It sends simulated trainer and heart-rate data to apps such as Zwift or TrainerRoad, while you control the numbers from the keyboard.

It can broadcast in two ways:

- **ANT+**: exposes a Fitness Equipment Control trainer channel plus a heart-rate channel through an ANT+ USB dongle.
- **Bluetooth**: exposes a BLE Fitness Machine Service (FTMS) trainer plus a BLE Heart Rate Service through BlueZ.

Antifier does not control a physical trainer brake. It is a software broadcaster/simulator: you set power, cadence, heart rate, and resistance interactively, and the selected transport broadcasts those values to a receiver app.

## What You Can Do

- Pair a computer running Antifier as an ANT+ FE-C trainer and ANT+ heart-rate sensor.
- Pair it as a Bluetooth FTMS controllable trainer and Bluetooth heart-rate sensor.
- Change the broadcast values live from a terminal dashboard.
- Let Bluetooth training apps send FTMS control-point commands such as request control, target resistance, target power, target inclination, start, stop, and indoor-bike simulation parameters.
- Customize ANT+ FE-C and heart-rate identity metadata with environment variables.

## Project Layout

This repository is intentionally simple and script-oriented:

- `antifier.py` is the main interactive broadcaster.
- `ant.py` contains ANT+ dongle discovery, setup, packet helpers, and channel configuration.
- `ble.py` contains the BlueZ/dbus-next Bluetooth FTMS and heart-rate broadcaster.
- `reset_ant_usb.py` and `reset_usb.py` are helper scripts for resetting an ANT+ USB stick.
- `Dockerfile` and `docker-compose.yml` provide a Python 3.14.6 runtime with USB passthrough.
- `trainer.py`, `power_curve.py`, `runoff_calibration.py`, `tacx_trainer_debug.py`, `old-scripts/`, and `T1942/` are historical or diagnostic tools.

## Requirements

### For ANT+ Mode

- Linux, Windows, or macOS can be used by the Python code, but this repository's Docker setup is Linux-oriented.
- An ANT+ USB dongle. Garmin/Suunto sticks commonly use USB IDs `0fcf:1009` or `0fcf:1008`.
- On Linux, a serial device such as `/dev/ttyUSB0`. Antifier probes `/dev/serial/by-id/*` entries containing `ant`, then `/dev/ttyUSB*`.
- Python packages: `pyserial` and `pyusb`.

### For Bluetooth Mode

- Linux with BlueZ.
- A running system D-Bus.
- A Bluetooth adapter that supports BLE peripheral advertising.
- Python package: `dbus-next`.

Bluetooth app behavior depends on the host adapter, BlueZ, and the receiver app. The code has been syntax-checked and locally smoke-tested, but real app compatibility should still be verified with your hardware.

### For Docker

- Docker Compose.
- Linux host access to the ANT+ dongle device.
- Privileged/device passthrough, as configured in `docker-compose.yml`.

## Step-by-Step Setup Guide

### 1. Clone the Project

```bash
git clone https://github.com/john-38787364/antifier.git
cd antifier
```

If you already have the repository, run the remaining commands from the repository root.

### 2. Choose a Runtime

Use Docker if you want the pinned Python 3.14.6 environment from this repository:

```bash
docker compose build
```

Use local Python if you prefer to run directly on the host:

```bash
python3 -m pip install pyserial pyusb dbus-next
```

For ANT+ only, `dbus-next` is not needed. For Bluetooth mode, it is required.

### 3. Plug In and Find the ANT+ Dongle

On Linux, plug in the ANT+ USB stick and check that the system sees it:

```bash
lsusb | grep 0fcf
ls -l /dev/serial/by-id/* /dev/ttyUSB*
```

If you run locally, Antifier will probe likely serial ports automatically.

If you run with Docker, edit the `devices:` entry in `docker-compose.yml` if your ANT+ stick has a different path:

```yaml
devices:
    - /dev/serial/by-id/your-ant-stick-id:/dev/ttyUSB0
```

You can also map a direct serial path:

```yaml
devices:
    - /dev/ttyUSB0:/dev/ttyUSB0
```

### 4. Start ANT+ Mode

ANT+ is the default transport.

Run locally:

```bash
python3 antifier.py
```

Run with Docker:

```bash
docker compose run --rm antifier
```

The terminal should show the Antifier dashboard. In your training app, search for a power source, controllable trainer, or FE-C trainer, then pair the discovered ANT+ device. Search for the heart-rate sensor separately if your app lists it as a separate device.

### 5. Start Bluetooth Mode

Bluetooth mode requires BlueZ, system D-Bus, and a BLE adapter that supports peripheral advertising.

Run locally:

```bash
python3 antifier.py --transport bluetooth
```

Or use the environment variable:

```bash
ANTIFIER_TRANSPORT=bluetooth python3 antifier.py
```

Run with Docker:

```bash
docker compose run --rm -e ANTIFIER_TRANSPORT=bluetooth antifier
```

The default advertised Bluetooth name is `Antifier`. Change it with:

```bash
ANTIFIER_BLUETOOTH_NAME="Antifier Bike" python3 antifier.py --transport bluetooth
```

If a training app cached an older Bluetooth service layout, forget/unpair the old trainer in that app and scan again.

### 6. Control the Broadcast Values

Antifier runs at about 4 Hz and shows the current values in the terminal. Use these keys while it is running:

| Key | Action |
| --- | --- |
| `q` / `a` | Increase/decrease power by 5 W |
| `w` / `s` | Increase/decrease cadence by 1 rpm |
| `e` / `d` | Increase/decrease heart rate by 1 bpm |
| `t` / `g` | Increase/decrease resistance by 1% |
| `r` | Reset to 150 W, 90 rpm, 120 bpm, 0% resistance |
| `x` | Quit |

In Bluetooth mode, the dashboard also shows the last FTMS command received from the connected app, including the command name, decoded value, result, raw bytes, control ownership, and age.

### 7. Stop and Reset the ANT+ Dongle if Needed

Quit Antifier with `x` or `Ctrl+C`.

If the ANT+ stick is left in a bad state or another app cannot use it, unplug/replug it or reset it from the host:

```bash
sudo python3 reset_usb.py list
sudo python3 reset_usb.py path /dev/bus/usb/001/002
```

Docker can also reset the ANT+ stick on start or exit:

```bash
docker compose run --rm -e ANTIFIER_RESET_ANT_USB_ON_START=1 antifier
docker compose run --rm -e ANTIFIER_RESET_ANT_USB_ON_EXIT=1 antifier
```

## Configuration

### Transport

```bash
python3 antifier.py --transport ant
python3 antifier.py --transport bluetooth
ANTIFIER_TRANSPORT=bluetooth python3 antifier.py
```

Accepted transport names are `ant`, `ant+`, `bluetooth`, and `ble`.

### ANT+ FE-C Identity

Zwift and similar apps do not receive a free-form ANT+ trainer name from this script. They usually label the pairing entry from ANT+ profile metadata such as device number, manufacturer, model, product, and serial fields.

The default FE-C metadata uses Tacx-like values. Override them before starting Antifier:

```bash
ANTIFIER_FEC_DEVICE_NUMBER=207 \
ANTIFIER_FEC_MANUFACTURER_ID=89 \
ANTIFIER_FEC_MODEL_NUMBER=33669 \
ANTIFIER_FEC_HARDWARE_REVISION=1 \
ANTIFIER_FEC_SOFTWARE_REVISION=1 \
ANTIFIER_FEC_SERIAL_NUMBER=1 \
python3 antifier.py
```

If Zwift still shows an old label, forget/unpair the cached trainer entry and rescan.

### ANT+ Heart-Rate Identity

```bash
ANTIFIER_HR_DEVICE_NUMBER=365 \
ANTIFIER_HR_MANUFACTURER_ID=89 \
ANTIFIER_HR_MODEL_NUMBER=120 \
ANTIFIER_HR_HARDWARE_REVISION=1 \
ANTIFIER_HR_SOFTWARE_REVISION=1 \
ANTIFIER_HR_SERIAL_NUMBER=365 \
python3 antifier.py
```

### Bluetooth Options

```bash
ANTIFIER_BLUETOOTH_NAME="Antifier"
ANTIFIER_BLUETOOTH_ADAPTER="/org/bluez/hci0"
ANTIFIER_BLUETOOTH_MIN_RESISTANCE=0
ANTIFIER_BLUETOOTH_MAX_RESISTANCE=100
ANTIFIER_BLUETOOTH_RESISTANCE_INCREMENT=1
ANTIFIER_BLUETOOTH_GRADE_RESISTANCE_FACTOR=1
```

Bluetooth mode advertises:

- Fitness Machine Service (`0x1826`)
- Heart Rate Service (`0x180d`)
- FTMS Indoor Bike Data (`0x2ad2`)
- FTMS Fitness Machine Feature (`0x2acc`)
- Supported Resistance Level Range (`0x2ad6`)
- Fitness Machine Control Point (`0x2ad9`)
- Fitness Machine Status (`0x2ada`)
- Device Information metadata

### Debug Output

Set `ANTIFIER_DEBUG=1` to use compact status output and print raw ANT+ messages:

```bash
ANTIFIER_DEBUG=1 python3 antifier.py
```

## Verification

Useful checks while developing or troubleshooting:

```bash
python3 -m compileall .
docker compose config
docker compose build
docker run --rm -v "$PWD:/antifier" -w /antifier tacx-ant-antifier python -m compileall .
docker run --rm -v "$PWD:/antifier" -w /antifier tacx-ant-antifier python -c "import usb.core, serial; import ant, antifier; print('imports ok')"
```

If local bytecode caches are not writable, use a temporary pycache directory:

```bash
PYTHONPYCACHEPREFIX=/tmp/tacx-ant-pycache python3 -m compileall ant.py antifier.py ble.py
```

## Troubleshooting

- **`ANT Stick not found`**: check `lsusb | grep 0fcf`, check `/dev/ttyUSB*`, and make sure the Docker device mapping points at the correct host device.
- **Permission denied on `/dev/ttyUSB0`**: run with suitable device permissions, add your user to the relevant serial group, or use Docker with the configured device passthrough.
- **Training app shows an old trainer name**: forget/unpair the old device in the app, restart the app, and scan again.
- **Bluetooth does not advertise**: confirm BlueZ is running, D-Bus is available, the adapter path is correct, and the adapter supports BLE peripheral advertising.
- **Another app cannot use the ANT+ dongle after Antifier exits**: unplug/replug the dongle or use `reset_usb.py` from the host.

## Current Limitations

- Bluetooth FTMS behavior still needs real-world verification against each target app and adapter combination.
- The Bluetooth broadcaster is a software GATT peripheral; it does not change resistance on a real trainer.
- ANT+ FE-C pairing names are controlled by ANT+ metadata and app behavior, not by a custom friendly name in Antifier.
- Historical scripts are kept for diagnostics and compatibility, but `antifier.py` is the main supported entry point.
