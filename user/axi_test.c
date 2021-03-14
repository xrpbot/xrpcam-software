#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <assert.h>

#include <xrp_axi_test_api.h>

enum op { OP_READ, OP_WRITE, OP_READ_ALL, OP_WRITE_ALL, OP_CLEAR_ALL, OP_SR_READ, OP_TEST, OP_ILL_READ, OP_ILL_WRITE };

void help(const char *prog_name)
{
    printf("Usage: %s [ cmd ] [ args ]\n", prog_name);
    printf("\n");
    printf("Available commands:\n");
    printf("    r [<reg>|all]     - read register\n");
    printf("    w <reg>|all <val> - write <val> to register <reg>, or all to registers\n");
    printf("    c                 - clear all registers\n");
    printf("    sr                - read special registers\n");
    printf("    t                 - perform register test, report summary result\n");
    printf("    ir                - perform illegal read\n");
    printf("    iw                - perform illegal write\n");
    printf("    h                 - show help (this text)\n");
}

int main(int argc, char *argv[])
{
    assert(argc >= 1);

    if(argc < 2) {
        printf("Usage: %s r|w|c|t|ir|iw|h [ args ]\n", argv[0]);
        printf("(%s h  for help)\n", argv[0]);
        return -1;
    }

    enum op op;

    if(strncmp(argv[1], "r", 1) == 0) {
        if(argc > 3) {
            printf("Usage: %s r [<reg>|all]\n", argv[0]);
            return -1;
        }

        if(argc < 3 || strcmp(argv[2], "all") == 0) {
            op = OP_READ_ALL;
        } else {
            op = OP_READ;
        }
    } else if(strncmp(argv[1], "w", 1) == 0) {
        op = OP_WRITE;
        if(argc != 4) {
            printf("Usage: %s w <reg>|all <val>\n", argv[0]);
            return -1;
        }
        if(strcmp(argv[2], "all") == 0)
            op = OP_WRITE_ALL;
    } else if(strncmp(argv[1], "c", 1) == 0) {
        if(argc != 2) {
            printf("Usage: %s c\n", argv[0]);
            return -1;
        }
        op = OP_CLEAR_ALL;
    } else if(strncmp(argv[1], "sr", 2) == 0) {
        if(argc != 2) {
            printf("Usage: %s sr\n", argv[0]);
            return -1;
        }
        op = OP_SR_READ;
    } else if(strncmp(argv[1], "t", 1) == 0) {
        if(argc != 2) {
            printf("Usage: %s t\n", argv[0]);
            return -1;
        }
        op = OP_TEST;
    } else if(strncmp(argv[1], "ir", 2) == 0) {
        if(argc != 2) {
            printf("Usage: %s ir\n", argv[0]);
            return -1;
        }
        op = OP_ILL_READ;
    } else if(strncmp(argv[1], "iw", 2) == 0) {
        if(argc != 2) {
            printf("Usage: %s iw\n", argv[0]);
            return -1;
        }
        op = OP_ILL_WRITE;
    } else if((strncmp(argv[1], "h", 1) == 0) ||
            (strcmp(argv[1], "-help") == 0) ||
            (strcmp(argv[1], "--help") == 0) ||
            (strcmp(argv[1], "-h") == 0)) {
        help(argv[0]);
        return 0;
    } else {
        printf("Unknown operation `%s`\n", argv[1]);
        printf("(%s h  for help)\n", argv[0]);
        return -1;
    }

    uint32_t reg = 0;
    uint32_t val = 0;

    if(op == OP_READ || op == OP_WRITE) {
        long arg;
        char *endptr;

        errno = 0;
        arg = strtol(argv[2], &endptr, 0);
        if(errno != 0 || *argv[2] == '\0' || *endptr != '\0') {
            printf("%s: invalid register argument `%s` (must be number)\n", argv[0], argv[2]);
            return -1;
        }

        if(arg < 0 || arg >= XATEST_N_REGS) {
            printf("%s: register argument (%ld) out of range (must be between 0..%d inclusive)\n", argv[0], arg, XATEST_N_REGS-1);
            return -1;
        }

        reg = arg;
    }

    if(op == OP_WRITE || op == OP_WRITE_ALL) {
        long arg;
        char *endptr;

        errno = 0;
        arg = strtol(argv[3], &endptr, 0);
        if(errno != 0 || *argv[3] == '\0' || *endptr != '\0') {
            printf("%s: invalid value argument `%s` (must be number)\n", argv[0], argv[3]);
            return -1;
        }

        val = arg;
    }

    int fd = open("/dev/xrp_axi_test", O_RDWR);
    if(fd < 0) {
        perror("open");
        return -2;
    }

    if(op == OP_READ) {
        struct xatest_read_arg ioc_arg = {
            .reg = reg,
            .val = 0
        };

        if(ioctl(fd, XAIOC_READ, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }

        printf("[%d] = 0x%x\n", reg, ioc_arg.val);
    } else if(op == OP_WRITE) {
        struct xatest_write_arg ioc_arg = {
            .reg = reg,
            .val = val
        };

        if(ioctl(fd, XAIOC_WRITE, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
    } else if(op == OP_READ_ALL) {
        struct xatest_read_all_arg ioc_arg = {
            .vals = { 0 }
        };

        if(ioctl(fd, XAIOC_READ_ALL, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }

        for(int reg=0; reg<XATEST_N_REGS; reg++) {
            printf("[%d] = 0x%x\n", reg, ioc_arg.vals[reg]);
        }
    } else if(op == OP_WRITE_ALL) {
        struct xatest_write_all_arg ioc_arg;
        for(int reg=0; reg<XATEST_N_REGS; reg++) {
            ioc_arg.vals[reg] = val;
        }

        if(ioctl(fd, XAIOC_WRITE_ALL, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
    } else if(op == OP_CLEAR_ALL) {
        if(ioctl(fd, XAIOC_CLEAR_ALL) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
    } else if(op == OP_SR_READ) {
        struct xatest_sr_read_arg ioc_arg;

        ioc_arg.sr = XASR_SW_STATE;
        if(ioctl(fd, XAIOC_SR_READ, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("SW_STATE:   0x%08x\n", ioc_arg.val);

        ioc_arg.sr = XASR_TIMER;
        if(ioctl(fd, XAIOC_SR_READ, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("TIMER:      %u\n", ioc_arg.val);

        ioc_arg.sr = XASR_INT_STATUS;
        if(ioctl(fd, XAIOC_SR_READ, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("INT_STATUS: 0x%08x\n", ioc_arg.val);

        ioc_arg.sr = XASR_INT_COUNT;
        if(ioctl(fd, XAIOC_SR_READ, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("INT_COUNT:  %u\n", ioc_arg.val);
    } else if(op == OP_TEST) {
        struct xatest_test_result ioc_arg;
        if(ioctl(fd, XAIOC_TEST_SMALL, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("Small read/write test: ");
        if(ioc_arg.result == 0) {
            printf("passed\n");
        } else {
            printf("FAILED (see kernel log for details)\n");
        }

        if(ioctl(fd, XAIOC_TEST_UNALIGNED, &ioc_arg) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
        printf("Unaligned read/write test: ");
        if(ioc_arg.result == 0) {
            printf("passed\n");
        } else {
            printf("FAILED (see kernel log for details)\n");
        }
    } else if(op == OP_ILL_READ) {
        printf("About to perform illegal read\n");
        fflush(stdout);
        if(ioctl(fd, XAIOC_TEST_ILL_READ) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
    } else if(op == OP_ILL_WRITE) {
        printf("About to perform illegal write\n");
        fflush(stdout);
        if(ioctl(fd, XAIOC_TEST_ILL_WRITE) < 0) {
            perror("ioctl");
            close(fd);
            return -2;
        }
    }

    if(close(fd) < 0) {
        perror("close");
        return -2;
    }

    return 0;
}
