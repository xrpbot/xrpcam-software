from nmigen import *
import axi

class PS7(Elaboratable):
    def __init__(self):
        self.fclk = Signal(4)
        self.m_axi_gp0 = axi.AXI3Bus()
        self.s_axi_hp0 = axi.AXI3Bus(id_bits=6, data_bits=64)
        self.irqf2p = Signal(16)
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

            # IRQF2P
            i_IRQF2P = self.irqf2p,

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
            o_MAXIGP0BREADY  = self.m_axi_gp0.bready,

            # S_AXI_HP0
            i_SAXIHP0ACLK    = self.s_axi_hp0.aclk,
            o_SAXIHP0ARESETN = self.s_axi_hp0.areset_n,

            i_SAXIHP0AWID    = self.s_axi_hp0.awid,
            i_SAXIHP0AWADDR  = self.s_axi_hp0.awaddr,
            i_SAXIHP0AWLEN   = self.s_axi_hp0.awlen,
            i_SAXIHP0AWSIZE  = self.s_axi_hp0.awsize,
            i_SAXIHP0AWBURST = self.s_axi_hp0.awburst,
            i_SAXIHP0AWLOCK  = self.s_axi_hp0.awlock,
            i_SAXIHP0AWCACHE = self.s_axi_hp0.awcache,
            i_SAXIHP0AWPROT  = self.s_axi_hp0.awprot,
            i_SAXIHP0AWQOS   = self.s_axi_hp0.awqos,
            i_SAXIHP0AWVALID = self.s_axi_hp0.awvalid,
            o_SAXIHP0AWREADY = self.s_axi_hp0.awready,

            i_SAXIHP0ARID    = self.s_axi_hp0.arid,
            i_SAXIHP0ARADDR  = self.s_axi_hp0.araddr,
            i_SAXIHP0ARLEN   = self.s_axi_hp0.arlen,
            i_SAXIHP0ARSIZE  = self.s_axi_hp0.arsize,
            i_SAXIHP0ARBURST = self.s_axi_hp0.arburst,
            i_SAXIHP0ARLOCK  = self.s_axi_hp0.arlock,
            i_SAXIHP0ARCACHE = self.s_axi_hp0.arcache,
            i_SAXIHP0ARPROT  = self.s_axi_hp0.arprot,
            i_SAXIHP0ARQOS   = self.s_axi_hp0.arqos,
            i_SAXIHP0ARVALID = self.s_axi_hp0.arvalid,
            o_SAXIHP0ARREADY = self.s_axi_hp0.arready,

            i_SAXIHP0WID     = self.s_axi_hp0.wid,
            i_SAXIHP0WDATA   = self.s_axi_hp0.wdata,
            i_SAXIHP0WSTRB   = self.s_axi_hp0.wstrb,
            i_SAXIHP0WLAST   = self.s_axi_hp0.wlast,
            i_SAXIHP0WVALID  = self.s_axi_hp0.wvalid,
            o_SAXIHP0WREADY  = self.s_axi_hp0.wready,

            o_SAXIHP0RID     = self.s_axi_hp0.rid,
            o_SAXIHP0RDATA   = self.s_axi_hp0.rdata,
            o_SAXIHP0RRESP   = self.s_axi_hp0.rresp,
            o_SAXIHP0RLAST   = self.s_axi_hp0.rlast,
            o_SAXIHP0RVALID  = self.s_axi_hp0.rvalid,
            i_SAXIHP0RREADY  = self.s_axi_hp0.rready,

            o_SAXIHP0BID     = self.s_axi_hp0.bid,
            o_SAXIHP0BRESP   = self.s_axi_hp0.bresp,
            o_SAXIHP0BVALID  = self.s_axi_hp0.bvalid,
            i_SAXIHP0BREADY  = self.s_axi_hp0.bready
        )

        return m
