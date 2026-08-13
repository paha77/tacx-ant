OVERVIEW
This project broadcasts ANT+ FE-C trainer data and ANT+ heart-rate data through an ANT+ dongle. Power, cadence, and heart rate are controlled interactively from the keyboard.

REQUIREMENTS
- ANT+ dongle, usually a Garmin or Suunto device with hardware ID 0fcf:1009 or 0fcf:1008
- Linux serial device mapping for the dongle, usually /dev/ttyUSB*
- Docker operation uses privileged mode and device passthrough

RUN
Native Python:
python3 antifier.py

Docker:
docker compose run --rm antifier

KEYBOARD CONTROLS
When run in an interactive terminal, antifier.py displays a colorful responsive text dashboard with the current broadcast values and controls. It falls back to a compact one-line status when stdout is not a terminal or ANTIFIER_DEBUG=1 is enabled.

q: Increase power by 5 W
a: Decrease power by 5 W
w: Increase cadence by 1 rpm
s: Decrease cadence by 1 rpm
e: Increase heart rate by 1 beat/minute
d: Decrease heart rate by 1 beat/minute
r: Reset to 150 W, 90 rpm, 120 bpm
x: Quit

DEBUGGING
Set ANTIFIER_DEBUG=1 to print raw ANT messages.

PROBLEMS
1. Unplug and replug the ANT+ dongle if another application has taken ownership.
2. Check the mapped device with ls /dev/ttyUSB* or ls /dev/serial/by-id/*.
3. Report issues via https://github.com/john-38787364/antifier.
