CC = $(CROSS_COMPILE)gcc
CFLAGS = -Wall -I../driver

KDIR ?= ../../linux

INCLUDES = ../driver/xrp_axi_test_api.h

.PHONY: all clean

all: axi_test axi_stat

axi_test: axi_test.c $(INCLUDES) Makefile
	$(CC) $(CFLAGS) -static -o $@ $<

axi_stat: axi_stat.c Makefile
	$(CC) $(CFLAGS) -static -I$(KDIR)/usr/include -o $@ $<

clean:
	rm -f axi_test axi_stat
