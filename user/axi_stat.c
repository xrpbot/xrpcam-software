#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <stdint.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/gpio.h>
#include <assert.h>

#define BITS(x, i, j) (((x)>>(i))&((1ull<<((j)-(i)))-1))

/* The Zynq PS has 118 GPIO lines. 54 of them are routed to actual package pins
 * (or unconnected, depending on the variant). The other 64 are connected
 * between the PS and the PL.
 *
 * /dev/gpiochip0:
 *     0 .. 53:   54 external GPIOs
 *     54 .. 117: 64 GPIOs between PS and PL
 */

int main(int argc, char *argv[])
{
    assert(argc >= 1);

    int fd = open("/dev/gpiochip0", O_RDWR);
    if(fd < 0) {
        perror("open");
        return -2;
    }

    struct gpiohandle_request req = {
        .flags = GPIOHANDLE_REQUEST_INPUT,
        .consumer_label = "axi_stat"
    };
    assert(GPIOHANDLES_MAX >= 64);
    for(int i=0; i<64; i++) {
        req.lineoffsets[i] = 54+i;
    }
    req.lines = 64;

    if(ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req) < 0) {
        perror("GPIO_GET_LINEHANDLE_IOCTL");
        close(fd);
        return -2;
    }

    if(close(fd) < 0) {
        perror("close fd");
        return -2;
    }

    struct gpiohandle_data data;
    if(ioctl(req.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data) < 0) {
        perror("GPIOHANDLE_GET_LINE_VALUES_IOCTL");
        close(req.fd);
    }

    uint64_t io = 0;
    for(int i=0; i<64; i++) {
        if(data.values[i])
            io |= ((uint64_t)1 << i);
    }
    printf("raw: %016llx\n", io);
    printf("waddr count: %lld\n", BITS(io, 0, 8));
    printf("wdata count: %lld\n", BITS(io, 8, 16));
    printf("wresp count: %lld\n", BITS(io, 16, 24));
    printf("raddr count: %lld\n", BITS(io, 24, 32));
    printf("rdata count: %lld\n", BITS(io, 32, 40));
    printf("reg0 (byte0): 0x%02llx\n", BITS(io, 40, 48));

    if(close(req.fd) < 0) {
        perror("close gpiofd");
        return -2;
    }

    return 0;
}
