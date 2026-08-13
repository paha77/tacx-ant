import os
import re
import select
import signal
import shutil
import sys
import termios
import time
from dataclasses import dataclass

import ant


DEBUG = os.environ.get("ANTIFIER_DEBUG", "").lower() in ("1", "true", "yes", "on")
RUNNING = True
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
  def __init__(self, metrics, controls, enabled=None):
    self.metrics = metrics
    self.controls = controls
    self.enabled = (sys.stdout.isatty() and not DEBUG) if enabled is None else enabled
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
        "\rPower %4d W | Cadence %3d rpm | HR %3d bpm   " %
        (state.power, state.cadence, state.heart_rate),
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
    subtitle = "broadcasting FE-C trainer + heart rate"
    status = "4 Hz  event %03d  uptime %02d:%02d" % (event_count, uptime // 60, uptime % 60)

    lines = [
      self.rule(width, "="),
      self.center(title, width),
      self.center(subtitle, width),
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
    if "broadcasting FE-C" in line:
      return self.style(line, "bright_cyan")
    if "4 Hz" in line and "uptime" in line:
      return self.style(line, "dim")
    if line == "Controls:":
      return self.style(line, "bold", "bright_magenta")
    if line.startswith("  "):
      return self.colorize_control_line(line)
    return line

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
  dashboard = TerminalDashboard(METRICS, CONTROLS)
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
          fec_page = [0x50, 0xff, 0xff, 0x01, 0x0f, 0x00, 0x85, 0x83]
        elif event_count % 66 in (32, 33):
          fec_page = [0x51, 0xff, 0xff, 0x01, 0x01, 0x00, 0x00, 0x00]
        elif event_count % 3 == 0:
          fec_page = build_fec_general_page(started_at, distance)
        else:
          fec_page = build_fec_trainer_page(event_count, state, accumulated_power)

        ant.send_ant([broadcast_data(0, fec_page)], dev_ant, DEBUG)
        ant.send_ant([broadcast_data(1, build_hr_page(event_count, state, hr_state))], dev_ant, DEBUG)

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
