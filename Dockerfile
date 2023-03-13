FROM python:2
RUN pip install pyserial && \
    pip install pyusb

