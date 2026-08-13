FROM python:3.14.6

ENV PYTHONUNBUFFERED=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends usbutils \
 && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir pyserial pyusb numpy

COPY docker-entrypoint.sh /usr/local/bin/antifier-docker-entrypoint
RUN chmod +x /usr/local/bin/antifier-docker-entrypoint

ENTRYPOINT ["/usr/local/bin/antifier-docker-entrypoint"]
