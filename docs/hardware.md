# Hardware

## Platform

- Raspberry Pi 5
- HiWonder MasterPi: mecanum base, 5-DOF arm, camera
- Expansion board over serial (UART)

## UART (Pi 5)

Stock HiWonder code expects **`/dev/ttyAMA0`**.

On Pi 5, enable the GPIO UART overlay in `/boot/firmware/config.txt`:

```text
dtoverlay=uart0-pi5
```

Avoid binding a login console to that same UART (`console=serial0,...` in cmdline) while using the robot board.

Reboot after changing boot config.

## Safety defaults

- Keep speeds low while bringing up code.
- Always send an explicit stop / neutral pose before exiting scripts.
- Watch battery voltage; HiWonder demos often warn when voltage is low.
- Clear space around wheels and arm before enabling actuators.
