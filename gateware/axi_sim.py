from collections.abc import Iterable
import random
from nmigen import *
from nmigen.back.pysim import *
import axi

class TWrite:
    """Class representing an AXI write transaction.

    addr -- Destination address.
    data -- Data to write. Can be a single value or a list (for burst
        transactions). Burst length is determined from the length of
        the list, or 1 if a single value.
    bytes_per_beat -- Number of bytes to transfer in each burst.
    awburst -- Burst type (AXI3Burst). See AXI spec.
    wstrb -- Write strobe. Can be 0 for a transaction that the slave should
        ignore or 'auto' to be determined from addr and bytes_per_beat.
    exp_resp -- Expected response (AXI3Response or None). If None, any response
        from the slave is accepted.
    """
    def __init__(self, addr, data, bytes_per_beat=4, awburst=axi.AXI3Burst.INCR, wstrb='auto', exp_resp=None):
        if bytes_per_beat == 1:
            self.awsize = 0
        elif bytes_per_beat == 2:
            self.awsize = 1
        elif bytes_per_beat == 4:
            self.awsize = 2
        else:
            raise RuntimeError("bytes_per_beat must be 1, 2 or 4")

        # allow aligned writes only
        if addr % bytes_per_beat != 0:
            raise RuntimeError("write must be aligned")

        if type(data) == int:
            burst_len = 1
            data = [ data ]
        else:
            burst_len = len(data)

        if awburst == axi.AXI3Burst.WRAP and (not burst_len in (2, 4, 8, 16)):
            raise RuntimeError("burst length for wrapping burst must be 2, 4, 8, or 16 transfers")

        self.data = []
        self.wstrb = []
        addr_i = addr

        dt_size = burst_len * bytes_per_beat
        wrap_boundary = (addr//dt_size) * dt_size
        for i in range(0, burst_len):
            if wstrb == 'auto':
                if bytes_per_beat == 1:
                    wstrb_i = (1 << (addr_i % 4))
                elif bytes_per_beat == 2:
                    wstrb_i = (3 << (addr_i % 4))
                else:
                    wstrb_i = 0xf
            elif wstrb == 0:
                wstrb_i = 0
            else:
                raise RuntimeError("wstrb must be 0 or 'auto'")
            self.wstrb.append(wstrb_i)

            # shift data to provide bytes on the correct byte lanes
            self.data.append(data[i] << 8*(addr_i % 4))

            if awburst == axi.AXI3Burst.INCR:
                addr_i += bytes_per_beat
            elif awburst == axi.AXI3Burst.WRAP:
                addr_i += bytes_per_beat
                if addr_i >= (wrap_boundary+dt_size):
                    addr_i = wrap_boundary

        self.addr = addr
        self.awlen = burst_len-1
        self.awburst = awburst
        self.exp_resp = exp_resp

def axi_write(axi_bus, transact, delay=0, assert_on_error=False, timeout=None):
    """Simulated AXI master performing one or more write transactions.

    axi_bus -- AXI bus (nMigen Record)
    transact -- list of write transactions (TWrite)
    delay -- Delay (in ticks). See below.
    assert_on_error -- assert if incorrent behavior from the slave is detected.
    timeout -- if not None, abort after this number of cycles.

    Note that aborting due to timeout will possibly leave the slave in an
    ongoing transaction. It is then required to perform an AXI reset.
    Otherwise, further AXI transactions afterwards should not be expected to
    work. The function does not report an abort due to timeout, as the
    parameter is currently used only in the AXI reset tests.

    The three AXI channels involved in a write transaction (write address,
    write data, write response) are independent, each with its own flow
    control. No ordering is enforced by the simulated master. The delay by the
    master is controlled by the delay parameter (in clock ticks). It can be a
    single number, a tuple of three numbers (one for each channel) or 'rand',
    in which case a random delay is chosen (independent for each channel and
    each beat in each transaction).
    """
    def get_delay(delay, ty):
        if delay == 'rand':
            return random.randrange(5)
        elif type(delay) == tuple:
            if ty == 'a':
                return delay[0]
            elif ty == 'd':
                return delay[1]
            elif ty == 'b':
                return delay[2]
        else:
            return delay

    addr = []
    aid =  []
    awlen = []
    awsize = []
    awburst = []
    data = []
    wstrb = []
    wlast = []
    exp_resp = []

    addr_i_for_data_i = []
    addr_i = 0

    for t in transact:
        addr.append(t.addr)
        aid.append(random.randrange(2**12))
        awlen.append(t.awlen)
        awsize.append(t.awsize)
        awburst.append(t.awburst)

        exp_resp.append(t.exp_resp)

        for d in t.data:
            data.append(d)
            wlast.append(0)
            addr_i_for_data_i.append(addr_i)
        wlast[-1] = 1

        for s in t.wstrb:
            wstrb.append(s)

        addr_i += 1

    addr_i = 0
    data_i = 0

    a_delay = get_delay(delay, 'a')
    d_delay = get_delay(delay, 'd')
    b_delay = get_delay(delay, 'b')

    cnt = 0
    b_done = 0
    while b_done < len(transact):
        if a_delay == 0 and addr_i < len(addr):
            yield axi_bus.awid.eq(aid[addr_i])
            yield axi_bus.awaddr.eq(addr[addr_i])
            yield axi_bus.awlen.eq(awlen[addr_i])
            yield axi_bus.awsize.eq(awsize[addr_i])
            yield axi_bus.awburst.eq(awburst[addr_i])
            yield axi_bus.awprot.eq(0)
            yield axi_bus.awvalid.eq(1)
        else:
            a_delay -= 1

        if d_delay == 0 and data_i < len(data):
            # The WID signal is obsolete and removed in AXI4.
            # We simply let WID equal AWID.
            yield axi_bus.wid.eq(aid[addr_i_for_data_i[data_i]])
            yield axi_bus.wdata.eq(data[data_i])
            yield axi_bus.wstrb.eq(wstrb[data_i])
            yield axi_bus.wlast.eq(wlast[data_i])
            yield axi_bus.wvalid.eq(1)
        else:
            d_delay -= 1

        if b_delay == 0:
            yield axi_bus.bready.eq(1)
        else:
            b_delay -= 1

        yield Tick()
        cnt += 1

        if timeout != None and cnt >= timeout:
            break

        if (yield axi_bus.awvalid == 1) and (yield axi_bus.awready == 1):
            yield axi_bus.awvalid.eq(0)
            a_delay = get_delay(delay, 'a')
            addr_i += 1

        if (yield axi_bus.wvalid == 1) and (yield axi_bus.wready == 1):
            yield axi_bus.wvalid.eq(0)
            d_delay = get_delay(delay, 'd')
            data_i += 1

        if (yield axi_bus.bvalid == 1) and (yield axi_bus.bready == 1):
            yield axi_bus.bready.eq(0)

            if (yield axi_bus.bid) != aid[b_done]:
                print("Bad response ID: got=%d, exp=%d" % ((yield axi_bus.bid), aid[b_done]))
                assert(not assert_on_error)

            if exp_resp[b_done] != None:
                if (yield axi_bus.bresp) != int(exp_resp[b_done]):
                    print("Bad response: got=%d, exp=%s" % ((yield axi_bus.bresp), repr(exp_resp[b_done])))
                    assert(not assert_on_error)
            b_delay = get_delay(delay, 'b')
            b_done += 1

# AXI read transaction
class TRead:
    """Class representing an AXI read transaction.

    addr -- Source address.
    burst_len -- Number of transfers in the burst, or 'auto' to be determined
        from length of exp_data. Only required if exp_data is not a list.
    bytes_per_beat -- Number of bytes to transfer in each burst.
    arburst -- Burst type (AXI3Burst). See AXI spec.
    exp_resp -- Expected read response. See below.
    exp_data -- Expected data to be returned from read.

    For burst transactions, the slave will return multiple read responses and
    read data. To accommodate this, exp_resp and exp_data can be:
    - None, in which case the response/data is not checked,
    - a single value, in which case that response/data is expected for all
      transfers in the burst,
    - a list, giving the expected responses/data. Items in the list can again
      be None to not check the response/data in that transfer.

    If exp_resp and exp_data are lists, their lengths must match, and must also
    match burst_len if given.
    """
    def __init__(self, addr, burst_len='auto', bytes_per_beat=4, arburst=axi.AXI3Burst.INCR, exp_resp=None, exp_data=None):
        if bytes_per_beat == 1:
            self.arsize = 0
        elif bytes_per_beat == 2:
            self.arsize = 1
        elif bytes_per_beat == 4:
            self.arsize = 2
        else:
            raise RuntimeError("bytes_per_beat must be 1, 2, or 4")

        # allow aligned reads only
        if addr % bytes_per_beat != 0:
            raise RuntimeError("Read must be aligned")

        if burst_len == 'auto':
            if isinstance(exp_data, Iterable):
                burst_len = len(exp_data)
            else:
                burst_len = 1

        if arburst == axi.AXI3Burst.WRAP and (not burst_len in (2, 4, 8, 16)):
            raise RuntimeError("burst length for wrapping burst must be 2, 4, 8, or 16 transfers")

        if not isinstance(exp_data, Iterable):
            exp_data = [ exp_data ] * burst_len

        if not isinstance(exp_resp, Iterable):
            exp_resp = [ exp_resp ] * burst_len

        if len(exp_data) != burst_len:
            raise RuntimeError("Mismatch between burst_len and length of exp_data")

        if len(exp_resp) != len(exp_data):
            raise RuntimeError("Mismatch between length of exp_resp and length of exp_data")

        self.addr = addr
        self.arlen = burst_len-1
        self.arburst = arburst
        self.exp_resp = exp_resp
        self.exp_data = exp_data

def axi_read(axi_bus, transact, delay=0, assert_on_error=False, timeout=None):
    """Simulated AXI master performing one or more read transactions.

    axi_bus -- AXI bus (nMigen Record)
    transact -- list of read transactions (TRead)
    delay -- Delay (in ticks). See below.
    assert_on_error -- assert if incorrent behavior from the slave is detected.
    timeout -- if not None, abort after this number of cycles.

    Note that aborting due to timeout will possibly leave the slave in an
    ongoing transaction. It is then required to perform an AXI reset.
    Otherwise, further AXI transactions afterwards should not be expected to
    work. The function does not report an abort due to timeout, as the
    parameter is currently used only in the AXI reset tests.

    The two AXI channels involved in a read transaction (read address, read
    data) are independent, each with its own flow control. No ordering is
    enforced by the simulated master. The delay by the master is controlled by
    the delay parameter (in clock ticks). It can be a single number, a tuple of
    two numbers (one for each channel) or 'rand', in which case a random delay
    is chosen (independent for each channel and each beat in each transaction).
    """

    def get_delay(delay, ty):
        if delay == 'rand':
            return random.randrange(5)
        elif type(delay) == tuple:
            if ty == 'a':
                return delay[0]
            elif ty == 'r':
                return delay[1]
        else:
            return delay

    addr = []
    aid = []
    arlen = []
    arsize = []
    arburst = []
    addr_i_for_resp_i = []
    exp_resp = []
    exp_data = []
    exp_rlast = []

    addr_i = 0
    for t in transact:
        addr.append(t.addr)
        aid.append(random.randrange(2**12))
        arlen.append(t.arlen)
        arsize.append(t.arsize)
        arburst.append(t.arburst)
        addr_i_for_resp_i += [ addr_i ] * (t.arlen+1)
        exp_resp += t.exp_resp
        exp_data += t.exp_data
        exp_rlast += [ 0 ] * (t.arlen+1)
        exp_rlast[-1] = 1

        addr_i += 1

    cnt = 0
    addr_i = 0
    r_done = 0

    a_delay = get_delay(delay, 'a')
    r_delay = get_delay(delay, 'r')

    while r_done < len(exp_data):
        if a_delay == 0:
            if addr_i < len(addr):
                yield axi_bus.arid.eq(aid[addr_i])
                yield axi_bus.araddr.eq(addr[addr_i])
                yield axi_bus.arlen.eq(arlen[addr_i])
                yield axi_bus.arsize.eq(arsize[addr_i])
                yield axi_bus.arburst.eq(arburst[addr_i])
                yield axi_bus.arprot.eq(0)
                yield axi_bus.arvalid.eq(1)
        else:
            a_delay -= 1

        if r_delay == 0:
            yield axi_bus.rready.eq(1)
        else:
            r_delay -= 1

        yield Tick()
        cnt += 1
        if timeout != None and cnt >= timeout:
            break

        if (yield axi_bus.arvalid == 1) and (yield axi_bus.arready == 1):
            yield axi_bus.arvalid.eq(0)
            a_delay = get_delay(delay, 'a')
            addr_i += 1

        if (yield axi_bus.rvalid == 1) and (yield axi_bus.rready == 1):
            yield axi_bus.rready.eq(0)
            r_delay = get_delay(delay, 'r')

            if (yield axi_bus.rid) != aid[addr_i_for_resp_i[r_done]]:
                print("Bad response ID: got=%d, exp=%d" % ((yield axi_bus.rid), aid[r_done]))
                assert(not assert_on_error)

            if exp_resp[r_done] != None:
                if (yield axi_bus.rresp) != int(exp_resp[r_done]):
                    print("Bad response: got=%d, exp=%s" % ((yield axi_bus.rresp), repr(exp_resp[r_done])))
                    assert(not assert_on_error)

            if exp_data[r_done] != None:
                if (yield axi_bus.rdata) != int(exp_data[r_done]):
                    print("Bad data: got=0x%x, exp=0x%x" % ((yield axi_bus.rdata), exp_data[r_done]))
                    assert(not assert_on_error)

            if (yield axi_bus.rlast) != exp_rlast[r_done]:
                print("Bad rlast: got=%d, exp=%d" % ((yield axi_bus.rlast), exp_rlast[r_done]))
                assert(not assert_on_error)

            r_done += 1
