from nmigen.build import *
from nmigen.vendor.xilinx_7series import *
from nmigen_boards.resources.user import *

__all__ = [ "ZedboardPlatform" ]

class ZedboardPlatform(Xilinx7SeriesPlatform):
    device = "xc7z020"
    package = "clg484"
    speed = 1

    resources = [
        Resource("gclk", 0, Pins("Y9", dir="i"), Attrs(IOSTANDARD="LVCMOS33"), Clock(100e6)),
        *LEDResources(pins="T22 T21 U22 U21 V22 W22 U19 U14", attrs=Attrs(IOSTANDARD="LVCMOS33"))
    ]
    connectors = []

    def toolchain_prepare(self, fragment, name, **kwargs):
        # The Zynq driver in the FPGA Manager framework on mainline Linux
        # expects bitstreams that are byte swapped with respect to what the
        # Vivado command `write_bitstream -bin_file` produces. Thus, use the
        # `write_cfgmem` command with appropriate options to generate the
        # bitstream (.bin file).
        overrides = {
            "script_after_bitstream":
                "write_cfgmem -force -format bin -interface smapx32 -disablebitswap "
                "-loadbit \"up 0 {name}.bit\" {name}.bin".format(name=name)
        }

        return super().toolchain_prepare(fragment, name, **overrides, **kwargs)
