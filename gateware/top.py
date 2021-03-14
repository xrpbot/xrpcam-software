from nmigen import *
import axi
from axi_reg_bank import AXIRegBank, Register_RO, Register_RW
from int_ctrl import IntCtrl
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

        # AXI
        axi_bus = ps7.m_axi_gp0
        m.d.comb += axi_bus.aclk.eq(clk)

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

        axi_slave = AXIRegBank(axi_bus, regs, 0x40000000)
        m.submodules += axi_slave

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

        m.d.comb += led[0].o.eq(timer_sync[27])

        m.d.comb += led[4].o.eq(regs[0].data_out[0])
        m.d.comb += led[5].o.eq(regs[0].data_out[1])
        m.d.comb += led[6].o.eq(regs[0].data_out[2])
        m.d.comb += led[7].o.eq(regs[0].data_out[3])

        return m
