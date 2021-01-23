from nmigen import *
import axi

class PS7(Elaboratable):
    def __init__(self):
        self.fclk = Signal(4)
        self.m_axi_gp0 = axi.AXI3Bus()
        self.emiogpio_i = Signal(64)
        self.emiogpio_o = Signal(64)
        self.emiogpio_tn = Signal(64)

    def elaborate(self, platform):
        m = Module()

        # NOTE: PS7 cell is required!
        m.submodules += Instance("PS7",
            # FLCK
            o_FCLKCLK = self.fclk,

            # EMIO GPIOs
            i_EMIOGPIOI=self.emiogpio_i,
            o_EMIOGPIOO=self.emiogpio_o,
            o_EMIOGPIOTN=self.emiogpio_tn,

            # M_AXI_GP0
            i_MAXIGP0ACLK    = self.m_axi_gp0.aclk,
            o_MAXIGP0ARESETN = self.m_axi_gp0.areset_n,

            o_MAXIGP0AWID    = self.m_axi_gp0.awid,
            o_MAXIGP0AWADDR  = self.m_axi_gp0.awaddr,
            o_MAXIGP0AWLEN   = self.m_axi_gp0.awlen,
            o_MAXIGP0AWSIZE  = self.m_axi_gp0.awsize,
            o_MAXIGP0AWBURST = self.m_axi_gp0.awburst,
            o_MAXIGP0AWLOCK  = self.m_axi_gp0.awlock,
            o_MAXIGP0AWCACHE = self.m_axi_gp0.awcache,
            o_MAXIGP0AWPROT  = self.m_axi_gp0.awprot,
            o_MAXIGP0AWQOS   = self.m_axi_gp0.awqos,
            o_MAXIGP0AWVALID = self.m_axi_gp0.awvalid,
            i_MAXIGP0AWREADY = self.m_axi_gp0.awready,

            o_MAXIGP0ARID    = self.m_axi_gp0.arid,
            o_MAXIGP0ARADDR  = self.m_axi_gp0.araddr,
            o_MAXIGP0ARLEN   = self.m_axi_gp0.arlen,
            o_MAXIGP0ARSIZE  = self.m_axi_gp0.arsize,
            o_MAXIGP0ARBURST = self.m_axi_gp0.arburst,
            o_MAXIGP0ARLOCK  = self.m_axi_gp0.arlock,
            o_MAXIGP0ARCACHE = self.m_axi_gp0.arcache,
            o_MAXIGP0ARPROT  = self.m_axi_gp0.arprot,
            o_MAXIGP0ARQOS   = self.m_axi_gp0.arqos,
            o_MAXIGP0ARVALID = self.m_axi_gp0.arvalid,
            i_MAXIGP0ARREADY = self.m_axi_gp0.arready,

            o_MAXIGP0WID     = self.m_axi_gp0.wid,
            o_MAXIGP0WDATA   = self.m_axi_gp0.wdata,
            o_MAXIGP0WSTRB   = self.m_axi_gp0.wstrb,
            o_MAXIGP0WLAST   = self.m_axi_gp0.wlast,
            o_MAXIGP0WVALID  = self.m_axi_gp0.wvalid,
            i_MAXIGP0WREADY  = self.m_axi_gp0.wready,

            i_MAXIGP0RID     = self.m_axi_gp0.rid,
            i_MAXIGP0RDATA   = self.m_axi_gp0.rdata,
            i_MAXIGP0RRESP   = self.m_axi_gp0.rresp,
            i_MAXIGP0RLAST   = self.m_axi_gp0.rlast,
            i_MAXIGP0RVALID  = self.m_axi_gp0.rvalid,
            o_MAXIGP0RREADY  = self.m_axi_gp0.rready,

            i_MAXIGP0BID     = self.m_axi_gp0.bid,
            i_MAXIGP0BRESP   = self.m_axi_gp0.bresp,
            i_MAXIGP0BVALID  = self.m_axi_gp0.bvalid,
            o_MAXIGP0BREADY  = self.m_axi_gp0.bready)

        return m
