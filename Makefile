# build and install rules for endurance tools and scripts

CFLAGS ?= -O2 -Wall -g

# add some extra warnings
CFLAGS += -Wmissing-prototypes -Wstrict-prototypes -Wsign-compare\
 -Wbad-function-cast -Wcast-qual -Wpointer-arith -Wshadow\
 -Wwrite-strings -Wcast-align -W

BIN = measure/proc2csv measure/sp-noncached
SRC = Makefile src/proc2csv.c src/sp_noncached.c
MAN = endurance-mem-overview.1 \
    endurance_plot.1 \
    endurance_report.py.1 \
    extract-endurance-process-smaps.1 \
    parse-endurance-measurements.1 \
    proc2csv.1 \
    recompress-endurance-measurements.1 \
    save-incremental-endurance-stats.1 \
    split-endurance-measurements.1 \
    syslog_parse.py.1 \
    sp-noncached.1
    
ifeq ($(NO_X),)
BIN += measure/xmeminfo
SRC += src/xmeminfo.c
MAN += xmeminfo.1
endif
DOC = README

ALL = $(SRC) $(BIN) $(DOC) postproc-lib

.PHONY: all
all: $(ALL)

postproc-lib/Makefile:
	cd postproc-lib && perl Makefile.PL

.PHONY: postproc-lib
postproc-lib: postproc-lib/Makefile
	cd postproc-lib && $(MAKE)

measure/proc2csv: src/proc2csv.c
	$(CC) $(CFLAGS) -o $@ $<

measure/xmeminfo: src/xmeminfo.c
	$(CC) -I/usr/X11R6/include $(CFLAGS) -o $@ $< -lXRes -lX11

measure/sp-noncached: src/sp_noncached.c
	$(CC) $(CFLAGS) -o $@ $<

.PHONY: clean
clean: 
	$(RM) measure/proc2csv
	$(RM) measure/xmeminfo
	$(RM) measure/sp-noncached
	[ ! -f postproc-lib/Makefile ] || $(MAKE) -C postproc-lib clean
	$(RM) postproc-lib/Makefile.old

mandir:
	install -d $(DESTDIR)/usr/share/man/man1/
	
recompress-endurance-measurements.1: postproc/recompress-endurance-measurements mandir
	pod2man postproc/recompress-endurance-measurements > man/$@
	install -m 644 man/$@ $(DESTDIR)/usr/share/man/man1/

%.1: man/$@ mandir
	install -m 644 man/$@ $(DESTDIR)/usr/share/man/man1/

DOCDIR ?= /usr/share/doc

.PHONY: install-measure
install-measure:
	install -d $(DESTDIR)/usr/bin/
	cp measure/* $(DESTDIR)/usr/bin/

.PHONY: install-postproc-lib
install-postproc-lib:
	cd postproc-lib && $(MAKE) install DESTDIR=$(DESTDIR)

.PHONY: install-postproc
install-postproc:
	install -d $(DESTDIR)/usr/bin/
	cp postproc/* $(DESTDIR)/usr/bin/
	install -d $(DESTDIR)/$(DOCDIR)/sp-endurance-postproc/
	cp README $(DESTDIR)/$(DOCDIR)/sp-endurance-postproc/
	cp doc/endurance.pdf $(DESTDIR)/$(DOCDIR)/sp-endurance-postproc/
	install -d $(DESTDIR)/usr/share/sp-endurance-postproc/
	cp -a syslog-parser-configurations/* $(DESTDIR)/usr/share/sp-endurance-postproc/

.PHONY: install-tests
install-tests:
	install -d $(DESTDIR)/usr/share/sp-endurance-tests/
	cp -a tests/* $(DESTDIR)/usr/share/sp-endurance-tests/

.PHONY: install
install: $(MAN) install-measure install-postproc-lib install-postproc install-tests
