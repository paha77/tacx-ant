apt-get install python3-pip
python3 -m pip install pyserial pyusb
mkdir antifier
cd antifier
wget --quiet -N https://raw.githubusercontent.com/john-38787364/antifier/master/antifier.py
wget --quiet -N https://raw.githubusercontent.com/john-38787364/antifier/master/ant.py
wget --quiet -N https://raw.githubusercontent.com/john-38787364/antifier/master/README.txt
echo "##########################################################################"
echo "This script has installed python3-pip, pyserial, and pyusb. It has created the"
echo "directory antifier and downloaded the required files."
echo "##########################################################################"
echo "Installation finished"
dongle=$(lsusb  | grep -o -i "0fcf:.\{4\}" | cut -c6-)
if [ -n "$dongle" ] ; then 
 echo "Dongle found"
else
 echo "Dongle not found"
 dongle="[PRODUCT ID OF DONGLE FROM lsusb]"
fi
echo "If you have problems finding the dongle then ensure /dev/ttyUSB0 exists"
echo "If /dev/ttyUSB0 does not exist then create /etc/udev/rules.d/garmin-ant2.rules and add:"
echo "SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"0fcf\", ATTRS{idProduct}==\"$dongle\", RUN+=\"/sbin/modprobe usbserial vendor=0x0fcf product=0x$dongle\""
echo "Now cd into antifier and read README.txt, then run sudo python3 ./antifier.py"
