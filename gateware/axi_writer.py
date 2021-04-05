from nmigen import *
from axi import AXI3Response, AXI3Burst, AXI3Prot

class AXIWriter_AddrReg:
    """AXI writer: address register

    Start address for DMA transaction. Must be 64 bit aligned. Therefore, the 3 lowest bits are forced to zero.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

        self._data = Signal(29)

class AXIWriter_CountReg:
    """AXI writer: count register

    Contains number of 64 bit words to transfer MINUS 1, i.e. set count register = 0 to transfer one word.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

        self._data = Signal(32)

class AXIWriter_StatusReg:
    """AXI writer: status register (read-only)

    Bit 10, 9: AXI response.
    Bit 8: ERROR. Set if an AXI error occured.
    Bit 0: BUSY. 1: DMA in progress.

    If an error response (0b10, SLVERR or 0b11, DECERR) is received during DMA,
    the ERROR bit is set and the AXI response bits record the response
    received. Further errors will not update the AXI reponse bits, i.e. they
    contain the first error received in case of multiple errors. The ERROR bit
    and the AXI response bits are automatically cleared on DMA start.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class AXIWriter_ControlReg:
    """AXI writer: control register (write-only)

    Bit 0: START. Write 1 to start DMA transaction.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class AXIWriter_ConfigReg:
    """AXI writer: configuration register

    Bit 0: INT_ENABLE. Set to 1 to enable interrupt once DMA transaction is completed.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class AXIWriter_IntStatusReg:
    """AXI writer: interrupt status register

    Bit 0: INT_PENDING. 1: A completion interrupt is pending. Write 1 to clear.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class AXIWriter(Elaboratable):
    def __init__(self, axi_bus, fifo):
        self.bus = axi_bus

        # Registers
        self.addr_reg = AXIWriter_AddrReg()
        self.count_reg = AXIWriter_CountReg()
        self.status_reg = AXIWriter_StatusReg()
        self.control_reg = AXIWriter_ControlReg()
        self.config_reg = AXIWriter_ConfigReg()
        self.int_status_reg = AXIWriter_IntStatusReg()

        # Data FIFO
        self.fifo = fifo

        # Interrupt output
        self.int_out = Signal()

    def elaborate(self, platform):
        # Implementation note on AXI bursts: the maximum burst length supported
        # by AXI3 is 16 transfers, or 128 bytes if each transfer is 8 bytes (64
        # bits) long. A burst must not cross a 4 KiB address boundary.
        # For performance reasons, we want to use maximum length bursts as much
        # as possible. The easiest way to ensure that these bursts do not cross
        # a 4 KiB address boundary is to align the start address of each burst
        # to 128 bytes, but we do not want to impose that constraint on the
        # user. Thus, we proceed as follows:
        # * The first burst transfers as many bytes as needed for alignment to
        #   a 128 byte boundary.
        # * The subsequent bursts transfer 128 bytes each.
        # * The last burst transfers as many bytes as needed to finish the
        #   transfer.
        # (Note that the first and the last burst may each transfer up to and
        # including 128 bytes, and that we finish after the first burst if we
        # are already done.)

        m = Module()

        start = Signal()
        busy = Signal()
        error = Signal()
        error_resp = Signal(2)
        int_enable = Signal()
        int_pending = Signal()
        addr_reg_data = Signal(32)

        # Address register logic
        # Note that the lowest 3 bits of the address are always zero (64 bit
        # alignment), and self.addr_reg._data therefore stores only the upper
        # 29 bits. Writes to the lowest 3 bits of the address register are
        # ignored.
        with m.If(self.addr_reg.wstrb_in[0] == 1):
            m.d.sync += self.addr_reg._data[0:5].eq(self.addr_reg.data_in[3:8])
        for i in range(1, 4):
            with m.If(self.addr_reg.wstrb_in[i] == 1):
                m.d.sync += self.addr_reg._data[8*i-3:8*(i+1)-3].eq(self.addr_reg.data_in[8*i:8*(i+1)])

        m.d.comb += addr_reg_data.eq(Cat(Const(0, 3), self.addr_reg._data))

        m.d.comb += self.addr_reg.data_out.eq(addr_reg_data)

        # Count register logic
        for i in range(0, 4):
            with m.If(self.count_reg.wstrb_in[i] == 1):
                m.d.sync += self.count_reg._data[8*i:8*(i+1)].eq(self.count_reg.data_in[8*i:8*(i+1)])

        m.d.comb += self.count_reg.data_out.eq(self.count_reg._data)

        # Status register logic
        m.d.comb += self.status_reg.data_out.eq(Cat(busy, Const(0, 7), error, error_resp, Const(0, 21)))

        # Control register logic
        m.d.comb += start.eq(self.control_reg.data_in[0] & self.control_reg.wstrb_in[0])
        m.d.comb += self.control_reg.data_out.eq(0)

        # Config register logic
        with m.If(self.config_reg.wstrb_in[0]):
            m.d.sync += int_enable.eq(self.config_reg.data_in[0])

        m.d.comb += self.config_reg.data_out.eq(Cat(int_enable, Const(0, 31)))

        # Interrupt logic
        busy_delay = Signal()

        m.d.sync += busy_delay.eq(busy)

        with m.If((busy == 0) & (busy_delay == 1) & (int_enable == 1)):
            m.d.sync += int_pending.eq(1)
        with m.Else():
            with m.If(self.int_status_reg.data_in[0] & self.int_status_reg.wstrb_in[0]):
                m.d.sync += int_pending.eq(0)

        m.d.comb += self.int_out.eq(int_pending)

        m.d.comb += self.int_status_reg.data_out.eq(Cat(int_pending, Const(0, 31)))

        # DMA engine
        n_data = Signal(32)
        n_addr = Signal(32)
        n_wlast = Signal(4)
        addr = Signal(32)
        n_resp = Signal(32)
        data_en = Signal()

        with m.If(n_wlast == 0):
            m.d.comb += self.bus.wlast.eq(1)
        with m.Else():
            m.d.comb += self.bus.wlast.eq(0)

        with m.If((data_en == 0) & (n_resp == 0)):
            m.d.comb += busy.eq(0)
        with m.Else():
            m.d.comb += busy.eq(1)

        m.d.comb += self.bus.wdata.eq(self.fifo.r_data)
        m.d.comb += self.bus.wvalid.eq(data_en & self.fifo.r_rdy)
        m.d.comb += self.fifo.r_en.eq(self.bus.wready & self.bus.wvalid)

        with m.FSM(reset="WAIT_START"):
            with m.State("WAIT_START"):
                with m.If(start == 1):
                    m.d.sync += n_data.eq(self.count_reg._data)

                    m.d.sync += error.eq(0)
                    m.d.sync += error_resp.eq(0)

                    m.d.sync += self.bus.awid.eq(0)
                    m.d.sync += self.bus.awaddr.eq(addr_reg_data)

                    # number of 64-bit words to 128 byte boundary
                    n_to_128 = ((0x80 - (addr_reg_data & 0x7F)) >> 3)

                    # NOTE: self.nr._data is number of 64-bit words to transfer MINUS 1
                    with m.If((self.count_reg._data > 15) & (n_to_128 == 16)):
                        # perform 16 word (= 128 byte) burst
                        m.d.sync += self.bus.awlen.eq(15)
                        m.d.sync += addr.eq(addr_reg_data+128)
                        m.d.sync += n_addr.eq(self.count_reg._data+1-16)
                        m.d.sync += n_wlast.eq(15)
                    with m.Elif(self.count_reg._data >= n_to_128):
                        # perform burst to 128 byte boundary
                        m.d.sync += self.bus.awlen.eq(n_to_128-1)
                        m.d.sync += addr.eq(addr_reg_data + (n_to_128<<3))
                        m.d.sync += n_addr.eq(self.count_reg._data+1 - n_to_128)
                        m.d.sync += n_wlast.eq(n_to_128-1)
                    with m.Else():
                        # perform complete transfer in one burst
                        m.d.sync += self.bus.awlen.eq(self.count_reg._data)
                        m.d.sync += n_addr.eq(0)
                        m.d.sync += n_wlast.eq(self.count_reg._data)

                    m.d.sync += self.bus.awsize.eq(3)
                    m.d.sync += self.bus.awburst.eq(AXI3Burst.INCR)
                    m.d.sync += self.bus.awlock.eq(0)

                    # AWCACHE: normal non-cacheable non-bufferable
                    m.d.sync += self.bus.awcache.eq(0b0010)

                    m.d.sync += self.bus.awprot.eq(AXI3Prot.UNPRIV | AXI3Prot.SECURE | AXI3Prot.DATA)
                    m.d.sync += self.bus.awqos.eq(0)
                    m.d.sync += self.bus.awvalid.eq(1)

                    m.d.sync += self.bus.wid.eq(0)
                    m.d.sync += self.bus.wstrb.eq(0xFF)
                    m.d.sync += data_en.eq(1)

                    m.next = "RUN"

            with m.State("RUN"):
                # address
                with m.If(self.bus.awready == 1):
                    with m.If(n_addr > 15):
                        # perform 16 word (= 128 byte) burst
                        m.d.sync += self.bus.awaddr.eq(addr)
                        m.d.sync += self.bus.awlen.eq(15)
                        m.d.sync += addr.eq(addr+128)
                        m.d.sync += n_addr.eq(n_addr-16)
                    with m.Elif(n_addr > 0):
                        # perform rest of burst
                        m.d.sync += self.bus.awaddr.eq(addr)
                        m.d.sync += self.bus.awlen.eq(n_addr-1)
                        m.d.sync += n_addr.eq(0)
                    with m.Else():
                        # done
                        m.d.sync += self.bus.awvalid.eq(0)

                # data
                with m.If((self.bus.wready == 1) & (self.bus.wvalid == 1)):
                    with m.If(n_data > 0):
                        m.d.sync += n_data.eq(n_data-1)
                    with m.Else():
                        m.d.sync += data_en.eq(0)

                    with m.If(n_wlast > 0):
                        m.d.sync += n_wlast.eq(n_wlast-1)
                    with m.Else():
                        with m.If(n_data > 15):
                            m.d.sync += n_wlast.eq(15)
                        with m.Else():
                            with m.If(n_data > 0):
                                m.d.sync += n_wlast.eq(n_data-1)
                            with m.Else():
                                m.d.sync += n_wlast.eq(0)

                # completion check
                with m.If((self.bus.awvalid == 0) & (data_en == 0)):
                    m.next = "WAIT_START"

        with m.If(self.bus.areset_n):
            m.d.sync += self.bus.bready.eq(1)
        with m.Else():
            m.d.sync += self.bus.bready.eq(0)

        with m.If((self.bus.bready == 1) & (self.bus.bvalid == 1) & (self.bus.bresp[1] == 1)):
            m.d.sync += error.eq(1)
            # record response for first error that occurs
            with m.If(error == 0):
                m.d.sync += error_resp.eq(self.bus.bresp)

        n_resp_incr = ((self.bus.awready == 1) & (self.bus.awvalid == 1))
        n_resp_decr = ((self.bus.bready == 1) & (self.bus.bvalid == 1))

        with m.If((n_resp_incr == 1) & (n_resp_decr == 0)):
            m.d.sync += n_resp.eq(n_resp + 1)
        with m.Elif((n_resp_incr == 0) & (n_resp_decr == 1)):
            m.d.sync += n_resp.eq(n_resp - 1)

        return m
