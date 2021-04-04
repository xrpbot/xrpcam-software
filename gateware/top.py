from nmigen import *
from nmigen.lib.fifo import SyncFIFO
import axi
from axi_reg_bank import AXIRegBank, Register_RO, Register_RW
from int_ctrl import IntCtrl
from test_data_source import TestDataSource
from axi_writer import AXIWriter
from ps7 import PS7

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        # PS7
        ps7 = PS7()
        m.submodules += ps7

        # Default clock (provided by PS7)
        m.domains.sync = ClockDomain("sync")
        clk = ClockSignal("sync")
        m.d.comb += clk.eq(ps7.fclk[0])

        # Clock constraint
        clk_ = Signal()
        m.d.comb += clk_.eq(clk)

        platform.add_clock_constraint(clk_, 100000000)

        # ZedBoard platform
        led = [ platform.request("led", i) for i in range(0, 8) ]
        switch = [ platform.request("switch", i) for i in range(0, 8) ]

        # AXI bus for CPU to access registers (gateware is slave)
        axi_reg_bus = ps7.m_axi_gp0
        m.d.comb += axi_reg_bus.aclk.eq(clk)

        # AXI bus for writer to access main memory (gateware is master)
        axi_mem_bus = ps7.s_axi_hp0
        m.d.comb += axi_mem_bus.aclk.eq(clk)

        # Synchronize switch input to `sync' clock
        sw_tmp1 = Signal(len(switch))
        sw_tmp2 = Signal(len(switch))
        sw_data = Signal(len(switch))

        for i in range(0, len(switch)):
            m.d.sync += sw_tmp1[i].eq(switch[i])
        m.d.sync += sw_tmp2.eq(sw_tmp1)
        m.d.sync += sw_data.eq(sw_tmp2)

        # Interrupt
        int_ctrl = IntCtrl()
        m.submodules += int_ctrl

        sw_last = Signal(len(switch))

        with m.If(sw_data != sw_last):
            m.d.sync += int_ctrl.int_req_in.eq(1)
            m.d.sync += sw_last.eq(sw_data)
        with m.Else():
            m.d.sync += int_ctrl.int_req_in.eq(0)

        m.d.comb += ps7.irqf2p[0].eq(int_ctrl.int_pending_out)
        m.d.comb += led[1].o.eq(int_ctrl.int_pending_out)

        # Timer
        timer_sync = Signal(32)
        m.d.sync += timer_sync.eq(timer_sync+1)

        # DMA
        fifo = SyncFIFO(width=64, depth=4)
        m.submodules += fifo

        data_source = TestDataSource(fifo)
        m.submodules += data_source

        axi_writer = AXIWriter(axi_mem_bus, fifo)
        m.submodules += axi_writer

        # Transaction counters (memory bus)
        cnt_mem_aw = Signal(32)
        cnt_mem_w = Signal(32)
        cnt_mem_b = Signal(32)

        with m.If((axi_mem_bus.awvalid == 1) & (axi_mem_bus.awready == 1)):
            m.d.sync += cnt_mem_aw.eq(cnt_mem_aw + 1)

        with m.If((axi_mem_bus.wvalid == 1) & (axi_mem_bus.wready == 1)):
            m.d.sync += cnt_mem_w.eq(cnt_mem_w + 1)

        with m.If((axi_mem_bus.bvalid == 1) & (axi_mem_bus.bready == 1)):
            m.d.sync += cnt_mem_b.eq(cnt_mem_b + 1)

        regs = []

        # Registers #0 - #6: read/write, no function
        for i in range(0, 7):
            reg = Register_RW()
            regs.append(reg)
            m.submodules += reg

        # Register #7 (0x4000001C): read-only, writes will be silently ignored
        reg = Register_RO(0xF000BAAA)
        regs.append(reg)
        m.submodules += reg

        # Register #8 (0x40000020): current state of switches (read-only)
        reg = Register_RO(sw_data)
        regs.append(reg)
        m.submodules += reg

        # Register #9 (0x40000024): current timer value (read-only)
        reg = Register_RO(timer_sync)
        regs.append(reg)
        m.submodules += reg

        # Register #10 (0x40000028): interrupt enable register (read/write)
        # Register #11 (0x4000002C): interrupt status register (write to clear)
        # Register #12 (0x40000030): interrupt count register (read-only)
        regs += [ int_ctrl.enable_reg, int_ctrl.status_reg, int_ctrl.count_reg ]

        # Register #13 (0x40000034): test data source: data register
        # Register #14 (0x40000038): test data source: count register
        # Register #16 (0x4000003C): test data source: status register
        # Register #15 (0x40000040): test data source: control register
        regs += [ data_source.data_reg, data_source.count_reg, data_source.status_reg, data_source.control_reg ]

        # Register #17 (0x40000044): memory write address count
        reg = Register_RO(cnt_mem_aw)
        regs.append(reg)
        m.submodules += reg

        # Register #18 (0x40000048): memory write data count
        reg = Register_RO(cnt_mem_w)
        regs.append(reg)
        m.submodules += reg

        # Register #19 (0x4000004C): memory write response count
        reg = Register_RO(cnt_mem_b)
        regs.append(reg)
        m.submodules += reg

        # Register #20 (0x40000050): AXI writer: address register
        # Register #21 (0x40000054): AXI writer: count register
        # Register #22 (0x40000058): AXI writer: status register
        # Register #23 (0x4000005C): AXI writer: control register
        regs += [ axi_writer.addr_reg, axi_writer.count_reg, axi_writer.status_reg, axi_writer.control_reg ]

        axi_slave = AXIRegBank(axi_reg_bus, regs, 0x40000000)
        m.submodules += axi_slave

        # Transaction counters (register bus)
        cnt_reg_aw = Signal(8)
        cnt_reg_w = Signal(8)
        cnt_reg_b = Signal(8)
        cnt_reg_ar = Signal(8)
        cnt_reg_r = Signal(8)

        with m.If((axi_reg_bus.awvalid == 1) & (axi_reg_bus.awready == 1)):
            m.d.sync += cnt_reg_aw.eq(cnt_reg_aw + 1)

        with m.If((axi_reg_bus.wvalid == 1) & (axi_reg_bus.wready == 1)):
            m.d.sync += cnt_reg_w.eq(cnt_reg_w + 1)

        with m.If((axi_reg_bus.bvalid == 1) & (axi_reg_bus.bready == 1)):
            m.d.sync += cnt_reg_b.eq(cnt_reg_b + 1)

        with m.If((axi_reg_bus.arvalid == 1) & (axi_reg_bus.arready == 1)):
            m.d.sync += cnt_reg_ar.eq(cnt_reg_ar + 1)

        with m.If((axi_reg_bus.rvalid == 1) & (axi_reg_bus.rready == 1)):
            m.d.sync += cnt_reg_r.eq(cnt_reg_r + 1)

        m.d.comb += ps7.emiogpio_i[0:8].eq(cnt_reg_aw)
        m.d.comb += ps7.emiogpio_i[8:16].eq(cnt_reg_w)
        m.d.comb += ps7.emiogpio_i[16:24].eq(cnt_reg_b)
        m.d.comb += ps7.emiogpio_i[24:32].eq(cnt_reg_ar)
        m.d.comb += ps7.emiogpio_i[32:40].eq(cnt_reg_r)

        m.d.comb += ps7.emiogpio_i[40:48].eq(regs[0].data_out[0:8])

        m.d.comb += led[0].o.eq(timer_sync[27])

        m.d.comb += led[4].o.eq(regs[0].data_out[0])
        m.d.comb += led[5].o.eq(regs[0].data_out[1])
        m.d.comb += led[6].o.eq(regs[0].data_out[2])
        m.d.comb += led[7].o.eq(regs[0].data_out[3])

        return m
