#!/bin/sh
set -eu

reset_ant_usb() {
  python3 /antifier/reset_ant_usb.py || true
}

child=

stop_child() {
  if [ -n "$child" ]; then
    kill -TERM "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  if [ "${ANTIFIER_RESET_ANT_USB_ON_EXIT:-0}" = "1" ]; then
    reset_ant_usb || true
  fi
  exit 143
}

trap stop_child INT TERM
trap 'status=$?; if [ "${ANTIFIER_RESET_ANT_USB_ON_EXIT:-0}" = "1" ]; then reset_ant_usb || true; fi; exit "$status"' EXIT

if [ "${ANTIFIER_RESET_ANT_USB_ON_START:-0}" = "1" ]; then
  reset_ant_usb || true
fi

case "${1:-}" in
  bash|sh|/bin/bash|/bin/sh)
    "$@"
    exit "$?"
    ;;
esac

"$@"
