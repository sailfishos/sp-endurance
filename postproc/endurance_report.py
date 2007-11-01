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
# 2006-01-02:
# - First version
# 2006-01-04:
# - Parses everything relevant from current endurance measurements data
# 2006-01-05:
# - Can now parse also syslog which is not pre-processed
# - Parses also DSME reports
# 2006-01-10:
# - Generate a graph of the memory usage increase
# 2006-01-12:
# - Parse also DSME reboot messages and Glib warnings
# - Use red text for processes with critical errors or triggering reboot
# - Show logging time
# 2006-01-20:
# - Show total amount of FDs for processes which changed and
#   warn if system free FD count is low
# - Improved error checking / messages
# - Show software release
# - show new processes
# 2006-01-23:
# - Show initial state errors
# - Show free memory below bg-kill limit as red
# 2006-01-24:
# - Link from overview to each test round
# 2006-01-25:
# - Update memory limits to new values from Leonid
# 2006-01-27:
# - Optionally parse SMAPS diff output and output into HTML
#   table of process memory usage changes
# - Nicer help output
# 2006-01-31:
# - List also exited processes
# - Fixes to SMAPS diff parsing
# - Parse and output also X resource usage differencies
# - Sort fd and memory changes according to totals and new commands
#   according to their names, right align changes and totals
# - Bold low/high memory values
# - Caption all tables
# 2006-02-03:
# - Fix maemo-launcher syslog message parsing
# 2006-03-01:
# - Update to parse output from proc2csv instead of meminfo, parsing
#   /proc/PID/status data for command names is not anymore needed
# 2006-03-14:
# - Update to new DSME log format and output also reasons (signals)
#   for system service restarts
# - Convert signal numbers to names
# 2006-05-03:
# - Change SMAPS diff parsing to parse the new (much changed) diff files
# - Fix regexps to parse additional text that is in some DSME lines
# 2006-05-04:
# - Add links to generated SMAPS HTML files
# 2006-06-05:
# - Add support for dynamic lowmem limits
# 2006-13-05:
# - Support Swap
# - Fix/clarify service crash and signal explanation texts
# 2006-07-06:
# - Fix bug in system free mem calculation introduced by swap support
# 2006-09-28:
# - Show the issues from syslog even if syslogs don't match
# 2006-10-18, from Tuukka:
# - Always print error message before failing exit
# - Make loadable as module, split parse_and_output function
# 2006-11-09:
# - Arguments are directories instead of file names
# - Syslog data is now parsed from file separate from the CSV file
# - Separated syslog parsing to syslog_parse.py
# 2006-11-14:
# - Output disk free changes (for '/' and '/tmp')
# - Show whole device /proc/sys/fs/file-nr changes
# - Output also X resource usage decreases
# - Save errors to separate HTML pages
# - Output statistics and summary of different error types
# - Output summary of memory/X resource/FD usage changes
# 2006-11-16:
# - minor updates for syslog_parse.py
# - Add process changed/total counts
#   - with started/exited processes side by side
#   - remove "sleep" from the lists
# - Color code different tables
# - Add links to DSME stats, syslog, CSV file...
# - Add change totals to all tables, not just errors
# 2006-11-22:
# - HTML comment summary of all statistics (even ones with value zero)
#   for maturity metrics
# - Parse process statistics from /proc/PID/status files
# - Generalize output_memory_graph_table() and add bars of memory
#   usage changes per process (to the overview section) for all processes
#   where RSS (maximum) usage changes, sorted according to RSS
# - Re-organize and fine-tune the output file to be more readable,
#   and contents with links etc
# - Remove "sleep" from *all* the lists
# 2006-11-28:
# - Fix bug in case none of the syslogs had errors
# 2006-12-05:
# - Fix (another) bug in case some syslog didn't have any errors
# 2006-12-14:
# - Add link to the previous round error page
# 2007-01-05:
# - Do bargraphs with tables instead of images, this way the report
#   works even when sent as email or attached to Bugzilla
# 2007-01-28:
# - Fix error message (gave Python exception)
# - Show FS usage, not free
# - Process memory usage graphs:
#   - sort in this order: name, first round in which process appears, pid
#   - differentiate processes by name+pid instead just by pid
#     (if device had rebooted and some other process got same pid,
#     earlier results were funny)
#   - show successive rounds without process with just one line
# 2007-02-07:
# - sp-smaps-visualize package scripts are way too slow,
#   added my own parsing of SMAPS Private_Dirty numbers to here
#   - Ignore values for memory mapped devices
# - Output process statuses in the processes RSS change list
# 2007-02-08:
# - cleanup SMAPS stuff
# 2007-02-15:
# - fix memory usage bars for the case when deny limit is crossed
# - In process memory bars:
#   - for rounds where the value doesn't change, replace the header
#     with: "Rounds X-Y"
#   - only if >0.2% memory change per round in RSS or Size, show the change
# 2007-02-16:
# - show busyness only if SleepAVG < 90%
# - have numbers in different columns in graph
# 2007-03-09:
# - check in how many rounds size increases before skipping process memory bars
# 2007-03-13:
# - Parse&show total amount of system private dirty code pages
# - Olev asked /dev/ files to be counted from SMAPS data too
#   in case somebody would leak e.g. dsptasks...
# 2007-04-12:
# - In process memory bars:
#   - Fix how threads are indentified for removal from memory usage graphs
#   - Show process if RSS changes in enough rounds (not just increases)
# 2007-04-16:
# - Cope with missing SMAPS data
# - Do not ignore any processes
# 2007-04-18:
# - List also changes in kernel threads and zombie processes
# - Handle usage.csv data with (incorrect) extra columns
# - Fix to new thread ignore code
# 2007-04-25:
# - Ignore extra threads in all resource usage lists
# - Add script version to reports (as HTML comment)
# 2007-05-03:
# - Sort resource usage tables according to changes, not total
# - Fix to get_pid_usage_diffs() 
# 2007-10-31:
# - Link list of open file descriptors and smaps.cap
# - Show differences in process thread counts
# TODO:
# - Mark reboots more prominently also in report (<h1>):
#   - dsme/stats/32wd_to -> HW watchdog reboot
#   - dsme/stats/sw_rst -> SW watchdog reboots
#   - bootreason -> last boot
# - Proper option parsing + possibility to state between which
#   test runs to produce the summaries?
# - Should the app memory usage changes uses SMAPS instead of RSS?
#   (it's good to have different sources so that one can compare though)
# - Show differences in slabinfo and vmstat numbers (pswpin/pswpout)?
"""
NAME
        <TOOL_NAME>

SYNOPSIS
        <TOOL_NAME> <data directories>

DESCRIPTION

This script reads data files produced by the SYTE endurance measurement
tools.   The data is gathered from proc, X server, SMAPS, syslog etc.

By default all arguments are assumed to be names of directories
containing (at least):
    - usage.csv   -- /proc/ info + X resource & disk usage in CSV format
    - slabinfo    -- information about kernel caches, see slabinfo(5)
    - stat        -- kernel/system statistics, see proc(5)
    - syslog[.gz] -- [compressed] syslog contents

As an output, it produces an HTML page listing/highlighting differencies
between the CSV, SMAPS and syslog files for the following values:
    - Graph of system free memory changes
    - Memory usages for processes which private memory usage
      changes (as reported by sp_smaps_snapshot)
    - Number of file descriptors used by the (system) processes
    - Number of logged errors (from syslog)
The errors in syslog are output to a separate file.
        
EXAMPLES
        <TOOL_NAME> usecase/ usecase2/ > report.html
"""

import sys, os, re
import syslog_parse as syslog

# CSV field separator
SEPARATOR = ','

# these are HTML hex color values for different tables
class Colors:
    errors = "FDEEEE"
    disk = "EEFDFD"
    memory = "EEEEFD"
    threads = "CFEFEF"
    xres = "FDEEFD"
    fds = "FDFDEE"

# color values for memuse, memfree, oom-limit
bar1colors = ("3149BD", "ADE739", "DE2821")        # blue, green, red
# color values for rss, size
bar2colors = ("DE2821", "EAB040")                # red, orange

# --------------------- SMAPS data parsing --------------------------

# address range, access rights, page offset, major:minor, inode, mmap()ed item
smaps_mmap = re.compile("^[-0-9a-f]+ ([-rwxps]+) [0-9a-f]+ [:0-9a-f]+ \d+ *(|[^ ].*)$")

# data from sp_smaps_snapshot
def parse_smaps(filename):
    "parse SMAPS and return process pid, private memory value array"
    file = open(filename)
    private_code = code = sum = idx = 0
    data = {}
    while 1:
        line = file.readline()
        if not line:
            if sum:
                #print "INSERT"        #DEBUG
                data[pid] = sum
            break
        idx += 1
        line = line.strip()
        if not line:
            continue
        #print line        #DEBUG
        first = line[0]
        if first == '=':
            # ==> /proc/767/smaps <==
            if sum:
                #print "INSERT"        #DEBUG
                data[pid] = sum
            # new process
            pid, sum = 0, 0
            #print "CLEAR"        #DEBUG
            continue
        if first == '#':
            if line.find("#Pid: ") == 0:
                pid = line[6:]
            #print "PID"        #DEBUG
            continue
        if not pid:
            # sanity check
            sys.stderr.write("ERROR: Pid missing for SMAPS line %d:\n  %s\n" % (idx, line))
            sys.exit(1)
        match = smaps_mmap.search(line)
        if match:
            # bef45000-bef5a000 rwxp bef45000 00:00 0          [stack]
            mmap = match.group(2)
            # code memory map = executable (..x.) and file (/path/...)?
            if match.group(1)[2] == 'x' and mmap and mmap[0] == '/':
                #debug_line = match.group(0)
                code = 1
            else:
                code = 0
            #print "MMAP"        #DEBUG
            continue
        if line.find("Private_Dirty:") == 0:
            amount = int(line[15:-2])
            if code and amount:
                #print debug_line
                #print mmap, code, amount
                private_code += amount
            # Private_Dirty:        0 kB
            #if mmap[:5] == "/dev/":
            #        # ignore memory mapped devices because RSS/Size don't
            #        # (usually?) count them:
            #        # 40008000-400c4000 rw-s 87e00000 00:0d 1354       /dev/fb0
            #        #print "DEV"        #DEBUG
            #        continue
            sum += amount
            #print "ADD"        #DEBUG
            continue
        # sanity check that mmap lines are not missed
        if (line[0] >= '0' and line[0] <= '9') or (line[0] >= 'a' and line[0] <= 'f'):
            sys.stderr.write("ERROR: SMAPS mmap line not matched:\n  %s\n" % line)
            sys.exit(1)
    #print data #DEBUG
    return (data, private_code)


# --------------------- CSV parsing ---------------------------

def get_filesystem_usage(file):
    """reads Filesystem,1k-blocks,Used,Available,Use%,Mountpoint fields
    until empty line, returns hash of free space on interesting mountpoints
    """
    mounts = {}
    # device root and tmpfs with fixed size
    keep = {'/':1, '/tmp':1}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        fs,blocks,used,available,inuse,mount = line.split(',')
        if mount not in keep:
            continue
        mounts[mount] = int(used)
    return mounts


def get_xclient_memory(file):
    "reads X client resource usage, return command hash of total X mem usage"
    clients = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        mem,pid,name = line.split(',')[8:11]
        if mem[-1] == 'B':
            mem = int(mem[:-1])
        else:
            sys.stderr.write("Error: X resource total memory value not followed by 'B':\n  %s\n" % line)
            sys.exit(1)
        # in KBs, check on clients taking > 1KB
        if mem >= 1024:
            clients[name] = mem/1024
    return clients


def get_process_info(file, headers):
    """returns all process information in a hash indexed by the process PID,
    containing hash of information provided by the /proc/PID/status file
    (proc entry field name works as the hash key)
    """
    kthreads = {}
    processes = {}
    fields = headers.strip().split(',')
    fields[-1] = fields[-1].split(':')[0]        # remove ':' from last field
    pididx = fields.index('Pid')
    nameidx = fields.index('Name')
    while 1:
        line = file.readline().strip()
        if not line:
            break
        item = {}
        info = line.split(',')
        # kernel threads & zombies don't have all the fields
        if len(info) < len(fields):
            kthreads[info[pididx]] = info[nameidx]
            continue
        elif len(info) > len(fields):
            sys.stderr.write("WARNING: Process [%s] has extra column(s) in CSV data!\n" % info[pididx])
        for idx in range(len(fields)):
            if info[idx][-3:] == " kB":
                # convert memory values to integers
                item[fields[idx]] = int(info[idx][:-3])
            else:
                item[fields[idx]] = info[idx]
        processes[item['Pid']] = item
    return processes, kthreads


def get_commands_and_fd_counts(file):
    """reads fdcount,pid,command lines until empty line,
    returns pid hashes of command names and fd counts"""
    commands = {}
    fd_counts = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        pid,fds,name = line.split(',')
        commands[pid] = name
        fd_counts[pid] = int(fds)
    return (commands,fd_counts)


def get_meminfo(data, headers, values):
    "adds meminfo values to data"
    headers = headers.split(',')
    values = values.split(',')
    mem = {}
    for i in range(len(values)):
        # remove 'kB'
        mem[headers[i]] = int(values[i].split(" kB")[0])
    total = mem['MemTotal']
    free = mem['MemFree']
    buffers = mem['Buffers']
    cached = mem['Cached']
    swaptotal = mem['SwapTotal']
    swapfree = mem['SwapFree']
    
    data['memtotal'] = total + swaptotal
    data['memfree'] = free + buffers + cached + swapfree
    data['memused'] = data['memtotal'] - data['memfree']
    data['swapused'] = swaptotal - swapfree


def skip_to(file, header):
    "reads the given file until first CSV column has given header"
    l = len(header)
    while 1:
        line = file.readline()
        if not line:
            sys.stderr.write("\nError: premature file end, CSV header '%s' not found\n" % header)
            sys.exit(2)
        if line[:l] == header:
            return line


def parse_csv(filename):
    "Parses interesting information from the endurance measurement CSV file"
    data = {}
    file = open(filename)
    # filename without the extension
    data['basedir'] = os.path.dirname(filename)
    
    # Check that file is generated with correct script so that
    # we can trust it's format and order of rows & fields:
    # format: generator = <generator name> <version>
    mygen = "syte-endurance-stats"
    generator = file.readline().strip().split(' ')
    if len(generator) < 3 or generator[2] != mygen:
        sys.stderr.write("\nError: CSV file '%s' is not generated by '%s'!\n" % (filename, mygen))
        sys.exit(1)
    
    # get the basic data
    file.readline()
    data['release'] = file.readline().strip()
    data['datetime'] = file.readline().strip()
    if data['release'][:2] != "SW" or data['datetime'][:4] != "date":
        sys.stderr.write("\nError: CSV file '%s' is missing 'SW-version' or 'date' fields!\n" % filename)
        sys.exit(1)

    # total,free,buffers,cached
    mem_header = skip_to(file, "MemTotal").strip()
    mem_values = file.readline().strip()
    get_meminfo(data, mem_header, mem_values)

    # low memory limits
    skip_to(file, "lowmem_")
    mem = file.readline().split(',')
    if len(mem) == 3:
        data['limitlow'] = int(mem[0])
        data['limithigh'] = int(mem[1])
        data['limitdeny'] = int(mem[2])
    else:
        # not fatal as lowmem stuff is not in standard kernel
        sys.stderr.write("\nWarning: CSV file '%s' lowmem limits are missing!\n" % filename)
        data['limitlow'] = data['limithigh'] = data['limitdeny'] = 0

    # get system free FDs
    skip_to(file, "Allocated FDs")
    fdused,fdfree,fdtotal = file.readline().split(',')
    data['fdfree'] = (int(fdtotal) - int(fdused)) + int(fdfree)

    # get the process FD usage
    skip_to(file, "PID,FD count,Command")
    data['commands'], data['fdcounts'] = get_commands_and_fd_counts(file)
    
    # get process statistics
    headers = skip_to(file, "Name,State,")
    data['processes'], data['kthreads'] = get_process_info(file, headers)
    
    # get the X resource usage
    skip_to(file, "res-base")
    data['xclients'] = get_xclient_memory(file)
    
    # get the file system usage
    skip_to(file, "Filesystem")
    data['mounts'] = get_filesystem_usage(file)
    
    # alles clar
    file.close()
    return data

# --------------------- HTML output ---------------------------

def get_pids_from_procs(processes, commands):
    "return pid:name dictionary for given processes array"
    pids = {}
    for process in processes.values():
        pid = process['Pid']
        name = process['Name']
        if name == "maemo-launcher":
            # commands array takes the name from /proc/PID/cmdline
            pids[pid] = commands[pid]
        else:
            pids[pid] = name
    return pids
        
def output_process_changes(pids1, pids2, titles, do_summary):
    "outputs which commands are new and which gone in separate columns"
    # ignore re-starts i.e. check only command names
    gone = []
    new_coms = []
    new_pids = []
    for pid in pids2:
        if pid not in pids1:
            new_coms.append("%s[%s]" % (pids2[pid], pid))
    for pid in pids1:
        if pid not in pids2:
            gone.append("%s[%s]" % (pids1[pid], pid))
    change = 0
    if gone or new_coms or new_pids:
        processes = len(pids2)
        change = processes - len(pids1)
        print "<p>%s: <b>%d</b>" % (titles[0], change)
        print "<br>(now totaling %d)." % processes

        print "<p><table border=1>"
        print "<tr><th>%s</th><th>%s</th><tr>" % (titles[1], titles[2])
        print "<tr><td>"
        if gone:
            print "<ul>"
            gone.sort()
            for name in gone:
                print "<li>%s" % name
            print "</ul>"
        print "</td><td>"
        if new_coms or new_pids:
            print "<ul>"
            new_coms.sort()
            for name in new_coms:
                print "<li>%s" % name
            new_pids.sort()
            for name in new_pids:
                print "<li>%s" % name
            print "</ul>"
        print "</td></tr></table>"
    if do_summary:
        print "<!--\n- %s: %+d\n-->" % (titles[0], change)


def output_diffs(diffs, title, colname, colamount, colors, do_summary):
    "output diffs of data: { difference, total, name }"
    total = 0
    if diffs:
        diffs.sort()
        diffs.reverse()
        print '\n<p><table border=1 bgcolor="#%s">' % colors
        print "<caption><i>%s</i></caption>" % title
        print "<tr><th>%s:</th><th>Change:</th><th>Total:</th></tr>" % colname
        for data in diffs:
            total += data[0]
            print "<tr><td>%s</td><td align=right><b>%+d</b>%s</td><td align=right>%d%s</td></tr>" % (data[2], data[0], colamount, data[1], colamount)
        print "<tr><td align=right><i>Total change =</i></td><td align=right><b>%+d%s</b></td><td>&nbsp;</td>" % (total, colamount)
        print "</table>"
    if do_summary:
        print "<!--\n- %s change: %+d\n-->" % (title, total)
    
    
def get_usage_diffs(list1, list2):
    """return {total, name, diff} hash of differences in numbers between
    two {name:value} hashes"""
    diffs = []
    for name,value2 in list2.items():
        if name in list1:
            value1 = list1[name]
            if value2 != value1:
                # will be sorted according to first column
                diffs.append((value2 - value1, value2, name))
    return diffs


def pid_is_main_thread(pid, commands, processes):
    "return true if PID is the main thread, otherwise false"
    # command list has better name than process list
    process = processes[pid]
    ppid = process['PPid']
    name = commands[pid]
    if ppid != '1' and ppid in commands and name == commands[ppid]:
        # parent has same name as this process...
        if ppid in processes and process['VmSize'] == processes[ppid]['VmSize']:
            # and also size
            # -> assume it's a thread which should be ignored
            return 0
    return 1


def get_pid_usage_diffs(commands, processes, values1, values2):
    """return {diff, total, name} hash of differences in numbers between
    two {pid:value} hashes, remove threads based on given 'processes' hash
    and name the rest based on the given 'commands' hash"""
    diffs = []
    for pid in values2:
        if pid in values1:
            c1 = values1[pid]
            c2 = values2[pid]
            if c1 != c2:
                if pid not in processes or pid not in commands:
                    sys.stderr.write("Warning: PID %s not in commands or processes\n" % pid)
                    continue
                if not pid_is_main_thread(pid, commands, processes):
                    continue
                name = commands[pid]
                # will be sorted according to first column (i.e. change)
                diffs.append((c2-c1, c2, "%s[%s]" % (name, pid)))
    return diffs


def get_thread_count_diffs(commands, processes1, processes2):
    """return { difference, total, name } hash where name is taken from
    'commands', total is taken from 'processes2', and differences in
    thread counts is between 'processes2'-'processes1' and all these
    are matched by pids."""
    diffs = []
    for pid in commands:
        if pid in processes2 and pid in processes1:
            name = commands[pid]
            t1 = processes1[pid]['Threads']
            t2 = processes2[pid]['Threads']
            # will be sorted according to first column
            diffs.append((t2-t1, t2, "%s[%s]" % (name, pid)))
    return diffs


def output_errors(idx, run1, run2):
    "write syslog errors to separate HTML file and return statistics"

    title = "Errors for round %d" % idx
    url = "%s/errors.html" % run2['basedir']
    write = open(url, "w").write

    # write the separate error report...
    write("<html>\n<title>%s</title>\n<body>\n<h1>%s</h1>\n" % (title, title))
    if 'errors' in run1:
        errors1 = run1['errors']
        path = run1['basedir']
        if path[0] != '/':
            # assume files are in the same hierachy
            path = "../" + path.split('/')[-1]
        path += "/errors.html"
        write('<a href="%s">Errors for previous round</a>\n' % path)
    else:
        errors1 = {}
    if 'errors' in run2:
        errors2 = run2['errors']
    else:
        errors2 = {}
    stat = syslog.output_errors(write, errors1, errors2)
    write("<hr>\n")
    syslog.explain_signals(write)
    write("</body>\n</html>\n")

    # ...and summary for the main page
    for value in stat.values():
        if value:
            syslog.errors_summary(stat, url, Colors.errors)
            break
    return stat


def output_data_links(run):
    "output links to all collected data"
    basedir = run['basedir']
    print "<h4>For more details on...</h4>"
    print "<ul>"
    if 'logfile' in run:
        print '<li>log messages, see <a href="%s">syslog</a>' % run['logfile']
    if os.path.exists("%s/smaps.html" % basedir):
        print "<li>private memory usage of all processes, see"
        print '<a href="%s/smaps.html">smaps overview</a>' % basedir
    elif os.path.exists("%s/smaps.cap" % basedir):
        print "<li>private memory usage of all processes, see"
        print '<a href="%s/smaps.cap">smaps data</a>' % basedir
    print "<li>process and device state details, see"
    print '<a href="%s/usage.csv">collected CSV data</a> and' % basedir
    print '<a href="%s/ifconfig">ifconfig output</a>' % basedir
    print "<li>rest of /proc/ information; see "
    if os.path.exists("%s/open-fds" % basedir):
        print '<a href="%s/open-fds">open file descriptors</a>, ' % basedir
    print '<a href="%s/interrupts">interrupts</a>, ' % basedir
    print '<a href="%s/slabinfo">slabinfo</a> and' % basedir
    print '<a href="%s/stat">stat</a> files' % basedir
    print "</ul>"
    

def output_run_diffs(idx1, idx2, data, do_summary):
    "outputs the differencies between two runs"

    run1 = data[idx1]
    run2 = data[idx2]
    if run1['release'] != run2['release']:
        syslog.parse_error(sys.stdout.write, "ERROR: release '%s' doesn't match previous round release '%s'!" % (run1['release'], run2['release']))
        return None

    # syslogged errors
    if do_summary:
        stat = None
    else:
        stat = output_errors(idx2, run1, run2)

    print "<h4>Resource usage changes</h4>"

    # overall stats
    free_change = run2['memfree'] - run1['memfree']
    fdfree_change = run2['fdfree'] - run1['fdfree']
    print "<p>System free memory change: <b>%+d</b> kB" % free_change
    print "<br>System unused file descriptor change: <b>%+d</b>" % fdfree_change
    if run2['fdfree'] < 200:
        print "<br><font color=red>Less than 200 FDs are free in the system.</font>"
    elif run2['fdfree'] < 500:
        print "<br>(Less that 500 FDs are free in the system.)"
    if do_summary:
        print "<!--\n- System free memory change: %+d\n- System free FD change: %+d\n-->" % (free_change, fdfree_change)
        if 'private_code' in run1:
            dcode_change = run2['private_code'] - run1['private_code']
            print "<p>System private dirty code pages change: <b>%+d</b> kB" % dcode_change

    # filesystem usage changes
    diffs = get_usage_diffs(run1['mounts'], run2['mounts'])
    output_diffs(diffs, "Filesystem usage", "Mount", " kB",
                Colors.disk, do_summary)

    # process private memory usage changes
    if 'smaps' in run1:
        diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                        run1['smaps'], run2['smaps'])
        output_diffs(diffs, "Process private memory usage (according to SMAPS)",
                "Command[Pid]", " kB", Colors.memory, do_summary)
    else:
        print "<p>No SMAPS data for process private memory usage available."
    
    # process X resource usage changes
    diffs = get_usage_diffs(run1['xclients'], run2['xclients'])
    output_diffs(diffs, "X resource usage", "X client", " kB",
                    Colors.xres, do_summary)
    
    # FD count changes
    diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                    run1['fdcounts'], run2['fdcounts'])
    output_diffs(diffs, "Process file descriptor count", "Command[Pid]", "",
                    Colors.fds, do_summary)

    print "\n<h4>Changes in processes</h4>"

    # thread count changes
    diffs = get_thread_count_diffs(run2['commands'],
                    run1['processes'], run2['processes'])
    output_diffs(diffs, "Process thread count", "Command[Pid]", "",
                    Colors.threads, do_summary)

    # new and closed processes
    titles = ("Change in number of processes",
              "Exited processes",
              "New processes")
    output_process_changes(
                get_pids_from_procs(run1['processes'], run1['commands']),
                get_pids_from_procs(run2['processes'], run2['commands']),
                titles, do_summary)

    # new and collected kthreads/zombies
    titles = ("Change in number of kernel threads and zombie processes",
              "Collected kthreads/zombies",
              "New kthreads/zombies")
    output_process_changes(run1['kthreads'], run2['kthreads'], titles, do_summary)
    return stat


def output_initial_state(run):
    "show basic information about the test run"
    print "<p>%s" % run['release']
    print "<p>%s" % run['datetime']
    print "<p>Free system memory: <b>%d</b> kB" % run['memfree']
    print "<br>(free = free+cached+buffered+swapfree)"
    if 'private_code' in run and run['private_code']:
        print "<p>Private dirty code pages: <b>%d</b> kB" % run['private_code']
        print "<br><i>(this means that system has incorrectly built shared libraries)</i>"
    output_errors(0, {}, run)
    print """
<p>Errors from each additional test round are listed below, but for
a summary of them, see <a href="#error-summary">all errors summary
section</a>. Note that the same issues (related to system services)
may appear under multiple error types.
""" # "fool Jed syntax highlighter
    output_data_links(run)
    print "<hr>\n"


# ------------------- output memory graphs -------------------------

def output_memory_graph_table(titles, colors, data):
    "outputs memory usage bars for given (name, (values), tex(t)) tupple array"
    width = 640 # total width of the graph bars
    print "<table><tr>"
    for title in titles:
        if title:
            print "<td><i>%s</i></td>" % title
    print "</tr>"
    for item in data:
        # row title
        print '<tr><td>%s</td>' % item[0]
        # graphical bar
        print "<td><table border=0 cellpadding=0 cellspacing=0><tr>"
        for idx in range(len(colors)):
            w = int(item[1][idx]*width)
            sys.stdout.write('<td bgcolor="%s" width=%d height=16></td>' % (colors[idx], w))
        print "</tr></table></td>"
        # texts at end
        for text in item[2]:
            if text:
                print '<td align="right">%s</td>' % text
        print "</tr>"
    print "</table>"


def output_apps_memory_graphs(cases):
    "outputs memory graphs bars for the individual processes"
    # arrange per use-case data to be per pid
    rounds = 0
    data = {}
    for testcase in cases:
        commands = testcase['commands']
        processes = testcase['processes']
        for process in processes.values():
            pid = process['Pid']
            if pid not in commands:
                sys.stderr.write("Debug: %s[%s] in status list but not in FD list\n" % (process['Name'], pid))
                continue
            if not pid_is_main_thread(pid, commands, processes):
                continue
            name = commands[pid]
            namepid = (name, pid)
            if namepid not in data:
                data[namepid] = {}
                data[namepid]['first'] = rounds
            # process is also in this round, so add its info
            data[namepid][rounds] = process
        rounds += 1

    # get largest size for any of the namepids, get largest rss
    # for sorting and ignore items which rss/size don't change
    sizes = []
    largest_size = 0
    for namepid in data:
        changerounds = pidrounds = 0
        max_size = max_rss = 0
        min_size = min_rss = 128*1024
        for idx in range(rounds):
            if idx in data[namepid]:
                rss = data[namepid][idx]['VmRSS']
                size = data[namepid][idx]['VmSize']
                if size < min_size:
                    if pidrounds:
                        changerounds += 1
                    min_size = size
                if size > max_size:
                    if pidrounds:
                        changerounds += 1
                    max_size = size
                if rss < min_rss:
                    min_rss = rss
                if rss > max_rss:
                    max_rss = rss
                if rss > max_rss:
                    max_rss = rss
                pidrounds += 1
        if pidrounds > 1:
            rss_change = (float)(max_rss - min_rss) / max_rss / pidrounds
            size_change = (float)(max_size - min_size) / max_size / pidrounds
            # if >0.2% memory change per round in RSS or Size, or
            # size changes on more than half of the rounds, add to list
            if rss_change > 0.002 or size_change > 0.002 or 2*changerounds > pidrounds:
                sizes.append((max_rss,namepid))
        if max_size > largest_size:
            largest_size = max_size
    largest_size = float(largest_size)
    
    # first sort according to the RSS size
    sizes.sort()
    sizes.reverse()
    # then sort according to names
    orders = []
    for size in sizes:
        namepid = size[1]
        # sorting order is: name, first round for pid, pid
        orders.append((namepid[0], data[namepid]['first'], namepid[1], namepid))
    del(sizes)
    orders.sort()
    
    # amount of memory in the device (float for calculations)
    print """
<p>Only processes which resident size changes during tests are listed.
If process has same name and (max) RSS as some other process, it's
assumed to be a thread and ignored.
"""
    for order in orders:
        namepid = order[3]
        process = data[namepid]
        print "<h4>%s [%s]</h4>" % namepid
        text = ''
        busy = 0
        prev_idx = 0
        prev_text = ""
        columndata = []
        for idx in range(rounds):
            if idx in process:
                item = process[idx]
                rss = item['VmRSS']
                size = item['VmSize']
                sizes = (rss/largest_size, (size - rss)/largest_size)

                sleepavg = int(item['SleepAVG'][:-1])
                if sleepavg < 90:
                    busy = 1
                    text = ("%skB" % rss, "%skB" % size, "(%d%%)" % sleepavg)
                else:
                    text = ("%skB" % rss, "%skB" % size)

                if idx:
                    if text == prev_text:
                        columndata.pop()
                        case = 'Rounds <a href="#round-%d">%02d</a> - <a href="#round-%d">%02d</a>:' % (prev_idx, prev_idx, idx, idx)
                    else:
                        case = 'Test round <a href="#round-%d">%02d</a>:' % (idx, idx)
                        prev_idx = idx
                else:
                    case = '<a href="#initial-state">Initial state</a>:'
                    prev_idx = idx
                prev_text = text
            else:
                nan = ("N/A",)
                if text == nan:
                    # previous one didn't have anything either
                    continue
                prev_rss = prev_size = 0
                sizes = (0,0)
                text = nan
                case = "---"
            columndata.append((case, sizes, text))
        if busy:
            sleeptext = "Sleep:"
        else:
            sleeptext = None
        titles = ("Test-case:", "Graph", "RSS:", "Size:", sleeptext)
        output_memory_graph_table(titles, bar2colors, columndata)


def output_system_memory_graphs(data):
    "outputs memory graphs bars for the system"
    idx = 0
    swapused = 0
    columndata = []
    for testcase in data:
        if not idx:
            case = '<a href="#initial-state">Initial state</a>:'
        else:
            case = '<a href="#round-%d">Test round %02d</a>:' % (idx, idx)
        idx += 1

        # amount of memory in the device (float for calculations)
        mem_total = float(testcase['memtotal'])
        # memory usage %-limit after which apps are bg-killed
        mem_low = testcase['limitlow']
        # memory usage %-limit after which apps refuse certain operations
        mem_high = testcase['limithigh']
        # memory usage %-limit after which kernel denies app allocs
        mem_deny = testcase['limitdeny']
        
        if mem_low + mem_high + mem_deny > 0:
            # convert percentages to real memory values
            mem_low = mem_total * mem_low / 100
            mem_high = mem_total * mem_high / 100
            mem_deny = mem_total * mem_deny / 100
        else:
            mem_low = mem_high = mem_deny = mem_total
            sys.stderr.write("Warning: low memory limits are zero -> disabling\n")

        mem_used = testcase['memused']
        mem_free = testcase['memfree']
        if mem_used > mem_high:
            text_used = "<font color=red><b>%d</b></font>" % mem_used
        elif mem_used > mem_low:
            text_used = "<font color=blue><b>%d</b></font>" % mem_used
        else:
            text_used = "%d" % mem_used
        text_used += "kB"
        text_free = "%dkB" % mem_free
        if testcase['swapused']:
            memtext = (text_used, text_free, "(%dkB)" % testcase['swapused'])
            swapused = 1
        else:
            memtext = (text_used, text_free)
        if mem_used > mem_deny:
            show_free = 0.0
            show_deny = (mem_total - mem_used)/mem_total
        else:
            show_free = (mem_free - mem_total + mem_deny)/mem_total
            show_deny = 1.0 - mem_deny/mem_total
        show_used = mem_used/mem_total
        columndata.append((case, (show_used, show_free, show_deny), memtext))
    if swapused:
        swaptext = "swap:"
    else:
        swaptext = None
    titles = ("Test-case:", "Memory usage graph:", "used:", "free:", swaptext)
    output_memory_graph_table(titles, bar1colors, columndata)
    print """
<table>
<tr><th></th><th align="left">Legend:</th></tr>
<tr><td bgcolor="blue"  height="16" width="16"></td><td>Memory used in the device</td></tr>
<tr><td bgcolor="green" height="16" width="16"></td><td>Memory "freely" usable in the device (free/cached/buffered)</td></tr>
<tr><td bgcolor="red"   height="16" width="16"></td><td>If memory usage reaches this, application allocations fail and the allocating app is OOM-killed (&gt;= %d MB used)</td></tr>
</table>""" % round(mem_deny/1024)
    if mem_low == mem_total:
        print "<p>(memory limits are not in effect)"
        return
    print """
<p>Memory usage values which trigger background killing are marked with
blue color (&gt;= <font color=blue><b>%d</b></font> MB used).<br>
After bg-killing and memory low mark comes the memory high pressure mark
at which point e.g.<br> Browser refuses to open new pages, these numbers
are marked with red color (&gt;= <font color=red><b>%d</b></font> MB used).
""" % (round(mem_low/1024), round(mem_high/1024))


# ------------------- output all data -------------------------

def output_html_report(data):
    title = "Endurance measurements report"
    rounds = len(data)-1
    last = rounds
    first = 1

    print """<html>
<head>
<title>%s</title>
</head>
<body>
<h1>%s</h1>

<!-- endurance_report.py v1.1.13 -->

<p><b>Contents:</b>
<ul>
<li><a href="#initial-state">Initial state</a>
<li>Memory usage overview for the test rounds:
  <ul>
    <li><a href="#system-memory">System memory usage</a>
    <li><a href="#process-memory">Processes memory usage</a>
  </ul>
<li>Resource usage changes for each of the test rounds:
  <ul>
""" % (title, title)   #" fool Jed syntax highlighter
    for round in range(len(data)-1):
        print '  <li><a href="#round-%d">Round %d</a>' % (round+1, round+1)
    print """
  </ul>
<li>Summary of changes between all the rounds after the initial one:
  <ul>
    <li><a href="#error-summary">Error summary</a>
    <li><a href="#resource-summary">Resource usage summary</a>
  </ul>
</ul>
<hr>

<a name="initial-state"></a>
<h2>Initial state</h2>
"""
    output_initial_state(data[0])

    print """
<a name="system-memory"></a>
<h2>Memory usage overview for the test rounds</h2>
<h3>System memory usage</h3>
"""
    output_system_memory_graphs(data)
    print """
<hr>
<a name="process-memory"></a>
<h3>Processes memory usage</h3>
""" # "fool Jed syntax highlighter
    output_apps_memory_graphs(data)
    if last - first > 1:
        summary = "resource-summary"
    else:
        summary = "round-%d" % last
    print"""
<hr>
<h2>Resource usage changes for the test rounds</h2>
<p>Details of resource changes are listed below, but for a summary,
see <a href="#%s">resource changes summary section</a>.
""" % summary # "fool Jed syntax highlighter

    err_stats = {}
    for idx in range(rounds):
        if idx:
            title = "Test round %d differences from round %d" % (idx+1, idx)
        else:
            title = "Test round 1 differences from initial state"
        print
        print '<a name="round-%d"></a>' % (idx+1)
        print "<h3>%s</h3>" % title
        print "<p>%s" % data[idx+1]['datetime']
        stat = output_run_diffs(idx, idx+1, data, 0)
        if stat:
            syslog.errors_add(err_stats, stat)
        output_data_links(data[idx+1])
        print "\n<hr>"
    
    print """
<a name="error-summary"></a>
<h2>Summary of changes between test rounds %d - %d</h2>
<h3>Error summary</h3>""" % (first, last)
    syslog.errors_summary(err_stats, "", Colors.errors)
    print "<!-- summary for automatic parsing:"
    syslog.use_html = 0
    syslog.errors_summary(err_stats)
    print """-->

<hr>
<a name="resource-summary"></a>
<h3>Resource usage summary</h3>
<p><font color="red">NOTE</font>: Process specific resource usage
changes are shown only for processes which exist in both of the
compared rounds!
"""
    output_run_diffs(first, last, data, 1)

    print "\n</body></html>"


# ------------------- go through all files -------------------------

def parse_syte_stats(dirs):
    """parses given CSV files into a data structure"""
    data = []
    for dirname in dirs:
        file = "%s/usage.csv" % dirname
        sys.stderr.write("Parsing '%s'...\n" % file)
        items = parse_csv(file)
        if not items:
            sys.stderr.write("CSV parsing failed\n")
            sys.exit(1)

        file = "%s/smaps.cap" % dirname
        if os.path.exists(file):
            sys.stderr.write("Parsing '%s'...\n" % file)
            items['smaps'], items['private_code'] = parse_smaps(file)
            if not items['smaps']:
                sys.stderr.write("SMAPS data parsing failed\n")
                sys.exit(1)

        file = "%s/syslog" % dirname
        if not (os.path.exists(file)):
            file = "%s/syslog.gz" % dirname
            if not (os.path.exists(file)):
                file = None
        if file:
            # get the crashes and other errors
            sys.stderr.write("Parsing '%s'...\n" % file)
            items['errors'] = syslog.parse_syslog(sys.stdout.write, file)
            items['logfile'] = file
        #print items
        data.append(items)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
        sys.stderr.write(msg)
        sys.exit(1)
    else:
        stats = parse_syte_stats(sys.argv[1:])
        output_html_report(stats)
