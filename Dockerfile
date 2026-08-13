FROM python:2.7.18

# Switch Debian 10 (buster) to archive mirrors and relax Valid-Until checks (archive metadata is often "expired")
RUN set -eux; \
  printf '%s\n' \
    'deb http://archive.debian.org/debian buster main contrib non-free' \
    'deb http://archive.debian.org/debian buster-updates main contrib non-free' \
    > /etc/apt/sources.list; \
  \
  # Some bases also have a separate security list; remove it because it points to security.debian.org (404 in your log)
  rm -f /etc/apt/sources.list.d/debian-security.list /etc/apt/sources.list.d/security.list 2>/dev/null || true; \
  \
  apt-get -o Acquire::Check-Valid-Until=false update; \
  apt-get install -y --no-install-recommends usbutils; \
  rm -rf /var/lib/apt/lists/*

# Pin pip to a Python-2-compatible version, then install
RUN python -m pip install --no-cache-dir "pip==20.3.4" \
 && python -m pip install --no-cache-dir pyserial pyusb
