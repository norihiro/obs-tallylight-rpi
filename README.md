# Tally-light control tool for OBS Studio using Raspberry Pi GPIO

## Introduction

This script is a deamon program that connects to OBS Studio using [obs-websocket](https://github.com/obsproject/obs-websocket/)
and controls tally-light(s) on GPIO.

## Example setup

Let's say you have two tally-light LEDs for two cameras.

At first, wire two LEDs to GPIO. 0 (header pin 11) and GPIO. 1 (header pin 12).

Then, run this script as below, where `192.0.2.2` is the IP address that obs-websocket is running,
and `camera 1` and `camera 2` are the source names capturing the cameras.
```bash
python3 obs_tallylight_rpi.py -d -c 192.0.2.2:4455 -a 11='camera 1' -a 12='camera 2'
```

You can assign more sources as much as there are available GPIO pins on Raspberry Pi.

## See also
- [OBS Studio](https://github.com/obsproject/obs-studio/)
- [obs-pi-tally](https://github.com/mrkeathley/obs-pi-tally)
