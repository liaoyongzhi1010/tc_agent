CC = $(CROSS_COMPILE)gcc
CFLAGS = -Wall -I$(TEEC_EXPORT)/include -I../aesgcm_ta
LDFLAGS = -L$(TEEC_EXPORT)/lib -lteec

BINARY = aesgcm

.PHONY: all clean

all: $(BINARY)

$(BINARY): aesgcm.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(BINARY)
