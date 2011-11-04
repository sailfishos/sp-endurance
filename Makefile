# build and install rules for endurance tools and scripts

CFLAGS ?= -O2 -Wall

# add some extra warnings
CFLAGS += -Wmissing-prototypes -Wstrict-prototypes -Wsign-compare\
 -Wbad-function-cast -Wcast-qual -Wpointer-arith -Wshadow\
 -Wwrite-strings -Wcast-align -W

BINS = measure/proc2csv measure/xmeminfo 
SRC_FILES = Makefile src/proc2csv.c src/xmeminfo.c
DOCS = README

ALL = $(SRC_FILES) $(BINS) $(DOCS) 

all: $(ALL)

measure/proc2csv: src/proc2csv.c
	gcc $(CFLAGS) -o $@ $<

measure/xmeminfo: src/xmeminfo.c
	gcc -I/usr/X11R6/include $(CFLAGS) -o $@ $< -lXRes

clean: 
	$(RM) measure/proc2csv
	$(RM) measure/xmeminfo

install:
	 install -d $(DESTDIR)/usr/bin/
	 cp measure/* $(DESTDIR)/usr/bin/
	 cp postproc/* $(DESTDIR)/usr/bin/
	 install -d $(DESTDIR)/usr/share/man/man1/
	 cp man/* $(DESTDIR)/usr/share/man/man1/
	 install -d $(DESTDIR)/usr/share/doc/sp-endurance-postproc/
	 cp README $(DESTDIR)/usr/share/doc/sp-endurance-postproc/
	 install -d $(DESTDIR)/usr/share/sp-endurance-tests/
	 cp -a tests/* $(DESTDIR)/usr/share/sp-endurance-tests/
	 install -d $(DESTDIR)/usr/share/sp-endurance-postproc/
	 cp -a syslog-parser-configurations/* $(DESTDIR)/usr/share/sp-endurance-postproc/
