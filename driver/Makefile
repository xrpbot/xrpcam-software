# SPDX-License-Identifier: GPL-2.0
#
# See https://www.kernel.org/doc/html/latest/kbuild/modules.html for
# information on how to build external modules for Linux.
# The use of the `always` variable to build an external device tree comes from
# http://xillybus.com/tutorials/device-tree-zynq-1

ifneq ($(KERNELRELEASE),)

# produce output from dev_dbg
ccflags-y += -DDEBUG

obj-m += xrp_axi_test.o
always := dts/zynq-zed-xrp.dtb

else
KDIR ?= ../../linux

default:
	make -C $(KDIR) M=$(PWD) modules

clean:
	make -C $(KDIR) M=$(PWD) clean

endif
