# antifier
This project broadcasts ANT+ FE-C trainer data and ANT+ heart-rate data through an ANT+ dongle. Power, cadence, and heart rate are controlled interactively from the keyboard.
Home page: https://github.com/john-38787364/antifier

## Resetting USB after usage
### Run on host (not in Docker-Container)
    python3 reset_usb.py /dev/bus/usb/001/002

## Run

Start the broadcaster with

`python3 antifier.py`

Or run it in Docker with

`docker compose run --rm antifier`

## Keyboard controls

When run in an interactive terminal, `antifier.py` displays a colorful responsive text dashboard with the current broadcast values and controls. It falls back to a compact one-line status when stdout is not a terminal or `ANTIFIER_DEBUG=1` is enabled.

* q: Increase power by 5 W
* a: Decrease power by 5 W
* w: Increase cadence by 1 rpm
* s: Decrease cadence by 1 rpm
* e: Increase heart rate by 1 beat/minute
* d: Decrease heart rate by 1 beat/minute
* r: Reset to 150 W, 90 rpm, 120 bpm
* x: Quit

## Zwift pairing identity

Zwift does not receive a free-form FE-C device name from this script. It usually labels the pairing entry from ANT+ profile metadata such as the FE-C device number, manufacturer, model, product, and serial fields.

By default the FE-C broadcast uses Tacx manufacturer metadata. You can override the values before starting the broadcaster:

```bash
ANTIFIER_FEC_DEVICE_NUMBER=207 \
ANTIFIER_FEC_MANUFACTURER_ID=89 \
ANTIFIER_FEC_MODEL_NUMBER=33669 \
ANTIFIER_FEC_SERIAL_NUMBER=1 \
python3 antifier.py
```

If Zwift has already paired the old entry, unpair/forget it or restart Zwift after changing these values.

## TODO

* Investigate Bluetooth FTMS broadcasting as a future option for custom human-readable device names such as `Peter's ANT+ dongle`.
