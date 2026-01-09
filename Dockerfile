FROM python:2 
RUN 	apt update && \ 
	apt install -y usbutils && \ 
	rm -rf /var/lib/apt/lists/* && \ 
	pip install pyserial && \ 
	pip install pyusb

