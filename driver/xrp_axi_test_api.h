/* SPDX-License-Identifier: GPL-2.0+ WITH Linux-syscall-note */
/*
 * Kernel driver to test AXI on Xilinx Zynq: userspace API
 *
 * Copyright (C) 2020-2021 Norbert Braun <norbert@xrpbot.org>
 */
#ifndef XRP_AXI_TEST_API_H
#define XRP_AXI_TEST_API_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define XATEST_N_REGS 8

struct xatest_read_arg {
    __u32 reg;
    __u32 val;
};

struct xatest_read_all_arg {
    __u32 vals[XATEST_N_REGS];
};

struct xatest_write_arg {
    __u32 reg;
    __u32 val;
};

struct xatest_write_all_arg {
    __u32 vals[XATEST_N_REGS];
};

struct xatest_test_result {
    __u32 result;
};

struct xatest_sr_read_arg {
    __u32 sr;
    __u32 val;
};

#define XASR_SW_STATE   1
#define XASR_TIMER      2
#define XASR_INT_STATUS 3
#define XASR_INT_COUNT  4

#define XAIOC_READ           _IOWR('t', 0, struct xatest_read_arg)
#define XAIOC_WRITE          _IOW('t', 1, struct xatest_write_arg)
#define XAIOC_READ_ALL       _IOWR('t', 2, struct xatest_read_all_arg)
#define XAIOC_WRITE_ALL      _IOW('t', 3, struct xatest_write_all_arg)
#define XAIOC_CLEAR_ALL      _IO('t', 4)
#define XAIOC_TEST_SMALL     _IOR('t', 5, struct xatest_test_result)
#define XAIOC_TEST_UNALIGNED _IOR('t', 6, struct xatest_test_result)
#define XAIOC_TEST_ILL_READ  _IO('t', 7)
#define XAIOC_TEST_ILL_WRITE _IO('t', 8)
#define XAIOC_SR_READ        _IOWR('t', 9, struct xatest_sr_read_arg)

struct xatest_event {
    __u32 swdata;
    __u32 timestamp;
};

#endif
