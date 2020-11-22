from nmigen import *
from nmigen.hdl.rec import Layout, Record

from enum import IntEnum

class AXI3Response(IntEnum):
    OKAY   = 0b00
    EXOKAY = 0b01
    SLVERR = 0b10
    DECERR = 0b11

class AXI3Burst(IntEnum):
    FIXED = 0b00
    INCR  = 0b01
    WRAP  = 0b10

class AXI3Layout(Layout):
    def __init__(self):
        super().__init__([
            # clock and reset
            ("aclk", 1),
            ("areset_n", 1),

            # write address channel
            ("awid", 12),
            ("awaddr", unsigned(32)),
            ("awlen", 4),
            ("awsize", 2),
            ("awburst", 2),
            ("awlock", 2),
            ("awcache", 4),
            ("awprot", 3),
            ("awqos", 4),
            ("awvalid", 1),
            ("awready", 1),

            # read address channel
            ("arid", 12),
            ("araddr", unsigned(32)),
            ("arlen", 4),
            ("arsize", 2),
            ("arburst", 2),
            ("arlock", 2),
            ("arcache", 4),
            ("arprot", 3),
            ("arqos", 4),
            ("arvalid", 1),
            ("arready", 1),

            # write data channel
            ("wid", 12),
            ("wdata", 32),
            ("wstrb", 4),
            ("wlast", 1),
            ("wvalid", 1),
            ("wready", 1),

            # read data channel
            ("rid", 12),
            ("rdata", 32),
            ("rresp", 2),
            ("rlast", 1),
            ("rvalid", 1),
            ("rready", 1),

            # write response channel
            ("bid", 12),
            ("bresp", 2),
            ("bvalid", 1),
            ("bready", 1)
        ])

class AXI3Bus(Record):
    def __init__(self):
        super().__init__(AXI3Layout())
