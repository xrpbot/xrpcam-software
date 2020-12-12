#!/usr/bin/python3

from nmigen.build import *
from nmigen.vendor.xilinx_7series import *
from nmigen_boards.resources.user import *

__all__ = [ "ZedboardPlatform" ]

class ZedboardPlatform(Xilinx7SeriesPlatform):
    device = "xc7z020"
    package = "clg484"
    speed = 1

    resources = [
        Resource("gclk", 0, Pins("Y9", dir="i"), Attrs(IOSTANDARD="LVCMOS33"), Clock(100e6)),
        *LEDResources(pins="T22 T21 U22 U21 V22 W22 U19 U14", attrs=Attrs(IOSTANDARD="LVCMOS33"))
    ]
    connectors = []
