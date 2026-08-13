#!/usr/bin/env python3
import os
import subprocess
import sys
import time

ANT_VENDOR_ID = "0fcf"
ANT_PRODUCT_IDS = {"1004", "1008", "1009"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def reset_ant_usb():
  found = False
  for name in os.listdir("/sys/bus/usb/devices"):
    device_dir = os.path.join("/sys/bus/usb/devices", name)
    try:
      with open(os.path.join(device_dir, "idVendor"), "r") as handle:
        vendor = handle.read().strip().lower()
      if vendor != ANT_VENDOR_ID:
        continue
      with open(os.path.join(device_dir, "idProduct"), "r") as handle:
        product = handle.read().strip().lower()
      if product not in ANT_PRODUCT_IDS:
        continue
      with open(os.path.join(device_dir, "busnum"), "r") as handle:
        busnum = int(handle.read().strip())
      with open(os.path.join(device_dir, "devnum"), "r") as handle:
        devnum = int(handle.read().strip())
    except OSError:
      continue

    found = True
    path = "/dev/bus/usb/%03d/%03d" % (busnum, devnum)
    print("Resetting ANT USB stick at %s" % path)
    subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "reset_usb.py"), "path", path], check=False)
    time.sleep(2)
    for _ in range(50):
      if any(name.startswith("ttyUSB") for name in os.listdir("/dev")):
        break
      time.sleep(0.1)

  if not found:
    print("No ANT USB stick found on the USB bus")
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(reset_ant_usb())
