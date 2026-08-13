import os
import select
import signal
import sys
import termios
import time
from dataclasses import dataclass

import ant


DEBUG = os.environ.get("ANTIFIER_DEBUG", "").lower() in ("1", "true", "yes", "on")
RUNNING = True


def request_stop(signum=None, frame=None):
  global RUNNING
  RUNNING = False
  if signum is not None:
    print("\nStopping...")


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)


@dataclass
class BroadcastState:
  power: int = 150
  cadence: int = 90
  heart_rate: int = 120


class KeyPoller:
  def __enter__(self):
    self.fd = sys.stdin.fileno()
    self.old_term = None
    if sys.stdin.isatty():
      self.old_term = termios.tcgetattr(self.fd)
      new_term = termios.tcgetattr(self.fd)
      new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO
      termios.tcsetattr(self.fd, termios.TCSAFLUSH, new_term)
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    if self.old_term is not None:
      termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

  def poll(self):
    if not sys.stdin.isatty():
      return None
    readable, _, _ = select.select([sys.stdin], [], [], 0)
    if readable:
      return sys.stdin.read(1)
    return None


def clamp(value, low, high):
  return max(low, min(high, int(value)))


def ant_message(message_id, payload):
  data = [0xa4, len(payload), message_id] + payload
  checksum = 0
  for value in data:
    checksum ^= value
  data.append(checksum)
  return " ".join(hex(value)[2:].zfill(2) for value in data) + " 00 00"


def broadcast_data(channel, page):
  return ant_message(0x4e, [channel] + page)


def build_fec_general_page(started_at, distance):
  elapsed_quarters = int((time.time() - started_at) / 0.25) % 256
  distance_byte = int(distance) % 256
  return [0x10, 0x19, elapsed_quarters, distance_byte, 0x00, 0x00, 0x00, 0x30]


def build_fec_trainer_page(event_count, state, accumulated_power):
  power = clamp(state.power, 0, 4093)
  cadence = clamp(state.cadence, 0, 253)
  power_msb_status = (power >> 8) & 0x0f
  return [
    0x19,
    event_count % 256,
    cadence,
    accumulated_power & 0xff,
    (accumulated_power >> 8) & 0xff,
    power & 0xff,
    power_msb_status,
    0x30,
  ]


def build_hr_page(event_count, state, hr_state):
  heart_rate = clamp(state.heart_rate, 0, 255)
  now_ms = time.time() * 1000
  if heart_rate > 0:
    beat_interval_ms = (60 / float(heart_rate)) * 1000
    while now_ms - hr_state["beat_time_ms"] >= beat_interval_ms:
      hr_state["beat_count"] = (hr_state["beat_count"] + 1) % 256
      hr_state["beat_time_ms"] += beat_interval_ms

  if hr_state["beat_time_ms"] - hr_state["cycle_started_ms"] >= 64000:
    hr_state["beat_time_ms"] = now_ms
    hr_state["cycle_started_ms"] = now_ms

  if event_count % 4 == 0:
    hr_state["toggle"] = 0 if hr_state["toggle"] else 0x80

  toggle = hr_state["toggle"]
  beat_time = int((hr_state["beat_time_ms"] - hr_state["cycle_started_ms"]) * 1.024) & 0xffff

  if event_count % 65 in (0, 1, 2, 3):
    first_bytes = [0x02 + toggle, 0x0f, 0x01, 0x00]
  elif event_count % 65 in (31, 32, 33, 34):
    first_bytes = [0x03 + toggle, 0x01, 0x01, 0x33]
  elif event_count % 65 in (11, 12, 13, 44):
    operating_time = int((time.time() - hr_state["started_at"]) / 2) & 0xffffff
    first_bytes = [
      0x01 + toggle,
      operating_time & 0xff,
      (operating_time >> 8) & 0xff,
      (operating_time >> 16) & 0xff,
    ]
  elif event_count % 65 in (21, 22, 23, 24):
    first_bytes = [0x06 + toggle, 0xff, 0x00, 0x00]
  elif event_count % 65 in (41, 42, 43):
    first_bytes = [0x07 + toggle, 0x64, 0x55, 0x13]
  else:
    first_bytes = [0x00 + toggle, 0xff, 0xff, 0xff]

  return first_bytes + [
    beat_time & 0xff,
    (beat_time >> 8) & 0xff,
    hr_state["beat_count"],
    heart_rate,
  ]


def apply_key(state, key):
  global RUNNING
  if key == "q":
    state.power = clamp(state.power + 5, 0, 4093)
  elif key == "a":
    state.power = clamp(state.power - 5, 0, 4093)
  elif key == "w":
    state.cadence = clamp(state.cadence + 1, 0, 253)
  elif key == "s":
    state.cadence = clamp(state.cadence - 1, 0, 253)
  elif key == "e":
    state.heart_rate = clamp(state.heart_rate + 1, 0, 255)
  elif key == "d":
    state.heart_rate = clamp(state.heart_rate - 1, 0, 255)
  elif key == "r":
    state.power = 150
    state.cadence = 90
    state.heart_rate = 120
  elif key in ("x", "\x03"):
    RUNNING = False


def print_controls():
  print("Keyboard controls:")
  print("  q/a  power +/- 5 W")
  print("  w/s  cadence +/- 1 rpm")
  print("  e/d  heart rate +/- 1 bpm")
  print("  r    reset to 150 W, 90 rpm, 120 bpm")
  print("  x    quit")
  print("")


def run_broadcaster(dev_ant):
  state = BroadcastState()
  event_count = 0
  accumulated_power = 0
  started_at = time.time()
  distance = 0
  hr_state = {
    "started_at": started_at,
    "beat_time_ms": time.time() * 1000,
    "cycle_started_ms": time.time() * 1000,
    "beat_count": 0,
    "toggle": 0,
  }
  last_status_at = 0

  print_controls()

  with KeyPoller() as key_poller:
    while RUNNING:
      loop_started_at = time.time()
      key = key_poller.poll()
      while key is not None:
        apply_key(state, key)
        key = key_poller.poll()

      accumulated_power = (accumulated_power + clamp(state.power, 0, 4093)) % 65536
      now = time.time()

      if event_count % 66 in (0, 1):
        fec_page = [0x50, 0xff, 0xff, 0x01, 0x0f, 0x00, 0x85, 0x83]
      elif event_count % 66 in (32, 33):
        fec_page = [0x51, 0xff, 0xff, 0x01, 0x01, 0x00, 0x00, 0x00]
      elif event_count % 3 == 0:
        fec_page = build_fec_general_page(started_at, distance)
      else:
        fec_page = build_fec_trainer_page(event_count, state, accumulated_power)

      ant.send_ant([broadcast_data(0, fec_page)], dev_ant, DEBUG)
      ant.send_ant([broadcast_data(1, build_hr_page(event_count, state, hr_state))], dev_ant, DEBUG)

      if now - last_status_at >= 1:
        print(
          "\rPower %4d W | Cadence %3d rpm | HR %3d bpm   " %
          (state.power, state.cadence, state.heart_rate),
          end="",
          flush=True,
        )
        last_status_at = now

      event_count = (event_count + 1) % 256
      sleep_time = 0.25 - (time.time() - loop_started_at)
      if sleep_time > 0:
        time.sleep(sleep_time)

  print("")


def main():
  dev_ant, msg = ant.get_ant(DEBUG)
  if not dev_ant:
    return 1

  if msg:
    print(msg)

  try:
    ant.antreset(dev_ant, DEBUG)
    ant.calibrate(dev_ant, DEBUG)
    ant.master_channel_config(dev_ant, DEBUG)
    ant.second_channel_config(dev_ant, DEBUG)
    run_broadcaster(dev_ant)
  finally:
    try:
      ant.antreset(dev_ant, DEBUG)
    except Exception as exc:
      print("Could not reset ANT dongle during shutdown: %s" % exc)
    try:
      dev_ant.close()
    except Exception:
      pass

  return 0


if __name__ == "__main__":
  sys.exit(main())
