xrpcam-software
===============

This repository will eventually contain gateware/firmware/software for the
XRPCam project. Right now, it mainly contains preliminary experiments.


Introduction
------------

XRPCam will use a Xilinx Zynq SoC as the main processor/FPGA. The Zynq family
of SoCs are a combination of a Linux-capable ARM processor and an FPGA on a
single chip. The processor (termed PS) and the FPGA logic (termed PL) are
tightly coupled, allowing for high-speed data transfer.  Data transfer happens
primarily by means of the ARM AXI bus.

While XRPCam will eventuall be based on a custom PCB, development currently
happens on an [Avnet Zedboard](http://zedboard.org/product/zedboard).

The gateware is written in [nMigen](https://github.com/nmigen/nmigen), a
modern, Python-based hardware description language.


Zynq details
------------

Xilinx maintains forked versions of U-Boot and the Linux kernel for the Zynq,
but enough of their changes have been upstreamed that mainline U-Boot/Linux
works quite well. We use a recent mainline kernel (Linux 5.7.0) in this project.

Mainline Linux is able to load bitstreams into the PL (through the [FPGA
Manager](https://www.kernel.org/doc/html/latest/driver-api/fpga/fpga-mgr.html)
framework), but does not seem to expose that functionality to userspace (unlike
the Xilinx kernels, which offered the (now deprecated) xdevcfg mechanism and
later a sysfs-based interface to control the FPGA manager). This is
intentional - as the gateware in the PL might be used by some kernel driver,
userspace should not be allowed to suddenly make that gateware disappear.
Device Tree Overlays should eventually offer a clean solution, but are not
(completely?) available in mainline yet. For this reason, our kernel driver is
responsible for loading our gateware into the PL before communicating with it.
By putting the driver into a kernel module, it becomes possible to try out new
bitstreams without rebooting (because the bitstream is reloaded every time the
module is initialized).

The PS provides 4 clocks to the PL. These clocks have to be configured from the
PS, through the Linux [Clock
Framework](https://www.kernel.org/doc/html/latest/core-api/kernel-api.html#clock-framework).
This is also handled by our driver. The Zedboard additionally attaches an
external 100 MHz oscillator directly to the PL, but later Zynq devboards (such
as the Microzed) do not do that any longer. We do not use that clock input in
our gateware.


AXI test
--------

The AXI test gateware provides 8 memory-mapped 32 bit registers. The first 7 of
them can be read and written. The last register is read-only, writes are
silently ignored. The 4 least-significant bits of the first register are output
to ZedBoard LEDs.

The kernel driver accesses the registers by various methods
(`ioread32`/`iowrite32`, `memcpy_fromio`/`memcpy_toio`, `memset_io`). A simple
userspace program, `axi_test`, communicates with the kernel driver and allows
to read/write registers (via the various methods) from the command line.

AXI is a burst-based protocol, meaning that every transaction may have multiple
data transfers (called "beats"). In practice, `memcpy_*` and `memset_io` seem
to cause this to happen (at least on my setup). This means that AXI components
must be prepared to handle it.

There is a variant called "AXI-Lite" where all transactions consist of a single
data transfer, but this is not provided directly by the Zynq hardware. Thus, a
(soft) AXI-to-AXI-Lite bridge would have to be implemented in the PL to use it.

The gateware provides some debug counters (number of transactions on the five
AXI channels) that can be read through GPIOs between PS and PL. The userspace
program `axi_stat` is provided to read them.

In addition, there are some further tests:

* **Small access:** Reads and writes parts of registers (via `iowrite8` etc.).
This mostly requires the gateware to handle the `WSTRB` signal correctly.

* **Unaligned access:** These seem to get split into two small accesses, so the
gateware does not have to specially handle them.

* **Illegal read:** The gateware returns a `DECERR` response if a read from
outside the register space is attempted. This causes an "Unhandled fault:
imprecise external abort" in the kernel. The userspace program is terminated
with a segmentation fault.

* **Illegal write:** The gateware returns a `DECERR` response if a write to
outside the register space is attempted. However, this seems to be ignored
(???).


### Simulating/building the gateware

This assumes you have nMigen and the vendor toolchain (Xilinx Vivado) installed.

    cd gateware

To run a simple simulation-based test suite:

    cd tests
    ./test_axi.py
    cd ..

To synthesize a bitstream:

    ./synth.py

If the synthesis succeeds, the bitstream is at `build/top.bin`. Copy this file
to `/lib/firmware/zynq_pl_image.bin` on the target system.


### Building the kernel module

You will need the source for the kernel running on the target system (i.e. the
Zedboard) to build the kernel module (see "Cross-compiling the Linux kernel",
below).

    export CROSS_COMPILE=arm-linux-gnueabihf-
    export ARCH=arm
    cd driver
    make KDIR=../../linux

Set `KDIR` to the actual location of the kernel source.

Copy the file `xrp_axi_test.ko` to the target system. Copy the generated device
tree `dts/zynq-zed-xrp.dtb` to the boot partition of the target system.


### Building the userspace programs

    export CROSS_COMPILE=arm-linux-gnueabihf-
    cd user
    make KDIR=../../linux

As above, set `KDIR` to the actual location of the kernel source.

Copy the files `axi_test` and `axi_stat` to the target system.


Setting up the environment
--------------------------

### Cross-compiling the Linux kernel

Clone the repository (only needed once):

    git clone -b v5.7 --depth 1 https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git

The `--depth 1` option will not download the entire git history, saving network
traffic in case you do not need it.

Copy the supplied configuration:

    cp xrpcam-software/files/linux/zedboard_xrp_defconfig linux/arch/arm/configs

This configuration is probably not optimal, and can be tweaked further. I tried
to include all config options required by systemd (see
https://github.com/systemd/systemd/blob/master/README).

Configure and build the kernel:

    cd linux
    export CROSS_COMPILE=arm-linux-gnueabihf-
    export ARCH=arm
    make zedboard_xrp_defconfig
    make -j4

The `-j4` option runs multiple processes in parallel. The number may need to be
adjusted depending on your machine.

Copy the file `arch/arm/boot/zImage` to the boot partition of the SD card. Note
that U-Boot supports booting from a zImage (via the `bootz` command), so
generating a uImage should not be required. You will also need a device tree
(`zynq-zed-xrp.dtb`), which is built as part of the driver (see above).

Collect the kernel modules:

    make modules_install INSTALL_MOD_PATH=modules

Copy the content of `modules/lib/modules` (should be a single directory named
`5.7.0`) to `/lib/modules` on the target system.

Prepare the kernel headers:

    make headers_install

This will install the kernel headers to `./usr`.


### Userland for Zynq

In principle, almost any userland can be used. However, I find it helpful to
have a full Linux system (as opposed to something based on BusyBox) for
development. Therefore, I use [Arch Linux ARM](https://archlinuxarm.org/),
which is [available for the
Zedboard](https://archlinuxarm.org/platforms/armv7/xilinx/zedboard).

One thing to note about Arch Linux ARM for Zedboard is that an entry for the
root partition `/dev/mmcblk0p2` is missing from `/etc/fstab`, causing weird
errors if the `rw` option happens to be missing from the kernel command line
(because the root partition will then remain mounted read-only).


Notes (unsorted)
----------------

### MAC address

Unfortunately, the Zynq does not have a MAC address for the Ethernet
controllers burned into the hardware. Xilinx-supplied images seem to use the
fixed MAC `00:0a:35:00:01:22`. While re-using the same MAC address on multiple
physical devices is very much not allowed by the standard (AFAIK), it should
not cause problems unless you have multiple of these Zynq devboards in your
network (in which case it will cause severe problems).

The MAC address of the ethernet interface is controlled by the U-Boot
environment variable `ethaddr`. It that is not set, U-Boot will set a random MAC
address that changes on every boot.

### RTC

The Zedboard does not have an RTC, so the current time will not be available on
startup. If the Zedboard is not connected to the Internet, NTP cannot be used
either, so timestamps of created files and in logs will be incorrect.

### JTAG

The Zedboard contains an FTDI-based interface to JTAG on the Zynq. There is
some support in [OpenOCD](http://openocd.org/):

    openocd -f board/digilent_zedboard.cfg

This is mainly useful for debugging software on the PS. Loading bitstreams into
the PL is handled by Linux on the PS.

### U-Boot

Normally, it should be ok to use the U-Boot supplied by whatever environment
you decided to use (e.g. Arch Linux). There are some [notes on
U-Boot](doc/u-boot.md) available.


Resources
---------

* [AMBA® AXI™ and ACE™ Protocol Specification](https://static.docs.arm.com/ihi0022/e/IHI0022E_amba_axi_and_ace_protocol_spec.pdf)
* [Advanced eXtensible Interface on Wikipedia](https://en.wikipedia.org/wiki/Advanced_eXtensible_Interface)
* [Zynq-7000 SoC Technical Reference manual](https://www.xilinx.com/support/documentation/user_guides/ug585-Zynq-7000-TRM.pdf)
* [nMigen documentation](https://nmigen.info/nmigen/latest/)
* [nMigen tutorial by Robert Baruch](https://github.com/robertbaruch/nmigen-tutorial)
* The [ZipCPU](https://zipcpu.com/) blog has lots of discussion about AXI components (and how to formally verify them).
