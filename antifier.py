import argparse
import os
import re
import select
import signal
import shutil
import sys
import termios
import time
from dataclasses import dataclass

import ble

try:
  import ant
  ANT_IMPORT_ERROR = None
except ImportError as exc:
  ant = None
  ANT_IMPORT_ERROR = exc


DEBUG = os.environ.get("ANTIFIER_DEBUG", "").lower() in ("1", "true", "yes", "on")
RUNNING = True
DEFAULT_TRANSPORT = os.environ.get("ANTIFIER_TRANSPORT", "ant").lower()
ANSI_RE = re.compile(r"\033\[[0-9;]*m")
STYLE_TAG_RE = re.compile(r"\{[a-z_]+\}")
ANSI = {
  "reset": "\033[0m",
  "bold": "\033[1m",
  "dim": "\033[2m",
  "cyan": "\033[36m",
  "green": "\033[32m",
  "yellow": "\033[33m",
  "magenta": "\033[35m",
  "red": "\033[31m",
  "bright_black": "\033[90m",
  "bright_cyan": "\033[96m",
  "bright_green": "\033[92m",
  "bright_yellow": "\033[93m",
  "bright_magenta": "\033[95m",
  "bright_red": "\033[91m",
}


def env_int(name, default):
  return int(os.environ.get(name, str(default)), 0)


FEC_MANUFACTURER_ID = env_int("ANTIFIER_FEC_MANUFACTURER_ID", 89)
FEC_MODEL_NUMBER = env_int("ANTIFIER_FEC_MODEL_NUMBER", 33669)
FEC_HARDWARE_REVISION = env_int("ANTIFIER_FEC_HARDWARE_REVISION", 1)
FEC_SOFTWARE_REVISION = env_int("ANTIFIER_FEC_SOFTWARE_REVISION", 1)
FEC_SERIAL_NUMBER = env_int("ANTIFIER_FEC_SERIAL_NUMBER", 1)
HR_DEVICE_NUMBER = env_int("ANTIFIER_HR_DEVICE_NUMBER", 365)
HR_MANUFACTURER_ID = env_int("ANTIFIER_HR_MANUFACTURER_ID", 89)
HR_MODEL_NUMBER = env_int("ANTIFIER_HR_MODEL_NUMBER", 120)
HR_HARDWARE_REVISION = env_int("ANTIFIER_HR_HARDWARE_REVISION", 1)
HR_SOFTWARE_REVISION = env_int("ANTIFIER_HR_SOFTWARE_REVISION", 1)
HR_SERIAL_NUMBER = env_int(
  "ANTIFIER_HR_SERIAL_NUMBER",
  HR_DEVICE_NUMBER & 0xffff,
)


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


@dataclass(frozen=True)
class MetricSpec:
  key: str
  label: str
  unit: str
  display_max: int
  color: str


@dataclass(frozen=True)
class ControlSpec:
  keys: str
  label: str


class AntBroadcaster:
  label = "ANT+ FE-C trainer + heart rate"
  transport = "ant"

  def __init__(self, debug=False):
    self.debug = debug
    self.dev_ant = None
    self.msg = ""

  def start(self):
    if ant is None:
      print("ANT+ mode requires pyserial and pyusb: %s" % ANT_IMPORT_ERROR)
      return False
    self.dev_ant, self.msg = ant.get_ant(self.debug)
    if not self.dev_ant:
      return False
    if self.msg:
      print(self.msg)
    ant.antreset(self.dev_ant, self.debug)
    ant.calibrate(self.dev_ant, self.debug)
    ant.master_channel_config(self.dev_ant, self.debug)
    ant.second_channel_config(self.dev_ant, self.debug)
    return True

  def broadcast(self, event_count, state, fec_page, hr_page):
    ant.send_ant([broadcast_data(0, fec_page)], self.dev_ant, self.debug)
    ant.send_ant([broadcast_data(1, hr_page)], self.dev_ant, self.debug)

  def stop(self):
    if not self.dev_ant:
      return
    try:
      ant.antreset(self.dev_ant, self.debug)
    except Exception as exc:
      print("Could not reset ANT dongle during shutdown: %s" % exc)
    try:
      self.dev_ant.close()
    except Exception:
      pass


class BluetoothBroadcaster:
  label = "Bluetooth FTMS trainer + heart rate"
  transport = "bluetooth"

  def __init__(self, debug=False):
    self.debug = debug
    self.broadcaster = ble.BluetoothBroadcaster(debug=debug)

  def start(self):
    self.broadcaster.start()
    print("Bluetooth advertising as %s" % self.broadcaster.name)
    return True

  def broadcast(self, event_count, state, fec_page, hr_page):
    self.broadcaster.broadcast(event_count, state, fec_page, hr_page)

  def stop(self):
    self.broadcaster.stop()


METRICS = [
  MetricSpec("power", "Power", "W", 500, "bright_yellow"),
  MetricSpec("cadence", "Cadence", "rpm", 130, "bright_cyan"),
  MetricSpec("heart_rate", "Heart rate", "bpm", 200, "bright_red"),
]

CONTROLS = [
  ControlSpec("q/a", "power +/- 5 W"),
  ControlSpec("w/s", "cadence +/- 1 rpm"),
  ControlSpec("e/d", "heart rate +/- 1 bpm"),
  ControlSpec("r", "reset values"),
  ControlSpec("x", "quit"),
]


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


def visible_width(text):
  return len(STYLE_TAG_RE.sub("", ANSI_RE.sub("", text)))


def fit_text(text, width):
  if width <= 0:
    return ""
  if visible_width(text) <= width:
    return text
  if width <= 1:
    return text[:width]
  return text[:width - 1] + "."


def bar(value, high, width):
  if width <= 0:
    return ""
  filled = int(round((clamp(value, 0, high) / float(high)) * width)) if high else 0
  return "#" * filled + "-" * (width - filled)


class TerminalDashboard:
  def __init__(self, metrics, controls, enabled=None, broadcast_label=None, transport=None):
    self.metrics = metrics
    self.controls = controls
    self.enabled = (sys.stdout.isatty() and not DEBUG) if enabled is None else enabled
    self.broadcast_label = broadcast_label or "FE-C trainer + heart rate"
    self.transport = transport or "ant"
    self.last_render = ""
    self.last_size = None
    self.started = time.time()

  def start(self):
    if self.enabled:
      print("\033[?25l\033[2J\033[H", end="", flush=True)

  def stop(self):
    if self.enabled:
      print("\033[?25h", end="", flush=True)

  def render(self, state, event_count, force=False):
    if not self.enabled:
      print(
        "\rMode %-9s | Power %4d W | Cadence %3d rpm | HR %3d bpm   " %
        (self.transport.upper(), state.power, state.cadence, state.heart_rate),
        end="",
        flush=True,
      )
      return

    size = shutil.get_terminal_size((80, 24))
    lines = self.build_lines(state, event_count, size.columns)
    output = "\n".join(self.colorize_lines(lines))
    if not force and output == self.last_render and size == self.last_size:
      return
    self.last_render = output
    self.last_size = size
    print("\033[H" + output + "\033[J", end="", flush=True)

  def build_lines(self, state, event_count, columns):
    width = max(20, columns)
    uptime = int(time.time() - self.started)
    title = "ANTIFIER"
    subtitle = "broadcasting %s" % self.broadcast_label
    status = "4 Hz  event %03d  uptime %02d:%02d" % (event_count, uptime // 60, uptime % 60)

    lines = [
      self.rule(width, "="),
      self.center(title, width),
      self.center(subtitle, width),
      self.transport_switch(width),
      self.center(status, width),
      self.rule(width, "-"),
    ]

    if width >= 92:
      lines.extend(self.wide_metrics(state, width))
    else:
      lines.extend(self.narrow_metrics(state, width))

    lines.append(self.rule(width, "-"))
    lines.extend(self.controls_lines(width))
    lines.append(self.rule(width, "="))
    return [fit_text(line, width) for line in lines]

  def wide_metrics(self, state, width):
    gap = "  "
    card_width = max(26, (width - len(gap) * (len(self.metrics) - 1)) // len(self.metrics))
    cards = [self.metric_card(metric, state, card_width) for metric in self.metrics]
    lines = []
    for row in range(len(cards[0])):
      lines.append(gap.join(card[row] for card in cards))
    return lines

  def narrow_metrics(self, state, width):
    lines = []
    for metric in self.metrics:
      lines.extend(self.metric_card(metric, state, width))
    return lines

  def metric_card(self, metric, state, width):
    value = getattr(state, metric.key)
    label_width = max(8, min(16, width // 3))
    value_text = "%d %s" % (value, metric.unit)
    bar_width = max(8, width - 6)
    meter = bar(value, metric.display_max, bar_width)
    metric_tag = "{%s}" % metric.color
    return [
      "+%s+" % ("-" * (width - 2)),
      "%s| %s %s |" % (
        metric_tag,
        fit_text(metric.label, label_width).ljust(label_width),
        value_text.rjust(width - label_width - 5),
      ),
      "%s| [%s] |" % (metric_tag, meter.ljust(width - 6)),
      "+%s+" % ("-" * (width - 2)),
    ]

  def controls_lines(self, width):
    lines = ["Controls:"]
    if width >= 76:
      chunks = ["%-5s %s" % (control.keys, control.label) for control in self.controls]
      current = "  "
      for chunk in chunks:
        next_text = chunk if current == "  " else "  " + chunk
        if len(current) + len(next_text) > width:
          lines.append(current.rstrip())
          current = "  " + chunk
        else:
          current += next_text
      if current.strip():
        lines.append(current.rstrip())
    else:
      for control in self.controls:
        lines.append("  %-5s %s" % (control.keys, control.label))
    return lines

  def transport_switch(self, width):
    switch = "[ ANT+ ]=== [ Bluetooth ]"
    return self.center(switch, width)

  def rule(self, width, char):
    return char * width

  def center(self, text, width):
    return fit_text(text, width).center(width)

  def colorize_lines(self, lines):
    return [self.colorize_line(line) for line in lines]

  def colorize_line(self, line):
    if set(line) in (set("="), set("-")):
      return self.style(line, "bright_black")
    if line.startswith("+") and line.endswith("+"):
      return self.style(line, "cyan")
    if STYLE_TAG_RE.search(line):
      return self.colorize_tagged_metric_line(line)
    if line.strip() == "ANTIFIER":
      return self.style(line, "bold", "bright_green")
    if "[ ANT+ ]" in line and "[ Bluetooth ]" in line:
      return self.colorize_transport_switch(line)
    if "broadcasting " in line:
      return self.style(line, "bright_cyan")
    if "4 Hz" in line and "uptime" in line:
      return self.style(line, "dim")
    if line == "Controls:":
      return self.style(line, "bold", "bright_magenta")
    if line.startswith("  "):
      return self.colorize_control_line(line)
    return line

  def colorize_transport_switch(self, line):
    ant_active = self.transport in ("ant", "ant+")
    ant_style = ("bold", "bright_green") if ant_active else ("dim", "bright_black")
    bluetooth_style = ("bold", "bright_cyan") if not ant_active else ("dim", "bright_black")
    line = line.replace("[ ANT+ ]", self.style("[ ANT+ ]", *ant_style))
    line = line.replace("[ Bluetooth ]", self.style("[ Bluetooth ]", *bluetooth_style))
    return line.replace("=", self.style("=", "bright_black"))

  def colorize_tagged_metric_line(self, line):
    parts = STYLE_TAG_RE.split(line)
    tags = STYLE_TAG_RE.findall(line)
    output = parts[0]
    for index, tag in enumerate(tags):
      color_name = tag.strip("{}")
      text = parts[index + 1]
      if "[" in text and "]" in text:
        output += self.colorize_bar_line(text, color_name)
      else:
        output += self.colorize_metric_value_line(text, color_name)
    return output

  def colorize_metric_value_line(self, line, color_name):
    if "|" not in line:
      return line
    parts = line.split("|")
    if len(parts) < 3:
      return line
    content = parts[1]
    label_width = len(content) - len(content.lstrip())
    content = content[:label_width] + self.style(content[label_width:], "bold", color_name)
    return "|".join([parts[0], content] + parts[2:])

  def colorize_bar_line(self, line, color_name):
    styled = []
    for char in line:
      if char == "#":
        styled.append(self.style(char, color_name))
      elif char == "-":
        styled.append(self.style(char, "bright_black"))
      elif char in "[]":
        styled.append(self.style(char, "bright_black"))
      else:
        styled.append(char)
    return "".join(styled)

  def colorize_control_line(self, line):
    return re.sub(r"(?<!\S)(q/a|w/s|e/d|r|x)(?!\S)", self.colorize_control_key, line)

  def colorize_control_key(self, match):
    return self.style(match.group(1), "bold", "bright_yellow")

  def style(self, text, *names):
    prefix = "".join(ANSI[name] for name in names)
    return prefix + text + ANSI["reset"]


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


def build_fec_manufacturer_page():
  return [
    0x50,
    0xff,
    0xff,
    FEC_HARDWARE_REVISION & 0xff,
    FEC_MANUFACTURER_ID & 0xff,
    (FEC_MANUFACTURER_ID >> 8) & 0xff,
    FEC_MODEL_NUMBER & 0xff,
    (FEC_MODEL_NUMBER >> 8) & 0xff,
  ]


def build_fec_product_page():
  return [
    0x51,
    0xff,
    0xff,
    FEC_SOFTWARE_REVISION & 0xff,
    FEC_SERIAL_NUMBER & 0xff,
    (FEC_SERIAL_NUMBER >> 8) & 0xff,
    (FEC_SERIAL_NUMBER >> 16) & 0xff,
    (FEC_SERIAL_NUMBER >> 24) & 0xff,
  ]


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
    first_bytes = [
      0x02 + toggle,
      HR_MANUFACTURER_ID & 0xff,
      HR_SERIAL_NUMBER & 0xff,
      (HR_SERIAL_NUMBER >> 8) & 0xff,
    ]
  elif event_count % 65 in (31, 32, 33, 34):
    first_bytes = [
      0x03 + toggle,
      HR_HARDWARE_REVISION & 0xff,
      HR_SOFTWARE_REVISION & 0xff,
      HR_MODEL_NUMBER & 0xff,
    ]
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


def run_broadcaster(broadcaster):
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
  dashboard = TerminalDashboard(
    METRICS,
    CONTROLS,
    broadcast_label=broadcaster.label,
    transport=broadcaster.transport,
  )
  last_status_at = 0

  if not dashboard.enabled:
    print_controls()

  dashboard.start()
  try:
    with KeyPoller() as key_poller:
      dashboard.render(state, event_count, force=True)
      while RUNNING:
        loop_started_at = time.time()
        display_dirty = False
        key = key_poller.poll()
        while key is not None:
          apply_key(state, key)
          display_dirty = True
          key = key_poller.poll()

        accumulated_power = (accumulated_power + clamp(state.power, 0, 4093)) % 65536
        now = time.time()

        if event_count % 66 in (0, 1):
          fec_page = build_fec_manufacturer_page()
        elif event_count % 66 in (32, 33):
          fec_page = build_fec_product_page()
        elif event_count % 3 == 0:
          fec_page = build_fec_general_page(started_at, distance)
        else:
          fec_page = build_fec_trainer_page(event_count, state, accumulated_power)

        hr_page = build_hr_page(event_count, state, hr_state)
        broadcaster.broadcast(event_count, state, fec_page, hr_page)

        if display_dirty or now - last_status_at >= 1:
          dashboard.render(state, event_count, force=display_dirty)
          last_status_at = now

        event_count = (event_count + 1) % 256
        sleep_time = 0.25 - (time.time() - loop_started_at)
        if sleep_time > 0:
          time.sleep(sleep_time)
  finally:
    dashboard.stop()
    print("")


def parse_args(argv):
  parser = argparse.ArgumentParser(description="Broadcast interactive trainer and heart-rate values.")
  parser.add_argument(
    "--transport",
    choices=("ant", "ant+", "bluetooth", "ble"),
    default=DEFAULT_TRANSPORT,
    help="Broadcast transport. Defaults to ANTIFIER_TRANSPORT or ant.",
  )
  return parser.parse_args(argv)


def create_broadcaster(transport):
  transport = transport.lower()
  if transport in ("ant", "ant+"):
    return AntBroadcaster(DEBUG)
  if transport in ("bluetooth", "ble"):
    return BluetoothBroadcaster(DEBUG)
  raise ValueError("Unsupported transport: %s" % transport)


def main(argv=None):
  args = parse_args(sys.argv[1:] if argv is None else argv)
  try:
    broadcaster = create_broadcaster(args.transport)
  except ValueError as exc:
    print(str(exc))
    return 1

  try:
    if not broadcaster.start():
      return 1
  except ble.BluetoothUnavailableError as exc:
    print("Bluetooth unavailable: %s" % exc)
    return 1

  print("HR sensor identity: device %d, manufacturer %d, model %d, serial %d" % (
    HR_DEVICE_NUMBER & 0xffff,
    HR_MANUFACTURER_ID & 0xff,
    HR_MODEL_NUMBER & 0xff,
    HR_SERIAL_NUMBER & 0xffff,
  ))

  try:
    run_broadcaster(broadcaster)
  finally:
    broadcaster.stop()

  return 0


if __name__ == "__main__":
  sys.exit(main())
