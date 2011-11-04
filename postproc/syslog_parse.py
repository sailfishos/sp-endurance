#!/usr/bin/python
# This file is part of sp-endurance.
#
# Copyright (C) 2006-2009,2011 by Nokia Corporation
#
# Contact: Eero Tamminen <eero.tamminen@nokia.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License 
# version 2 as published by the Free Software Foundation. 
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA
#
# CHANGES:
#
# 2006-11-09:
# - Parse normal/separate syslog files instead of CSV endurance file
# - Split this code from endurance-report.py
# - Add support for gzipped syslog files
# - Separate different DSME and Glib errors types
# - Parse kernel Oopses from the syslog
# - Support both HTML and ASCII output
# - Count the number of errors
# - Parsing debug option
# 2006-11-14:
# - Added error summary functionality
# - Shortened function names + documented which are public
# - Fix bug in syslog parsing (appended syslogs may have empty lines)
# - Improvements to the error output
# - Caller can give write function for (some of the) output functions
#   so that the parsed output can be directed to other files
# 2006-11-16:
# - Count reboots, DSP errors etc from syslogs
#   - "mbox: Illegal seq bit!" -> FATAL
#   - "omapdsp: poll error!" -> FATAL
#   - "mbx: ERR" -> WARNING
#   - "syslogd" (restarted on reboot)
# 2006-11-17:
# - Fix regex for DSP errors
# - Fix DSME parsing + parse returns with exit values too
# - Search & count Connectivity errors from the syslogs
#   - We haven't got a WR_READY/READY interrupt from WAKEUP/DMA_READY
#   - cx3110x ERROR
#   - TX dropped
# 2006-11-29:
# - Parse DSME "respawn too fast -> reset"
# 2006-11-30:
# - Parse kernel OOM-killer and lowmem allocation denial
# 2006-12-04:
# - Parse Glib ERROR
# 2006-12-20:
# - Add contents links to HTML report
# 2007-01-03:
# - Count only errors that are not immediately repeated
#   (within test round / error type)
# 2007-02-16:
# - Check each line for each message as syslog can sometimes have several
#   messages on the same line
# - Remove successive error "compression", it's hiding issues
# 2007-02-20:
# - remove buggy counter
# 2007-02-26:
# - Check for SysRq
# 2007-05-24:
# - Parse bootup reasons
# 2007-06-19:
# - Parse kernel I/O errors (MMC FAT problems)
# 2007-08-21:
# - Add day to output
# - Add charger bootup reason
# - Indicate in output titles where the stats come
# - Syslogd restarts don't anymore mean device restarts
# 2007-10-02:
# - Patch for Tuukka to catch syslog read failures
# - Don't duplicate time for Glib messages
# 2008-06-10:
# - Parse also program names with spaces in them from syslog
# 2008-06-24:
# - Parse kernel BUG and onenand_wait issues
# 2009-03-02:
# - Parse Maemo DBus warnings about too wide signal match patterns
# 2009-04-21:
# - Support lzop compressed syslogs
# 2009-04-28:
# - Parse upstart messages
# - Use the psyco JIT compiler, if installed. Gives 2-3x speed up.
# 2009-10-26:
# - Generalize compressed file opening in syslog parsing and endurance
#   report generation to common function here

"""
NAME
        <TOOL_NAME>

SYNOPSIS
        <TOOL_NAME> <syslog1> [syslog2 ...]

DESCRIPTION

This script parses different kinds of issues from given syslog files:
    - Device bootups (based on boot reasons and syslog restarts)
    - SysRq messages indicating faulty device setup
    - Kernel Oopses and BUGs
    - DSP errors and warnings
    - Kernel errors for FAT (I/O) JFFS2 (onenand_wait)
    - DSME reported system service restarts and reboots
    - Maemo-launcher reported application crashes
    - Critical errors and warnings reported by Glib
    - Maemo DBus warnings about applications listening to signals too widely
Then it counts and presents them in more readable form.
    
It can be used as a standalone program or imported to another python
script.  As a standalone program it produces a full HTML page, when
imported, a partial HTML page.


PUBLIC METHODS

When this is imported, following methods are intended for public use:
    parse_syslog()    -- parses given syslog
    parse_error()     -- outputs parsing error messages
    output_errors()   -- outputs the parsed errors
    errors_add()      -- adds together error statistics from output_errors()
    errors_summary()  -- outputs error statistics
    explain_signals() -- output (HTML) info on termination signals
The output is by default in HTML mode (controlled by use_html).

EXAMPLES
        <TOOL_NAME> syslog1 | less
"""

import sys, os, re, string, gzip


# whether to use HTML output or not
use_html = 1

verbose = ""
verbose_options = [
"sysrq", "bootup", "syslog", "kernel", "fs", "dsp", "connectivity", "dsme", "glib", "dbus", "upstart", "all"
]


# -------------------- error helpers --------------------------

def parse_error(write, error):
    "output given error/warning both to stderr and as HTML using given write func"
    if use_html:
        write("<p><font color=red>%s</font>\n" % error)
    sys.stderr.write("%s\n" % error)


def error_exit(msg):
    "outputs given message as error to stderr and exit"
    sys.stderr.write("ERROR: %s!\n" % msg)
    sys.exit(1)

# --------------------- file helper --------------------------

FATAL = True

def open_compressed(filename, fatal = False):
    """Open potentially compressed file and return its name and handle.
       First checks whether there's a gzipped or lzopped version
       of the file and if not, assumes file to be non-compressed.
       If the file doesn't exist, return None.
    """
    for suffix in ("", ".gz", ".lzo", ".xz"):
        tmp = filename + suffix
        if os.path.exists(tmp):
            filename = tmp
            break

    if not os.path.exists(filename):
        if fatal == FATAL:
            error_exit("%s missing" % filename)
        return (None, None)

    sys.stderr.write("Parsing '%s'...\n" % filename)

    if filename.endswith(".gz"):
        # Unfortunately the python gzip module is slow. Using /bin/zcat and
        # popen() gives 2-3x speed up.
        if os.system("which zcat >/dev/null") == 0:
            file = os.popen("zcat %s" % filename)
        else:
            file = gzip.open(filename, "r")

    elif filename.endswith(".lzo"):
        if os.system("which lzop >/dev/null") == 0:
            file = os.popen("lzop -dc %s" % filename)
        else:
            error_exit("file '%s' was compressed with lzop, but decompression program not available" % filename)

    elif filename.endswith(".xz"):
        if os.system("which xzcat >/dev/null") == 0:
            file = os.popen("xzcat %s" % filename)
        else:
            error_exit("file '%s' was compressed with XZ, but decompression program not available" % filename)

    else:
        file = open(filename, "r")

    return file, filename


# --------------------- signal utility --------------------------

signals = {
1: "HUP",
2: "INT",
3: "QUIT",
4: "ILL",
5: "TRAP",
6: "ABRT",
7: "BUS",
8: "FPE",
9: "KILL",
10: "USR1",
11: "SEGV",
12: "USR2",
13: "PIPE",
14: "ALRM",
15: "TERM",
16: "STKFLT",
17: "CHLD",
18: "CONT",
19: "STOP",
20: "TSTP",
21: "TTIN",
22: "TTOU",
23: "URG",
24: "XCPU",
25: "XFSZ",
26: "VTALRM",
27: "PROF",
28: "WINCH",
29: "IO/POLL",
30: "PWR",
31: "SYS"
}

def parse_signal(string):
    "gets integer string, returns (signal number, signal name)"
    signum = int(string)
    if signum in signals:
        signame = "signal SIG%s (%d)" % (signals[signum], signum)
    else:
        signame = "UNKNOWN signal (%d)" % signum
    return (signum, signame)


# ------------------- date/time parsing --------------------------

time_pattern = re.compile(" (\d+) (\d+:\d+:\d+) ")

def parse_time(line):
    match = time_pattern.search(line)
    if match:
        # 00:00:00/day
        return "%02d/%s" % (int(match.group(1)), match.group(2))
    else:
        sys.stderr.write("ERROR: line didn't match date/time:\n  %s\n" % line)
        sys.exit(1)


# --------------------- bootup parsing ---------------------------

bootup_reason = re.compile(" Bootup reason: (.*)$")

def parse_bootups(powerkeys, alarms, charger, swresets, hwresets, line):
    "appends to given array simplified bootup reason messages"
    match = bootup_reason.search(line)
    if match:
        time = parse_time(line)
        reason = match.group(1)
        if reason == "pwr_key":
            return powerkeys.append("%s user had booted the device" % time)
        elif reason == "rtc_alarm":
            return alarms.append("%s alarm had woken up the device" % time)
        elif reason == "charger":
            return charger.append("%s charger connection had woken up the device" % time)
        elif reason == "sw_rst":
            return swresets.append("%s SW watchdog had rebooted the device" % time)
        elif reason == "32wd_to":
            return hwresets.append("%s HW watchdog had rebooted the device" % time)
    if verbose in [ "all", "bootup" ]:
        sys.stderr.write("Warning: bootup reason pattern didn't match:\n  %s\n" % line)


# --------------------- restart parsing ---------------------------

syslog_restart = re.compile(" [^:]* syslogd .* restart.*$")

def parse_restarts(restarts, line):
    "appends to given array simplified syslogd (=device) restart message"
    match = syslog_restart.search(line)
    if match:
        restarts.append("%s syslogd restart" % parse_time(line))
    elif verbose in [ "all", "syslog" ]:
        sys.stderr.write("Warning: syslog pattern(s) didn't match:\n  %s\n" % line)


# --------------------- Kernel parsing ---------------------------

kernel_oops = re.compile(" kernel: .* [Oo]ops: (.*)$")
kernel_bugs = re.compile(" kernel BUG at (.*)$")

def parse_kernel(oopses, bugs, line):
    "appends to given array simplified kernel Oops/BUG message line"
    match = kernel_oops.search(line)
    if match:
        oopses.append("%s Kernel Oops: %s" % (parse_time(line), match.group(1)))
    else:
        match = kernel_bugs.search(line)
        if match:
            bugs.append("%s Kernel BUG at: %s" % (parse_time(line), match.group(1)))
        elif verbose in [ "all", "kernel" ]:
            sys.stderr.write("Warning: kernel pattern(s) didn't match:\n  %s\n" % line)


# --------------------- OOM parsing ---------------------------

kernel_oom = re.compile(" kernel: .* ([Oo]ut of [Mm]emory: [Kk]ill|lowmem: denying memory)(.*)$")

def parse_oom(ooms, line):
    "appends to given array simplified kernel OOM message line"
    match = kernel_oom.search(line)
    if match:
        ooms.append("%s %s%s" % (parse_time(line), match.group(1), match.group(2)))
    elif verbose in [ "all", "kernel" ]:
        sys.stderr.write("Warning: kernel pattern(s) didn't match:\n  %s\n" % line)

# --------------------- FS error parsing ---------------------------

io_error = re.compile(" kernel: [^]]*[]] (.*)$")
nand_error = re.compile(" onenand[^:]*_wait: (.*)$")

def parse_fs(io_errors, nand_errors, line):
    "appends to given arrays simplified kernel I/O and nand access error messages"
    match = nand_error.search(line)
    if match:
        nand_errors.append("%s NAND issue: %s" % (parse_time(line), match.group(1)))
    else:
        match = io_error.search(line)
        if match:
            io_errors.append("%s %s" % (parse_time(line), match.group(1)))
        elif verbose in [ "all", "fs" ]:
            sys.stderr.write("Warning: kernel FS error pattern(s) didn't match:\n  %s\n" % line)


# --------------------- DSP error parsing ---------------------------

dsp_error = re.compile(" (mbox: Illegal seq bit.*|omapdsp: poll error.*)$")
dsp_warn = re.compile(" (mbx: ERR.*)$")

def parse_dsp(errors, warnings, line):
    "appends to given array simplified DSP error or warning message"
    match = dsp_error.search(line)
    if match:
        errors.append("%s %s" % (parse_time(line), match.group(1)))
    else:
        match = dsp_warn.search(line)
        if match:
            warnings.append("%s %s" % (parse_time(line), match.group(1)))
        elif verbose in [ "all", "dsp" ]:
            sys.stderr.write("Warning: DSP pattern(s) didn't match:\n  %s\n" % line)


# ----------------- Connectivity error parsing ---------------------------

conn_error = re.compile("(cx3110x ERROR.*|TX dropped.*|We haven't got a [A-Z_]+ interrupt from [A-Z_]+.*)$")

def parse_connectivity(errors, line):
    "appends to given array simplified Connectivity error or warning message"
    match = conn_error.search(line)
    if match:
        errors.append("%s %s" % (parse_time(line), match.group(1)))
    elif verbose in [ "all", "connectivity" ]:
        sys.stderr.write("Warning: connectivity pattern(s) didn't match:\n  %s\n" % line)


# --------------------- DSME error parsing ---------------------------

dsme_respawn = re.compile(" DSME:[^']* '([^']+)' spawning too fast -> reset")
dsme_reset = re.compile(" DSME:[^']* '([^']+)' exited (with RESET|and restarted)")
dsme_signal = re.compile(" DSME:[^']* '([^']+)' with pid ([0-9]+) exited with signal: ([0-9]+)")
dsme_exit = re.compile(" DSME:[^']* '([^']+)' with pid ([0-9]+) (exited with return value: .*)")

def parse_dsme(resets, restarts, crashes, exits, line):
    "appends to given array simplified DSME device reset or process restart message"
    match = dsme_signal.search(line)
    if match:
        signum, signal = parse_signal(match.group(3))
        output = (parse_time(line), match.group(1), match.group(2), signal)
        # termination requests: HUP, INT, TERM
        if signum in (1, 2, 15):
            exits.append("%s %s[%s]: exited with %s" % output)
        else:
            # kills
            crashes.append("%s %s[%s]: exited with %s" % output)
        return
    match = dsme_reset.search(line)
    if match:
        output = (parse_time(line), match.group(1))
        if match.group(2) == "with RESET":
            resets.append("%s %s (RESET)" % output)
        else:
            restarts.append("%s %s" % output)
        return
    match = dsme_exit.search(line)
    if match:
        output = "%s[%s]: %s" % match.groups()
        exits.append("%s %s" % (parse_time(line), output))
        return
    match = dsme_respawn.search(line)
    if match:
        resets.append("%s %s (RESET)" % (parse_time(line), match.group(1)))
        return
    if verbose in [ "all", "dsme" ]:
        sys.stderr.write("Warning: DSME patterns didn't match:\n  %s\n" % line)


# --------------------- GLIB error parsing ---------------------------

#glib_pattern = re.compile(" (\S+): GLIB (WARNING|CRITICAL) \*\* (.*)$")
# pattern: time, device name, program name (may have spaces) + [pid], GLIB issue
glib_pattern = re.compile(" \d+:\d+:\d+ +[^ ]+ +([^]]+[]]): GLIB (WARNING|CRITICAL|ERROR) \*\* (.*)$")

def parse_glib(criticals, warnings, line):
    "appends to given array simplified Glib critical error or warning"
    match = glib_pattern.search(line)
    if match:
        output = (parse_time(line), match.group(1), match.group(3))
        if match.group(2) == "ERROR":
            criticals.append("%s %s (ERROR): %s" % output)
        elif match.group(2) == "CRITICAL":
            criticals.append("%s %s (CRITICAL): %s" % output)
        else:
            warnings.append("%s %s: %s" % output)
    elif verbose in [ "all", "glib" ]:
        sys.stderr.write("Warning: GLIB WARNING/CRITICAL pattern(s) did not match:\n  %s\n" % line)


# --------------------- maemo-launcher parsing ---------------------------

def parse_launcher(deaths, lines, line, start):
    "Parses both launcher application exits and invocations to get app names"
    signal = line.find("signal=")
    if signal >= 0:
        pid = line[line.find("(pid=")+5:line.rfind(')')]
        search = "maemo-launcher[%s]" % pid
        found = 0
        # find the invocation line for the exited app
        for check in lines:
            if check.find(search) >= 0:
                # application name without path or quotes
                time = parse_time(line)
                app = check[check.find("invoking")+10:-1].split('/')[-1]
                signal = line[signal + len("signal="):]
                signum, signame = parse_signal(signal)
                # app name: signal (at time)
                deaths.append("%s %s: exited with %s" % (time, app, signame))
                found = 1
                break
        if not found:
            sys.stderr.write("Warning: no maemo-launched application invocation matches:\n  '%s'!\n" % search)
    else:
        # need to add these in reverse order so that
        # search above finds last invocation
        if line.find("invoking") >= 0:
            lines.insert(0, line)


# --------------------- DBus broadcast signal warning ---------------------------

dbus_sig_pattern1 = re.compile("dbus\[\d+\]: WARNING: match (.*) added by (.*) who owns services:")
dbus_sig_pattern2 = re.compile("dbus\[\d+\]:  :\d+\.\d+")
dbus_sig_pattern3 = re.compile("dbus\[\d+\]:  (.*)")

def parse_dbus_signal_warning(dbus_sigs, line):
    "Parses Maemo DBus warnings about applications that match DBus signals too widely"
    match1 = dbus_sig_pattern1.search(line)
    match2 = dbus_sig_pattern2.search(line)
    match3 = dbus_sig_pattern3.search(line)
    if verbose in [ "all", "dbus" ]:
        sys.stderr.write("matching dbus to %s\n" % line)
    if match1:
        dbus_sigs.append("%s %s registered too wide pattern \"%s\"" % (parse_time(line), match1.group(2), match1.group(1)))
    elif match2:
        # ignore, only repeats the ID, such as :1.30
        pass
    elif match3:
        if len(dbus_sigs) > 0:
            dbus_sigs[-1] += (", owns \"%s\"" % (match3.group(1)));
        elif verbose in [ "all", "dbus" ]:
            sys.stderr.write("Warning: dbus matched service name without initial warning:\n  %s\n" % line)
    elif verbose in [ "all", "dbus" ]:
        sys.stderr.write("Warning: dbus pattern didn't match:\n  %s\n" % line)


# -------------------------------- Upstart --------------------------------------------------------
#
#Jan  1 04:13:45 Nokia-NXX-18-5 init: xomap main process (851) terminated with status 6
#Jan  1 04:13:45 Nokia-NXX-18-5 init: xomap main process ended, respawning
#Jan  1 04:13:46 Nokia-NXX-18-5 init: xsession pre-stop process (1765) terminated with status 1
#Jan  1 04:13:46 Nokia-NXX-18-5 init: xsession main process (879) killed by TERM signal
#Jan  1 04:13:46 Nokia-NXX-18-5 init: osso-systemui main process (1186) terminated with status 1
#Jan  1 06:26:10 Nokia-NXX-18-5 init: cellmo-watch main process (704) killed by TERM signal
#Jan  1 07:03:15 Nokia-NXX-18-5 init: osso-systemui main process (875) terminated with status 6
#Jan  1 07:03:15 Nokia-NXX-18-5 init: osso-systemui main process ended, respawning
#Jan  1 07:04:11 Nokia-NXX-18-5 init: osso-systemui main process (1485) killed by signal 64
#Jan  1 07:04:11 Nokia-NXX-18-5 init: osso-systemui main process ended, respawning
#Jan  1 07:07:11 Nokia-NXX-18-5 init: osso-systemui main process (1503) killed by HUP signal
#Jan  1 07:07:11 Nokia-NXX-18-5 init: osso-systemui main process ended, respawning
#Jan  1 07:07:54 Nokia-NXX-18-5 init: osso-systemui main process (1520) killed by INT signal
#Jan  1 07:07:54 Nokia-NXX-18-5 init: osso-systemui main process ended, respawning
#Jan  1 07:07:54 Nokia-NXX-18-5 init: osso-systemui respawning too fast, stopped

upstart_nonzero_exit = re.compile(" init: (.*) process \((\d+)\) terminated with status (\d+)")
upstart_killed1      = re.compile(" init: (.*) process \((\d+)\) killed by (.*) signal")
upstart_killed2      = re.compile(" init: (.*) process \((\d+)\) killed by signal (\d+)")
upstart_respawn      = re.compile(" init: (.*) process ended, respawning")
upstart_respawn2fast = re.compile(" init: (.*) respawning too fast, stopped")

def parse_upstart(exit, kill, respawn, respawn2fast, line):
    time = parse_time(line)
    m = upstart_nonzero_exit.search(line)
    if m:
        exit.append("%s %s[%s]: exited with return value: %s" % ((time,) + m.group(1,2,3)))
        return
    m = upstart_killed1.search(line)
    if m:
        kill.append("%s %s[%s]: killed by signal SIG%s" % ((time,) + m.group(1,2,3)))
        return
    m = upstart_killed2.search(line)
    if m:
        signum, signame = parse_signal(m.group(3))
        kill.append("%s %s[%s]: killed by %s" % ((time,) + m.group(1,2) + (signame,)))
        return
    m = upstart_respawn.search(line)
    if m:
        respawn.append("%s %s" % (time, m.group(1)))
        return
    m = upstart_respawn2fast.search(line)
    if m:
        respawn2fast.append("%s %s" % (time, m.group(1)))
        return
    if verbose in [ "all", "upstart" ]:
        sys.stderr.write("Warning: no match for upstart messages:\n  %s\n" % line)


# --------------------- syslog parsing ---------------------------

def parse_syslog(write, syslog):
    "parses kernel, DSP, connectivity, DSME, Maemo-launcher and Glib reported errors from syslog"
    # Syslog entry examples:
    # Nov 16 01:53:52 Nokia770-44 syslogd 1.4.1#17.osso1: restart.
    # Feb 26 20:19:53 Nokia-N800-08 kernel: [ 9899.620422] Bootup reason: sw_rst
    # Oct 23 14:16:53 Nokia770-42 kernel: [44449.006805] Internal error: Oops: 7 [#1]
    # Feb 22 13:55:06 Nokia-N800-03 kernel: [11162.797271] kernel BUG at drivers/mmc/omap.c:213!
    # Sep 19 00:17:28 Nokia-N800-37 kernel: [    9.382812] onenand_wait: ECC error = 0x5555
    # Oct 19 17:55:08 Nokia770-42 kernel: [  873.693267] Out of Memory: Kill process 1138 (metalayer-crawl) score 2183 and children.
    # Oct 30 07:04:05 Nokia770-43 kernel: [  555.411865] omapdsp: poll error!
    # Oct 30 07:03:24 Nokia770-43 kernel: [  514.219909] mbox: Illegal seq bit!(54010000) ignored
    # Nov 14 18:32:47 Nokia-N800-45 kernel: [ 3021.950042] TX dropped
    # Nov 10 00:01:47 Nokia770-45 kernel: [111139.518127] We haven't got a READY interrupt from WAKEUP (firmware crashed?).
    # Dec 30 03:07:08 Nokia770-50 DSME: process '/usr/bin/esd' exited and restarted with pid 760
    # Nov 28 19:27:32 Nokia-N800-47 DSME: '/usr/sbin/osso-media-server' spawning too fast -> reset
    # Nov 14 17:39:13 Nokia-N800-45 DSME: process '/usr/sbin/wlancond' with pid 941 exited with return value: 1
    # Jan 11 22:06:36 Nokia770-50 DSME: '/usr/bin/dbus-daemon-1 --system ' exited with RESET policy -> reset
    # Dec 30 03:07:49 Nokia770-50 maemo-launcher[880]: invoking '/usr/bin/ossoemail.launch'
    # Dec 30 11:10:37 Nokia770-50 maemo-launcher[601]: child (pid=774) exited due to signal=6
    # Dec 30 03:45:56 Nokia770-50 Browser 2005.50[1636]: GLIB CRITICAL ** Gtk - gtk_widget_destroy: assertion GTK_IS_WIDGET (widget)' failed
    # Apr 12 17:00:08 Nokia-N800-14 kernel: [ 2122.396057] end_request: I/O error, dev mmcblk0, sector 965286
    # Apr 12 17:00:08 Nokia-N800-14 kernel: [ 2122.412841] Buffer I/O error on device mmcblk0p1, logical block 657144
    # Jan  1 00:02:00 Nokia-NXX-10-2 dbus[1212]: WARNING: match type='signal',sender='org.freedesktop.DBus',path='/org/freedesktop/DBus',interface='org.freedesktop.DBus' added by :1.30 (pid=1226, uid=0) who owns services:
    # Jan  1 00:02:00 Nokia-NXX-10-2 dbus[1212]:  :1.30
    # Jan  1 00:02:00 Nokia-NXX-10-2 dbus[1212]:  org.freedesktop.ohm

    messages = {
        'sysrq':      [],
        'powerkeys':  [],
        'alarms':     [],
        'charger':    [],
        'swresets':   [],
        'hwresets':   [],
        'syslogs':    [],
        'oopses':     [],
        'BUGs':       [],
        'ooms':       [],
        'io_errors':  [],
        'nand_errors':[],
        'dsp_errors': [],
        'dsp_warns':  [],
        'conn_errors':[],
        'dbus_sigs':  [],
        'resets':     [],
        'crashes':    [],
        'restarts':   [],
        'exits':      [],
        'deaths':     [],
        'criticals':  [],
        'warnings':   [],
        'ups_exit':   [],
        'ups_kill':   [],
        'ups_respawn':[],
        'ups_re2f':   [],
    }
    lines = []
    while 1:
        try:
            line = syslog.readline()
        except IOError, e:
            parse_error(write, "ERROR: syslog file '%s': %s" % (file, e))
            break
        if not line:
            break
        line = line.strip()
        # Each line has to be checked for each message because sometimes
        # syslog has different messages on the same line.  This can happen
        # e.g. when the device reboots and we don't want to miss any of them
        #
        # faster to check with find first...
        if line.find(' SysRq ') >= 0:
            messages['sysrq'].append("%s SysRq message" % parse_time(line))
        if line.find(' GLIB ') >= 0:
            parse_glib(messages['criticals'], messages['warnings'], line)
        if line.find('DSME:') >= 0:
            parse_dsme(messages['resets'], messages['restarts'],
                       messages['crashes'], messages['exits'], line)
        if line.find('syslogd ') >= 0:
            parse_restarts(messages['syslogs'], line)
        if line.find('Bootup reason') >= 0:
            parse_bootups(messages['powerkeys'], messages['alarms'], messages['charger'],
                          messages['swresets'], messages['hwresets'], line)
        if line.find('Oops:') >= 0 or line.find('BUG at') >= 0:
            parse_kernel(messages['oopses'], messages['BUGs'], line)
        if line.find('ut of memory') >= 0 or line.find('Memory:') >= 0 or line.find('lowmem:') >= 0:
            parse_oom(messages['ooms'], line)
        if line.find('I/O error') >= 0 or line.find(' onenand') >= 0:
            parse_fs(messages['io_errors'], messages['nand_errors'], line)
        if line.find('mbox:') >= 0 or line.find('omapdsp:') >= 0 or line.find('mbx:') >= 0:
            parse_dsp(messages['dsp_errors'], messages['dsp_warns'], line)
        if line.find('TX dropped') >= 0 or line.find('cx3110x ERROR') >= 0 or line.find('READY interrupt') >= 0:
            parse_connectivity(messages['conn_errors'], line)
        start = line.find('maemo-launcher[')
        if start >= 0:
            parse_launcher(messages['deaths'], lines, line, start)
        if line.find('dbus') >= 0:
            parse_dbus_signal_warning(messages['dbus_sigs'], line)
        if line.find(' init:') >= 0:
            parse_upstart(messages['ups_exit'], messages['ups_kill'], messages['ups_respawn'], messages['ups_re2f'], line)

    syslog.close()
    # check whether we got any errors
    for arr in messages.values():
        if arr:
            return messages
    # no error messages
    return None


# --------------------- Text/HTML output ---------------------------

# Names for different error types.
# NOTE: they are automatically parsed, so don't change them!
error_titles = {
'sysrq':      ["Faulty setup",
  "SysRq messages - serial console enabled without device being attached to dock, device can spuriously reboot at any moment"],
'syslogs':    ["Syslogd restarts",
  "(Not really an error, just something to note.)" ],
'powerkeys':  ["Device booted normally with powerkey (bootup reason)", None],
'alarms':     ["Device alarm wakeups (bootup reason)", None],
'charger':    ["Device charger wakeups (bootup reason)", None],
'swresets':   ["Device HW SW-resets (bootup reason)", None],
'hwresets':   ["Device HW watchdog reboots (bootup reason)", None],
'resets':     ["Device resets by SW watchdog (DSME)",
  "System service crashes causing device to be restarted by DSME"],
'crashes':    ["Crashed system services (from DSME)",
  'Life-guarded system services crashing to <a href="#signals">signals about serious errors</a>'],
'restarts':   ["System service restarts (from DSME)",
  "Life-guarded system services restarted by the DSME SW watchdog"],
'exits':      ["Terminated system services (from DSME)", None],
'oopses':     ["Kernel Oopses", None],
'BUGs':       ["Kernel BUGs", None],
'ooms':       ["Kernel memory shortage issues", None],
'io_errors':  ["Kernel I/O errors (FAT issues)", None],
'nand_errors':["Kernel NAND issues (bad blocks etc)", None],
'dsp_errors': ["DSP errors", None],
'dsp_warns':  ["DSP warnings", None],
'conn_errors':["Connectivity errors", None],
'dbus_sigs':  ["DBus signal matching warnings (using too wide match pattern)", None],
'deaths':     ["Maemo-launched applications which crashed",
  'See <a href="#signals">the explanation of signals</a>'],
'criticals':  ["Glib reported errors",
  "Behaviour of a program logging CRITICAL error is undefined"],
'warnings':   ["Glib warnings", None],
'ups_exit':   ["Terminated system services (from Upstart)", None],
'ups_kill':   ["Killed system services (from Upstart)",
  'See <a href="#signals">the explanation of signals</a>'],
'ups_respawn':["Restarted system services (from Upstart)", None],
'ups_re2f':   ["Too fast restarting system services (from Upstart)",
  "The process has restarted too many times in a small period of time, so Upstart has decided not to restart it anymore"],
}

# Dicts are not sorted, so we need a lookup array
title_order = [
    'sysrq',
    'hwresets',
    'swresets',
    'alarms',
    'powerkeys',
    'resets',
    'crashes',
    'restarts',
    'exits',
    'ups_kill',
    'ups_exit',
    'ups_respawn',
    'ups_re2f',
    'oopses',
    'BUGs',
    'ooms',
    'io_errors',
    'nand_errors',
    'dsp_errors',
    'dsp_warns',
    'conn_errors',
    'dbus_sigs',
    'deaths',
    'criticals',
    'warnings',
    'syslogs'
]

def explain_signals(write):
        write("""
<a name="signals"></a>
<h2>Crash signals explained</h2>
<p>Explanations of some common exit signals on the Maemo platform:
<table border="1">
<tr><th>Signal nro:</th><th>Signal name:</th><th>Usual meaning:</th></tr>
<tr><td>15</td><td>SIGTERM</td><td>Application was unresponsive so system terminated it.
Other reasons for termination are background killing, locale change and shutdown.
For the first case application should catch it and call exit() so that its clipboard
contents are saved to system clipboard.</td></tr>
<tr><td>11</td><td>SIGSEGV</td><td>Process crashed to memory access error</td></tr>
<tr><td>9</td><td>SIGKILL</td><td>Application was very unresponsive and/or didn't react to SIGTERM so system forcibly terminated it</td></tr>
<tr><td>6</td><td>SIGABORT</td><td>Program (glibc/glib) called abort() when a fatal program error was detected</td></tr>
<tr><td>7</td><td>SIGBUS</td><td>DSP was reseted so system terminated the DSP clients to get them restarted (or bad memory access)</td></tr>
<table>
""")


def list_issues(write, dict1, dict2, key, idx):
    "list issues from list2 which are not in list1 using given write function"
    if dict1 and dict1.has_key(key):
        list1 = dict1[key]
    else:
        list1 = []
    if not (dict2 and dict2.has_key(key)):
        return 0
    list2 = dict2[key]
    
    old_len = len(list1)
    new_len = len(list2)
    heading = error_titles[key][0]
    if old_len and (old_len > new_len or list1[0] != list2[0] or list1[old_len-1] != list2[old_len-1]):
        parse_error(write, "Warning: previous round '%s' list (%d items)\n doesn't match one for the current round (%d items)!" % (heading, old_len, new_len))
        old_len = 0
    if new_len == old_len:
        return 0

    # list issues regardless of errors
    if use_html:
        write('\n<a name="%s-%d"></a>' % (key, idx))
        write("<h4>%s</h4>\n" % heading)
        notes = error_titles[key][1]
        if notes:
            # show notes only in HTML format
            write("<p>%s:\n" % notes)
        write("<ul>\n")
        for line in list2[old_len:]:
            write("<li>%s</li>\n" % line)
        write("</ul>\n")
    else:
        write("\n%s:\n" % heading)
        for line in list2[old_len:]:
            print line
    # return number of issues
    return len(list2[old_len:])


def output_errors(write, run1, run2, idx = 0):
    """output different error categories using the given write function.
    return how many of each of them were"""

    errors = {}
    for key in title_order:
        errors[key] = list_issues(write, run1, run2, key, idx)
    return errors


def errors_summary(stats, url = "", color = "", idx = 0):
    """outputs summary of the given error statistics.  If url is given,
    link items with errors to given url, otherwise color table differently"""
    if use_html:
        errors = 0
        if color:
            color = 'bgcolor="#%s"' % color
        print "\n<p><table border=1 %s>" % color
        print "<caption><i>Items logged to syslog</i></caption>"
        print "<tr><th>Error types:</th><th>Count:</th></tr>"
        for key in title_order:
            if not stats.has_key(key):
                continue
            value = stats[key]
            title = error_titles[key][0]
            if not value:
                continue
            if url:
                title = '<a href="%s#%s-%d">%s</a>' % (url, key, idx, title)
            print "<tr>"
            print "<td align=left>%s</td>" % title
            print "<td align=right>%d</td>" % value
            print "</tr>"
            errors += value
        print "<tr><td align=right><i>Total of items =</i></td><td align=right><b>%d</b></td></tr>" % errors
        print "</table>"
    else:
        for key in title_order:
            print "- %d %s" % (stats[key], error_titles[key][0])


def errors_add(stats, stat):
    "adds new stats (from output_errors()) to existing stats"
    for key, value in stat.items():
        if key in stats:
            stats[key] += value
        else:
            stats[key] = value


def output_html_report(files):
    "outputs lists of errors from given syslog files in HTML format"
    global use_html
    use_html = 1
    write = sys.stdout.write
    title = "Syslog report"
    print """<html>
<head>
<title>%s</title>
</head>
<body>
<h1>%s</h1>
""" % (title, title)
    idx = 0
    for path in files:
        run = parse_syslog(write, open_compressed(path, FATAL)[0])
        print "<h1>%s</h2>" % os.path.basename(path)
        print "<font size=-1>(%s)</font>" % path
        if run:
            print "<p><b>Contents:</b><ul>"
            for key in title_order:
                print '<li><a href="#%s-%d">%s</a>' % (key, idx, error_titles[key][0])
            print '<li><a href="#summary-%d">Summary</a>' % idx
            print "</ul>"
            
            stat = output_errors(write, {}, run, idx)
            print "<hr>"
            print '<a name="summary-%d"></a>' % idx
            print "<h2>Summary</h2>"
            errors_summary(stat)
            idx += 1
        else:
            print "<p>No notifiable syslog items identified."
        print "<hr>\n"
    print explain_signals(write)
    print "</body>\n</html>"


def output_text_report(files):
    "outputs lists of errors from given syslog files in ASCII format"
    global use_html
    use_html = 0
    write = sys.stdout.write
    print """
Syslog report
============="""
    for path in files:
        print
        print path
        print "-" * len(path)
        run = parse_syslog(write, open_compressed(path, FATAL)[0])
        if run:
            stat = output_errors(write, {}, run)
            print
            print "Summary:"
            print "- ------"
            errors_summary(stat)
        else:
            print
            print "No notifiable syslog items identified."


def __help(error=''):
    msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
    sys.stderr.write(msg)
    if error:
        sys.stderr.write("\n\nERROR: %s\n\n" % error)
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        __help()
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    if sys.argv[1][0] == "-":
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            __help()
        else:
            __help("unknown option: %s" % sys.argv[1])
    else:
        output_text_report(sys.argv[1:])
