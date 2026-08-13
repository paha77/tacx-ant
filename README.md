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

* q: Increase power by 5 W
* a: Decrease power by 5 W
* w: Increase cadence by 1 rpm
* s: Decrease cadence by 1 rpm
* e: Increase heart rate by 1 beat/minute
* d: Decrease heart rate by 1 beat/minute
* r: Reset to 150 W, 90 rpm, 120 bpm
* x: Quit
