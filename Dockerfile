FROM python:3.14.6

RUN apt-get update \
 && apt-get install -y --no-install-recommends usbutils \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir pyserial pyusb numpy
