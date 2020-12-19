from nmigen import *
from axi import AXI3Response, AXI3Burst

class Register_RO(Elaboratable):
    def __init__(self, value):
        self.value = value

        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

    def elaborate(self, platform):
        m = Module()

        m.d.comb += self.data_out.eq(self.value)

        return m

class Register_RW(Elaboratable):
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

        self._data = Signal(32)

    def elaborate(self, platform):
        m = Module()

        for i in range(0, 4):
            with m.If(self.wstrb_in[i] == 1):
                m.d.sync += self._data[8*i:8*(i+1)].eq(self.data_in[8*i:8*(i+1)])

        m.d.comb += self.data_out.eq(self._data)

        return m

class AXIRegBank(Elaboratable):
    def __init__(self, axi_bus, regs, base_addr):
        self.bus = axi_bus
        self.regs = Array(regs)
        self.base_addr = base_addr

    def elaborate(self, platform):
        m = Module()

        # Write handling
        awaddr = Signal(self.bus.awaddr.shape())
        awsize = Signal(self.bus.awsize.shape())
        w_wrap_mask = Signal(self.bus.awaddr.shape())

        for i in range(0, len(self.regs)):
            for j in range(0, 4):
                m.d.comb += self.regs[i].data_in.eq(self.bus.wdata)
                m.d.comb += self.regs[i].wstrb_in[j].eq(0)

        with m.FSM(reset="RESET"):
            with m.State("RESET"):
                with m.If(self.bus.areset_n == 1):
                    m.next = "WAIT_ADDR"

            with m.State("WAIT_ADDR"):
                with m.If(self.bus.areset_n == 0):
                    m.next = "RESET"
                with m.Elif(self.bus.awvalid == 1):
                    m.d.sync += awaddr.eq(self.bus.awaddr)
                    m.d.sync += awsize.eq(self.bus.awsize)

                    with m.If(self.bus.awburst == AXI3Burst.FIXED):
                        m.d.sync += w_wrap_mask.eq(0)
                    with m.Elif(self.bus.awburst == AXI3Burst.INCR):
                        m.d.sync += w_wrap_mask.eq(~0)
                    with m.Else():  # AXI3Burst.WRAP
                        # The AXI spec guarantees that awlen+1 will be a power of 2 for wrapping bursts.
                        m.d.sync += w_wrap_mask.eq(((self.bus.awlen+1) << (self.bus.awsize))-1)

                    m.d.sync += self.bus.bresp.eq(AXI3Response.OKAY)
                    m.d.sync += self.bus.bid.eq(self.bus.awid)
                    m.d.sync += self.bus.awready.eq(1)
                    m.d.sync += self.bus.wready.eq(1)
                    m.next = "WAIT_DATA"

            with m.State("WAIT_DATA"):
                m.d.sync += self.bus.awready.eq(0)

                with m.If(self.bus.areset_n == 0):
                    m.d.sync += self.bus.wready.eq(0)
                    m.next = "RESET"
                with m.Elif(self.bus.wvalid == 1):
                    with m.If((awaddr >= self.base_addr) & ((awaddr - self.base_addr) < 4*len(self.regs))):
                        reg_addr = (awaddr - self.base_addr) >> 2
                        m.d.comb += self.regs[reg_addr].wstrb_in.eq(self.bus.wstrb)
                    with m.Else():
                        m.d.sync += self.bus.bresp.eq(AXI3Response.DECERR)

                    m.d.sync += awaddr.eq((awaddr & ~w_wrap_mask) | ((awaddr + (1<<awsize)) & w_wrap_mask))

                    with m.If(self.bus.wlast == 1):
                        m.d.sync += self.bus.wready.eq(0)
                        m.d.sync += self.bus.bvalid.eq(1)
                        m.next = "WAIT_RESP_READY"

            with m.State("WAIT_RESP_READY"):
                with m.If(self.bus.areset_n == 0):
                    m.d.sync += self.bus.bvalid.eq(0)
                    m.next = "RESET"
                with m.Elif(self.bus.bready == 1):
                    m.d.sync += self.bus.bvalid.eq(0)
                    m.next = "WAIT_ADDR"

        # Read handling
        arid = Signal(self.bus.arid.shape())
        araddr = Signal(self.bus.araddr.shape())
        arlen = Signal(self.bus.arlen.shape())
        arsize = Signal(self.bus.arsize.shape())
        r_wrap_mask = Signal(self.bus.araddr.shape())

        with m.FSM(reset="RESET"):
            with m.State("RESET"):
                with m.If(self.bus.areset_n == 1):
                    m.d.sync += self.bus.arready.eq(1)
                    m.next = "WAIT_VALID"

            with m.State("WAIT_VALID"):
                with m.If(self.bus.areset_n == 0):
                    m.d.sync += self.bus.arready.eq(0)
                    m.next = "RESET"
                with m.Elif(self.bus.arvalid == 1):
                    m.d.sync += arid.eq(self.bus.arid)
                    m.d.sync += araddr.eq(self.bus.araddr)
                    m.d.sync += arlen.eq(self.bus.arlen)
                    m.d.sync += arsize.eq(self.bus.arsize)

                    with m.If(self.bus.arburst == AXI3Burst.FIXED):
                        m.d.sync += r_wrap_mask.eq(0)
                    with m.Elif(self.bus.arburst == AXI3Burst.INCR):
                        m.d.sync += r_wrap_mask.eq(~0)
                    with m.Else():  # AXI3Burst.WRAP
                        # The AXI spec guarantees that arlen+1 will be a power of 2 for wrapping bursts.
                        m.d.sync += r_wrap_mask.eq(((self.bus.arlen+1) << (self.bus.arsize))-1)

                    m.d.sync += self.bus.arready.eq(0)
                    m.d.sync += self.bus.rvalid.eq(1)
                    m.next = "SEND_DATA"

            with m.State("SEND_DATA"):
                with m.If(self.bus.areset_n == 0):
                    m.d.sync += self.bus.rvalid.eq(0)
                    m.next = "RESET"
                with m.Elif(self.bus.rready == 1):
                    with m.If(arlen == 0):
                        m.d.sync += self.bus.rvalid.eq(0)
                        m.d.sync += self.bus.arready.eq(1)
                        m.next = "WAIT_VALID"
                    with m.Else():
                        m.d.sync += araddr.eq((araddr & ~r_wrap_mask) | ((araddr + (1<<arsize)) & r_wrap_mask))
                        m.d.sync += arlen.eq(arlen-1)
                        m.next = "SEND_DATA"

        with m.If((araddr >= self.base_addr) & ((araddr - self.base_addr) < 4*len(self.regs))):
            m.d.comb += self.bus.rdata.eq(self.regs[(araddr - self.base_addr) >> 2].data_out)
            m.d.comb += self.bus.rresp.eq(AXI3Response.OKAY)
        with m.Else():
            m.d.comb += self.bus.rdata.eq(0xDEADBEEF)
            m.d.comb += self.bus.rresp.eq(AXI3Response.DECERR)

        m.d.comb += self.bus.rid.eq(arid)

        with m.If(arlen == 0):
            m.d.comb += self.bus.rlast.eq(1)
        with m.Else():
            m.d.comb += self.bus.rlast.eq(0)

        return m
