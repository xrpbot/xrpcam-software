from nmigen import *
import axi
from axi_test_slave import AXITestSlave
from ps7 import PS7

class Top(Elaboratable):
    def elaborate(self, platform):
        m = Module()
        clk = ClockSignal("sync")

        # PS7
        ps7 = PS7()
        m.submodules += ps7

        # AXI
        axi_bus = ps7.m_axi_gp0
        m.d.comb += axi_bus.aclk.eq(clk)

        axi_slave = AXITestSlave(axi_bus, 8, 0x40000000)
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

        m.d.comb += ps7.emiogpio_i[40:48].eq(axi_slave.regs[0][0:8])

        timer_sync = Signal(28)
        m.d.sync += timer_sync.eq(timer_sync+1)

        m.d.comb += led[0].o.eq(timer_sync[-1])

        m.d.comb += led[4].o.eq(axi_slave.regs[0][0])
        m.d.comb += led[5].o.eq(axi_slave.regs[0][1])
        m.d.comb += led[6].o.eq(axi_slave.regs[0][2])
        m.d.comb += led[7].o.eq(axi_slave.regs[0][3])

        return m
