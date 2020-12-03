# antifier
This project will enable a Windows or Linux PC to broadcast ANT+ data via a dongle from a Tacx trainer connected to it via USB. This can be either be from a standalone PC broadcasting to a PC or tablet running e.g. Zwift or Trainerroad, or from a Windows PC already running Zwift/ Trainerroad (this PC will therefore require two ANT+ dongles) 
Home page: https://github.com/john-38787364/antifier

## Simulation with keyboard controls

Start simulation with

`python antifier.py -l -c power_calc_factors_fortius.txt -s`

* q: Increase speed by 1 km/h
* a: Decrease speed by 1 km/h


* w: Increase cadence by 1 rpm
* s: Increase cadence by 1 rpm


* e: Increase heart rate by 1 beat / minute
* d: Decrease heart rate by 1 beat / minute

