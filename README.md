# antifier
This project broadcasts interactive trainer power/cadence data and heart-rate data over ANT+ or Bluetooth. Power, cadence, and heart rate are controlled interactively from the keyboard.
Home page: https://github.com/john-38787364/antifier

## Resetting USB after usage
### Run on host (not in Docker-Container)
    python3 reset_usb.py /dev/bus/usb/001/002

## Run

Start the broadcaster with

`python3 antifier.py`

Or run it in Docker with

`docker compose run --rm antifier`

ANT+ is the default transport. Select the transport with either `--transport` or `ANTIFIER_TRANSPORT`:

```bash
python3 antifier.py --transport ant
python3 antifier.py --transport bluetooth
ANTIFIER_TRANSPORT=bluetooth python3 antifier.py
```

Bluetooth mode advertises a BLE Fitness Machine Service plus Heart Rate Service through BlueZ, then notifies connected apps with the same interactive power, cadence, resistance, and heart-rate values as the ANT+ stack. It requires a Bluetooth adapter that supports BLE peripheral advertising, a running BlueZ service, and the `dbus-next` Python package. The advertised local name defaults to `Antifier` and can be changed with `ANTIFIER_BLUETOOTH_NAME`.

In Bluetooth mode, Antifier also exposes the FTMS Fitness Machine Feature, Supported Resistance Level Range, Fitness Machine Control Point, and Fitness Machine Status characteristics. Apps can request control and set target resistance through the control point. Resistance defaults to a 0-100% range in 1% steps and can be changed with `ANTIFIER_BLUETOOTH_MIN_RESISTANCE`, `ANTIFIER_BLUETOOTH_MAX_RESISTANCE`, and `ANTIFIER_BLUETOOTH_RESISTANCE_INCREMENT`.

## Keyboard controls

When run in an interactive terminal, `antifier.py` displays a colorful responsive text dashboard with the current broadcast values and controls. It falls back to a compact one-line status when stdout is not a terminal or `ANTIFIER_DEBUG=1` is enabled.

* q: Increase power by 5 W
* a: Decrease power by 5 W
* w: Increase cadence by 1 rpm
* s: Decrease cadence by 1 rpm
* e: Increase heart rate by 1 beat/minute
* d: Decrease heart rate by 1 beat/minute
* t: Increase resistance by 1%
* g: Decrease resistance by 1%
* r: Reset to 150 W, 90 rpm, 120 bpm, 0% resistance
* x: Quit

## Zwift pairing identity

Zwift does not receive a free-form FE-C or heart-rate device name from this script. It usually labels the pairing entry from ANT+ profile metadata such as the device number, manufacturer, model, product, and serial fields.

By default the FE-C broadcast uses Tacx manufacturer metadata. You can override the values before starting the broadcaster:

```bash
ANTIFIER_FEC_DEVICE_NUMBER=207 \
ANTIFIER_FEC_MANUFACTURER_ID=89 \
ANTIFIER_FEC_MODEL_NUMBER=33669 \
ANTIFIER_FEC_SERIAL_NUMBER=1 \
python3 antifier.py
```

The heart-rate broadcast also has configurable identity metadata. Its default device number is `365`, and the default serial metadata is non-zero so Zwift should not show the HR sensor as `[0]`.

```bash
ANTIFIER_HR_DEVICE_NUMBER=365 \
ANTIFIER_HR_MANUFACTURER_ID=89 \
ANTIFIER_HR_MODEL_NUMBER=120 \
ANTIFIER_HR_SERIAL_NUMBER=365 \
python3 antifier.py
```

If Zwift has already paired the old entry, unpair/forget it or restart Zwift after changing these values.

## TODO

* Verify Bluetooth FTMS behavior against target apps such as Zwift and TrainerRoad on real hardware.
