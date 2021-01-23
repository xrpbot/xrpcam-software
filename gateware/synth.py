#!/usr/bin/python3
from nmigen import *
from zedboard import ZedBoardPlatform
from top import Top

platform = ZedBoardPlatform()
platform.build(Top())
