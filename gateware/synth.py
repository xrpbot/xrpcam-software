#!/usr/bin/python3
from nmigen import *
from zedboard import ZedboardPlatform
from top import Top

platform = ZedboardPlatform()
platform.build(Top())
