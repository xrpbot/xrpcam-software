// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Kernel driver to test AXI on Xilinx Zynq
 *
 * Copyright (C) 2020 Norbert Braun <norbert@xrpbot.org>
 */
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/fs.h>
#include <linux/miscdevice.h>
#include <linux/of.h>
#include <linux/clk.h>
#include <linux/fpga/fpga-mgr.h>
#include <asm/io.h>

#include "xrp_axi_test_api.h"

struct xatest_device {
    struct miscdevice miscdev;
    struct device *dev;
    void __iomem *regs;
    struct clk *clk;
};

static u32 xatest_read(struct xatest_device *xadev, u32 reg)
{
    if(reg < XATEST_N_REGS) {
        return ioread32((u32 __iomem *) xadev->regs + reg);
    } else {
        dev_warn(xadev->dev, "read from illegal location ignored");
        return 0;
    }
}

static void xatest_write(struct xatest_device *xadev, u32 reg, u32 val)
{
    if(reg < XATEST_N_REGS) {
        iowrite32(val, (u32 __iomem *) xadev->regs + reg);
    } else {
        dev_warn(xadev->dev, "write to illegal location ignored");
    }
}

static void xatest_read_all(struct xatest_device *xadev, u32* vals)
{
    memcpy_fromio(vals, xadev->regs, XATEST_N_REGS*4);
}

static void xatest_write_all(struct xatest_device *xadev, const u32* vals)
{
    memcpy_toio(xadev->regs, vals, XATEST_N_REGS*4);
}

static void xatest_clear_all(struct xatest_device *xadev)
{
    memset_io(xadev->regs, 0, XATEST_N_REGS*4);
}

/* Test reads and writes smaller than 32 bits */
static int xatest_test_small(struct xatest_device *xadev)
{
    u32 val;

    iowrite32(0x11223344, (u8 __iomem *) xadev->regs);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x11223344) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x11223344);
        return -1;
    }

    iowrite16(0xabcd, (u8 __iomem *)xadev->regs + 1);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x11abcd44) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x11abcd44);
        return -1;
    }

    iowrite8(0x55, (u8 __iomem *) xadev->regs + 3);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x55abcd44) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x55abcd44);
        return -1;
    }

    iowrite8(0x66, (u8 __iomem *) xadev->regs + 2);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x5566cd44) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x5566cd44);
        return -1;
    }

    iowrite8(0x77, (u8 __iomem *) xadev->regs + 1);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x55667744) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x55667744);
        return -1;
    }

    iowrite8(0x88, (u8 __iomem *) xadev->regs);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x55667788) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x55667788);
        return -1;
    }

    val = ioread16((u8 __iomem *) xadev->regs);
    if(val != 0x7788) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x7788);
        return -1;
    }

    val = ioread8((u8 __iomem *) xadev->regs + 1);
    if(val != 0x77) {
        dev_warn(xadev->dev, "TEST FAILED (small, read=0x%x, exp=0x%x)", val, 0x77);
        return -1;
    }

    return 0;
}

/* Test unaligned reads and writes */
static int xatest_test_unaligned(struct xatest_device *xadev)
{
    u32 val;

    iowrite32(0x44332211, (u8 __iomem *) xadev->regs);
    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0x44332211) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0x44332211);
        return -1;
    }

    iowrite32(0x88776655, (u8 __iomem *) xadev->regs + 4);
    val = ioread32((u8 __iomem *) xadev->regs + 4);
    if(val != 0x88776655) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0x88776655);
        return -1;
    }

    val = ioread32((u8 __iomem *) xadev->regs + 2);
    if(val != 0x66554433) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0x66554433);
        return -1;
    }

    iowrite32(0xaabbccdd, (u8 __iomem *) xadev->regs + 2);

    val = ioread32((u8 __iomem *) xadev->regs);
    if(val != 0xccdd2211) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0xccdd2211);
        return -1;
    }

    val = ioread32((u8 __iomem *) xadev->regs + 4);
    if(val != 0x8877aabb) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0x8877aabb);
        return -1;
    }

    val = ioread32((u8 __iomem *) xadev->regs + 2);
    if(val != 0xaabbccdd) {
        dev_warn(xadev->dev, "TEST FAILED (unaligned, read=0x%x, exp=0x%x)", val, 0xaabbccdd);
        return -1;
    }

    return 0;
}

/* Perform illegal read */
static void xatest_ill_read(struct xatest_device *xadev)
{
    dev_warn(xadev->dev, "about to perform illegal read");
    ioread32((u8 __iomem *) xadev->regs + 0x100);
}

/* Perform illegal write */
static void xatest_ill_write(struct xatest_device *xadev)
{
    dev_warn(xadev->dev, "about to perform illegal write");
    iowrite32(0, (u8 __iomem *) xadev->regs + 0x100);
}

static long xatest_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct xatest_read_arg xa_read_arg;
    struct xatest_write_arg xa_write_arg;
    struct xatest_read_all_arg xa_read_all_arg;
    struct xatest_write_all_arg xa_write_all_arg;
    struct xatest_test_result xa_test_result;
    u32 val;

    struct xatest_device *xadev = container_of(file->private_data, struct xatest_device, miscdev);

    if(_IOC_DIR(cmd) != _IOC_NONE && !access_ok((void __user *)arg, _IOC_SIZE(cmd)))
        return -EFAULT;

    switch(cmd) {
        case XAIOC_READ:
            if(copy_from_user(&xa_read_arg, (void __user *)arg, sizeof(struct xatest_read_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "read: reg=%d", xa_read_arg.reg);
            val = xatest_read(xadev, xa_read_arg.reg);
            dev_dbg(xadev->dev, "read: val=0x%x", val);
            xa_read_arg.val = val;
            if(copy_to_user((void __user*) arg, &xa_read_arg, sizeof(struct xatest_read_arg)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_WRITE:
            if(copy_from_user(&xa_write_arg, (void __user *)arg, sizeof(struct xatest_write_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "write: reg=%d, val=0x%x", xa_write_arg.reg, xa_write_arg.val);
            xatest_write(xadev, xa_write_arg.reg, xa_write_arg.val);
            return 0;

        case XAIOC_READ_ALL:
            if(copy_from_user(&xa_read_all_arg, (void __user *)arg, sizeof(struct xatest_read_all_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "read_all");
            xatest_read_all(xadev, xa_read_all_arg.vals);
            if(copy_to_user((void __user*) arg, &xa_read_all_arg, sizeof(struct xatest_read_all_arg)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_WRITE_ALL:
            if(copy_from_user(&xa_write_all_arg, (void __user *)arg, sizeof(struct xatest_write_all_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "write_all");
            xatest_write_all(xadev, xa_write_all_arg.vals);
            return 0;

        case XAIOC_CLEAR_ALL:
            dev_dbg(xadev->dev, "clear_all");
            xatest_clear_all(xadev);
            return 0;

        case XAIOC_TEST_SMALL:
            dev_dbg(xadev->dev, "test_small");
            xa_test_result.result = xatest_test_small(xadev);
            if(copy_to_user((void __user*) arg, &xa_test_result, sizeof(struct xatest_test_result)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_TEST_UNALIGNED:
            dev_dbg(xadev->dev, "test_unaligned");
            xa_test_result.result = xatest_test_unaligned(xadev);
            if(copy_to_user((void __user*) arg, &xa_test_result, sizeof(struct xatest_test_result)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_TEST_ILL_READ:
            xatest_ill_read(xadev);
            return 0;

        case XAIOC_TEST_ILL_WRITE:
            xatest_ill_write(xadev);
            return 0;

        default:
            return -ENOTTY;
    }
}

static const struct file_operations xatest_fops = {
    .owner = THIS_MODULE,
    .unlocked_ioctl = xatest_ioctl,
    .compat_ioctl = compat_ptr_ioctl
};

static struct xatest_device xatest_dev = {
    .miscdev = {
        .minor = MISC_DYNAMIC_MINOR,
        .name = "xrp_axi_test",
        .fops = &xatest_fops
    }
};

static int __init fpga_init(struct device *dev)
{
    struct device_node *dt_fpga_region, *dt_fpga_mgr;
    struct fpga_manager *fpga_mgr;
    struct fpga_image_info *img_info;
    int ret = 0;

    dt_fpga_region = of_find_compatible_node(NULL, NULL, "fpga-region");
    if(!dt_fpga_region) {
        dev_err(dev, "FPGA region not found\n");
        return -ENODEV;
    }

    dt_fpga_mgr = of_parse_phandle(dt_fpga_region, "fpga-mgr", 0);
    of_node_put(dt_fpga_region);
    if(!dt_fpga_mgr) {
        dev_err(dev, "FPGA manager not found\n");
        return -ENODEV;
    }

    fpga_mgr = of_fpga_mgr_get(dt_fpga_mgr);
    of_node_put(dt_fpga_mgr);
    if(IS_ERR(fpga_mgr)) {
        dev_err(dev, "failed to get FPGA manager");
        return PTR_ERR(fpga_mgr);
    }

    img_info = fpga_image_info_alloc(dev);
    if(!img_info) {
        ret = -ENOMEM;
        goto out;
    }
    img_info->firmware_name = devm_kstrdup(dev, "zynq_pl_image.bin", GFP_KERNEL);
    if(!img_info->firmware_name) {
        ret = -ENOMEM;
        goto out;
    }

    ret = fpga_mgr_lock(fpga_mgr);
    if(ret != 0) {
        goto out;
    }

    ret = fpga_mgr_load(fpga_mgr, img_info);

    fpga_mgr_unlock(fpga_mgr);

out:
    fpga_mgr_put(fpga_mgr);

    fpga_image_info_free(img_info);

    return ret;
}

static int __init xatest_probe(struct platform_device *pdev)
{
    int ret;
    struct resource *res;
    struct clk *clk;

    /* only one device is supported */
    if(xatest_dev.dev)
        return -EBUSY;

    xatest_dev.dev = &pdev->dev;
    xatest_dev.miscdev.parent = &pdev->dev;

    ret = fpga_init(&pdev->dev);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to init FPGA");
        return ret;
    }

    res = platform_get_resource(pdev, IORESOURCE_MEM, 0);
    xatest_dev.regs = devm_ioremap_resource(&pdev->dev, res);
    if(IS_ERR(xatest_dev.regs))
        return PTR_ERR(xatest_dev.regs);

    clk = devm_clk_get(&pdev->dev, NULL);
    if(IS_ERR(clk)) {
        dev_err(&pdev->dev, "failed to get clock");
        return PTR_ERR(clk);
    }

    ret = clk_set_rate(clk, 100000000);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to set clock rate");
        return ret;
    }

    ret = clk_prepare_enable(clk);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to enable clock");
        return ret;
    }
    xatest_dev.clk = clk;

    dev_info(&pdev->dev, "fclk0 set to %ld Hz", clk_get_rate(clk));

    ret = misc_register(&xatest_dev.miscdev);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to register misc device");
        goto out;
    }

    dev_info(&pdev->dev, "initialized");

    return 0;

out:
    clk_disable_unprepare(clk);

    return ret;
}

static int xatest_remove(struct platform_device *pdev)
{
    misc_deregister(&xatest_dev.miscdev);
    clk_disable_unprepare(xatest_dev.clk);
    xatest_dev.dev = NULL;
    xatest_dev.miscdev.parent = NULL;
    dev_info(&pdev->dev, "cleanup done");

    return 0;
}

static const struct of_device_id xrp_axi_test_dt_ids[] = {
    { .compatible = "xrp,axi-test" },
    { }
};
MODULE_DEVICE_TABLE(of, xrp_axi_test_dt_ids);

static struct platform_driver xrp_axi_test_driver = {
    .driver = {
        .name = "xrp_axi_test",
        .of_match_table = xrp_axi_test_dt_ids
    },
    .remove = xatest_remove
};
module_platform_driver_probe(xrp_axi_test_driver, xatest_probe);

MODULE_AUTHOR("Norbert Braun <norbert@xrpbot.org>");
MODULE_DESCRIPTION("AXI test for Zynq");
MODULE_LICENSE("GPL");
