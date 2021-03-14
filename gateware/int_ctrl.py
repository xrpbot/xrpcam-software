from nmigen import *

class IntEnableRegister:
    """Interrupt controller: interrupt enable register (read/write)

    Bit 0: Interrupt enable. Set to 1 to enable interrupt requests.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class IntStatusRegister:
    """Interrupt controller: interrupt status register (write to clear)

    Bit 16: Interrupt overflow. Reads as 1 if an interrupt arrived while the last one was still pending. Write 1 to clear.
    Bit 0: Interrupt pending. Reads as 1 if an interrupt is pending. Write 1 to clear.
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class IntCountRegister:
    """Interrupt controller: count register (read-only)

    Total number of interrupt requests (32 bit).
    """
    def __init__(self):
        self.data_in = Signal(32)
        self.wstrb_in = Signal(4)
        self.data_out = Signal(32)

class IntCtrl(Elaboratable):
    def __init__(self):
        self.enable_reg = IntEnableRegister()
        self.status_reg = IntStatusRegister()
        self.count_reg = IntCountRegister()

        self.int_req_in = Signal(1)
        self.int_pending_out = Signal(1)

        self._int_enable = Signal(1)
        self._int_pending = Signal(1)
        self._int_overflow = Signal(1)
        self._cnt = Signal(32)

    def elaborate(self, platform):
        m = Module()

        # register read
        m.d.comb += self.enable_reg.data_out.eq(Cat(self._int_enable, Const(0, 31)))
        m.d.comb += self.status_reg.data_out.eq(Cat(self._int_pending, Const(0, 15), self._int_overflow, Const(0, 15)))
        m.d.comb += self.count_reg.data_out.eq(self._cnt)

        # register write
        with m.If(self.enable_reg.wstrb_in[0] == 1):
            m.d.sync += self._int_enable.eq(self.enable_reg.data_in[0])

        with m.If((self.status_reg.wstrb_in[0] == 1) & (self.status_reg.data_in[0] == 1)):
            m.d.sync += self._int_pending.eq(0)

        with m.If((self.status_reg.wstrb_in[2] == 1) & (self.status_reg.data_in[16] == 1)):
            m.d.sync += self._int_overflow.eq(0)

        # logic
        with m.If(self.int_req_in):
            m.d.sync += self._cnt.eq(self._cnt+1)
            with m.If(self._int_enable):
                with m.If(self._int_pending):
                    m.d.sync += self._int_overflow.eq(1)
                m.d.sync += self._int_pending.eq(1)

        m.d.comb += self.int_pending_out.eq(self._int_pending)

        return m
