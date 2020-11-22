#!/usr/bin/python3
import random
import sys
from nmigen import *
from nmigen.sim import *
from axi import *
from axi_sim import *
from axi_test_slave import AXITestSlave

def test_process():
    for i in range(0, 10):
        axi_write_transact = [
            TWrite(0x40000000, [0x00, 0x00, 0x00, 0x00], bytes_per_beat=1, exp_resp=AXI3Response.OKAY),
            TWrite(0x40000001, [0x55, 0x66, 0x77, 0x88], bytes_per_beat=1, exp_resp=AXI3Response.OKAY),
            TWrite(0x40000004, [0x22334455], bytes_per_beat=4, exp_resp=AXI3Response.OKAY),
            TWrite(0x40000006, [0x9009, 0xa00a, 0xb00b, 0xc00c], bytes_per_beat=2, exp_resp=AXI3Response.OKAY),
            TWrite(0x4000000e, [0xdd], bytes_per_beat=1, exp_resp=AXI3Response.OKAY),
            TWrite(0x4000000f, [0xee], bytes_per_beat=1, exp_resp=AXI3Response.OKAY),
            TWrite(0x40000003, [0x33, 0x00, 0x11, 0x22], bytes_per_beat=1, awburst=AXI3Burst.WRAP, exp_resp=AXI3Response.OKAY)
        ]

        if i % 3 == 0:
            yield from axi_write(axi_bus, axi_write_transact, delay=0)
        else:
            yield from axi_write(axi_bus, axi_write_transact, delay='rand')

        assert((yield axi_slave.regs[0]) == 0x33221100)
        assert((yield axi_slave.regs[1]) == 0x90094455)
        assert((yield axi_slave.regs[2]) == 0xb00ba00a)
        assert((yield axi_slave.regs[3]) == 0xeeddc00c)

        v = [ random.randrange(2**32) for _ in range(0, 4) ]
        axi_write_transact = [
                TWrite(0x40000100, random.randrange(2**32), exp_resp=AXI3Response.DECERR),
                TWrite(0x4000000c, v[3], exp_resp=AXI3Response.OKAY),
                TWrite(0x40000004, [v[1], v[2]], exp_resp=AXI3Response.OKAY),
                TWrite(0x40000200, random.randrange(2**32), exp_resp=AXI3Response.DECERR),
                TWrite(0x4000000c, v[3], exp_resp=AXI3Response.OKAY),
                TWrite(0x40001000, random.randrange(2**32), exp_resp=AXI3Response.DECERR),
                TWrite(0x40000000, [ random.randrange(2**32) for _ in range(0, 4) ], wstrb=0, exp_resp=AXI3Response.OKAY),
                TWrite(0x40000000, [ random.randrange(2**32), random.randrange(2**32), random.randrange(2**32), v[0] ], awburst=AXI3Burst.FIXED, exp_resp=AXI3Response.OKAY)
            ]
        if i % 3 == 1:
            yield from axi_write(axi_bus, axi_write_transact, delay=0)
        else:
            yield from axi_write(axi_bus, axi_write_transact, delay='rand')

        for j in range(0, 4):
            assert((yield axi_slave.regs[j]) == v[j])

        axi_read_transact = [
            TRead(0x40000000, exp_resp=AXI3Response.OKAY, exp_data=v[0]),
            TRead(0x40000000, exp_resp=AXI3Response.OKAY, exp_data=[v[0], v[1]]),
            TRead(0x40000000, exp_resp=AXI3Response.OKAY, exp_data=[v[0], v[1], v[2]]),
            TRead(0x40000000, exp_resp=AXI3Response.OKAY, exp_data=[v[0], v[1], v[2], v[3]]),
            TRead(0x40000006, exp_resp=AXI3Response.OKAY, bytes_per_beat=2, exp_data=[v[1], v[2], v[2], v[3], v[3]]),
            TRead(0x40000010, exp_resp=AXI3Response.DECERR),
            TRead(0x40000006, exp_resp=AXI3Response.OKAY, bytes_per_beat=2, exp_data=[v[1], v[2], v[2], v[3], v[3]]),
            TRead(0x4000000c, exp_resp=AXI3Response.OKAY, arburst=AXI3Burst.WRAP, exp_data=[v[3], v[0], v[1], v[2]])
        ]
        yield from axi_read(axi_bus, axi_read_transact, delay='rand')

        for j in range(0, 4):
            assert((yield axi_slave.regs[j]) == v[j])

if len(sys.argv) > 1:
    seed = int(sys.argv[1])
else:
    seed = random.randrange(2**32)

print("seed = %d" % seed)

random.seed(seed)

m = Module()

axi_bus = AXI3Bus()

axi_slave = AXITestSlave(axi_bus, 4, 0x40000000)
m.submodules += axi_slave

sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(test_process)

with sim.write_vcd("sim.vcd"):
    sim.run()
