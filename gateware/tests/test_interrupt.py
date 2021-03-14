#!/usr/bin/python3
import sys
import os.path
from nmigen import *
from nmigen.sim import *

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from axi import *
from axi_sim import *
from axi_reg_bank import AXIRegBank
from int_ctrl import IntCtrl

INT_ENABLE_REG = 0x40000000
INT_STATUS_REG = 0x40000004
INT_COUNT_REG  = 0x40000008

def test_process():
    yield axi_bus.areset_n.eq(1)

    # test single interrupt request
    axi_write_transact = [ TWrite(INT_ENABLE_REG, 0x1, exp_resp=AXI3Response.OKAY) ]
    yield from axi_write(axi_bus, axi_write_transact, delay=0)

    assert((yield int_ctrl.int_pending_out) == 0)

    yield int_ctrl.int_req_in.eq(1)
    yield Tick()
    yield int_ctrl.int_req_in.eq(0)
    yield Tick()

    assert((yield int_ctrl.int_pending_out) == 1)

    axi_read_transact = [ TRead(INT_STATUS_REG, exp_resp=AXI3Response.OKAY, exp_data=0x1) ]
    yield from axi_read(axi_bus, axi_read_transact, delay=0)

    axi_write_transact = [ TWrite(INT_STATUS_REG, 0x1, exp_resp=AXI3Response.OKAY) ]
    yield from axi_write(axi_bus, axi_write_transact, delay=0)

    axi_read_transact = [ TRead(INT_STATUS_REG, exp_resp=AXI3Response.OKAY, exp_data=0x0) ]
    yield from axi_read(axi_bus, axi_read_transact, delay=0)

    assert((yield int_ctrl.int_pending_out) == 0)

    # test interrupt request overflow
    yield int_ctrl.int_req_in.eq(1)
    yield Tick()
    yield Tick()
    yield int_ctrl.int_req_in.eq(0)
    yield Tick()

    assert((yield int_ctrl.int_pending_out) == 1)

    axi_read_transact = [ TRead(INT_STATUS_REG, exp_resp=AXI3Response.OKAY, exp_data=0x10001) ]
    yield from axi_read(axi_bus, axi_read_transact, delay=0)

    axi_write_transact = [ TWrite(INT_STATUS_REG, 0x10001, exp_resp=AXI3Response.OKAY) ]
    yield from axi_write(axi_bus, axi_write_transact, delay=0)

    axi_read_transact = [ TRead(INT_STATUS_REG, exp_resp=AXI3Response.OKAY, exp_data=0x0) ]
    yield from axi_read(axi_bus, axi_read_transact, delay=0)

    assert((yield int_ctrl.int_pending_out) == 0)

    # check interrupt count
    axi_read_transact = [ TRead(INT_COUNT_REG, exp_resp=AXI3Response.OKAY, exp_data=3) ]
    yield from axi_read(axi_bus, axi_read_transact, delay=0)

m = Module()

axi_bus = AXI3Bus()

int_ctrl = IntCtrl()
m.submodules += int_ctrl

regs = [ int_ctrl.enable_reg, int_ctrl.status_reg, int_ctrl.count_reg ]

axi_slave = AXIRegBank(axi_bus, regs, 0x40000000)
m.submodules += axi_slave

sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(test_process)

with sim.write_vcd("sim.vcd"):
    sim.run()
