#!/usr/bin/python3
import random
import sys
import os.path
from nmigen import *
from nmigen.lib.fifo import SyncFIFO
from nmigen.sim import *

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from axi import *
from axi_sim import *
from axi_reg_bank import AXIRegBank, Register_RO
from test_data_source import TestDataSource
from axi_writer import AXIWriter

use_test_data_source = True

DMA_ADDR_REG =       0x40000000
DMA_COUNT_REG =      0x40000004
DMA_STATUS_REG =     0x40000008
DMA_CONTROL_REG =    0x4000000C

DS_DATA_REG =        0x40000010
DS_COUNT_REG =       0x40000014
DS_STATUS_REG =      0x40000018
DS_CONTROL_REG =     0x4000001C

# Python dictionary backing the simulated memory
memory = dict()

# AXI bus for AXI writer to access memory
axi_mem_bus = AXI3Bus(data_bits=64)

# AXI bus to control AXI writer and data source
axi_reg_bus = AXI3Bus()

# FIFO used to feed data into AXI writer
data_fifo = SyncFIFO(width=64, depth=2)

def test_process():
    if use_test_data_source:
        fifo = None
    else:
        fifo = data_fifo

    yield axi_reg_bus.areset_n.eq(1)

    yield from dma_test(0x50000FF0, 100, fifo)
    yield from dma_test(0x50000FF8, 100, fifo)
    yield from dma_test(0x50000000, 100, fifo)
    yield from dma_test(0x50000FF0, 10, fifo)
    yield from dma_test(0x50000FF8, 10, fifo)
    yield from dma_test(0x50000000, 10, fifo)
    yield from dma_test(0x50000FF0, 1, fifo)
    yield from dma_test(0x50000FF8, 1, fifo)
    yield from dma_test(0x50000000, 1, fifo)

    yield from dma_test(0xEFFFFFF0, 40, fifo, exp_error=0x2)

    for i in range(0, 10):
        addr = random.randrange(0, 2**29) * 8
        num_words = random.randrange(1, 100)
        if (addr + 8*num_words) > 0xF0000000:
            exp_error = 0x2
        else:
            exp_error = 0
        yield from dma_test(addr, num_words, fifo, exp_error)

    for _ in range(0, 10):
        yield Tick()

def dma_test(addr, num_words, fifo=None, exp_error=0):
    if (addr & 0x7) != 0:
        raise RuntimeError("DMA start address must be 64-bit aligned")

    if num_words == 0:
        raise RuntimeError("Cannot do DMA transfer with 0 words")

    # clear target memory
    memory.clear()

    start = random.randrange(2**32)
    data = start

    # if FIFO is controlled directly: pre-fill the FIFO
    if fifo is not None:
        prefill = random.randrange(0, min(num_words, fifo.depth))
        for _ in range(0, prefill):
            yield fifo.w_data.eq((data+1)<<32 | data)
            yield fifo.w_en.eq(1)
            yield Tick()
            data += 2
        yield fifo.w_en.eq(0)

    # configure AXI writer: start address, count
    axi_transact = [
        TWrite(DMA_ADDR_REG, addr, exp_resp=AXI3Response.OKAY),
        TWrite(DMA_COUNT_REG, num_words-1, exp_resp=AXI3Response.OKAY)
    ]
    yield from axi_write(axi_reg_bus, axi_transact, delay=0)

    # check that registers reflect the value written
    axi_transact = [
        TRead(DMA_ADDR_REG, exp_data=addr, exp_resp=AXI3Response.OKAY),
        TRead(DMA_COUNT_REG, exp_data=num_words-1, exp_resp=AXI3Response.OKAY)
    ]
    yield from axi_read(axi_reg_bus, axi_transact, delay=0)

    # if data source is used: configure and start data source
    if fifo is None:
        axi_transact = [
            TWrite(DS_DATA_REG, start, exp_resp=AXI3Response.OKAY),
            TWrite(DS_COUNT_REG, num_words-1, exp_resp=AXI3Response.OKAY)
        ]
        yield from axi_write(axi_reg_bus, axi_transact, delay=0)

        # check that registers reflect the value written
        axi_transact = [
            TRead(DS_DATA_REG, exp_data=start, exp_resp=AXI3Response.OKAY),
            TRead(DS_COUNT_REG, exp_data=num_words-1, exp_resp=AXI3Response.OKAY)
        ]
        yield from axi_read(axi_reg_bus, axi_transact, delay=0)

        # start data source
        axi_transact = [
            TWrite(DS_CONTROL_REG, 0x1, exp_resp=AXI3Response.OKAY)
        ]
        yield from axi_write(axi_reg_bus, axi_transact, delay=0)

        # verify that BUSY bit is set
        # Note: this test may fail for very short transfers.
        if num_words >= 10:
            axi_transact = [
                TRead(DS_STATUS_REG, exp_data=0x1, exp_resp=AXI3Response.OKAY)
            ]
            yield from axi_read(axi_reg_bus, axi_transact, delay=0)

    # start DMA
    axi_transact = [
        TWrite(DMA_CONTROL_REG, 0x1, exp_resp=AXI3Response.OKAY),
    ]
    yield from axi_write(axi_reg_bus, axi_transact, delay=0)

    # verify that BUSY bit is set
    # Note: This test may fail for very short DMA transfers, or if an error is to be reported.
    if num_words >= 10 and exp_error == 0:
        axi_transact = [
            TRead(DMA_STATUS_REG, exp_data=1, exp_resp=AXI3Response.OKAY)
        ]
        yield from axi_read(axi_reg_bus, axi_transact, delay=0)

    # if FIFO is controlled directly: keep filling the FIFO
    if fifo is not None:
        for _ in range(0, num_words-prefill):
            yield fifo.w_data.eq((data+1)<<32 | data)
            yield fifo.w_en.eq(1)
            yield Tick()
            yield fifo.w_en.eq(0)
            for _ in range(0, random.randrange(0, 3)):
                yield Tick()
            data += 2

    # wait for DMA completion
    while ((yield axi_writer.status_reg.data_out[0]) == 1):
        yield Tick()

    # verify that potential errors are correctly reported
    if exp_error != 0:
        axi_transact = [
            TRead(DMA_STATUS_REG, exp_data=(0x0100 | (exp_error << 9)), exp_resp=AXI3Response.OKAY)
        ]
    else:
        axi_transact = [
            TRead(DMA_STATUS_REG, exp_data=0, exp_resp=AXI3Response.OKAY)
        ]
    yield from axi_read(axi_reg_bus, axi_transact, delay=0)

    # if data source is used: verify that data source BUSY bit is clear
    if fifo is None:
        axi_transact = [
            TRead(DS_STATUS_REG, exp_data=0, exp_resp=AXI3Response.OKAY)
        ]
        yield from axi_read(axi_reg_bus, axi_transact, delay=0)

    # check if only the expected memory locations were written to, and if they contain the right values
    if sorted(memory.keys()) == list(range(addr, addr+8*num_words, 8)):
        mem_check = True
        for i in range(0, num_words):
            if memory[addr+8*i] != (start+2*i+1)<<32 | (start+2*i):
                print("Memory content mismatch @0x%x, found=0x%x, exp=0x%x" % (addr+8*i, memory[addr+8*i], (start+2*i+1)<<32 | (start+2*i)))
                mem_check = False
    else:
        print("Error: invalid addresses written in memory")
        mem_check = False

    if not mem_check:
        print("Error: memory check failed")
    # print("mem_check: %s" % str(mem_check))

def mem_sim_process():
    yield Passive()

    yield axi_mem_bus.areset_n.eq(1)

    yield axi_mem_bus.awready.eq(1)
    yield axi_mem_bus.wready.eq(1)

    addr_fifo = []
    resp_fifo = []

    cur_len = 0

    while True:
        if (yield axi_mem_bus.awvalid) == 1:
            addr = (yield axi_mem_bus.awaddr)
            awlen = (yield axi_mem_bus.awlen)
            # print("addr = 0x%x, awlen=%d" % (addr, awlen))
            if (addr & ~0x7F) != ((addr+8*awlen) & ~0x7f):
                print("Error: transaction crosses 128 byte boundary")
            addr_fifo.insert(0, (addr, awlen))
        if (yield axi_mem_bus.wvalid) == 1:
            wlast_exp = 0
            if cur_len == 0:
                (addr, awlen) = addr_fifo.pop()
                cur_len = awlen+1
                cur_addr = addr
            if cur_len == 1:
                wlast_exp = 1
                if cur_addr >= 0xF0000000:
                    resp_fifo.insert(0, 0x2)
                else:
                    resp_fifo.insert(0, 0x0)
            wdata = (yield axi_mem_bus.wdata)
            wstrb = (yield axi_mem_bus.wstrb)
            wlast = (yield axi_mem_bus.wlast)
            # print("data[0x%x] = 0x%x, wlast = %d, wlast_exp = %d" % (cur_addr, wdata, wlast, wlast_exp))
            if wlast != wlast_exp:
                print("Error: wrong value for wlast (%d, exp=%d)" % (wlast, wlast_exp))
            if wstrb == 0xFF:
                memory[cur_addr] = wdata
            elif wstrb == 0:
                pass
            else:
                print("Error: WSTRB value 0x%02x unhandled by memory simulator" % wstrb)
            cur_addr += 8
            cur_len -= 1
        if len(resp_fifo) > 0:
            yield axi_mem_bus.bresp.eq(resp_fifo[-1])
            yield axi_mem_bus.bvalid.eq(1)
        else:
            yield axi_mem_bus.bvalid.eq(0)
        yield Tick()
        if ((yield axi_mem_bus.bvalid) == 1) and ((yield axi_mem_bus.bready) == 1):
            resp_fifo.pop()

if len(sys.argv) > 1:
    seed = int(sys.argv[1])
else:
    seed = random.randrange(2**32)

print("seed = %d" % seed)

random.seed(seed)

m = Module()
m.submodules += data_fifo

if use_test_data_source:
    data_source = TestDataSource(data_fifo)
    m.submodules += data_source

axi_writer = AXIWriter(axi_mem_bus, data_fifo)
m.submodules += axi_writer

regs = [ axi_writer.addr_reg, axi_writer.count_reg, axi_writer.status_reg, axi_writer.control_reg ]

if use_test_data_source:
    regs += [ data_source.data_reg, data_source.count_reg, data_source.status_reg, data_source.control_reg ]

axi_reg_bank = AXIRegBank(axi_reg_bus, regs, 0x40000000)
m.submodules += axi_reg_bank

sim = Simulator(m)
sim.add_clock(1e-6)
sim.add_sync_process(mem_sim_process)
sim.add_sync_process(test_process)
with sim.write_vcd("sim.vcd"):
    sim.run()
