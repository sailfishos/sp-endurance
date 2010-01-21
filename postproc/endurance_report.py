#!/usr/bin/python
# This file is part of sp-endurance.
#
# Copyright (C) 2006-2009 by Nokia Corporation
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
# 2007-11-05:
# - Include SwapCached to system free and report swap usage
#   separately in summary
# - Handle compressed smaps.cap files
# 2007-11-29:
# - App memory usage graphs show also SMAPS private memory usage
# 2008-04-30:
# - Show optional use-case step description
# 2008-08-21:
# - Kernels from v2.6.22 don't anymore provide PID/status:SleepAVG
#   -> remove support for it (it was fairly useless anyway)
# 2008-12-04:
# - Show difference in shared memory segments use
#   (subset of FDs with their own limits)
# 2009-04-01:
# - Parse swap usage from SMAPS and add 'Swap' column in process memory usage.
#   Swap is shown in the graphs as well, although it's often just a few pixels
#   in width.
# - Parse PSS from SMAPS and add 'PSS' column in per-process tables.
# - Include Slab Reclaimable in system free memory calculations. The kernel low
#   memory notification calculations take these into account as well.
# - Remove SwapCached from the free memory calculations, it is already included
#   in SwapFree.
# - Take swap into consideration when looking for changes in Dirty and Size.
#   This affects what processes are listed under the "Processes memory usage"
#   section.
# - Add legend for the "Processes memory usage" section graphs.
# - Add UTF-8 header in HTML, some X client names may contain UTF-8 characters.
# - Include process name when giving warning about missing SMAPS data.
# - Python Gzip module is slow, so use /bin/zcat and popen() instead if
#   available. Gives 2-3x speed up.
# - Use the psyco JIT compiler, if installed. Gives 2-3x speed up.
# 2009-04-22:
# - Add System Load graph to the resource usage overview, that shows the CPU
#   time distribution between system processes, user processes, I/O-wait, etc.
#   The graph is generated with information parsed from /proc/stat.
# - Add Process CPU Usage graph for each test rounds, that shows the CPU time
#   distribution between processes during that particular test round. The graph
#   is generated with information parsed from /proc/pid/stat files.
# - Use RSS and Size from SMAPS data if available, instead of the ones from
#   /proc/pid/status. This fixes cases where PSS > RSS, because the SMAPS data
#   also includes device mappings.
# - Add support for lzop compressed smaps and syslog files.
# 2009-05-13:
# - Introduce a new section Kernel Events, and add tables Virtual Memory
#   Subsystem and Low Level System Events. The former includes details about
#   page faults and swap, and the latter details about the number of interrupts
#   and context switches. Data is parsed from /proc/stat and /proc/vmstat.
#   The numbers are highlited in red if they exceed certain fixed thresholds.
# - Process CPU Usage graph: show summary about the processes that we did not
#   include in the graph.
# 2009-06-01:
# - System Load graph: fix division with zero with exactly identical data.
#   This happened if user manually made another copy of one of the snapshot
#   directories.
# 2009-10-15:
# - Take last three xresource values, not ones from fixed offset.
# 2009-10-26:
# - Adapt to proc2csv providing whole command line
# - Parse X client resource counts and show them in summary
# - Parse ifconfig output and show network usage distribution between
#   interfaces (network/radio usage has use-time implications)
# - Generalize and move compressed file logging, opening and error
#   handling to syslog_parse.py
# 2009-10-29:
# - Show program cmdline with acronym tag (mouse highlight)
# - In memory graphs, handle process as same one regardless
#   of program name/cmdline changes
# - Get right fields from ifconfig and show network usage changes, not totals
# 2009-11-02:
# - Support Fremantle low memory limits scheme in addition to Diablo one
# TODO:
# - Mark reboots more prominently also in report (<h1>):
#   - dsme/stats/32wd_to -> HW watchdog reboot
#   - dsme/stats/sw_rst -> SW watchdog reboots
#   - bootreason -> last boot
# - Proper option parsing + possibility to state between which
#   test runs to produce the summaries?
# - Show differences in slabinfo and vmstat numbers (pswpin/pswpout)?
"""
NAME
        <TOOL_NAME>

SYNOPSIS
        <TOOL_NAME> <data directories>

DESCRIPTION

This script reads data files produced by the endurance measurement
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

# these are HTML hex color values for different HTML tables
class Colors:
    errors = "FDEEEE"
    disk = "EEFDFD"
    memory = "EEEEFD"
    threads = "CFEFEF"
    xres_mem = "FDEEFD"
    xres_count = "EEDDEE"
    fds = "FDFDEE"
    shm = "EEEEEE"
    kernel = "EFFDF0"

# color values for (Swap used, RAM used, memory free, oom-limit)
#      magenta, blue, light green, red
bar1colors = ("EE00FF", "3149BD", "ADE739", "DE2821")
# color values for (Swap, Dirty, PSS, RSS, Size)
#      magenta, red, orange, orangeish, yellow
bar2colors = (bar1colors[0], "DE2821", "E0673E", "EAB040", "FBE84A")
# color values for CPU load (system, user, user nice, iowait, idle)
#      red, blue, light blue, magenta, light green
bar3colors = (bar2colors[1], bar1colors[1], "4265FF", bar1colors[0], bar1colors[2])


# --------------------- SMAPS data parsing --------------------------

# address range, access rights, page offset, major:minor, inode, mmap()ed item
smaps_mmap = re.compile("^[-0-9a-f]+ ([-rwxps]+) [0-9a-f]+ [:0-9a-f]+ \d+ *(|[^ ].*)$")

# data from sp_smaps_snapshot
def parse_smaps(file):
    """
    Parse SMAPS and return (smaps, private_code):
      'smaps'        : Per PID dict with keys: private_dirty, swap, pss, rss
                       and size, which are sums of the SMAPS fields. All these
                       fields are initialized to 0 for each PID.
      'private_code' : Amount of Private Dirty mappings for code pages in whole
                       system.
    Everything is in kilobytes.
    """
    private_code = code = pid = idx = 0
    smaps = {}
    while 1:
        try:
            line = file.readline()
        except IOError, e:
            syslog.parse_error(write, "ERROR: SMAPS file '%s': %s" % (file, e))
            break
        if not line:
            break
        idx += 1
        line = line.strip()
        if not line:
            continue
        #print line        #DEBUG
        if line.startswith('='):
            # ==> /proc/767/smaps <==
            continue
        if line.startswith('#'):
            if line.find("#Pid: ") == 0:
                pid = line[6:]
                smaps[pid] = { 'private_dirty' : 0,
                               'swap'          : 0,
                               'pss'           : 0,
                               'rss'           : 0,
                               'size'          : 0 }
            continue
        if not pid:
            # sanity check
            sys.stderr.write("ERROR: Pid missing for SMAPS line %d:\n  %s\n" % (idx, line))
            sys.exit(1)
        if line.startswith("Private_Dirty:"):
            amount = int(line[15:-2])
            if code and amount:
                #print line
                #sys.stderr.write("dirty code: %s, %dkB\n" %(mmap, amount))
                private_code += amount
            smaps[pid]['private_dirty'] += amount
            #print "ADD"        #DEBUG
            continue
        if line.startswith("Swap:"):
            smaps[pid]['swap'] += int(line[6:-2])
            continue
        if line.startswith("Pss:"):
            smaps[pid]['pss'] += int(line[5:-2])
            continue
        if line.startswith("Rss:"):
            smaps[pid]['rss'] += int(line[5:-2])
            continue
        if line.startswith("Size:"):
            smaps[pid]['size'] += int(line[6:-2])
            continue
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
        # sanity check that mmap lines are not missed
        if (line[0] >= '0' and line[0] <= '9') or (line[0] >= 'a' and line[0] <= 'f'):
            sys.stderr.write("ERROR: SMAPS mmap line not matched:\n  %s\n" % line)
            sys.exit(1)
    return (smaps, private_code)


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


def get_xres_usage(file):
    "reads X client resource usage, return command hash of total X mem usage"
    xres_mem = {}
    xres_count = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        
        # last three columns are the most interesting ones
        mem,pid,name = line.split(',')[-3:]
        if pid[-1] != 'B' and mem[-1] == 'B':
            mem = int(mem[:-1])
        else:
            sys.stderr.write("Error: X resource total memory value not followed by 'B':\n  %s\n" % line)
            sys.exit(1)
        # in KBs, check on clients taking > 1KB
        if mem >= 1024:
            xres_mem[name] = mem/1024
        
        count = 0
        # resource base, counts of resources, their memory usages, PID, name
        cols = line.split(',')
        for i in range(1, len(cols) - 3):
            if cols[i][-1] != 'B':
                count += int(cols[i])
        xres_count[name] = count

    return (xres_mem, xres_count)


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


def get_shm_counts(file):
    """reads shared memory segment lines until empty line,
    returns total count of segments and ones with <2 users"""

    headers = file.readline().strip()
    if ("size" not in headers) or ("nattch" not in headers):
        sys.stderr.write("\nError: Shared memory segments list header '%s' missing 'nattch' or 'size' column\n" % headers)
        sys.exit(1)
    nattach_idx = headers.split(',').index("nattch")
    #size_idx = headers.split(',').index("size")
    
    size = others = orphans = 0
    while 1:
        line = file.readline().strip()
        if not line:
            break
        items = line.split(',')
        # how many processes attaches to the segment
        if int(items[nattach_idx]) > 1:
            others += 1
        else:
            orphans += 1
        # size in KB, rounded to next page
        #size += (int(items[size_idx]) + 4095) / 1024
    return {
        #"Total of segment sizes (KB)": size,
        "Normal segments (>1 attached processes)": others,
        "Orphan segments (<=1 attached processes)": orphans
    }


def get_commands_and_fd_counts(file):
    """reads fdcount,pid,command lines until empty line,
    returns pid hashes of command names and fd counts"""
    commands = {}
    fd_counts = {}
    cmdlines = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        cols = line.split(',')
        pid = cols[0]
        fd_counts[pid] = int(cols[1])
        # need to handle command lines with commas
        cmdline = ",".join(cols[2:])
        cmdlines[pid] = cmdline
        commands[pid] = os.path.basename(cmdline.split(' ')[0])
    return (commands,fd_counts,cmdlines)


def parse_proc_stat(file):
    "Parses relevant data from /proc/stat"
    stat = {}
    # CPU: take everything except "steal" and "guest", which are some
    # virtualization related counters, obviously not useful in our case.
    cpu = re.compile("^cpu\s+(\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)")
    # Interrupts: take first column, it contains the sum of the individual
    # interrupts.
    intr = re.compile("^intr\s+(\d+)")
    # Context switches.
    ctxt = re.compile("^ctxt\s+(\d+)")
    for line in file:
        m = cpu.search(line)
        if m:
            stat['cpu'] = {}
            stat['cpu']['user'],       \
            stat['cpu']['user_nice'],  \
            stat['cpu']['system'],     \
            stat['cpu']['idle'],       \
            stat['cpu']['iowait'],     \
            stat['cpu']['irq'],        \
            stat['cpu']['softirq']     \
                = [int(x) for x in m.groups()]
            continue
        m = intr.search(line)
        if m:
            stat['intr'] = int(m.group(1))
            continue
        m = ctxt.search(line)
        if m:
            stat['ctxt'] = int(m.group(1))
            continue
    return stat


def get_proc_pid_stat(file):
    """
    Parses relevant data from /proc/pid/stat entries, and returns dict with per
    process information:
                pid : utime
                pid : stime
    """
    stat = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        pid = int(line.split(',')[0])
        utime, stime = [int(x) for x in line.split(',')[13:15]]
        stat[pid] = {}
        stat[pid]['utime'] = utime
        stat[pid]['stime'] = stime
    return stat


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
    slab_reclaimable = mem['SReclaimable']
    swaptotal = mem['SwapTotal']
    swapfree = mem['SwapFree']

    data['ram_total'] = total
    data['ram_free'] = free + buffers + cached + slab_reclaimable
    data['ram_used'] = data['ram_total'] - data['ram_free']
    data['swap_total'] = swaptotal
    data['swap_free'] = swapfree
    data['swap_used'] = swaptotal - swapfree


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


def skip_to_next_header(file):
    "reads the given file until we get first nonempty line"
    while 1:
        line = file.readline()
        if not line:
            sys.stderr.write("\nError: premature file end while scanning for CSV header\n")
            sys.exit(2)
        if line.strip():
            return line.strip()


def parse_csv(file, filename):
    "Parses interesting information from the endurance measurement CSV file"
    data = {}
    
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

    # /proc/vmstat
    # The header line ends with ':', so get rid of that.
    keys = skip_to(file, "nr_free_pages").strip()[:-1].split(',')
    try:
        vals = [int(x) for x in file.readline().strip().split(',')]
        data['/proc/vmstat'] = dict(zip(keys, vals))
    except:
        pass

    # low memory limits
    skip_to(file, "lowmem_")
    mem = file.readline().split(',')
    if len(mem) in (3, 6):
        data['limitlow'] = int(mem[0])
        data['limithigh'] = int(mem[1])
        data['limitdeny'] = int(mem[2])
        if len(mem) == 6:
            data['limitlowpages'] = int(mem[3])
            data['limithighpages'] = int(mem[4])
            data['limitdenypages'] = int(mem[5])
    else:
        # not fatal as lowmem stuff is not in standard kernel
        sys.stderr.write("\nWarning: CSV file '%s' lowmem limits are missing!\n" % filename)

    # get shared memory segment counts
    skip_to(file, "Shared memory segments")
    data['shm'] = get_shm_counts(file)

    # get system free FDs
    skip_to(file, "Allocated FDs")
    fdused,fdfree,fdtotal = file.readline().split(',')
    data['fdfree'] = (int(fdtotal) - int(fdused)) + int(fdfree)

    # get the process FD usage
    skip_to(file, "PID,FD count,Command")
    data['commands'], data['fdcounts'], data['cmdlines'] = get_commands_and_fd_counts(file)
    
    # get process statistics
    headers = skip_to(file, "Name,State,")
    data['processes'], data['kthreads'] = get_process_info(file, headers)

    # check if we have /proc/pid/stat in the CSV file
    headers = skip_to_next_header(file)
    if headers.startswith("Process status:"):
        data['/proc/pid/stat'] = get_proc_pid_stat(file)
        skip_to(file, "res-base")
    elif headers.startswith("res-base"):
        pass
    else:
        sys.stderr.write("\nError: unexpected '%s' in CSV file\n" % headers)
        sys.exit(2)

    # get the X resource usage
    data['xclient_mem'], data['xclient_count'] = get_xres_usage(file)
    
    # get the file system usage
    skip_to(file, "Filesystem")
    data['mounts'] = get_filesystem_usage(file)
    
    return data

# ------------------- ifconfig parsing -----------------------

def parse_ifconfig(file):
    """reads interface = [send,receive] information from ifocnfig output"""
    #regex = re.compile("packets:([0-9]+) errors:([0-9]+) dropped:([0-9]+)")
    regex = re.compile("RX bytes:([0-9]+) [^:]*TX bytes:([0-9]+)")
    transfers = {}
    interface = None
    rbytes = tbytes = 0
    while 1:
        line = file.readline()
        if not line:
            break
        if line[0] > ' ':
            if interface and interface != "lo":
                transfers[interface] = int(rbytes) + int(tbytes)
            interface = line.split()[0]
            continue
        line = line.strip()
        if line.startswith("RX bytes"):
            match = regex.search(line)
            if match:
                rbytes,tbytes = match.groups()
    if interface and interface != "lo":
        transfers[interface] = int(rbytes) + int(tbytes)
    return transfers


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
    """return list of (total, name, diff) change tuples for given items"""
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
            t1 = int(processes1[pid]['Threads'])
            t2 = int(processes2[pid]['Threads'])
            if t1 == t2:
                continue
            name = commands[pid]
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
    "output links to all collected uncompressed data"
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

def combine_dirty_and_swap(smaps):
    "Combines private dirty and swap memory usage for each PID"
    result = {}
    for pid in smaps:
        result[pid] = smaps[pid]['private_dirty'] + smaps[pid]['swap']
    return result

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

    # Create the following table (based on /proc/pid/stat):
    #
    #   Command[Pid]: system / user       CPU Usage:
    #   app2[1234]:   ###########%%%%%%%  45%  (90s)
    #   app1[987]:    ######%%%%%%%%%     44%  (88s)
    #   app3[543]:    #%                   5%  (10s)
    #
    def process_cpu_usage():
        CLK_TCK=100.0
        if not '/proc/pid/stat' in run1 or not '/proc/pid/stat' in run2:
            return
        print "<h4>Process CPU usage</h4>"
        cpusum1 = sum(run1['/proc/stat']['cpu'].itervalues())
        cpusum2 = sum(run2['/proc/stat']['cpu'].itervalues())
        if cpusum2 < cpusum1:
            print "<p><i>System reboot detected, omitted.</i>"
            return
        elif cpusum2 == cpusum1:
            # Two identical entries? Most likely user has manually copied the snapshot directories.
            print "<p><i>Identical snapshots detected, omitted.</i>"
            return
        cpu_total_diff = float(cpusum2-cpusum1)
        print "<p>Interval between rounds was %d seconds." % (cpu_total_diff/CLK_TCK)
        if cpu_total_diff <= 0:
            return
        print "<p>"
        diffs = []
        for pid in iter(run2['/proc/pid/stat']):
            stime1 = utime1 = 0
            if pid in run1['/proc/pid/stat']:
                stime1 = run1['/proc/pid/stat'][pid]['stime']
                utime1 = run1['/proc/pid/stat'][pid]['utime']
            stimediff  = run2['/proc/pid/stat'][pid]['stime']-stime1
            utimediff  = run2['/proc/pid/stat'][pid]['utime']-utime1
            if str(pid) in run2['kthreads']:
                name = "[" + run2['kthreads'][str(pid)] + "]"
            else:
                name = run2['commands'][str(pid)]
            diffs.append(("%s[%d]" % (name, pid), stimediff, utimediff))
        # Other processes often eat significant amount of CPU, so lets show
        # that to the user as well.
        def total_sys(r):
            return r['/proc/stat']['cpu']['system'] + r['/proc/stat']['cpu']['irq'] + r['/proc/stat']['cpu']['softirq']
        def total_usr(r):
            return r['/proc/stat']['cpu']['user'] + r['/proc/stat']['cpu']['user_nice']
        UNACC = "<i>(Unaccounted CPU time)</i>"
        diffs.append((UNACC,\
                total_sys(run2)-total_sys(run1)-sum([x[1] for x in diffs]),\
                total_usr(run2)-total_usr(run1)-sum([x[2] for x in diffs])))
        # Dont include in the graph those processes that have used only a
        # little CPU, but collect them and show some statistics.
        THRESHOLD = max(1, 0.005*cpu_total_diff)
        filtered_out = []
        diffs2 = []
        for x in diffs:
            if x[1]+x[2] > THRESHOLD:
                diffs2.append(x)
            elif x[1]+x[2] > 0:
                filtered_out.append(x)
        diffs = diffs2
        # Sort in descending order of CPU ticks used.
        diffs.sort(lambda x,y: cmp(x[1]+x[2], y[1]+y[2]))
        diffs.reverse()
        if len(diffs)==0:
            return
        # Scale the graphics to the largest CPU usage value.
        divisor = float(sum(diffs[0][1:3]))
        output_graph_table(\
            ("Command[Pid]:", "<font color=%s>system</font> / <font color=%s>user</font>" % bar3colors[0:2], "CPU Usage:"),
            bar3colors[0:2],\
            [(x[0], (x[1]/divisor, x[2]/divisor),\
                ["%.2f%% (%.2fs)" % (100*(x[1]+x[2])/cpu_total_diff, (x[1]+x[2])/CLK_TCK)]) for x in diffs]\
            + [("", (0,0), ["<i>%.2f%% (%.2fs)</i>" % (\
                    100*sum([x[1]+x[2] for x in diffs])/cpu_total_diff,\
                        sum([x[1]+x[2] for x in diffs])/CLK_TCK)\
                ])])
        if filtered_out:
            print "<p><i>Note:</i> %d other processes also used some CPU, but "\
                  "did not exceed the threshold of 0.5%% CPU Usage (%.2f seconds).<br>"\
                  "They used %.2f seconds of CPU time in total." \
                  % (len(filtered_out), THRESHOLD/CLK_TCK, sum([x[1]+x[2] for x in filtered_out])/CLK_TCK)
        if UNACC in [x[0] for x in diffs]:
            print "<p><i>Unaccounted CPU time</i> stands for such CPU time that "\
                  "could not be attributed to any process.<br>"\
                  "These can be for example short living programs that "\
                  "started and exited during one round of the tests."

    process_cpu_usage()

    print "<h4>Resource usage changes</h4>"

    # overall stats
    total_change = (run2['ram_free']+run2['swap_free']) - (run1['ram_free']+run1['swap_free'])
    ram_change = run2['ram_free'] - run1['ram_free']
    swap_change = run2['swap_free'] - run1['swap_free']
    fdfree_change = run2['fdfree'] - run1['fdfree']
    print "<p>System free memory change: <b>%+d</b> kB" % total_change
    if ram_change or swap_change:
        print "<br>(free RAM change: <b>%+d</b> kB, free swap change: <b>%+d</b> kB)" % (ram_change, swap_change)
    print "<br>System unused file descriptor change: <b>%+d</b>" % fdfree_change
    if run2['fdfree'] < 200:
        print "<br><font color=red>Less than 200 FDs are free in the system.</font>"
    elif run2['fdfree'] < 500:
        print "<br>(Less that 500 FDs are free in the system.)"
    if do_summary:
        print """
<!--
- System free memory change: %+d
- System free RAM change: %+d
- System free swap change: %+d
- System free FD change: %+d
-->""" % (total_change, ram_change, swap_change, fdfree_change)
        if 'private_code' in run1:
            dcode_change = run2['private_code'] - run1['private_code']
            if dcode_change:
                print "<br>System private dirty code pages change: <b>%+d</b> kB" % dcode_change

    # filesystem usage changes
    diffs = get_usage_diffs(run1['mounts'], run2['mounts'])
    output_diffs(diffs, "Filesystem usage", "Mount", " kB",
                Colors.disk, do_summary)

    # Combine Private dirty + swap into one table. The idea is to reduce the
    # amount of data included in the report (=less tables & smaller HTML file
    # size), and entries like -4 kB private dirty & +4 kB swap. Most of the
    # swapped pages will be private dirty anyways.
    if 'smaps' in run1:
        diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                        combine_dirty_and_swap(run1['smaps']),
                        combine_dirty_and_swap(run2['smaps']))
        output_diffs(diffs,
                "Process private and swap memory usages combined (according to SMAPS)",
                "Command[Pid]", " kB", Colors.memory, do_summary)
    else:
        print "<p>No SMAPS data for process private memory usage available."
    
    # process X resource usage changes
    diffs = get_usage_diffs(run1['xclient_mem'], run2['xclient_mem'])
    output_diffs(diffs, "X resource memory usage", "X client", " kB",
                 Colors.xres_mem, do_summary)
    if do_summary:
        diffs = get_usage_diffs(run1['xclient_count'], run2['xclient_count'])
        output_diffs(diffs, "X resource count", "X client", "",
                     Colors.xres_count, do_summary)
    
    # FD count changes
    diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                    run1['fdcounts'], run2['fdcounts'])
    output_diffs(diffs, "Process file descriptor count", "Command[Pid]", "",
                    Colors.fds, do_summary)

    # shared memory segment count changes
    diffs = get_usage_diffs(run1['shm'], run2['shm'])
    output_diffs(diffs, "Shared memory segments", "Type", "",
                Colors.shm, do_summary)

    # Kernel statistics
    cpu_total_diff = float(sum(run2['/proc/stat']['cpu'].itervalues())-sum(run1['/proc/stat']['cpu'].itervalues()))
    if cpu_total_diff > 0:
        print "\n<h4>Kernel events</h4>"

        def format_key(key, max):
            if key > max:
                return "<font color=red>%.1f</font>" % key
            else:
                return "%.1f" % key

        # Kernel virtual memory subsystem statistics, /proc/vmstat
        pgmajfault = (run2['/proc/vmstat']['pgmajfault']-run1['/proc/vmstat']['pgmajfault'])/cpu_total_diff*3600
        pswpin     = (run2['/proc/vmstat']['pswpin']-run1['/proc/vmstat']['pswpin'])/cpu_total_diff*3600
        pswpout    = (run2['/proc/vmstat']['pswpout']-run1['/proc/vmstat']['pswpout'])/cpu_total_diff*3600
        diffs = []
        if pgmajfault > 0:
            diffs.append(("Major page faults per hour", format_key(pgmajfault, 1000)))
        if pswpin > 0:
            diffs.append(("Page swap ins per hour", format_key(pswpin, 10000)))
        if pswpout > 0:
            diffs.append(("Page swap outs per hour", format_key(pswpout, 1000)))
        if diffs:
            print '\n<p><table border=1 bgcolor=%s>' % Colors.kernel
            print "<caption><i>Virtual memory subsystem</i></caption>"
            print "<tr><th>Type:</th><th>Value:</th></tr>"
            for data in diffs:
                print "<tr><td>%s</td><td align=right><b>%s</b></td></tr>" % data
            print "</table>"

        # Interrupts and context switches.
        intr = (run2['/proc/stat']['intr']-run1['/proc/stat']['intr'])/cpu_total_diff
        ctxt = (run2['/proc/stat']['ctxt']-run1['/proc/stat']['ctxt'])/cpu_total_diff
        diffs = [
                 ("Interrupts per second", format_key(intr, 1e5/3600)),
                 ("Context switches per second", format_key(ctxt, 1e6/3600)),
                ]
        print '\n<p><table border=1 bgcolor=%s>' % Colors.kernel
        print "<caption><i>Low level system events</i></caption>"
        print "<tr><th>Type:</th><th>Value:</th></tr>"
        for data in diffs:
            print "<tr><td>%s</td><td align=right><b>%s</b></td></tr>" % data
        print "</table>"


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
    print "<p>Free system RAM: <b>%d</b> kB" % run['ram_free']
    print "<br>(free = free+cached+buffered+slab reclaimable)"
    if run['swap_total']:
        print "<p>Free system Swap: <b>%d</b> kB (out of <b>%d</b> kB)" % (run['swap_free'], run['swap_total'])
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

def output_graph_table(titles, colors, data):
    "outputs memory usage bars for given (name, (values), tex(t)) tupple array"
    width = 640 # total width of the graph bars
    print "<table><tr>"
    # column titles
    for title in titles:
        if title:
            print "<th>%s</th>" % title
        else:
            print "<th></th>"
    print "</tr>"
    for item in data:
        # row title
        print '<tr><td>%s</td>' % item[0]
        # graphical bar
        print "<td><table border=0 cellpadding=0 cellspacing=0><tr>"
        for idx in range(len(colors)):
            w = int(item[1][idx]*width)
            if w:
                sys.stdout.write('<td bgcolor="%s" width=%d height=16></td>' % (colors[idx], w))
        print "</tr></table></td>"
        # texts at end
        for text in item[2]:
            if text:
                print '<td align="right">%s</td>' % text
            else:
                print "<td></td>"
        print "</tr>"
    print "</table>"


def output_apps_memory_graphs(cases):
    "outputs memory graphs bars for the individual processes"
    # arrange per use-case data to be per pid
    smaps_available = 0
    rounds = 0
    data = {}
    pidinfo = {}
    # get names and pids
    for testcase in cases:
        commands = testcase['commands']
        cmdlines = testcase['cmdlines']
        processes = testcase['processes']
        for process in processes.values():
            pid = process['Pid']
            if pid not in commands:
                sys.stderr.write("Debug: %s[%s] in status list but not in FD list\n" % (process['Name'], pid))
                continue
            if not pid_is_main_thread(pid, commands, processes):
                continue
            name = commands[pid]
            try:
                process['SMAPS_PRIVATE_DIRTY'] = testcase['smaps'][pid]['private_dirty']
                smaps_available = 1
            except KeyError:
                if 'smaps' in testcase:
                    syslog.parse_error(sys.stdout.write, "WARNING: SMAPS data missing for %s[%s]" % (name,pid))
            try: process['SMAPS_SWAP'] = testcase['smaps'][pid]['swap']
            except KeyError: pass
            try: process['SMAPS_PSS'] = testcase['smaps'][pid]['pss']
            except KeyError: pass
            try: process['SMAPS_RSS'] = testcase['smaps'][pid]['rss']
            except KeyError: pass
            try: process['SMAPS_SIZE'] = testcase['smaps'][pid]['size']
            except KeyError: pass
            if pid not in data:
                data[pid] = {}
                pidinfo[pid] = {}
            data[pid][rounds] = process
            pidinfo[pid] = (name, cmdlines[pid])
        rounds += 1

    # get largest size for any of the namepids, get largest rss
    # for sorting and ignore items which rss/size don't change
    #
    # Also filter out processes that get dirty pages swapped to disk:
    #
    #     initial state: Swap:0kB Dirty:100kB
    #     ...
    #     last round:    Swap:8kB Dirty:92kB
    #
    sizes = []
    largest_size = 0
    for pid in data:
        changerounds = pidrounds = 0
        max_size = max_dirty = max_swap = 0
        min_size = min_dirty = min_swap = 512*1024
        for idx in range(rounds):
            if idx in data[pid]:
                try:    dirty = data[pid][idx]['SMAPS_PRIVATE_DIRTY']
                except: dirty = data[pid][idx]['VmRSS']
                try:    size  = data[pid][idx]['SMAPS_SIZE']
                except: size  = data[pid][idx]['VmSize']
                try:    swap  = data[pid][idx]['SMAPS_SWAP']
                except: swap  = 0
                min_dirty = min(dirty, min_dirty)
                max_dirty = max(dirty, max_dirty)
                min_swap = min(swap, min_swap)
                max_swap = max(swap, max_swap)
                if size < min_size:
                    if pidrounds:
                        changerounds += 1
                    min_size = size
                if size > max_size:
                    if pidrounds:
                        changerounds += 1
                    max_size = size
                pidrounds += 1
        if pidrounds > 1:
            if max_dirty+min_swap:
                swap_and_dirty_change = (float)((max_dirty+min_swap) - (min_dirty+max_swap)) / (max_dirty+min_swap) / pidrounds
            else:
                if smaps_available:
                    syslog.parse_error(sys.stdout.write, "WARNING: no SMAPS dirty for %s[%s]. Disable swap and try again\n\t(SMAPS doesn't work properly with swap)" % (pid, pidinfo[pid][0]))
                swap_and_dirty_change = 0
            size_change = (float)(max_size - min_size) / max_size / pidrounds
            # if >0.2% memory change per round in dirty or Size, or
            # size changes on more than half of the rounds, add to list
            if swap_and_dirty_change > 0.002 or size_change > 0.002 or 2*changerounds > pidrounds:
                sizes.append((max_dirty,pid))
        if max_size > largest_size:
            largest_size = max_size
    largest_size = float(largest_size)
    
    # first sort according to the dirty (or RSS) size
    sizes.sort()
    sizes.reverse()
    # then sort according to names
    orders = []
    for size in sizes:
        pid = size[1]
        # data and sorting order is: name, first round for pid, pid
        orders.append((pidinfo[pid][0], min(data[pid].keys()), pid))
    del(sizes)
    orders.sort()
    
    # amount of memory in the device (float for calculations)
    print """
<p>Only processes which VmSize and amount of private dirty memory
changes during tests are listed.  If a process has same name and size
as its parent, it's assumed to be a thread and ignored.

<p>Note: RSS can decrease if device is just running low on memory because
kernel can just discard unmodified/unused pages. Size tells amount of
all virtual allocations and memory maps of a process, so it might not
have any relation to real process memory usage. However, it can show
leaks which cause process eventually to run out of (2GB) address space
(e.g. if it's not collecting joinable thread resources).
"""

    # LEGEND
    print '<p><table><tr><th><th align="left">Legend:'
    if smaps_available: print """
<tr><td bgcolor="%s" height="16" width="16"><td>Swap
<tr><td bgcolor="%s" height="16" width="16"><td>Dirty
<tr><td bgcolor="%s" height="16" width="16"><td>PSS: Proportional Set Size -- amount of resident memory, where each 4kB memory page is divided by the number of processes sharing it.
""" % (bar2colors[0], bar2colors[1], bar2colors[2])
    print """
<tr><td bgcolor="%s" height="16" width="16"><td>RSS: Resident Set Size
<tr><td bgcolor="%s" height="16" width="16"><td>Size
</table>
""" % (bar2colors[3], bar2colors[4])

    for order in orders:
        name = order[0]
        pid = order[2]
        cmdline = pidinfo[pid][1].replace('"', "&quot;")
        print '<h4><i><acronym title="%s">%s</acronym> [%s]</i></h4>' % (cmdline, name, pid)
        process = data[pid]
        namepid = (name, pid)
        text = ''
        prev_idx = 0
        prev_text = ""
        columndata = []
        for idx in range(rounds):
            if idx in process:
                item = process[idx]

                rss = item['VmRSS']
                size = item['VmSize']
                if smaps_available:
                    try: dirty = item['SMAPS_PRIVATE_DIRTY']
                    except: dirty = 0
                    try: swap = item['SMAPS_SWAP']
                    except: swap = 0
                    try: rss = item['SMAPS_RSS']
                    except: pass
                    try: pss = item['SMAPS_PSS']
                    except: pss = 0
                    try: size = item['SMAPS_SIZE']
                    except: pass
                    if rss < dirty:
                        syslog.parse_error(sys.stdout.write, "WARNING: %s[%s] RSS (%s) < SMAPS dirty (%s)" % (namepid + (rss, dirty)))
                        rss = dirty
                    if pss < dirty:
                        syslog.parse_error(sys.stdout.write, "WARNING: %s[%s] SMAPS PSS (%s) < SMAPS dirty (%s)" % (namepid + (pss, dirty)))
                    if rss < pss:
                        syslog.parse_error(sys.stdout.write, "WARNING: %s[%s] RSS (%s) < SMAPS PSS (%s)" % (namepid + (rss, pss)))
                    text = ["%skB" % swap, "%skB" % dirty, "%skB" % pss, "%skB" % rss, "%skB" % size]
                else:
                    swap = 0
                    dirty = 0
                    pss = 0
                    text = ["", "", "", "%skB" % rss, "%skB" % size]
                barwidth_swap  = swap/largest_size
                barwidth_dirty = dirty/largest_size
                barwidth_pss   = pss/largest_size
                barwidth_rss   = rss/largest_size
                barwidth_size  = size/largest_size
                #  ___________________________________________________
                # |      |    ____________________     |              |
                # |      |   |  _______________   |    |              |
                # |      |   | |               |  |    |              |
                # | SWAP |   | | Private Dirty |  |    |              |
                # |      |   | |_______________|  |    |              |
                # |      |   |        PSS         |    |              |
                # |      |   |____________________|    |              |
                # |      |            RSS              |              |
                # |______|_____________________________|              |
                # |                   Size                            |
                # |___________________________________________________|
                #
                sizes = (barwidth_swap,
                         barwidth_dirty,
                         barwidth_pss - barwidth_dirty,
                         barwidth_rss - barwidth_pss,
                         barwidth_size - barwidth_swap - barwidth_rss)
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
                sizes = (0,0,0,0,0)
                text = nan
                case = "---"
            columndata.append((case, sizes, text))
        titles = ['Test-case:', 'Graph', 'Swap:', 'Dirty:', 'PSS:', 'RSS:', 'Size:']
        if not smaps_available:
            titles[2] = "" #Swap
            titles[3] = "" #Dirty
            titles[4] = "" #PSS
        output_graph_table(titles, bar2colors, columndata)


def output_system_load_graphs(data):
    print '<p>System CPU time distribution during the execution of test cases.'
    print '<p>'
    prev = data[0]
    entries = []
    idx = 1
    reboots = []
    for testcase in data[1:]:
        case = '<a href="#round-%d">Test round %02d</a>:' % (idx, idx)
        if sum(testcase['/proc/stat']['cpu'].itervalues()) < sum(prev['/proc/stat']['cpu'].itervalues()):
            entries.append((case, (0,0,0,0,0), "-"))
            reboots.append(idx)
        elif sum(testcase['/proc/stat']['cpu'].itervalues()) == sum(prev['/proc/stat']['cpu'].itervalues()):
            # Two identical entries? Most likely user has manually copied the snapshot directories.
            entries.append((case, (0,0,0,0,0), "-"))
        else:
            diffs = {}
            for key in testcase['/proc/stat']['cpu'].keys():
                diffs[key] = testcase['/proc/stat']['cpu'][key] - prev['/proc/stat']['cpu'][key]
            divisor = float(sum(diffs.values()))
            if divisor <= 0:
                entries.append((case, (0,0,0,0,0), "-"))
            else:
                for key in diffs.keys():
                    diffs[key] = diffs[key] / divisor
                bars = (diffs['system'] + diffs['irq'] + diffs['softirq'], \
                        diffs['user'], \
                        diffs['user_nice'], \
                        diffs['iowait'], \
                        diffs['idle'])
                entries.append((case, bars, ["%d%%" % int(100-100*diffs['idle'])]))
        idx += 1
        prev = testcase
    titles = ("Test-case:", "system load:", "CPU usage-%:")
    output_graph_table(titles, bar3colors, entries)
    if reboots:
        text = '<p>Reboots occured during rounds:'
        for r in reboots:
            text += " %d," % r
        print text[:-1] + '.<br>'
    # Legend
    print '<table><tr><th><th align="left">Legend:'
    print '<tr><td bgcolor="%s" height=16 width=16><td>CPU time used by <i>system</i> tasks, including time spent in interrupt handling' % bar3colors[0]
    print '<tr><td bgcolor="%s" height=16 width=16><td>CPU time used by <i>user</i> tasks' % bar3colors[1]
    print '<tr><td bgcolor="%s" height=16 width=16><td>CPU time used by <i>user</i> tasks with <i>low priority</i> (nice)' % bar3colors[2]
    print '<tr><td bgcolor="%s" height=16 width=16><td>CPU time wasted waiting for I/O (idle)' % bar3colors[3]
    print '<tr><td bgcolor="%s" height=16 width=16><td>CPU time idle' % bar3colors[4]
    print '</table>'


def output_network_use_graphs(data):
    interfaces = {}
    # collect interfaces
    for testcase in data:
        for face in testcase['transfers']:
            if face not in interfaces and testcase['transfers'][face] > 0:
                interfaces[face] = []
    faces = interfaces.keys()
    if not faces:
        print "<p>Only local or no interfaces up when measurements were taken."
        return

    # collect test round data per interfaces
    faces.sort()
    for testcase in data:
        for face in faces:
            if face in testcase['transfers']:
                interfaces[face].append(testcase['transfers'][face])
            else:
                interfaces[face].append(0)
    
    # arrange values shown as numbers and used for bar sizes into rounds
    previous = []
    for face in faces:
        previous.append(interfaces[face][0])
    prevrange = range(len(previous))
    # ...with max bar size to use as scale
    scale = 0
    rounds = []
    for r in range(1, len(data)):
        valdiff = []
        bardiff = []
        current = []
        for face in faces:
            current.append(interfaces[face][r])
        for i in prevrange:
            if current[i]:
                diff = current[i] - previous[i]
                valdiff.append(diff)
                if diff > 0:
                    bardiff.append(diff)
                else:
                    # interface down and up, show as zero (bar size cannot be negative)
                    bardiff.append(0)
            else:
                # interface down
                valdiff.append(0)
                bardiff.append(0)
        previous = current
        total = sum(bardiff)
        if total > scale:
            scale = total
        rounds.append((bardiff,valdiff))

    scale = float(scale)
    if not scale:
        print "<p>Active interfaces, but no network traffic during the test-cases."
        return
    
    # create table
    print '<p>Network interface usage distribution during the test-cases.'
    print '<p>'
    idx = 0
    entries = []
    for b,v in rounds:
        idx += 1
        bars = [x/scale for x in b]
        vals = ["%dkB" % (x/1024) for x in v]
        entries.append(('Test round %02d:' % idx, bars, vals))
    titles = ["Test-case:", "network usage:"] + ["%s:" % x for x in faces]
    output_graph_table(titles, bar1colors[:len(faces)], entries)
    # Legend
    print '<table><tr><th><th align="left">Legend:'
    for i in range(len(faces)):
        print '<tr><td bgcolor="%s" height=16 width=16><td>%s' % (bar1colors[i], faces[i])
    print '</table>'


def output_system_memory_graphs(data):
    "outputs memory graphs bars for the system"
    idx = 0
    swaptext = None
    columndata = []
    # See whether swap was used during the tests. We need to know this in
    # advance in the next loop.
    for testcase in data:
        if testcase['swap_used']:
            swaptext = "swap used:"
            break
    for testcase in data:
        if not idx:
            case = '<a href="#initial-state">Initial state</a>:'
        else:
            case = '<a href="#round-%d">Test round %02d</a>:' % (idx, idx)
        idx += 1

        # amount of memory in the device (float for calculations)
        mem_total = float(testcase['ram_total'] + testcase['swap_total'])
        
        # Fremantle low mem limits?
        if 'limitlowpages' in testcase:
            # limit is given as available free memory in pages
            mem_low  = mem_total - 4*testcase['limitlowpages']
            mem_high = mem_total - 4*testcase['limithighpages']
            mem_deny = mem_total - 4*testcase['limitdenypages']
        # Diablo low mem limits?
        elif 'limitlow' in testcase:
            # convert percentages to real memory values
            percent = 0.01 * mem_total
            # memory usage %-limit after which apps are bg-killed
            mem_low  = testcase['limitlow'] * percent
            # memory usage %-limit after which apps refuse certain operations
            mem_high = testcase['limithigh'] * percent
            # memory usage %-limit after which kernel denies app allocs
            mem_deny = testcase['limitdeny'] * percent
        # valid mem low limits?
        if mem_low + mem_high + mem_deny <= 0:
            mem_low = mem_high = mem_deny = mem_total
            sys.stderr.write("Warning: low memory limits are zero -> disabling\n")
        
        mem_used = testcase['ram_used'] + testcase['swap_used']
        mem_free = testcase['ram_free'] + testcase['swap_free']
        # Graphics
        show_swap = testcase['swap_used']/mem_total
        show_ram  = testcase['ram_used']/mem_total
        if mem_used > mem_deny:
            show_deny = (mem_total - mem_used)/mem_total
            show_free = 0.0
        else:
            show_deny = 1.0 - mem_deny/mem_total
            show_free = 1.0 - show_swap - show_ram - show_deny
        bars = (show_swap, show_ram, show_free, show_deny)
        # Numbers
        def label():
            if mem_used > mem_high: return "<font color=red><b>%d</b></font>kB"
            if mem_used > mem_low:  return "<font color=blue><b>%d</b></font>kB"
            return "%dkB"
        memtext = None
        if swaptext: memtext = label() % testcase['swap_used']
        memtext = (memtext,) + (label() % testcase['ram_used'], "%dkB" % mem_free)
        # done!
        columndata.append((case, bars, memtext))
    titles = ("Test-case:", "memory usage graph:", swaptext, "RAM used:", "free:")
    output_graph_table(titles, bar1colors, columndata)
    print '<table><tr><th><th align="left">Legend:'
    if testcase['swap_total']:
        print '<tr><td bgcolor="%s" height="16" width="16"><td>Swap used' % bar1colors[0]
    print """
<tr><td bgcolor="%s" height="16" width="16"><td>RAM used in the device
<tr><td bgcolor="%s" height="16" width="16"><td>RAM and swap freely usable in the device
<tr><td bgcolor="%s" height="16" width="16"><td>If memory usage reaches this, applications allocations fail and usually they abort as a result (&gt;= %d MB used)
""" % (bar1colors[1], bar1colors[2], bar1colors[3], round(mem_deny/1024))
    print "</table>"
    if mem_low == mem_total:
        print "<p>(memory limits are not in effect)"
        return
    print """
<p>Memory usage values which trigger application background killing and disable their
pre-starting are marked with blue color (&gt;= <font color=blue><b>%d</b></font> MB used).<br>
After bg-killing and memory low mark comes the memory high pressure mark at which point
even pre-started applications are killed and e.g. Browser refuses to open new pages,
these numbers are marked with red color (&gt;= <font color=red><b>%d</b></font> MB used).
""" % (round(mem_low/1024), round(mem_high/1024))


# ------------------- output all data -------------------------

def output_html_report(data):
    title = "Endurance measurements report"
    rounds = len(data)-1
    last = rounds
    first = 1

    # X client names may contain UTF-8 characters, so add character encoding.
    print """<html>
<head>
<meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>
<title>%s</title>
</head>
<body>
<h1>%s</h1>

<!-- endurance_report.py v2.0 -->

<p><b>Contents:</b>
<ul>
<li><a href="#initial-state">Initial state</a>
<li>Resource usage overview for the test rounds:
  <ul>
    <li><a href="#system-memory">System memory usage</a>
    <li><a href="#system-load">System load</a>
    <li><a href="#network-use">Network usage</a>
    <li><a href="#process-memory">Processes memory usage</a>
  </ul>
<li>Resource usage changes for each of the test rounds:
  <ul>
""" % (title, title)   #" fool Jed syntax highlighter
    for round in range(rounds):
        idx = round + 1
        if data[idx].has_key('description') and data[idx]['description']:
            desc = " (%s)" % data[idx]['description']
        else:
            desc = ""
        print '  <li><a href="#round-%d">Round %d</a>%s' % (idx, idx, desc)
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
<h2>Resource usage overview for the test rounds</h2>
<h3>System memory usage</h3>
"""
    output_system_memory_graphs(data)
    print """
<hr>
<a name="system-load"></a>
<h3>System load</h3>"""
    output_system_load_graphs(data)
    print """
<hr>
<a name="network-use"></a>
<h3>Network usage</h3>"""
    output_network_use_graphs(data)
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

        # get basic information
        file, filename = syslog.open_compressed("%s/usage.csv" % dirname, syslog.FATAL)
        items = parse_csv(file, filename)
        if not items:
            syslog.error_exit("CSV parsing failed")

        # filename without the extension
        items['basedir'] = dirname

        filename = "%s/step.txt" % dirname
        if os.path.exists(filename):
            # use-case step description
            items['description'] = open(filename).read().strip()

        file, filename = syslog.open_compressed("%s/smaps.cap" % dirname)
        if file:
            # get system SMAPS memory usage data
            items['smaps'], items['private_code'] = parse_smaps(file)
            if not items['smaps']:
                syslog.error_exit("SMAPS data parsing failed")

        file, filename = syslog.open_compressed("%s/syslog" % dirname)
        if file:
            # get the crashes and other errors
            items['logfile'] = filename
            items['errors'] = syslog.parse_syslog(sys.stdout.write, file)

        file, filename = syslog.open_compressed("%s/stat" % dirname)
        if file:
            items['/proc/stat'] = parse_proc_stat(file)
            if not items['/proc/stat']:
                syslog.error_exit("/proc/stat parsing failed")

        file, filename = syslog.open_compressed("%s/ifconfig" % dirname)
        if file:
            items['transfers'] = parse_ifconfig(file)
            if not items['transfers']:
                syslog.error_exit("ifconfig output parsing failed")

        data.append(items)
    return data


if __name__ == "__main__":
    if len(sys.argv) < 3:
        msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
        syslog.error_exit(msg)
    # Use psyco if available. Gives 2-3x speed up.
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    stats = parse_syte_stats(sys.argv[1:])
    output_html_report(stats)
