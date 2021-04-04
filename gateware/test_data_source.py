from nmigen import *
from nmigen.lib.fifo import SyncFIFO

class TestDataSource_DataReg:
    """Test data source: data register

    Start value for the test data generator (see description of the
    TestDataSource class for details).
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

        self._data = Signal(32)

class TestDataSource_CountReg:
    """Test data source: count register

    Contains number of 64 bit words to generate MINUS 1, i.e. set count register = 0 to generate one word.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

        self._data = Signal(32)

class TestDataSource_StatusReg:
    """Test data source: status register (read-only)

    Bit 0: BUSY.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class TestDataSource_ControlReg:
    """Test data source: control register (write-only)

    Bit 0: START.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class TestDataSource(Elaboratable):
    """TestDataSource

    Creates a stream of a configurable number of 64 bit words and feeds them
    into the fifo. The words are of the form Cat(i, i+1), where i is a 32 bit
    value that increments by 2 between words and the addition is truncated to
    32 bits. The initial value of i is configurable.
    """
    def __init__(self, fifo):
        # Registers
        self.data_reg = TestDataSource_DataReg()
        self.count_reg = TestDataSource_CountReg()
        self.status_reg = TestDataSource_StatusReg()
        self.control_reg = TestDataSource_ControlReg()

        # Data FIFO
        self.fifo = fifo

    def elaborate(self, platform):
        m = Module()

        # Data register logic
        for i in range(0, 4):
            with m.If(self.data_reg.wstrb_in[i] == 1):
                m.d.sync += self.data_reg._data[8*i:8*(i+1)].eq(self.data_reg.data_in[8*i:8*(i+1)])

        m.d.comb += self.data_reg.data_out.eq(self.data_reg._data)

        # Count register logic
        for i in range(0, 4):
            with m.If(self.count_reg.wstrb_in[i] == 1):
                m.d.sync += self.count_reg._data[8*i:8*(i+1)].eq(self.count_reg.data_in[8*i:8*(i+1)])

        m.d.comb += self.count_reg.data_out.eq(self.count_reg._data)

        # Status register logic
        busy = Signal()
        m.d.comb += self.status_reg.data_out.eq(Cat(busy, Const(0, 31)))

        # Control register logic
        start = Signal()
        m.d.comb += start.eq(self.control_reg.data_in[0] & self.control_reg.wstrb_in[0])
        m.d.comb += self.control_reg.data_out.eq(0)

        # Engine
        data = Signal(32)
        n_data = Signal(32)
        m.d.comb += self.fifo.w_data.eq(Cat(data, (data+1)[0:32]))

        with m.FSM(reset="WAIT_START"):
            with m.State("WAIT_START"):
                with m.If(start == 1):
                    m.d.sync += data.eq(self.data_reg._data)
                    m.d.sync += n_data.eq(self.count_reg._data)
                    m.d.sync += self.fifo.w_en.eq(1)
                    m.d.sync += busy.eq(1)
                    m.next = "RUN"
            with m.State("RUN"):
                with m.If(self.fifo.w_rdy == 1):
                    with m.If(n_data > 0):
                        m.d.sync += n_data.eq(n_data-1)
                        m.d.sync += data.eq(data+2)
                    with m.Else():
                        m.d.sync += self.fifo.w_en.eq(0)
                        m.d.sync += busy.eq(0)
                        m.next = "WAIT_START"

        return m
