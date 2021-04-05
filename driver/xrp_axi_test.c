// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Kernel driver to test AXI on Xilinx Zynq
 *
 * Copyright (C) 2020-2021 Norbert Braun <norbert@xrpbot.org>
 */
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/device.h>
#include <linux/circ_buf.h>
#include <linux/fs.h>
#include <linux/poll.h>
#include <linux/miscdevice.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/clk.h>
#include <linux/interrupt.h>
#include <linux/dma-mapping.h>
#include <linux/build_bug.h>
#include <linux/fpga/fpga-mgr.h>
#include <asm/io.h>

#include "xrp_axi_test_api.h"

#define XRP_SW_STATE_REG   0x20

#define XRP_TIMER_REG      0x24

/* Interrupt test */
#define XRP_INT_ENABLE_REG 0x28
#define XRP_INT_ENABLE_REG__INT_ENABLE   0x1

#define XRP_INT_STATUS_REG 0x2C
#define XRP_INT_STATUS_REG__INT_OVERFLOW 0x0100
#define XRP_INT_STATUS_REG__INT_PENDING  0x0001

#define XRP_INT_COUNT_REG  0x30

/* Test data source */
#define XRP_DS_DATA_REG    0x34

#define XRP_DS_COUNT_REG   0x38

#define XRP_DS_STATUS_REG  0x3C
#define XRP_DS_STATUS_REG__BUSY 0x1

#define XRP_DS_CONTROL_REG 0x40
#define XRP_DS_CONTROL_REG__START 0x1

/* AXI bus counters */
#define XRP_MEM_AW_COUNT_REG 0x44

#define XRP_MEM_W_COUNT_REG  0x48

#define XRP_MEM_B_COUNT_REG  0x4C

/* AXI writer */
#define XRP_DMA_ADDR_REG   0x50

#define XRP_DMA_COUNT_REG  0x54

#define XRP_DMA_STATUS_REG 0x58
#define XRP_DMA_STATUS_REG__BUSY  0x0001
#define XRP_DMA_STATUS_REG__ERROR 0x0100
#define XRP_DMA_STATUS_REG__ERROR_RESP_MASK 0x0600
#define XRP_DMA_STATUS_REG__ERROR_RESP_SHIFT 9

#define XRP_DMA_CONTROL_REG 0x5C
#define XRP_DMA_CONTROL_REG__START 0x1

#define XRP_DMA_CONFIG_REG 0x60
#define XRP_DMA_CONFIG_REG__INT_ENABLE 0x1

#define XRP_DMA_INT_STATUS_REG 0x64
#define XRP_DMA_INT_STATUS_REG__INT_PENDING 0x1


#define DMA_BUFFER_SIZE (4*1024*1024)

static DEFINE_MUTEX(dma_test_mutex);

struct xatest_device {
    struct miscdevice miscdev;
    struct device *dev;
    void __iomem *regs;
    struct clk *clk;
};

static u32 xatest_reg_read(struct xatest_device *xadev, u32 reg)
{
    if(reg < XATEST_N_REGS) {
        return ioread32((u32 __iomem *) xadev->regs + reg);
    } else {
        dev_warn(xadev->dev, "read from illegal location ignored");
        return 0;
    }
}

static void xatest_reg_write(struct xatest_device *xadev, u32 reg, u32 val)
{
    if(reg < XATEST_N_REGS) {
        iowrite32(val, (u32 __iomem *) xadev->regs + reg);
    } else {
        dev_warn(xadev->dev, "write to illegal location ignored");
    }
}

static void xatest_reg_read_all(struct xatest_device *xadev, u32* vals)
{
    memcpy_fromio(vals, xadev->regs, XATEST_N_REGS*4);
}

static void xatest_reg_write_all(struct xatest_device *xadev, const u32* vals)
{
    memcpy_toio(xadev->regs, vals, XATEST_N_REGS*4);
}

static void xatest_reg_clear_all(struct xatest_device *xadev)
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
static void xatest_ill_reg_read(struct xatest_device *xadev)
{
    dev_warn(xadev->dev, "about to perform illegal read");
    ioread32((u8 __iomem *) xadev->regs + 0x100);
}

/* Perform illegal write */
static void xatest_ill_reg_write(struct xatest_device *xadev)
{
    dev_warn(xadev->dev, "about to perform illegal write");
    iowrite32(0, (u8 __iomem *) xadev->regs + 0x100);
}

/* Inspect hardware registers from userspace (intended for debugging only) */
static int xatest_sr_read(struct xatest_device *xadev, u32 reg, u32 *val)
{
    switch(reg) {
        case XASR_SW_STATE:
            *val = ioread32(xadev->regs + XRP_SW_STATE_REG);
            return 0;
        case XASR_TIMER:
            *val = ioread32(xadev->regs + XRP_TIMER_REG);
            return 0;
        case XASR_INT_STATUS:
            *val = ioread32(xadev->regs + XRP_INT_STATUS_REG);
            return 0;
        case XASR_INT_COUNT:
            *val = ioread32(xadev->regs + XRP_INT_COUNT_REG);
            return 0;
        case XASR_MEM_AW_COUNT:
            *val = ioread32(xadev->regs + XRP_MEM_AW_COUNT_REG);
            return 0;
        case XASR_MEM_W_COUNT:
            *val = ioread32(xadev->regs + XRP_MEM_W_COUNT_REG);
            return 0;
        case XASR_MEM_B_COUNT:
            *val = ioread32(xadev->regs + XRP_MEM_B_COUNT_REG);
            return 0;
        default:
            dev_warn(xadev->dev, "attempted to read unknown special register");
            return -EINVAL;
    }
}

static void xatest_enable_interrupt(struct xatest_device *xadev)
{
    iowrite32(XRP_INT_ENABLE_REG__INT_ENABLE, xadev->regs + XRP_INT_ENABLE_REG);
}

static void xatest_disable_interrupt(struct xatest_device *xadev)
{
    iowrite32(0, xadev->regs + XRP_INT_ENABLE_REG);
}

static DECLARE_WAIT_QUEUE_HEAD(dma_event_queue);

static int xatest_test_dma(struct xatest_device *xadev)
{
    DEFINE_WAIT(wait);
    u32 *dma_buf;
    dma_addr_t dma_addr;
    u32 data = 0xf000baaa;
    size_t i;
    int ret;

    BUILD_BUG_ON_MSG((DMA_BUFFER_SIZE % 8) != 0, "DMA buffer size must be an integer multiple of 8 bytes");
    BUILD_BUG_ON_MSG((DMA_BUFFER_SIZE / 8) <= 0, "DMA buffer size must not be zero");

    if(mutex_lock_interruptible(&dma_test_mutex) != 0)
        return -EALREADY;

    dma_buf = devm_kmalloc(xadev->dev, DMA_BUFFER_SIZE, GFP_DMA32);
    if(!dma_buf) {
        dev_err(xadev->dev, "failed to allocate buffer");
        mutex_unlock(&dma_test_mutex);
        return -ENOMEM;
    }

    dev_info(xadev->dev, "allocated buffer at physical address 0x%x", __pa(dma_buf));

    dma_addr = dma_map_single(xadev->dev, dma_buf, DMA_BUFFER_SIZE, DMA_FROM_DEVICE);
    if(dma_mapping_error(xadev->dev, dma_addr)) {
        dev_err(xadev->dev, "failed to map buffer");
        mutex_unlock(&dma_test_mutex);
        return -EINVAL;
    }

    dev_info(xadev->dev, "buffer mapped, dma_addr=0x%x", dma_addr);

    if(dma_addr & 0x7) {
        dev_err(xadev->dev, "DMA buffer is not 64-bit aligned");
        dma_unmap_single(xadev->dev, dma_addr, DMA_BUFFER_SIZE, DMA_FROM_DEVICE);
        mutex_unlock(&dma_test_mutex);
        return -EINVAL;
    }

    /* configure test data source */
    iowrite32(data, xadev->regs + XRP_DS_DATA_REG);
    iowrite32(DMA_BUFFER_SIZE/8 - 1, xadev->regs + XRP_DS_COUNT_REG);
    iowrite32(XRP_DS_CONTROL_REG__START, xadev->regs + XRP_DS_CONTROL_REG);

    /* configure DMA engine */
    iowrite32(dma_addr, xadev->regs + XRP_DMA_ADDR_REG);
    /* XRP_DMA_COUNT_REG is number of 64-bit words to write, MINUS 1 */
    iowrite32(DMA_BUFFER_SIZE/8 - 1, xadev->regs + XRP_DMA_COUNT_REG);

    /* enable DMA completion interrupt */
    iowrite32(XRP_DMA_CONFIG_REG__INT_ENABLE, xadev->regs + XRP_DMA_CONFIG_REG);

    prepare_to_wait(&dma_event_queue, &wait, TASK_UNINTERRUPTIBLE);

    /* start DMA */
    iowrite32(XRP_DMA_CONTROL_REG__START, xadev->regs + XRP_DMA_CONTROL_REG);

    while(1) {
        schedule();

        finish_wait(&dma_event_queue, &wait);

        if(!(ioread32(xadev->regs + XRP_DMA_STATUS_REG) & XRP_DMA_STATUS_REG__BUSY))
            break;

        dev_warn(xadev->dev, "DMA event received, but DMA engine is still busy");

        prepare_to_wait(&dma_event_queue, &wait, TASK_UNINTERRUPTIBLE);
    }

    dma_unmap_single(xadev->dev, dma_addr, DMA_BUFFER_SIZE, DMA_FROM_DEVICE);

    if(ioread32(xadev->regs + XRP_DMA_STATUS_REG) & XRP_DMA_STATUS_REG__ERROR) {
        u32 error_resp = (ioread32(xadev->regs + XRP_DMA_STATUS_REG) & XRP_DMA_STATUS_REG__ERROR_RESP_MASK)
            >> XRP_DMA_STATUS_REG__ERROR_RESP_SHIFT;
        dev_err(xadev->dev, "DMA engine reports AXI error (%u)", error_resp);
        devm_kfree(xadev->dev, dma_buf);
        mutex_unlock(&dma_test_mutex);
        return 2;
    }

    /* print out beginning of DMA buffer */
    /* for(i=0; (i<16) && (i<(DMA_BUFFER_SIZE/8)); i++) {
        dev_info(xadev->dev, "[%04x]  0x%08x 0x%08x", 8*i, dma_buf[2*i+0], dma_buf[2*i+1]);
    } */

    for(i=0; i<(DMA_BUFFER_SIZE/sizeof(u32)); i++) {
        if(dma_buf[i] != data++) {
            break;
        }
    }

    devm_kfree(xadev->dev, dma_buf);

    if(i != (DMA_BUFFER_SIZE/sizeof(u32))) {
        dev_err(xadev->dev, "DMA buffer does not contain expected content");
        ret = 1;
    } else {
        dev_info(xadev->dev, "DMA buffer content ok");
        ret = 0;
    }

    mutex_unlock(&dma_test_mutex);

    return ret;
}

static DEFINE_SPINLOCK(dma_irq_lock);

static irqreturn_t xatest_dma_isr(int irq, void *dev_id)
{
    struct xatest_device *xadev = (struct xatest_device *) dev_id;

    spin_lock(&dma_irq_lock);

    if(!ioread32(xadev->regs + XRP_DMA_INT_STATUS_REG) & XRP_DMA_INT_STATUS_REG__INT_PENDING) {
        dev_warn(xadev->dev, "DMA completion handler called, but no interrupt was pending");
        spin_unlock(&dma_irq_lock);
        return IRQ_NONE;
    }

    /* acknowledge interrupt to hardware */
    iowrite32(XRP_DMA_INT_STATUS_REG__INT_PENDING, xadev->regs + XRP_DMA_INT_STATUS_REG);

    wake_up(&dma_event_queue);

    dev_info(xadev->dev, "DMA completion interrupt");

    spin_unlock(&dma_irq_lock);
    return IRQ_HANDLED;
}

static DECLARE_WAIT_QUEUE_HEAD(int_event_queue);
static DEFINE_SPINLOCK(inttest_irq_lock);

#define XATEST_CIRC_BUF_SIZE 16

struct xatest_circ_buf {
    struct xatest_event data[XATEST_CIRC_BUF_SIZE];
    int head;
    int tail;
};

static struct xatest_circ_buf event_buf = {
    .head = 0,
    .tail = 0
};

static irqreturn_t xatest_inttest_isr(int irq, void *dev_id)
{
    struct xatest_device *xadev = (struct xatest_device *) dev_id;
    u32 swdata, timestamp;
    int tail;

    spin_lock(&inttest_irq_lock);
    /* acknowledge interrupt to hardware */
    iowrite32(XRP_INT_STATUS_REG__INT_PENDING, xadev->regs + XRP_INT_STATUS_REG);

    swdata = ioread32(xadev->regs + XRP_SW_STATE_REG);
    timestamp = ioread32(xadev->regs + XRP_TIMER_REG);

    tail = READ_ONCE(event_buf.tail);
    if(CIRC_SPACE(event_buf.head, tail, XATEST_CIRC_BUF_SIZE) >= 1) {
        event_buf.data[event_buf.head].swdata = swdata;
        event_buf.data[event_buf.head].timestamp = timestamp;
        smp_store_release(&event_buf.head, (event_buf.head+1)&(XATEST_CIRC_BUF_SIZE-1));
        wake_up_interruptible(&int_event_queue);
    } else {
        /* buffer overrun, data lost */
    }
    spin_unlock(&inttest_irq_lock);
    return IRQ_HANDLED;
}

static long xatest_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
    struct xatest_read_arg xa_read_arg;
    struct xatest_write_arg xa_write_arg;
    struct xatest_read_all_arg xa_read_all_arg;
    struct xatest_write_all_arg xa_write_all_arg;
    struct xatest_test_result xa_test_result;
    struct xatest_sr_read_arg xa_sr_read_arg;
    u32 val;
    int ret;

    struct xatest_device *xadev = container_of(file->private_data, struct xatest_device, miscdev);

    if(_IOC_DIR(cmd) != _IOC_NONE && !access_ok((void __user *)arg, _IOC_SIZE(cmd)))
        return -EFAULT;

    switch(cmd) {
        case XAIOC_READ:
            if(copy_from_user(&xa_read_arg, (void __user *)arg, sizeof(struct xatest_read_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "read: reg=%d", xa_read_arg.reg);
            val = xatest_reg_read(xadev, xa_read_arg.reg);
            dev_dbg(xadev->dev, "read: val=0x%x", val);
            xa_read_arg.val = val;
            if(copy_to_user((void __user*) arg, &xa_read_arg, sizeof(struct xatest_read_arg)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_WRITE:
            if(copy_from_user(&xa_write_arg, (void __user *)arg, sizeof(struct xatest_write_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "write: reg=%d, val=0x%x", xa_write_arg.reg, xa_write_arg.val);
            xatest_reg_write(xadev, xa_write_arg.reg, xa_write_arg.val);
            return 0;

        case XAIOC_READ_ALL:
            if(copy_from_user(&xa_read_all_arg, (void __user *)arg, sizeof(struct xatest_read_all_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "read_all");
            xatest_reg_read_all(xadev, xa_read_all_arg.vals);
            if(copy_to_user((void __user*) arg, &xa_read_all_arg, sizeof(struct xatest_read_all_arg)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_WRITE_ALL:
            if(copy_from_user(&xa_write_all_arg, (void __user *)arg, sizeof(struct xatest_write_all_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "write_all");
            xatest_reg_write_all(xadev, xa_write_all_arg.vals);
            return 0;

        case XAIOC_CLEAR_ALL:
            dev_dbg(xadev->dev, "clear_all");
            xatest_reg_clear_all(xadev);
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
            xatest_ill_reg_read(xadev);
            return 0;

        case XAIOC_TEST_ILL_WRITE:
            xatest_ill_reg_write(xadev);
            return 0;

        case XAIOC_SR_READ:
            if(copy_from_user(&xa_sr_read_arg, (void __user *)arg, sizeof(struct xatest_sr_read_arg)) != 0)
                return -EFAULT;
            dev_dbg(xadev->dev, "read special: reg=%d", xa_sr_read_arg.sr);
            ret = xatest_sr_read(xadev, xa_sr_read_arg.sr, &val);
            if(ret != 0)
                return ret;
            dev_dbg(xadev->dev, "read special: val=0x%x", val);
            xa_sr_read_arg.val = val;
            if(copy_to_user((void __user*) arg, &xa_sr_read_arg, sizeof(struct xatest_sr_read_arg)) != 0)
                return -EFAULT;
            return 0;

        case XAIOC_TEST_DMA:
            ret = xatest_test_dma(xadev);
            if(ret < 0)
                return ret;
            xa_test_result.result = ret;
            if(copy_to_user((void __user*) arg, &xa_test_result, sizeof(struct xatest_test_result)) != 0)
                return -EFAULT;
            return 0;

        default:
            return -ENOTTY;
    }
}

static DEFINE_SPINLOCK(reader_lock);

static ssize_t xatest_read(struct file *file, char __user *buf, size_t count, loff_t *off)
{
    DEFINE_WAIT(wait);
    size_t requested, read = 0;
    struct xatest_event data[4];
    int head, tail, avail;
    int nonblock = READ_ONCE(file->f_flags) & O_NONBLOCK;

    if(count == 0)
        return count;

    if(count < sizeof(struct xatest_event))
        return -EINVAL;

    requested = count / sizeof(struct xatest_event);
    if(requested > ARRAY_SIZE(data))
        requested = ARRAY_SIZE(data);

    while(1) {
        if(!nonblock)
            prepare_to_wait(&int_event_queue, &wait, TASK_INTERRUPTIBLE);

        spin_lock(&reader_lock);
        head = smp_load_acquire(&event_buf.head);
        tail = event_buf.tail;
        avail = CIRC_CNT(head, tail, XATEST_CIRC_BUF_SIZE);
        if(avail >= 1) {
            while(read < avail && read < requested) {
                    data[read] = event_buf.data[tail];
                    read++;
                    tail = (tail + 1) & (XATEST_CIRC_BUF_SIZE-1);
            }
            smp_store_release(&event_buf.tail, tail);
        }
        spin_unlock(&reader_lock);

        if(nonblock)
            break;

        if(read == 0)
            schedule();

        finish_wait(&int_event_queue, &wait);

        if(read > 0)
            break;

        if(signal_pending(current))
            return -ERESTARTSYS;
    }

    if(read == 0) {
        return -EAGAIN;
    }

    if(copy_to_user(buf, data, read*sizeof(struct xatest_event))) {
        return -EFAULT;
    }

    return read*sizeof(struct xatest_event);
}

static unsigned int xatest_poll(struct file *file, struct poll_table_struct *poll_table)
{
    int head, avail;

    poll_wait(file, &int_event_queue, poll_table);

    spin_lock(&reader_lock);
    head = smp_load_acquire(&event_buf.head);
    avail = CIRC_CNT(head, event_buf.tail, XATEST_CIRC_BUF_SIZE);
    spin_unlock(&reader_lock);

    if(avail >= 1) {
        return POLLIN | POLLRDNORM;
    } else {
        return 0;
    }
}

static const struct file_operations xatest_fops = {
    .owner = THIS_MODULE,
    .unlocked_ioctl = xatest_ioctl,
    .compat_ioctl = compat_ptr_ioctl,
    .read = xatest_read,
    .poll = xatest_poll
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
    int irq;
    struct resource *res;
    struct clk *clk;

    /* only one device is supported */
    if(xatest_dev.dev)
        return -EBUSY;

    mutex_init(&dma_test_mutex);

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

    irq = platform_get_irq(pdev, 0);
    if(irq <= 0) {
        ret = -ENXIO;
        goto out;
    }

    ret = devm_request_irq(&pdev->dev, irq, xatest_inttest_isr, 0, dev_name(&pdev->dev), &xatest_dev);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to register test interrupt");
        goto out;
    }

    irq = platform_get_irq(pdev, 1);
    if(irq <= 0) {
        ret = -ENXIO;
        goto out;
    }

    ret = devm_request_irq(&pdev->dev, irq, xatest_dma_isr, 0, dev_name(&pdev->dev), &xatest_dev);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to register DMA interrupt");
        goto out;
    }

    ret = misc_register(&xatest_dev.miscdev);
    if(ret != 0) {
        dev_err(&pdev->dev, "failed to register misc device");
        goto out;
    }

    xatest_enable_interrupt(&xatest_dev);

    dev_info(&pdev->dev, "initialized");

    return 0;

out:
    clk_disable_unprepare(clk);

    return ret;
}

static int xatest_remove(struct platform_device *pdev)
{
    xatest_disable_interrupt(&xatest_dev);
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
