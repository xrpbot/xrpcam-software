from nmigen import *
import axi
from axi_reg_bank import AXIRegBank, Register_RO, Register_RW
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

        # AXI
        axi_bus = ps7.m_axi_gp0
        m.d.comb += axi_bus.aclk.eq(clk)

        regs = []
        for i in range(0, 7):
            reg = Register_RW()
            regs.append(reg)
            m.submodules += reg

        # Register #7 is read-only, writes will be silently ignored
        reg = Register_RO(0xF000BAAA)
        regs.append(reg)
        m.submodules += reg

        axi_slave = AXIRegBank(axi_bus, regs, 0x40000000)
        m.submodules += axi_slave

        led = [ platform.request("led", i) for i in range(0, 8) ]

        # Transaction counters
        cnt_aw = Signal(8)
        cnt_w = Signal(8)
        cnt_b = Signal(8)
        cnt_ar = Signal(8)
        cnt_r = Signal(8)

        with m.If((axi_bus.awvalid == 1) & (axi_bus.awready == 1)):
            m.d.sync += cnt_aw.eq(cnt_aw+1)

        with m.If((axi_bus.wvalid == 1) & (axi_bus.wready == 1)):
            m.d.sync += cnt_w.eq(cnt_w+1)

        with m.If((axi_bus.bvalid == 1) & (axi_bus.bready == 1)):
            m.d.sync += cnt_b.eq(cnt_b + 1)

        with m.If((axi_bus.arvalid == 1) & (axi_bus.arready == 1)):
            m.d.sync += cnt_ar.eq(cnt_ar + 1)

        with m.If((axi_bus.rvalid == 1) & (axi_bus.rready == 1)):
            m.d.sync += cnt_r.eq(cnt_r + 1)

        m.d.comb += ps7.emiogpio_i[0:8].eq(cnt_aw)
        m.d.comb += ps7.emiogpio_i[8:16].eq(cnt_w)
        m.d.comb += ps7.emiogpio_i[16:24].eq(cnt_b)
        m.d.comb += ps7.emiogpio_i[24:32].eq(cnt_ar)
        m.d.comb += ps7.emiogpio_i[32:40].eq(cnt_r)

        m.d.comb += ps7.emiogpio_i[40:48].eq(regs[0].data_out[0:8])

        timer_sync = Signal(28)
        m.d.sync += timer_sync.eq(timer_sync+1)

        m.d.comb += led[0].o.eq(timer_sync[-1])

        m.d.comb += led[4].o.eq(regs[0].data_out[0])
        m.d.comb += led[5].o.eq(regs[0].data_out[1])
        m.d.comb += led[6].o.eq(regs[0].data_out[2])
        m.d.comb += led[7].o.eq(regs[0].data_out[3])

        return m
