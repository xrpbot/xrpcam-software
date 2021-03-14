#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <assert.h>

#include <xrp_axi_test_api.h>

int do_blocking_read()
{
    int fd = open("/dev/xrp_axi_test", O_RDONLY);
    if(fd < 0) {
        perror("open");
        return -2;
    }

    while(1) {
        struct xatest_event buf[4];
        ssize_t ret = read(fd, &buf, sizeof(buf));
        if(ret < 0) {
            perror("read");
            close(fd);
            return -2;
        } else if(ret == 0) {
            fprintf(stderr, "read() returned 0\n");
        }

        size_t n = ret/sizeof(struct xatest_event);

        for(size_t i=0; i<n; i++) {
            printf("%02x (%u)  ", buf[i].swdata, buf[i].timestamp);
        }
        printf("\n");
    }

    if(close(fd) < 0) {
        perror("close");
        return -2;
    }

    return 0;
}

int do_nonblocking_read()
{
    int fd = open("/dev/xrp_axi_test", O_RDONLY | O_NONBLOCK);
    if(fd < 0) {
        perror("open");
        return -2;
    }

    int got_data;
    int was_waiting = 0;

    while(1) {
        got_data = 0;
        while(1) {
            struct xatest_event buf[4];
            ssize_t ret = read(fd, &buf, sizeof(buf));
            if(ret < 0) {
                if(errno == EAGAIN) {
                    break;
                } else {
                    perror("read");
                    close(fd);
                    return -2;
                }
            } else if(ret == 0) {
                fprintf(stderr, "read() returned 0\n");
                break;
            } else {
                size_t n = ret/sizeof(struct xatest_event);
                got_data = 1;

                if(was_waiting)
                    printf("\n");

                was_waiting = 0;

                for(size_t i=0; i<n; i++) {
                    printf("%02x (%u)  ", buf[i].swdata, buf[i].timestamp);
                }
            }
        }

        if(got_data) {
            printf("\n");
        } else {
            if(was_waiting) {
                printf(".");
            } else {
                printf("Waiting .");
            }
            was_waiting = 1;

            fflush(stdout);
        }

        sleep(1);
    }

    if(close(fd) < 0) {
        perror("close");
        return -2;
    }

    return 0;
}

int do_select()
{
    int fd = open("/dev/xrp_axi_test", O_RDONLY | O_NONBLOCK);
    if(fd < 0) {
        perror("open");
        return -2;
    }

    assert(fd < FD_SETSIZE);

    while(1) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(fd, &fds);

        int s_ret = select(fd+1, &fds, NULL, NULL, NULL);
        if(s_ret < 0) {
            perror("select");
            close(fd);
            return -2;
        } else if(s_ret == 0) {
            fprintf(stderr, "select() returned 0\n");
        } else {
            struct xatest_event buf[4];
            ssize_t r_ret = read(fd, &buf, sizeof(buf));
            if(r_ret < 0) {
                perror("read");
                close(fd);
                return -2;
            } else if(r_ret == 0) {
                fprintf(stderr, "read() returned 0\n");
            }

            size_t n = r_ret/sizeof(struct xatest_event);

            for(size_t i=0; i<n; i++) {
                printf("%02x (%u)  ", buf[i].swdata, buf[i].timestamp);
            }
            printf("\n");
        }
    }

    if(close(fd) < 0) {
        perror("close");
        return -2;
    }

    return 0;
}

int main(int argc, char *argv[])
{
    assert(argc >= 1);

    if(argc == 1) {
        return do_blocking_read();
    } else if(argc == 2 && strncmp(argv[1], "b", 1) == 0) {
        return do_blocking_read();
    } else if(argc == 2 && strncmp(argv[1], "n", 1) == 0) {
        return do_nonblocking_read();
    } else if(argc == 2 && strncmp(argv[1], "s", 1) == 0) {
        return do_select();
    } else {
        printf("Usage: %s [b|n|s]\n", argv[0]);
        printf("    b - blocking read (default)\n");
        printf("    n - nonblocking read\n");
        printf("    s - select\n");
        return -1;
    }
}
