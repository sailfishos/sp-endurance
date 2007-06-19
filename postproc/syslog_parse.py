#!/usr/bin/python
# -*- indent-tabs-mode: t -*-
# This file is part of sp-endurance.
#
# Copyright (C) 2006,2007 by Nokia Corporation
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
"""
NAME
	<TOOL_NAME>

SYNOPSIS
	<TOOL_NAME> <syslog1> [syslog2 ...]

DESCRIPTION

This script parses different kinds of issues from given syslog files:
    - Device bootups (based on boot reasons and syslog restarts)
    - SysRq messages indicating faulty device setup
    - Kernel Oopses
    - DSP errors and warnings
    - DSME reported system service restarts and reboots
    - Maemo-launcher reported application crashes
    - Critical errors and warnings reported by Glib
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


OPTIONS

When run as a program, you can use either of these options (not both):
	--html         Use HTML output (text output is default)
	--debug=value  Complain about matched, but unknown syslog rows
	
EXAMPLES
	<TOOL_NAME> --html syslog1 syslog2 > syslog-errors.html
	<TOOL_NAME> --debug=all syslog1 syslog2 > syslog-errors.txt
"""

import sys, os, re, string, gzip


# whether to use HTML output or not
use_html = 1

# sysrq/syslog/kernel/io/dsp/connectivity/dsme/glib/launcher/all
verbose = ""
verbose_options = [
"sysrq", "bootup", "syslog", "kernel", "io", "dsp", "connectivity", "dsme", "glib", "all"
]


def parse_error(write, error):
    "outputs error/warning both to stderr and as HTML using given write func"
    if use_html:
	write("<p><font color=red>%s</font>\n" % error)
    sys.stderr.write("%s\n" % error)


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


# --------------------- sysrq parsing ---------------------------

sysrq_msg = re.compile(" (\d+:\d+:\d+) .* SysRq .*$")

def parse_sysrq(sysrq, line):
    "appends to given array sysrq timestamps"
    match = sysrq_msg.search(line)
    if match:
	sysrq.append("SysRq message at %s" % match.group(1))
    elif verbose in [ "all", "sysrq" ]:
	sys.stderr.write("Warning: sysrq pattern didn't match:\n  %s\n" % line)


# --------------------- bootup parsing ---------------------------

bootup_reason = re.compile(" (\d+:\d+:\d+) .* Bootup reason: (.*)$")

def parse_bootups(powerkeys, alarms, swresets, hwresets, line):
    "appends to given array simplified bootup reason messages"
    match = bootup_reason.search(line)
    if match:
	time = match.group(1)
	reason = match.group(2)
	if reason == "pwr_key":
	    return powerkeys.append("%s user had booted the device" % time)
	elif reason == "rtc_alarm":
	    return alarms.append("%s alarm had woken up the device" % time)
	elif reason == "sw_rst":
	    return swresets.append("%s SW watchdog had rebooted the device" % time)
	elif reason == "32wd_to":
	    return hwresets.append("%s HW watchdog had rebooted the device" % time)
    if verbose in [ "all", "bootup" ]:
	sys.stderr.write("Warning: bootup reason pattern didn't match:\n  %s\n" % line)


# --------------------- restart parsing ---------------------------

syslog_restart = re.compile(" (\d+:\d+:\d+) [^:]* syslogd .* restart.*$")

def parse_restarts(restarts, line):
    "appends to given array simplified syslogd (=device) restart message"
    match = syslog_restart.search(line)
    if match:
	restarts.append("%s syslogd restart" % match.group(1))
    elif verbose in [ "all", "syslog" ]:
	sys.stderr.write("Warning: syslog pattern(s) didn't match:\n  %s\n" % line)


# --------------------- Kernel parsing ---------------------------

kernel_oops = re.compile(" (\d+:\d+:\d+) .* kernel: .* Oops: (.*)$")
kernel_oom = re.compile(" (\d+:\d+:\d+) .* kernel: .* (Out of Memory: Kill|lowmem: denying memory)(.*)$")

def parse_kernel(oopses, ooms, line):
    "appends to given array simplified kernel Oops message line"
    match = kernel_oops.search(line)
    if match:
	oopses.append("%s Kernel Oops: %s" % match.groups())
    else:
	match = kernel_oom.search(line)
	if match:
	    ooms.append("%s %s%s" % match.groups())
	elif verbose in [ "all", "kernel" ]:
	    sys.stderr.write("Warning: kernel pattern(s) didn't match:\n  %s\n" % line)


# --------------------- I/O error parsing ---------------------------

io_error = re.compile(" (\d+:\d+:\d+) .* kernel: [^]]*[]] (.*)$")

def parse_io(errors, line):
    "appends to given array simplified kernel I/O error messages"
    match = io_error.search(line)
    if match:
	errors.append("%s %s" % match.groups())
    elif verbose in [ "all", "io" ]:
	sys.stderr.write("Warning: I/O error pattern(s) didn't match:\n  %s\n" % line)


# --------------------- DSP error parsing ---------------------------

dsp_error = re.compile(" (\d+:\d+:\d+) .* (mbox: Illegal seq bit.*|omapdsp: poll error.*)$")
dsp_warn = re.compile(" (\d+:\d+:\d+) .* (mbx: ERR.*)$")

def parse_dsp(errors, warnings, line):
    "appends to given array simplified DSP error or warning message"
    match = dsp_error.search(line)
    if match:
	errors.append("%s %s" % match.groups())
    else:
	match = dsp_warn.search(line)
	if match:
	    warnings.append("%s %s" % match.groups())
	elif verbose in [ "all", "dsp" ]:
	    sys.stderr.write("Warning: DSP pattern(s) didn't match:\n  %s\n" % line)


# ----------------- Connectivity error parsing ---------------------------

conn_error = re.compile(" (\d+:\d+:\d+) .*(cx3110x ERROR.*|TX dropped.*|We haven't got a [A-Z_]+ interrupt from [A-Z_]+.*)$")

def parse_connectivity(errors, line):
    "appends to given array simplified Connectivity error or warning message"
    match = conn_error.search(line)
    if match:
	errors.append("%s %s" % match.groups())
    elif verbose in [ "all", "connectivity" ]:
	sys.stderr.write("Warning: connectivity pattern(s) didn't match:\n  %s\n" % line)


# --------------------- DSME error parsing ---------------------------

dsme_respawn = re.compile(" (\d+:\d+:\d+) .* DSME:[^']* '([^']+)' spawning too fast -> reset")
dsme_reset = re.compile(" (\d+:\d+:\d+) .* DSME:[^']* '([^']+)' exited (with RESET|and restarted)")
dsme_signal = re.compile(" (\d+:\d+:\d+) .* DSME:[^']* '([^']+)' with pid ([0-9]+) exited with signal: ([0-9]+)")
dsme_exit = re.compile(" (\d+:\d+:\d+) .* DSME:[^']* '([^']+)' with pid ([0-9]+) (exited with return value: .*)")

def parse_dsme(resets, restarts, crashes, exits, line):
    "appends to given array simplified DSME device reset or process restart message"
    match = dsme_signal.search(line)
    if match:
	signum, signal = parse_signal(match.group(4))
	output = (match.group(1), match.group(2), match.group(3), signal)
	# termination requests: HUP, INT, TERM
	if signum in (1, 2, 15):
	    exits.append("%s %s[%s]: exited with %s" % output)
	else:
	    # kills
	    crashes.append("%s %s[%s]: exited with %s" % output)
	return
    match = dsme_reset.search(line)
    if match:
	output = (match.group(1), match.group(2))
	if match.group(3) == "with RESET":
	    resets.append("%s %s (RESET)" % output)
	else:
	    restarts.append("%s %s" % output)
	return
    match = dsme_exit.search(line)
    if match:
	    exits.append("%s %s[%s]: %s" % match.groups())
	    return
    match = dsme_respawn.search(line)
    if match:
	    resets.append("%s %s (RESET)" % match.groups())
	    return
    if verbose in [ "all", "dsme" ]:
	sys.stderr.write("Warning: DSME patterns didn't match:\n  %s\n" % line)


# --------------------- GLIB error parsing ---------------------------

#glib_pattern = re.compile(" (\S+): GLIB (WARNING|CRITICAL) \*\* (.*)$")
glib_pattern = re.compile(" (\d+:\d+:\d+) [-0-9A-Za-z.]+ (.*[]]+): GLIB (WARNING|CRITICAL|ERROR) \*\* (.*)$")

def parse_glib(criticals, warnings, line):
    "appends to given array simplified Glib critical error or warning"
    match = glib_pattern.search(line)
    if match:
	output = (match.group(1), match.group(2), match.group(4))
	if match.group(3) == "ERROR":
	    criticals.append("%s %s (ERROR): %s" % output)
	elif match.group(3) == "CRITICAL":
	    criticals.append("%s %s (CRITICAL): %s" % output)
	else:
	    warnings.append("%s %s: %s" % output)
    elif verbose in [ "all", "glib" ]:
	sys.stderr.write("Warning: GLIB WARNING/CRITICAL pattern(s) did not match:\n  %s\n" % line)


# --------------------- maemo-launcher parsing ---------------------------

time_pattern = re.compile(" (\d+:\d+:\d+) ")

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
		app = check[check.find("invoking")+10:-1].split('/')[-1]
		time = time_pattern.search(line).group(1)
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


# --------------------- syslog parsing ---------------------------

def parse_syslog(write, file):
    "parses DSP, connectivity, DSME, Maemo-launcher and Glib reported errors from syslog"
    # Syslog entry examples:
    # Nov 16 01:53:52 Nokia770-44 syslogd 1.4.1#17.osso1: restart.
    # Feb 26 20:19:53 Nokia-N800-08 kernel: [ 9899.620422] Bootup reason: sw_rst
    # Oct 23 14:16:53 Nokia770-42 kernel: [44449.006805] Internal error: Oops: 7 [#1]
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

    if not os.path.exists(file):
	parse_error(write, "ERROR: syslog file '%s' doesn't exist!" % file)
	sys.exit(1)

    if file[-3:] == ".gz":
	syslog = gzip.open(file, "r")
    else:
	syslog = open(file, "r")

    messages = {
	'sysrq':      [],
	'powerkeys':  [],
	'alarms':     [],
	'swresets':   [],
	'hwresets':   [],
	'reboots':    [],
	'oopses':     [],
	'ooms':       [],
	'io_errors':  [],
	'dsp_errors': [],
	'dsp_warns':  [],
	'conn_errors':[],
	'resets':     [],
	'crashes':    [],
	'restarts':   [],
	'exits':      [],
	'deaths':     [],
	'criticals':  [],
	'warnings':   []
    }
    lines = []
    while 1:
	line = syslog.readline()
	if not line:
	    break
	line = line.strip()
	# Each line has to be checked for each message because sometimes
	# syslog has different messages on the same line.  This can happen
	# e.g. when the device reboots and we don't want to miss any of them
	#
	# faster to check with find first...
	if line.find(' SysRq ') >= 0:
	    parse_sysrq(messages['sysrq'], line)
	if line.find(' GLIB ') >= 0:
	    parse_glib(messages['criticals'], messages['warnings'], line)
	if line.find('DSME:') >= 0:
	    parse_dsme(messages['resets'], messages['restarts'],
	               messages['crashes'], messages['exits'], line)
	if line.find('syslogd ') >= 0:
	    parse_restarts(messages['reboots'], line)
	if line.find('Bootup reason') >= 0:
	    parse_bootups(messages['powerkeys'], messages['alarms'],
	                  messages['swresets'], messages['hwresets'], line)
	if line.find('Oops:') >= 0 or line.find('Memory:') >= 0 or line.find('lowmem:') >= 0:
	    parse_kernel(messages['oopses'], messages['ooms'], line)
	if line.find('I/O error') >= 0:
	    parse_io(messages['io_errors'], line)
	if line.find('mbox:') >= 0 or line.find('omapdsp:') >= 0 or line.find('mbx:') >= 0:
	    parse_dsp(messages['dsp_errors'], messages['dsp_warns'], line)
	if line.find('TX dropped') >= 0 or line.find('cx3110x ERROR') >= 0 or line.find('READY interrupt') >= 0:
	    parse_connectivity(messages['conn_errors'], line)
	start = line.find('maemo-launcher[')
	if start >= 0:
	    parse_launcher(messages['deaths'], lines, line, start)

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
'reboots':    ["Device (syslogd) restarts", None],
'powerkeys':  ["Device booted normally with powerkey", None],
'alarms':     ["Device alarm wakeups", None],
'swresets':   ["Device SW watchdog reboots", None],
'hwresets':   ["Device HW watchdog reboots", None],
'resets':     ["Device resets by SW watchdog",
  "System service crashes causing device to restart"],
'crashes':    ["Crashed system services",
  'Life-guarded system services crashing to <a href="#signals">signals about serious errors</a>'],
'restarts':   ["System service restarts",
  "Life-guarded system services restarted by SW watchdog"],
'exits':      ["Terminated system services", None],
'oopses':     ["Kernel Oopses", None],
'ooms':       ["Kernel memory shortage issues", None],
'io_errors':  ["Kernel I/O errors", None],
'dsp_errors': ["DSP errors", None],
'dsp_warns':  ["DSP warnings", None],
'conn_errors':["Connectivity errors", None],
'deaths':     ["Maemo-launched applications which crashed",
  'See <a href="#signals">the explanation of signals</a>'],
'criticals':  ["Glib reported errors",
  "Behaviour of a program logging CRITICAL error is undefined"],
'warnings':   ["Glib warnings", None]
}

# Dicts are not sorted, so we need a lookup array
title_order = [
'sysrq','hwresets','swresets','alarms','powerkeys','reboots','resets','crashes','restarts','exits','oopses','ooms','io_errors','dsp_errors','dsp_warns','conn_errors','deaths','criticals','warnings'
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
	sys.stderr.write("Parsing '%s'...\n" % path)
	run = parse_syslog(write, path)
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
	run = parse_syslog(write, path)
	if run:
	    stat = output_errors(write, {}, run)
	    print
	    print "Summary:"
	    print "- ------"
	    errors_summary(stat)
	else:
	    print
	    print "No notifiable syslog items identified."


def help(error=''):
    msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
    sys.stderr.write(msg)
    if error:
	sys.stderr.write("\n\nERROR: %s\n\n" % error)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
	help()
    if sys.argv[1][0] == "-":
	if sys.argv[1] == "--html":
	    output_html_report(sys.argv[2:])
	elif sys.argv[1][:8] == "--debug=":
	    verbose = sys.argv[1][8:]
	    if verbose in verbose_options:
		output_text_report(sys.argv[2:])
	    else:
		help("debug value should be one of:\n  %s" % string.join(verbose_options))
	else:
	    help("unknown option: %s" % sys.argv[1])
    else:
	output_text_report(sys.argv[1:])

