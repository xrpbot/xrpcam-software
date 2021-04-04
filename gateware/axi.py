from nmigen import *
from nmigen.hdl.rec import Layout, Record

from enum import IntEnum

class AXI3Response(IntEnum):
    OKAY   = 0b00
    EXOKAY = 0b01
    SLVERR = 0b10
    DECERR = 0b11

class AXI3Prot:
    UNPRIV     = 0b000
    PRIV       = 0b001
    SECURE     = 0b000
    NON_SECURE = 0b010
    DATA       = 0b000
    INSTR      = 0b100

class AXI3Burst(IntEnum):
    FIXED = 0b00
    INCR  = 0b01
    WRAP  = 0b10

class AXI3Layout(Layout):
    def __init__(self, id_bits=12, data_bits=32):
        super().__init__([
            # clock and reset
            ("aclk", 1),
            ("areset_n", 1),

            # write address channel
            ("awid", id_bits),
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
            ("arid", id_bits),
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
            ("wid", id_bits),
            ("wdata", data_bits),
            ("wstrb", data_bits//8),
            ("wlast", 1),
            ("wvalid", 1),
            ("wready", 1),

            # read data channel
            ("rid", id_bits),
            ("rdata", data_bits),
            ("rresp", 2),
            ("rlast", 1),
            ("rvalid", 1),
            ("rready", 1),

            # write response channel
            ("bid", id_bits),
            ("bresp", 2),
            ("bvalid", 1),
            ("bready", 1)
        ])

class AXI3Bus(Record):
    def __init__(self, **kwargs):
        super().__init__(AXI3Layout(**kwargs))
