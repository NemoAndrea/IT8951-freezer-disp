# IT8951

Circuitpython code to control the IT8951 E-ink display panel driver IC. This IC is found on adapter boards for certain Waveshare E-paper displays. The code here is designed to run on an ESP32-S3 running circuitpython, and tuned for the [waveshare 10.3-inch 1872x1404 display](https://www.waveshare.com/product/displays/e-paper/10.3inch-e-paper-hat-g.htm?sku=26936). It is based on a python3 implementation that is available on GitHub (see the credit section below for more info.)

### Notes on performance

#### VCOM value

You should try setting different VCOM values and seeing how that affects the performance of your display. Every
one is different. There might be a suggested VCOM value marked on the cable of your display.

## Credit

This is a forked version of the original [IT8951](https://github.com/GregDMeyer/IT8951/tree/master) repository by GregDMeyer. 

Thanks to the following folks for helping improve the original library:

 - @BackSlasher
 - @cetres
 - @azzeloof
 - @matyasf
 - @grob6000
 - @txoof
