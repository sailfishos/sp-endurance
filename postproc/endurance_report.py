#!/usr/bin/python
# vim: et:ts=4:sw=4:
#
# This file is part of sp-endurance.
#
# Copyright (C) 2006-2012 by Nokia Corporation
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
# - See git and project changelog file.
#
# TODO:
# - Proper option parsing + possibility to state between which
#   test runs to produce the summaries?
"""
NAME
        <TOOL_NAME>

SYNOPSIS
        <TOOL_NAME> [options] <data directories>

OPTIONS

  --show-all  Give memory graphs for all processes, don't use heuristics
              to hide "non-interesting" ones
  -h, --help  This help

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

logparser_config_syslog = None

# how many CPU clock ticks kernel reports / second
CLK_TCK=100.0

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

    magenta     = "EE00FF"
    blue        = "3149BD"
    light_green = "ADE739"
    red         = "DE2821"
    orange      = "E0673E"
    orangeish   = "EAB040"
    yellow      = "FBE84A"
    light_blue  = "4265FF"

# color values for (Swap used, RAM used, memory free, oom-limit)
bar1colors = (Colors.magenta, Colors.blue, Colors.light_green, Colors.red)

# color values for (Swap, Dirty, PSS, RSS, Size)
bar2colors = (Colors.magenta, Colors.red, Colors.orange, Colors.orangeish, Colors.yellow)

# color values for CPU load (system, user, user nice, iowait, idle)
bar3colors = (Colors.red, Colors.blue, Colors.light_blue, Colors.magenta, Colors.light_green)

# color values for network interfaces
interface_colors = (Colors.magenta, Colors.blue, Colors.orange, Colors.light_green, Colors.red, Colors.orangeish, Colors.light_blue, Colors.yellow)

# whether to show memory graphs for all processes
show_all_processes = False

def error_exit(msg):
    sys.stderr.write("ERROR: %s!\n" % msg)
    sys.exit(1)

def parse_warning(msg):
    print "<p><font color=red>%s</font>" % msg
    print >>sys.stderr, msg

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
    for line in file:
        if not line:
            break
        idx += 1
        line = line[:-1]
        if not line:
            continue
        #print line        #DEBUG
        if line[0] == '=':
            # ==> /proc/767/smaps <==
            continue
        if line[0] == '#':
            if line[0:6] == "#Pid: ":
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
        if line[0] >= 'A' and line[0] <= 'Z':
            if line[0:14] == "Private_Dirty:":
                amount = int(line[15:-2])
                if code and amount:
                    #print line
                    #sys.stderr.write("dirty code: %s, %dkB\n" %(mmap, amount))
                    private_code += amount
                smaps[pid]['private_dirty'] += amount
                #print "ADD"        #DEBUG
                continue
            if line[0:5] == 'Swap:':
                smaps[pid]['swap'] += int(line[6:-2])
                continue
            if line[0:4] == "Pss:":
                smaps[pid]['pss'] += int(line[5:-2])
                continue
            if line[0:4] == 'Rss:':
                smaps[pid]['rss'] += int(line[5:-2])
                continue
            if line[0:5] == 'Size:':
                smaps[pid]['size'] += int(line[6:-2])
                continue
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


# --------------------- DSME rich-cores parsing ---------------------------

def get_dsme_rich_cores(dirname):
    dsme_rich_cores = {}
    try:
        for entry in os.listdir(dirname + "/dsme/rich-cores"):
            f = None
            try:
                f = open(dirname + "/dsme/rich-cores/" + entry)
            except IOError: pass
            if not f: continue
            core_count = f.readline().strip()
            f.close()
            if not core_count: continue
            try:
                core_count = int(core_count)
                if core_count <= 0: continue
                dsme_rich_cores[entry] = core_count
            except ValueError:
                continue
    except OSError:
        pass
    return dsme_rich_cores

# --------------------- Upstart respawned jobs ---------------------------

def get_upstart_jobs_respawned(file):
    upstart_jobs_respawned = {}
    for line in file:
        m = re.search("(\S+): (\d+)", line)
        if m:
            job = m.group(1)
            if not job:
                continue
            count = m.group(2)
            try:
                count = int(count)
                if count <= 0:
                    continue
            except ValueError:
                continue
            upstart_jobs_respawned[job] = count
    return upstart_jobs_respawned

# --------------------- CSV parsing ---------------------------

def get_filesystem_usage(file, split_pattern):
    """reads Filesystem,1k-blocks,Used,Available,Use%,Mountpoint fields
    until empty line, returns hash of free space on interesting mountpoints
    """
    prev = None
    mounts = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        cols = re.split(split_pattern, line)
        # handle lines that 'df' has split
        if len(cols) < 6:
            if prev:
                sys.stderr.write("Error: invalid number of columns in 'df' output:\n  %s\n" % line)
                sys.exit(1)
            prev = cols
            continue
        if prev:
            # first column should be empty, it indicates line is wrapped
            if cols[0]:
                sys.stderr.write("Error: invalid number of columns in 'df' output:\n  %s\n" % line)
                sys.exit(1)
            cols = prev+cols[1:]
            prev = None
        fs,blocks,used,available,inuse,mount = cols
        mounts[mount] = int(used)
    return mounts

def get_filesystem_usage_csv(file):
    return get_filesystem_usage(file, ",")

def get_filesystem_usage_df(file):
    if not file.readline().startswith("Filesystem"):
        raise RuntimeError
    return get_filesystem_usage(file, "\s+")

# Input from sp-endurance < v2.1.5 (column order is fixed):
#    res-base,Windows,Pixmaps,GCs,Fonts,Cursors,Colormaps,Map entries,Other clients,\
#             Grabs,Pictures,Pictformats,Glyphsets,CRTCs,Modes,Outputs,Xi clients,\
#             Unknown,Pixmap mem,Misc mem,Total mem,PID,Identifier
#    0e00000,6,15,1,1,1,1,0,3,0,57,0,14,0,0,0,6,201,2428324B,7984B,2436308B,1227,duihome
#    1800000,13,18,3,1,1,3,0,1,0,69,0,9,0,0,0,13,28,2415322B,4384B,2419706B,2197,Status Indicator Menu
#    0800000,0,157,1,0,0,1,0,1,0,173,0,0,0,0,0,1,64,993033B,5784B,998817B,-1,<unknown>
#    ...
#
# Input from sp-endurance >= v2.1.5 (resource atom column order varies):
#    res-base,WINDOW,FONT,CURSOR,COLORMAP,PICTFORMAT,XvRTPort,MODE,CRTC,OUTPUT,\
#             ...,\
#             total_resource_count,Pixmap mem,Misc mem,Total mem,PID,Identifier
#    1a00000,12,1,1,4,0,0,0,0,0,3,0,0,0,15,2,1,58,16,28,3,12,1,1,1,0,0,0,0,0,159,1689742B,4456B,1694198B,1982,LockScreenUI
#    1000000,9,1,1,1,0,0,0,0,0,1,0,0,6,6,3,9,4,0,138,0,5,1,0,1,0,1,8,1,6,202,1589760B,5704B,1595464B,-1,MCompositor
#    0a00000,0,0,0,1,0,0,0,0,0,0,0,0,0,160,1,1,176,0,65,0,1,1,0,1,0,0,0,0,0,407,959714B,5928B,965642B,-1,<unknown>
#    ...
#
# Output:
#  {
#    'res-base' = {
#              'duihome': '0e00000',
#              'clipboard': '3a00000',
#    },
#    'FONT' = {
#              'duihome': 1,
#              'clipboard': 2,
#    },
#    'WINDOW' = {
#              'duihome': 3,
#              'clipboard': 4,
#    },
#    ...
#    'total_resource_count' = {
#              'duihome': 128,
#              'clipboard': 256,
#    },
#    'Pixmap mem' = {...},
#    'Misc mem' = {...},
#    'Total mem' = {...},
#    'PID' = {...},
#  }
def get_xres_usage(file, header = None):
    xmeminfo = {}
    if not header:
        header = file.readline()
    columns = header.strip().split(',')
    while 1:
        line = file.readline().strip()
        if not line:
            break

        cols = line.split(',')
        # If the name contained commas, fix it back to original form.
        if len(cols) > len(columns):
            name = ",".join(cols[len(columns)-1:])
            del cols[len(columns)-1:]
            cols.append(name)
        else:
            name = cols[-1]
        for i in range(len(columns)-1):
            if not columns[i] in xmeminfo: xmeminfo[columns[i]] = {}
            xmeminfo[columns[i]][name] = cols[i]

        for memcol in ("Pixmap mem", "Misc mem", "Total mem"):
            if xmeminfo[memcol][name][-1] != 'B':
                sys.stderr.write("Error: X resource total memory value not followed by 'B':\n  %s\n" % line)
                sys.exit(1)
            xmeminfo[memcol][name] = int(xmeminfo[memcol][name][:-1]) / 1024

        # Convert numerical values to integers.
        for i in range(len(columns)-1)[1:]:
            xmeminfo[columns[i]][name] = int(xmeminfo[columns[i]][name])

        # total_resource_count column was added to xmeminfo in v2.1.5.
        if not 'total_resource_count' in columns:
            if not 'total_resource_count' in xmeminfo: xmeminfo['total_resource_count'] = {}
            xmeminfo['total_resource_count'][name] = sum([int(x) for x in cols[1:-5]])

    return xmeminfo

def get_component_version(file):
    component_version = {}
    for line in file:
        m = re.match("product\s+(\S+)", line)
        if m:
            component_version['product'] = m.group(1)
        m = re.match("hw-build\s+(\S+)", line)
        if m:
            component_version['hw-build'] = m.group(1)
    return component_version

#++ BME stat
#   charger state:         CONNECTED
#   charger type:          USBWALL
#   charging state:        STARTED
#   charging type:         LITHIUM
#   charging time:         15
#   battery state:         OK
#   battery type:          LI4V35
#   battery temperature:   33.85
#   battery max. level:    8
#   battery cur. level:    8
#   battery pct. level:    100
#   battery max. capacity: 1450
#   battery cur. capacity: 1450
#   battery last full cap: 1508
#   battery max. voltage:  4350
#   battery cur. voltage:  4333
#   battery current:       -146
#   battery condition:     UNKNOWN
def get_bmestat(file):
    bmestat = {}
    for line in file:
        m = re.match("\s+(\S+.*):\s*(\S+)", line)
        if m:
            key = m.group(1)
            value = m.group(2)
            key = key.replace(' ', '_')
            key = key.replace('.', '')
            bmestat[key] = value
    return bmestat

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


def get_proc_pid_iostat(file, headers):
    "parse processes disk write statistics from CSV file"
    fields = headers.strip().split(',')
    pididx = fields.index('PID')
    wrtidx = fields.index('write_bytes')
    stat = {}
    while 1:
        line = file.readline().strip()
        if not line:
            break
        cols = line.split(',')
        stat[cols[pididx]] = int(cols[wrtidx])/1024
    return stat


def parse_cgroups(file):
    pid2cgroup = {}
    tid2cgroup = {}
    cgroups = {}
    for line in file:
        if not line:
            break
        m = re.search("^==> /syspart(\S*/)memory\.memsw\.usage_in_bytes <==", line)
        if m:
            groupname = m.group(1)
            if not groupname in cgroups:
                cgroups[groupname] = {}
            for usageline in file:
                usage = usageline
                break
            cgroups[groupname]['memory.memsw.usage_in_bytes'] = int(usage)
            continue
        m = re.search("^==> /syspart(\S*/)memory\.usage_in_bytes <==", line)
        if m:
            groupname = m.group(1)
            if not groupname in cgroups:
                cgroups[groupname] = {}
            for usageline in file:
                usage = usageline
                break
            cgroups[groupname]['memory.usage_in_bytes'] = int(usage)
            continue
        m = re.search("^==> /syspart(\S*/)memory\.limit_in_bytes <==", line)
        if m:
            groupname = m.group(1)
            if not groupname in cgroups:
                cgroups[groupname] = {}
            for usageline in file:
                usage = usageline
                break
            cgroups[groupname]['memory.limit_in_bytes'] = int(usage)
            continue
        m = re.search("^==> /syspart(\S*/)cgroup\.procs <==", line)
        if m:
            groupname = m.group(1)
            for proc in file:
                if not proc:
                    break
                m = re.search("(^\d+)", proc)
                if not m:
                    break
                pid = int(m.group(1))
                pid2cgroup[pid] = groupname
            continue
        m = re.search("^==> /syspart(\S*/)tasks <==", line)
        if m:
            groupname = m.group(1)
            for proc in file:
                if not proc:
                    break
                m = re.search("(^\d+)", proc)
                if not m:
                    break
                tid = int(m.group(1))
                tid2cgroup[tid] = groupname
            continue
    return (pid2cgroup, tid2cgroup, cgroups)

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


def skip_to(file, header, mandatory):
    "reads the given file until first CSV column has the given header"
    while 1:
        line = file.readline()
        if not line:
            if not mandatory:
                return None
            sys.stderr.write("\nError: premature file end, CSV header '%s' not found\n" % header)
            sys.exit(2)
        if line.startswith(header):
            return line

def skip_to_next_header(file):
    "reads the given file until we get first nonempty line"
    while 1:
        line = file.readline()
        if not line:
            sys.stderr.write("\nError: premature file end while scanning for CSV header\n")
            sys.exit(2)
        line = line.strip()
        if line:
            return line


def parse_csv(file, filename):
    "Parses interesting information from the endurance measurement CSV file"
    data = {}
    
    # Check that file is generated with correct script so that
    # we can trust it's format and order of rows & fields:
    # format: generator = <generator name> <version>
    mygen = "syte-endurance-stats"
    generator = file.readline().strip().split(' ')
    if len(generator) < 4 or generator[2] != mygen:
        sys.stderr.write("\nError: CSV file '%s' is not generated by '%s'!\n" % (filename, mygen))
        sys.exit(1)

    generator_version_major = -1
    try: generator_version_major = int(generator[3][1])
    except: pass

    # get the basic data
    file.readline()
    data['release'] = file.readline().strip()
    data['datetime'] = file.readline().strip()
    if data['release'][:2] != "SW" or data['datetime'][:7] != "date = ":
        sys.stderr.write("\nError: CSV file '%s' is missing 'SW-version' or 'date' fields!\n" % filename)
        sys.exit(1)

    data['datetime'] = data['datetime'][7:]

    # get uptime for reboot detection
    skip_to(file, "Uptime", True)
    data['uptime'] = float(file.readline().split(',')[0])

    # total,free,buffers,cached
    mem_header = skip_to(file, "MemTotal", True).strip()
    mem_values = file.readline().strip()
    get_meminfo(data, mem_header, mem_values)

    # /proc/vmstat
    # The header line ends with ':', so get rid of that.
    keys = skip_to(file, "nr_free_pages", True).strip()[:-1].split(',')
    try:
        vals = [int(x) for x in file.readline().strip().split(',')]
        data['/proc/vmstat'] = dict(zip(keys, vals))
    except:
        pass

    # get shared memory segment counts
    skip_to(file, "Shared memory segments", True)
    data['shm'] = get_shm_counts(file)

    # get system free FDs
    skip_to(file, "Allocated FDs", True)
    fdused,fdfree,fdtotal = file.readline().split(',')
    data['fdfree'] = (int(fdtotal) - int(fdused)) + int(fdfree)

    # get the process FD usage
    skip_to(file, "PID,FD count,Command", True)
    data['commands'], data['fdcounts'], data['cmdlines'] = get_commands_and_fd_counts(file)
    
    # get process statistics
    headers = skip_to(file, "Name,State,", True)
    data['processes'], data['kthreads'] = get_process_info(file, headers)

    # check if we have /proc/pid/stat in the CSV file
    headers = skip_to_next_header(file)

    if generator_version_major > 2:
        # get numeric process information
        data['/proc/pid/stat'] = get_proc_pid_stat(file)

        # get optional IO statistics, if they exist
        headers = skip_to(file, "PID,rchar,", False)
        if headers:
            data['IO'] = get_proc_pid_iostat(file, headers)
        return data
    
    # Rest of the sections only available in endurance data versions prior to v3.

    if headers.startswith("Process status:"):
        data['/proc/pid/stat'] = get_proc_pid_stat(file)
        headers = skip_to(file, "res-base", True)
    elif headers.startswith("res-base"):
        pass
    else:
        sys.stderr.write("\nError: unexpected '%s' in CSV file\n" % headers)
        sys.exit(2)

    # get the X resource usage
    data['xmeminfo'] = get_xres_usage(file, headers)

    # get the file system usage
    skip_to(file, "Filesystem", True)
    data['mounts'] = get_filesystem_usage_csv(file)
    
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

def __unique_names(namepid1, namepid2):
    unused_new_pids = {}
    for name, pid in namepid2:
        unused_new_pids[pid] = 1
    new_namepid1 = []
    for name, pid in namepid1:
        name_unique = True
        for name2, pid2 in namepid2:
            if name == name2 and pid2 in unused_new_pids:
                name_unique = False
                del unused_new_pids[pid2]
                break
        new_namepid1.append((name, pid, name_unique))
    return new_namepid1

def output_process_changes(pids1, pids2, titles, pid2cgroup1, pid2cgroup2, do_summary, show_cgroups=True):
    "outputs which commands are new and which gone in separate columns"
    # ignore re-starts i.e. check only command names
    namepid_gone = []
    namepid_new = []
    for pid in pids2:
        if pid not in pids1:
            namepid_new.append((pids2[pid], int(pid)))
    for pid in pids1:
        if pid not in pids2:
            namepid_gone.append((pids1[pid], int(pid)))
    namepid_gone.sort()
    namepid_new.sort()

    # Check respawned processes so that we can highlight those that did not
    # respawn:
    namepid_gone2 = __unique_names(namepid_gone, namepid_new)
    namepid_new2 = __unique_names(namepid_new, namepid_gone)

    namepid_gone = namepid_gone2
    namepid_new = namepid_new2

    change = 0
    if namepid_gone or namepid_new:
        processes = len(pids2)
        change = processes - len(pids1)
        print "<p>%s: <b>%d</b>" % (titles[0], change)
        print "<br>(now totaling %d)." % processes

        print "<p><table border=0>"
        print "<tr style='vertical-align: top'>"

        print "<td><table border=1>"
        print "<tr><th>%s" % titles[1]
        print "<tr><th>Command[Pid]:"
        for name, pid, name_unique in namepid_gone:
            if name_unique:
                print ("<tr>" \
                        + "<td><del>%s</del>[%d]") \
                        % (name, pid)
            else:
                print ("<tr>" \
                        + "<td>%s[%d]") \
                        % (name, pid)
        print "</table>"

        print "<td><table border=1>"
        if show_cgroups:
            print "<tr><th colspan=2>%s" % titles[2]
            print "<tr><th>Command[Pid]:<th>Cgroup"
        else:
            print "<tr><th>%s" % titles[2]
            print "<tr><th>Command[Pid]:"
        for name, pid, name_unique in namepid_new:
            cgroup = ""
            if show_cgroups:
                if pid2cgroup2 and pid in pid2cgroup2:
                    cgroup = pid2cgroup2[pid]
                if name_unique:
                    cgroup = "<td><ins>%s</ins>" % cgroup
                else:
                    cgroup = "<td>%s" % cgroup
            if name_unique:
                print ("<tr>" \
                        + "<td><ins><b>%s</b>[%d]</ins>" \
                        + "%s") \
                        % (name, pid, cgroup)
            else:
                print ("<tr>" \
                        + "<td>%s[%d]" \
                        + "%s") \
                        % (name, pid, cgroup)
        print "</table>"

        print "</table>"

    if do_summary:
        print "<!--\n- %s: %+d\n-->" % (titles[0], change)

def output_new_dsme_rich_cores(dsme_rich_cores1, dsme_rich_cores2):
    crashed_processes = {}
    for process in dsme_rich_cores2:
        cnt2 = dsme_rich_cores2[process]
        if not process in dsme_rich_cores1:
            crashed_processes[process] = cnt2
        else:
            cnt1 = dsme_rich_cores1[process]
            if cnt2 > cnt1:
                crashed_processes[process] = cnt2 - cnt1
    if not crashed_processes:
        return
    print "<p><table border=1>"
    print "<caption><i>Process crashes reported by DSME</i></caption>"
    print "<tr>" \
            + "<th>Process:" \
            + "<th>Crashes:"
    for process in crashed_processes:
        print ("<tr>" \
                + "<td>%s" \
                + "<td align=right><b>%d</b>") % \
                (process, crashed_processes[process])
    print "</table>"

def output_new_upstart_jobs_respawned(upstart_jobs_respawned1, upstart_jobs_respawned2):
    respawned_jobs = {}
    for job in upstart_jobs_respawned2:
        cnt2 = upstart_jobs_respawned2[job]
        if not job in upstart_jobs_respawned1:
            respawned_jobs[job] = cnt2
        else:
            cnt1 = upstart_jobs_respawned1[job]
            if cnt2 > cnt1:
                respawned_jobs[job] = cnt2 - cnt1
    if not respawned_jobs:
        return
    print "<p><table border=1>"
    print "<caption><i>Upstart respawned jobs</i></caption>"
    print "<tr>" \
            + "<th>Job:" \
            + "<th>Respawn count:"
    for job in sorted(respawned_jobs.keys()):
        print ("<tr>" \
                + "<td>%s" \
                + "<td align=right><b>%d</b>") % \
                (job, respawned_jobs[job])
    print "</table>"

def output_cgroup_diffs(cgroups1, cgroups2):
    all_groups = cgroups2.keys()
    all_groups.sort()
    if not all_groups:
        return
    print "<p><table border=1 bgcolor=#%s>" % Colors.memory
    print "<caption><i>Control Groups</i></caption>"
    print "<tr>" \
            + "<th>Cgroup:" \
            + "<th>RAM+swap usage:" \
            + "<th>RAM usage (% of limit):" \
            + "<th>RAM usage change:" \
            + "<th>Swap usage:" \
            + "<th>Swap usage change:"
    for cgroup in all_groups:
        memory_limit_in_bytes = cgroups2[cgroup]['memory.limit_in_bytes']
        if memory_limit_in_bytes == 9223372036854775807 or memory_limit_in_bytes == 0:
            ram_pct = "N/A"
        else:
            ram_pct = 100 * (float(cgroups2[cgroup]['memory.usage_in_bytes']) / float(memory_limit_in_bytes))
            ram_pct = str(int(ram_pct)) + "%"
        swap1_kb = (cgroups1[cgroup]['memory.memsw.usage_in_bytes'] -
                    cgroups1[cgroup]['memory.usage_in_bytes']) / 1024
        swap2_kb = (cgroups2[cgroup]['memory.memsw.usage_in_bytes'] -
                    cgroups2[cgroup]['memory.usage_in_bytes']) / 1024
        print ("<tr>" \
                + "<td>%s" \
                + "<td align=right>%d kB" \
                + "<td align=right>%d kB (%s)" \
                + "<td align=right><b>%+d</b> kB" \
                + "<td align=right>%d kB" \
                + "<td align=right><b>%+d</b> kB") % \
                (cgroup,
                    cgroups2[cgroup]['memory.memsw.usage_in_bytes'] / 1024,
                    cgroups2[cgroup]['memory.usage_in_bytes'] / 1024, ram_pct,
                    (cgroups2[cgroup]['memory.usage_in_bytes'] -
                     cgroups1[cgroup]['memory.usage_in_bytes']) / 1024,
                    swap2_kb,
                    swap2_kb - swap1_kb)
    print "</table>"

def output_diffs(diffs, title, first_column_title, data_units, bgcolor, idx1, do_summary):
    "diffs = { <change>, <change from initial>, <total value>, <name> }"
    total_change              = sum([x[0] for x in diffs])
    total_change_from_initial = sum([x[1] for x in diffs])
    if diffs:
        diffs.sort()
        diffs.reverse()
        print '\n<p><table border=1 bgcolor="#%s">' % bgcolor
        print "<caption><i>%s</i></caption>" % title
        # HTML end tags (</th>, </tr>, </td>) omitted on purpose to reduce
        # output file size, it's permitted by the HTML4 spec.
        if idx1 > 0:
            print "<tr><th>%s:<th>Total:<th>Change:<th>Change from<br>initial state:" % first_column_title
        else:
            print "<tr><th>%s:<th>Total:<th>Change:" % first_column_title
        for change, change_from_initial, value, name in diffs:
            initialch = ""
            if idx1 > 0:
                initialch = "<td align=right>%+d%s" % (change_from_initial, data_units)
            print "<tr><td>%s<td align=right>%d%s<td align=right><b>%+d</b>%s%s" % \
                    (name, \
                     value, data_units, \
                     change, data_units, \
                     initialch)
        initialch = ""
        if idx1 > 0:
            initialch = "<td align=right>%+d%s" % (total_change_from_initial, data_units)
        print "<tr><td align=right><i>Total change =</i><td>&nbsp;<td align=right><b>%+d%s</b>%s" % \
                (total_change, data_units, initialch)
        print "</table>"
    if do_summary:
        print "<!--\n- %s change: %+d\n-->" % (title, total_change)

# list0: initial values
# list1 & list2: compare these rounds
#
# Input:
#   list0: {'/tmp': 48, '/': 852140}
#   list1: {'/tmp': 48, '/': 852140}
#   list2: {'/tmp': 52, '/': 851804}
#
# Output:
#   [
#    (4, 4, 52, '/tmp'),
#    (-336, -336, 851804, '/')
#   ]
#
def get_usage_diffs(list0, list1, list2):
    """return [(<change>, <change from initial>, <total value>, <name>), ...]"""
    diffs = []
    for name,value2 in list2.items():
        if name in list1:
            value1 = list1[name]
            if value2 != value1:
                change_from_initial = 0
                try: change_from_initial = value2 - list0[name]
                except KeyError: pass
                # will be sorted according to first column
                diffs.append((value2 - value1, change_from_initial, value2, name))
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

# values0: initial values
# values1 & values2: compare these rounds
#
# Input:
#   values0: {'4134': 12128, '3035': 2292, '2062': 1296, ...}
#   values1: {'4134': 12260, '3035': 2396, '2062': 1296, ...}
#   values2: {'4134': 12352, '3035': 2496, '2062': 1304, ...}
#
# Output:
#  [
#    (92, 224, 12352, 'fennec[4134]'),
#    (100, 204, 2496, 'mcompositor[3035]'),
#    (8, 8, 1304, 'sensord[2062]'),
#    ...
#  ]
#
def get_pid_usage_diffs(commands, processes, values0, values1, values2, kthreads=None):
    """return [(<change>, <change from initial>, <total value>, <name>), ...]
    of differences in numbers between two {pid:value} hashes, remove threads
    based on given 'processes' hash and name the rest based on the given
    'commands' hash"""
    diffs = []
    for pid in values2:
        if pid in values1:
            c1 = values1[pid]
            c2 = values2[pid]
            if c1 != c2:
                if pid in processes and pid in commands:
                    if not pid_is_main_thread(pid, commands, processes):
                        continue
                    name = commands[pid]
                elif kthreads and pid in kthreads:
                    name = "[%s]" % kthreads[pid]
                else:
                    sys.stderr.write("Warning: PID %s not in commands or processes\n" % pid)
                    continue
                if pid in values0:
                    change_from_initial = c2 - values0[pid]
                else:
                    change_from_initial = 0
                diffs.append((c2-c1, change_from_initial, c2, "%s[%s]" % (name, pid)))
    return diffs


def get_thread_count_diffs(commands, processes0, processes1, processes2):
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
            t0 = 0
            try: t0 = t2 - int(processes0[pid]['Threads'])
            except KeyError: pass
            # will be sorted according to first column
            diffs.append((t2-t1, t0, t2, "%s[%s]" % (name, pid)))
    return diffs

def syslog_error_summary_text(new_errors_by_category):
    for category in logparser_config_syslog.categories:
        count = 0
        if category in new_errors_by_category:
            count = len(new_errors_by_category[category])
        print "- %d %s" % (count, category)

def category_to_anchor(category):
    return category.replace("/", "_")

def create_errors_html(idx, run1, run2, new_errors_by_category):
    title = "Syslog errors for round %d" % idx
    url = "%s/errors.html" % run2['basedir']
    f = open(url, "w")
    print >>f, "<html>\n<title>%s</title>\n<body>\n<h1>%s</h1>\n" % (title, title)
    if 'basedir' in run1:
        path = run1['basedir']
        if path[0] != '/':
            # assume files are in the same hierachy
            path = "../" + path.split('/')[-1]
        path += "/errors.html"
        print >>f, '<a href="%s">Errors for previous round</a>' % path
    if new_errors_by_category:
        for category in logparser_config_syslog.categories:
            if category not in new_errors_by_category \
                    or len(new_errors_by_category[category]) <= 0:
                continue
            if category in logparser_config_syslog.category_description \
                    and logparser_config_syslog.category_description[category]:
                title = '<abbr title="%s">%s</abbr>' % (category,
                        logparser_config_syslog.category_description[category])
            else:
                title = category
            print >>f, '<a name="%s"></a>' % category_to_anchor(category)
            print >>f, "<h4>%s</h4>" % title
            print >>f, "<ul>"
            for message in new_errors_by_category[category]:
                print >>f, "<li>%s</li>" % message
            print >>f, "</ul>"
    print >>f, "<hr>"
    print >>f, """
<a name="signals"></a>
<h2>Crash signals explained</h2>
<p>Explanations of some common exit signals on the Maemo platform:
<table border="1">
<tr><th>Signal nro:</th><th>Signal name:</th><th>Usual meaning:</th></tr>
<tr><td>15</td><td>SIGTERM</td><td>Application was unresponsive so system terminated it.
Other reasons for termination are background killing, locale change and shutdown.</td></tr>
<tr><td>11</td><td>SIGSEGV</td><td>Process crashed to memory access error</td></tr>
<tr><td>9</td><td>SIGKILL</td><td>Application was unresponsive and/or didn't react to SIGTERM so system forcibly terminated it</td></tr>
<tr><td>6</td><td>SIGABORT</td><td>Program (glibc/glib) called abort() when a fatal program error was detected</td></tr>
<tr><td>7</td><td>SIGBUS</td><td>The process was terminated due to bad memory access.</td></tr>
<table>
"""
    print >>f, "</body>\n</html>"
    f.close()

def syslog_error_summary(run, new_errors_by_category, links=True):
    error_cnt = sum([len(new_errors_by_category[category]) for category in new_errors_by_category])
    if error_cnt <= 0:
        return
    errors_html = None
    if links and 'basedir' in run and os.path.exists("%s/errors.html" % run['basedir']):
        errors_html = "%s/errors.html" % run['basedir']
    print '\n<p><table border=1 bgcolor="#%s">' % Colors.errors
    print "<caption><i>Items logged to syslog</i></caption>"
    print "<tr><th>Error types:<th>Count:</tr>"
    for category in logparser_config_syslog.categories:
        if category not in new_errors_by_category \
                or len(new_errors_by_category[category]) <= 0:
            continue
        if category in logparser_config_syslog.category_description \
                and logparser_config_syslog.category_description[category]:
            title = '<abbr title="%s">%s</abbr>' % (category,
                    logparser_config_syslog.category_description[category])
        else:
            title = category
        print "<tr>"
        if errors_html:
            print ' <td align=left><a href="%s#%s">%s</a></td>' % \
                (errors_html, category_to_anchor(category), title)
        else:
            print " <td align=left>%s</td>" % title
        print " <td align=right>%d</td>" % len(new_errors_by_category[category])
        print "</tr>"
    print "<tr><td align=right><i>Total of items =</i></td><td align=right><b>%d</b></td></tr>" % error_cnt
    print "</table>"

def get_new_errors_by_category(run1, run2):
    errors_by_category1, errors_by_category2 = None, None
    if 'syslog_errors_by_category' in run1:
        errors_by_category1 = run1['syslog_errors_by_category']
    if 'syslog_errors_by_category' in run2:
        errors_by_category2 = run2['syslog_errors_by_category']
    if not errors_by_category1:
        return errors_by_category2
    if not errors_by_category2:
        return errors_by_category2
    new_errors_by_category = {}
    for category in errors_by_category2.keys():
        if not category in errors_by_category1:
            new_errors_by_category[category] = errors_by_category2[category]
            continue
        for message in errors_by_category2[category]:
            if message not in errors_by_category1[category]:
                if not category in new_errors_by_category:
                    new_errors_by_category[category] = []
                new_errors_by_category[category].append(message)
    return new_errors_by_category

def output_errors(idx, run1, run2):
    new_errors_by_category = get_new_errors_by_category(run1, run2)
    if new_errors_by_category:
        create_errors_html(idx, run1, run2, new_errors_by_category)
        syslog_error_summary(run2, new_errors_by_category)

def output_data_links(run):
    "output links to all collected uncompressed data"
    compression_suffixes = ("", ".gz", ".xz", ".lzo")
    basedir = run['basedir']
    print "<h4>For more details on...</h4>"
    print "<ul>"
    if 'logfile' in run:
        print '<li>log messages, see <a href="%s">syslog</a>' % run['logfile']
    if os.path.exists("%s/smaps.html" % basedir):
        print "<li>private memory usage of all processes, see"
        print '<a href="%s/smaps.html">smaps overview</a>' % basedir
    for suffix in compression_suffixes:
        if os.path.exists("%s/smaps.cap%s" % (basedir, suffix)):
            print "<li>private memory usage of all processes, see"
            print '<a href="%s/smaps.cap%s">smaps data</a>' % (basedir, suffix)
            break
    print "<li>process and device state details, see"
    print '<a href="%s/usage.csv">collected CSV data</a> and' % basedir
    print '<a href="%s/ifconfig">ifconfig output</a>' % basedir
    print "<li>rest of /proc/ information; see "
    for suffix in compression_suffixes:
        if os.path.exists("%s/open-fds%s" % (basedir, suffix)):
            print '<a href="%s/open-fds%s">open file descriptors</a>, ' % (basedir, suffix)
            break
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

#  Input (key='mounts'):
#     data[0]['mounts'] = {'/tmp': 48, '/': 852108}
#     data[1]['mounts'] = {'/tmp': 48, '/': 852140}
#     data[2]['mounts'] = {'/tmp': 48, '/': 851804, '/foo': 1}
#     ...
#
#  Output:
#     {'/tmp': 48, '/': 852108, '/foo' : 1}
#
def initial_values(data, key):
    result = {}
    for round in range(0, len(data)):
        if not key in data[round]:
            continue
        for x in data[round][key]:
            if x not in result:
                try: result[x] = data[round][key][x]
                except KeyError: pass
            else:
                try:
                    for y in data[round][key][x]:
                        if y not in result[x]:
                            result[x][y] = data[round][key][x][y]
                except KeyError: pass
                except TypeError: pass

    return result

def __cpu_tickdiff(round1, round2, pid, category):
    return round2['/proc/pid/stat'][int(pid)][category] - \
           round1['/proc/pid/stat'][int(pid)][category]

# Per-PID difference in used user+sys CPU clock ticks between given rounds.
def cpu_tickdiff(round1, round2, pid):
    return __cpu_tickdiff(round1, round2, pid, 'stime') + \
           __cpu_tickdiff(round1, round2, pid, 'utime')

# Total difference in CPU clock ticks between given rounds.
def total_cpu_tickdiff(round1, round2):
    try:
        return sum(round2['/proc/stat']['cpu'].itervalues()) - \
               sum(round1['/proc/stat']['cpu'].itervalues())
    except KeyError:
        return 0

def resource_overall_changes(data, idx1, idx2, do_summary):
    run1 = data[idx1]
    run2 = data[idx2]
    memory_change = (run2['ram_free']+run2['swap_free']) - (run1['ram_free']+run1['swap_free'])
    ram_change = run2['ram_free'] - run1['ram_free']
    swap_change = run2['swap_free'] - run1['swap_free']
    fdfree_change = run2['fdfree'] - run1['fdfree']
    change_from_initial = [(run2['ram_free']+run2['swap_free']) - (data[0]['ram_free']+data[0]['swap_free'])]
    change_from_initial += [run2[key]-data[0][key] for key in ['ram_free', 'swap_free', 'fdfree']]

    print "<p>System free memory change: <b>%+d</b> kB" % memory_change
    if ram_change or swap_change:
        print "<br>(free RAM change: <b>%+d</b> kB, free swap change: <b>%+d</b> kB)" % (ram_change, swap_change)
    print "<br>System unused file descriptor change: <b>%+d</b>" % fdfree_change
    if idx1 > 0:
        print "<br>(change from initial state: free memory: %+d kB [RAM: %+d kB, swap: %+d kB], FD: %+d)" % \
                (change_from_initial[0], change_from_initial[1], change_from_initial[2], change_from_initial[3])
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
-->""" % (memory_change, ram_change, swap_change, fdfree_change)
        if 'private_code' in run1:
            dcode_change = run2['private_code'] - run1['private_code']
            if dcode_change:
                print "<br>System private dirty code pages change: <b>%+d</b> kB" % dcode_change


def output_run_diffs(idx1, idx2, data, do_summary):
    "outputs the differencies between two runs"

    run1 = data[idx1]
    run2 = data[idx2]
    if run1['release'] != run2['release']:
        parse_warning("ERROR: release '%s' doesn't match previous round release '%s'!" \
                % (run1['release'], run2['release']))
        return None

    # syslogged errors
    if not do_summary:
        output_errors(idx2, run1, run2)

    cpu_total_diff = total_cpu_tickdiff(run1, run2)
    cpu_total_secs = float(cpu_total_diff)/CLK_TCK

    # Create the following table (based on /proc/pid/stat):
    #
    #   Command[Pid]: system / user       CPU Usage:
    #   app2[1234]:   ###########%%%%%%%  45%  (90s)
    #   app1[987]:    ######%%%%%%%%%     44%  (88s)
    #   app3[543]:    #%                   5%  (10s)
    #
    def process_cpu_usage():
        if not '/proc/pid/stat' in run1 or not '/proc/pid/stat' in run2:
            return
        print "<h4>Process CPU usage</h4>"
        if cpu_total_diff < 0:
            print "<p><i>WARNING: system reboot detected, CPU usage omitted.</i>"
            return
        if cpu_total_diff == 0:
            # No CPU spent? Most likely user has manually copied the snapshot directories.
            print "<p><i>WARNING: identical snapshots detected, CPU usage omitted.</i>"
            return
        if cpu_total_secs >= 3600:
            print "<p>Interval between rounds was %d seconds (%d hours %d minutes)." % \
                    (cpu_total_secs, int(cpu_total_secs/3600), int((cpu_total_secs%3600)/60))
        elif cpu_total_secs >= 60:
            print "<p>Interval between rounds was %d seconds (%d minutes)." % \
                    (cpu_total_secs, int(cpu_total_secs/60))
        else:
            print "<p>Interval between rounds was %d seconds." % cpu_total_secs

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
                ["%.2f%% (%.2fs)" % (100.0*(x[1]+x[2])/cpu_total_diff, (x[1]+x[2])/CLK_TCK)]) for x in diffs]\
            + [("", (0,0), ["<i>%.2f%% (%.2fs)</i>" % (\
                    100.0*sum([x[1]+x[2] for x in diffs])/cpu_total_diff,\
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
    resource_overall_changes(data, idx1, idx2, do_summary)

    # filesystem usage changes
    if 'mounts' in run1 and 'mounts' in run2:
        diffs = get_usage_diffs(initial_values(data, 'mounts'),
                            run1['mounts'],
                            run2['mounts'])
        output_diffs(diffs, "Filesystem usage", "Mount", " kB",
                    Colors.disk, idx1, do_summary)

    # processes disk writes
    if 'IO' in run1 and 'IO' in run2:
        diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                                    initial_values(data, 'IO'),
                                    run1['IO'], run2['IO'],
                                    run2['kthreads'])
        output_diffs(diffs, "Disk page writes", "Process", " kB",
                    Colors.disk, idx1, do_summary)

    # Combine Private dirty + swap into one table. The idea is to reduce the
    # amount of data included in the report (=less tables & smaller HTML file
    # size), and entries like -4 kB private dirty & +4 kB swap. Most of the
    # swapped pages will be private dirty anyways.
    if 'smaps' in run1:
        diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                        combine_dirty_and_swap(initial_values(data, 'smaps')),
                        combine_dirty_and_swap(run1['smaps']),
                        combine_dirty_and_swap(run2['smaps']))
        output_diffs(diffs,
                "Process private dirty and swap memory usages combined (according to SMAPS)",
                "Command[Pid]", " kB", Colors.memory, idx1, do_summary)
    else:
        print "<p>No SMAPS data for process memory usage available."
    
    # process X resource usage changes
    xmeminfo_initial = initial_values(data, 'xmeminfo')
    try:
        diffs = get_usage_diffs(xmeminfo_initial['Total mem'],
                                run1['xmeminfo']['Total mem'],
                                run2['xmeminfo']['Total mem'])
        output_diffs(diffs, "X resource memory usage", "X client", " kB",
                     Colors.xres_mem, idx1, do_summary)
    except KeyError: pass
    try:
        diffs = get_usage_diffs(xmeminfo_initial['DRI2Drawable'],
                                run1['xmeminfo']['DRI2Drawable'],
                                run2['xmeminfo']['DRI2Drawable'])
        output_diffs(diffs, "X resource DRI2Drawable count", "X client", "",
                     Colors.xres_count, idx1, do_summary)
    except KeyError: pass
    if do_summary:
        try:
            diffs = get_usage_diffs(xmeminfo_initial['total_resource_count'],
                                    run1['xmeminfo']['total_resource_count'],
                                    run2['xmeminfo']['total_resource_count'])
            output_diffs(diffs, "X resource count", "X client", "",
                         Colors.xres_count, idx1, do_summary)
        except KeyError: pass
    
    # FD count changes
    diffs = get_pid_usage_diffs(run2['commands'], run2['processes'],
                    initial_values(data, 'fdcounts'),
                    run1['fdcounts'], run2['fdcounts'])
    output_diffs(diffs, "Process file descriptor count", "Command[Pid]", "",
                    Colors.fds, idx1, do_summary)

    # shared memory segment count changes
    diffs = get_usage_diffs(initial_values(data, 'shm'),
                            run1['shm'],
                            run2['shm'])
    output_diffs(diffs, "Shared memory segments", "Type", "",
                Colors.shm, idx1, do_summary)

    if 'cgroups' in run1 and 'cgroups' in run2:
        output_cgroup_diffs(run1['cgroups'], run2['cgroups'])

    # Kernel statistics
    if cpu_total_diff > 0:
        print "\n<h4>Kernel events</h4>"

        def format_key(key, max):
            if key > max:
                return "<font color=red>%.1f</font>" % key
            else:
                return "%.1f" % key

        # Kernel virtual memory subsystem statistics, /proc/vmstat
        pgmajfault = (run2['/proc/vmstat']['pgmajfault']-run1['/proc/vmstat']['pgmajfault'])/cpu_total_secs
        pswpin     = (run2['/proc/vmstat']['pswpin']-run1['/proc/vmstat']['pswpin'])/cpu_total_secs
        pswpout    = (run2['/proc/vmstat']['pswpout']-run1['/proc/vmstat']['pswpout'])/cpu_total_secs
        diffs = []
        if pgmajfault > 0:
            diffs.append(("Major page faults per second", format_key(pgmajfault, 1000)))
        if pswpin > 0:
            diffs.append(("Page swap ins per second", format_key(pswpin, 100)))
        if pswpout > 0:
            diffs.append(("Page swap outs per second", format_key(pswpout, 100)))
        if diffs:
            print '\n<p><table border=1 bgcolor=%s>' % Colors.kernel
            print "<caption><i>Virtual memory subsystem</i></caption>"
            print "<tr><th>Type:</th><th>Value:</th></tr>"
            for d in diffs:
                print "<tr><td>%s</td><td align=right><b>%s</b></td></tr>" % d
            print "</table>"

        # Interrupts and context switches.
        intr = (run2['/proc/stat']['intr']-run1['/proc/stat']['intr'])/cpu_total_secs
        ctxt = (run2['/proc/stat']['ctxt']-run1['/proc/stat']['ctxt'])/cpu_total_secs
        diffs = [
                 ("Interrupts per second", format_key(intr, 1e5/3600)),
                 ("Context switches per second", format_key(ctxt, 1e6/3600)),
                ]
        print '\n<p><table border=1 bgcolor=%s>' % Colors.kernel
        print "<caption><i>Low level system events</i></caption>"
        print "<tr><th>Type:</th><th>Value:</th></tr>"
        for d in diffs:
            print "<tr><td>%s</td><td align=right><b>%s</b></td></tr>" % d
        print "</table>"


    print "\n<h4>Changes in processes</h4>"

    # thread count changes
    diffs = get_thread_count_diffs(run2['commands'],
                    initial_values(data, 'processes'),
                    run1['processes'], run2['processes'])
    output_diffs(diffs, "Process thread count", "Command[Pid]", "",
                    Colors.threads, idx1, do_summary)

    pid2cgroup1 = None
    pid2cgroup2 = None
    if 'pid2cgroup' in run1: pid2cgroup1 = run1['pid2cgroup']
    if 'pid2cgroup' in run2: pid2cgroup2 = run2['pid2cgroup']

    # new and closed processes
    titles = ("Change in number of processes",
              "Exited processes",
              "New processes")
    output_process_changes(
                get_pids_from_procs(run1['processes'], run1['commands']),
                get_pids_from_procs(run2['processes'], run2['commands']),
                titles, pid2cgroup1, pid2cgroup2, do_summary)

    # new and collected kthreads/zombies
    titles = ("Change in number of kernel threads and zombie processes",
              "Collected kthreads/zombies",
              "New kthreads/zombies")
    output_process_changes(run1['kthreads'], run2['kthreads'], titles,
                pid2cgroup1, pid2cgroup2, do_summary,
                show_cgroups=False)

    # DSME reported process crashes
    if 'dsme_rich_cores' in run2:
        dsme_rich_cores1 = {}
        dsme_rich_cores2 = run2['dsme_rich_cores']
        if 'dsme_rich_cores' in run1: dsme_rich_cores1 = run1['dsme_rich_cores']
        output_new_dsme_rich_cores(dsme_rich_cores1, dsme_rich_cores2)

    # Upstart respawned jobs
    if 'upstart_jobs_respawned' in run2:
        upstart_jobs_respawned1 = {}
        upstart_jobs_respawned2 = run2['upstart_jobs_respawned']
        if 'upstart_jobs_respawned' in run1: upstart_jobs_respawned1 = run1['upstart_jobs_respawned']
        output_new_upstart_jobs_respawned(upstart_jobs_respawned1, upstart_jobs_respawned2)

def hw_string(run):
    hw = ''
    if 'component_version' in run:
        if 'product' in run['component_version']:
            hw += run['component_version']['product']
        if 'hw-build' in run['component_version']:
            hw += ':' + run['component_version']['hw-build']
    return hw

def output_initial_state(run):
    "show basic information about the test run"
    print "<p>%s" % run['release']
    if hw_string(run):
        print "<p>HW: %s" % hw_string(run)
    print "<p>Date: %s" % run['datetime']
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
    # Determine largest width we have for all rows for the 'graphical bar'.
    maxw = 0
    for item in data:
        w = 0
        for idx in range(len(colors)):
            w = w + int(item[1][idx]*width)
        maxw = max(maxw, w)
    for item in data:
        # row title
        print '<tr><td>%s</td>' % item[0]
        # graphical bar
        print "<td><table border=0 cellpadding=0 cellspacing=0><tr>"
        wpad = maxw
        for idx in range(len(colors)):
            w = int(item[1][idx]*width)
            if w:
                sys.stdout.write('<td bgcolor="%s" width=%d height=16></td>' % (colors[idx], w))
                wpad = wpad - w
        # Pad with invisible <td> element so that the embedded <table> inside
        # for each row will be of equal width. Browser zooming may change the
        # widths of the per-row <table>s, and if they are not of equal width,
        # the result can be misleading.
        if wpad > 0:
            print "<td width='%d' height='16'></td>" % wpad
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
                    # The endurance snapshotting script uses the 'sp-noncached'
                    # utility for streaming data from & to disk. The processes
                    # are short-living, so do not bother to give a warning
                    # about those.
                    if name != 'sp-noncached':
                        parse_warning("WARNING: SMAPS data missing for %s[%s]" % (name,pid))
                continue
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

    # Collect processes that used at least 0.5% of CPU time, this should
    # roughly match the processes listed in 'Process CPU usage' graphs in the
    # per-round difference summaries. We will include these processes in the
    # memory usage graphs even if their memory usage does not change.
    cpuhoggers = []
    for pid in data:
        try:
            first_round = min([x for x in data[pid].iterkeys() if x>0])
            last_round  = max(data[pid].iterkeys())
            if first_round < last_round:
                ticks_diff = cpu_tickdiff(cases[first_round], cases[last_round], pid)
                cpu_total_diff = total_cpu_tickdiff(cases[first_round], cases[last_round])
                if ticks_diff > 0.005*cpu_total_diff:
                    cpuhoggers.append(pid)
        except: pass

    # get largest size for any of the namepids, get largest dirty (or RSS)
    # for sorting and ignore items which dirty/size don't change.
    # dirty is private_dirty + swap.
    sizes = []
    largest_size = 0
    for pid in data:
        changerounds = pidrounds = 0
        max_size = max_dirty = 0
        min_size = min_dirty = 512*1024
        prev_dirty = prev_size = 0
        for idx in range(rounds):
            if idx in data[pid]:
                try:    priv = data[pid][idx]['SMAPS_PRIVATE_DIRTY']
                except: priv = data[pid][idx]['VmRSS'] # bad substitute
                try:    swap = data[pid][idx]['SMAPS_SWAP']
                except: swap = 0
                try:    size = data[pid][idx]['SMAPS_SIZE']
                except: size = data[pid][idx]['VmSize']
                dirty = priv+swap
                max_size  = max(size, max_size)
                min_size  = min(size, min_size)
                # skip initial state for dirty and change checks
                if prev_dirty and prev_size:
                    max_dirty = max(dirty, max_dirty)
                    min_dirty = min(dirty, min_dirty)
                    if dirty != prev_dirty or size != prev_size:
                        changerounds += 1
                prev_dirty = dirty
                prev_size = size
                pidrounds += 1
        if max_size > largest_size:
            largest_size = max_size

        if show_all_processes:
            sizes.append((max_dirty,pid))
        # use heuristics to include only "interesting" processes
        elif pid in cpuhoggers:
            sizes.append((max_dirty,pid))
        elif pidrounds == 1:
            # show single round processes using >1MB
            if dirty > 1024:
                sizes.append((dirty,pid))
        else:
            try:
                # Filter out processes that did not eat any CPU ticks.
                first_round = min([x for x in data[pid].iterkeys() if x>0])
                last_round  = max(data[pid].iterkeys())
                if first_round < last_round:
                    ticks_diff = cpu_tickdiff(cases[first_round], cases[last_round], pid)
                    if ticks_diff <= 0:
                        continue
            except: pass

            if not max_dirty:
                # show 2 round processes if their memory usage changes
                min_dirty = min(prev_dirty, dirty)
                max_dirty = max(prev_dirty, dirty)

            dirty_max_diff = max_dirty - min_dirty
            try: dirty_change_per_round = float(dirty_max_diff) / max_dirty / pidrounds
            except ZeroDivisionError: dirty_change_per_round = 0
            try: size_change_per_round = (float)(max_size - min_size) / max_size / pidrounds
            except ZeroDivisionError: size_change_per_round = 0

            # if >0.2% average memory change per round in dirty or Size, or
            # size/dirty changes on more than half of all the rounds, add
            # process to list.
            # average dirty differences is ignored if maximum difference
            # in dirty (private+swap) is < 16kB.
            if (dirty_max_diff >= 16 and dirty_change_per_round > 0.002) or\
               size_change_per_round > 0.002 or 2*changerounds >= rounds:
                sizes.append((max_dirty,pid))

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
        print '<a name="memory_%s_%s"></a>' % (name, pid)
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
                        parse_warning("WARNING: %s[%s] RSS (%s) < SMAPS dirty (%s)" \
                                % (namepid + (rss, dirty)))
                        rss = dirty
                    if pss < dirty:
                        parse_warning("WARNING: %s[%s] SMAPS PSS (%s) < SMAPS dirty (%s)" \
                                % (namepid + (pss, dirty)))
                    if rss < pss:
                        parse_warning("WARNING: %s[%s] RSS (%s) < SMAPS PSS (%s)" \
                                % (namepid + (rss, pss)))
                    text = ["%s kB" % swap, "%s kB" % dirty, "%s kB" % pss, "%s kB" % rss, "%s kB" % size]
                else:
                    swap = 0
                    dirty = 0
                    pss = 0
                    text = ["", "", "", "%s kB" % rss, "%s kB" % size]
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

def test_round_link(idx):
    if idx == 0:
        return '<a href="#initial-state">Initial state</a>:'
    else:
        return '<a href="#round-%d">Test round %02d</a>:' % (idx, idx)

def output_system_load_graphs(data):
    print '<p>System CPU time distribution during the execution of test cases.'
    print '<p>'
    prev = data[0]
    entries = []
    idx = 1
    for testcase in data[1:]:
        case = test_round_link(idx)
        if total_cpu_tickdiff(prev, testcase) < 0:
            entries.append((case, (0,0,0,0,0), "-"))
        elif total_cpu_tickdiff(prev, testcase) == 0:
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
        try:
            for face in testcase['transfers']:
                if face not in interfaces and testcase['transfers'][face] > 0:
                    interfaces[face] = []
        except KeyError: pass
    faces = interfaces.keys()
    if not faces:
        print "<p>Only local or no interfaces up when measurements were taken."
        return

    # collect test round data per interfaces
    faces.sort()
    for testcase in data:
        for face in faces:
            if 'transfers' in testcase and face in testcase['transfers']:
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
        vals = ["%d kB" % (x/1024) for x in v]
        entries.append((test_round_link(idx), bars, vals))
    titles = ["Test-case:", "network usage:"] + ["%s:" % x for x in faces]
    ifcolors = [interface_colors[i % len(interface_colors)] for i in range(len(faces))]
    output_graph_table(titles, ifcolors, entries)
    # Legend
    print '<table><tr><th><th align="left">Legend:'
    for i in range(len(faces)):
        print '<tr><td bgcolor="%s" height=16 width=16><td>%s' % (ifcolors[i], faces[i])
    print '</table>'

def hl_error(s):
    if "ERROR" in s:
        return "<font color='red'>%s</font>" % s
    return s

def output_battery_data(data):
    skip = True
    for testcase in data:
        if 'bmestat' in testcase:
            skip = False
    if skip:
        return
    print "<hr>"
    print "<h3>Battery status</h3>"
    print "<table border='1' cellpadding='3'>"
    print " <thead>"
    print "  <tr>"
    print "   <th>"
    print "   <th colspan='2'>Charger"
    print "   <th colspan='2'>Charging"
    print "   <th colspan='4'>Battery"
    print "  <tr>"
    print "   <th>Test-case:"
    print "   <th>State:"
    print "   <th>Type:"
    print "   <th>State:"
    print "   <th>Type:"
    print "   <th>State:"
    print "   <th>Temperature:"
    print "   <th>Capacity:"
    print "   <th>Voltage:"
    print " </thead>"
    print " <tbody>"
    idx = 0
    for testcase in data:
        if 'bmestat' in testcase:
            try:
                print "  <tr>"
                print "   <td>%s" % test_round_link(idx)
                print "   <td>%s" % hl_error(testcase['bmestat']['charger_state'])
                print "   <td>%s" % hl_error(testcase['bmestat']['charger_type'])
                print "   <td>%s" % hl_error(testcase['bmestat']['charging_state'])
                print "   <td>%s" % hl_error(testcase['bmestat']['charging_type'])
                print "   <td>%s" % hl_error(testcase['bmestat']['battery_state'])
                print "   <td>%s&deg;C" % testcase['bmestat']['battery_temperature']
                print "   <td>%smAh" % testcase['bmestat']['battery_cur_capacity']
                print "   <td>%.3fV" % (float(testcase['bmestat']['battery_cur_voltage'])/1000)
            except:
                pass
        idx += 1
    print " </tbody>"
    print "</table>"

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
        case = test_round_link(idx)
        idx += 1

        # amount of memory in the device (float for calculations)
        mem_total = float(testcase['ram_total'] + testcase['swap_total'])
        mem_oom = 97*mem_total/100 # hard-coded OOM-limit in Linux kernel
        mem_used = testcase['ram_used'] + testcase['swap_used']
        mem_free = testcase['ram_free'] + testcase['swap_free']
        # Graphics
        show_swap = testcase['swap_used']/mem_total
        show_ram  = testcase['ram_used']/mem_total
        if mem_used > mem_oom:
            show_oom = (mem_total - mem_used)/mem_total
            show_free = 0.0
        else:
            show_oom = 1.0 - mem_oom/mem_total
            show_free = 1.0 - show_swap - show_ram - show_oom
        bars = (show_swap, show_ram, show_free, show_oom)
        # Numbers
        def label():
            if mem_used >= mem_oom: return "<font color=red><b>%d</b></font> kB"
            return "%d kB"
        memtext = None
        if swaptext: memtext = label() % testcase['swap_used']
        memtext = (memtext,) + (label() % testcase['ram_used'], "%d kB" % mem_free)
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
<tr><td bgcolor="%s" height="16" width="16"><td>OOM-kill limit (&gt;= %d MB used)
""" % (bar1colors[1], bar1colors[2], bar1colors[3], round(mem_oom/1024))
    print "</table>"


def output_reboots(reboots):
    if not reboots:
        return
    print """
<p><font color="red">ERROR: reboots detected on round(s) %s.
Please use only endurance data from rounds between reboots!</font>
""" % ", ".join([str(x) for x in reboots])


def readable_uptime(fuptime):
    uptime = int(fuptime)
    divs = (60, 60, 24, 7 ,1)
    names = ("seconds", "minutes", "hours", "days", "weeks")
    values = []
    for div in divs:
        values.append(uptime % div)
        uptime /= div
    split = ret = ""
    order = range(len(names))
    order.reverse()
    for i in order:
        if values[i]:
            ret += "%s%d %s" % (split, values[i], names[i])
            split = ", "
    return ret


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

<!-- endurance_report.py v2.1.5 -->

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
    reboots = []
    uptime_prev = data[0]['uptime']
    for round in range(rounds):
        idx = round + 1
        uptime_next = data[idx]['uptime']
        if uptime_next < uptime_prev:
            reboots.append(idx)
            print "  <li><font color=red>REBOOT</font> (after <i>previous</i> round uptime of %s)</i>" % readable_uptime(uptime_prev)
        uptime_prev = uptime_next
        desc = ""
        if 'datetime' in data[idx] and data[idx]['datetime']:
            desc += " [%s]" % data[idx]['datetime']
        if data[idx].has_key('description') and data[idx]['description']:
            desc += " (%s)" % data[idx]['description']
        print '  <li><a href="#round-%d">Round %d</a>%s' % (idx, idx, desc)
    print """
  </ul>
<li>Summary of changes between all the rounds after the initial one:
  <ul>
    <li><a href="#error-summary">Error summary</a>
    <li><a href="#resource-summary">Resource usage summary</a>
  </ul>
</ul>"""
    output_reboots(reboots)
    print """
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
    output_battery_data(data)
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
        print "<p>Date: %s" % data[idx+1]['datetime']
        output_run_diffs(idx, idx+1, data, 0)
        output_data_links(data[idx+1])
        print "\n<hr>"
    
    print """
<a name="error-summary"></a>
<h2>Summary of changes between test rounds %d - %d</h2>
<h3>Error summary</h3>""" % (first, last)
    new_errors_by_category = get_new_errors_by_category(data[first], data[last])
    if new_errors_by_category:
        syslog_error_summary(data[last], new_errors_by_category, links=False)
        print "<!-- summary for automatic parsing:"
        syslog_error_summary_text(new_errors_by_category)
        print "-->"
    else:
        print "<p>No identified errors logged."

    print """<hr>
<a name="resource-summary"></a>
<h3>Resource usage summary</h3>
<p><font color="red">NOTE</font>: Process specific resource usage
changes are shown only for processes which exist in both of the
compared rounds!
"""
    output_reboots(reboots)
    output_run_diffs(first, last, data, 1)

    print "\n</body></html>"


# ------------------- go through all files -------------------------

def parse_syte_stats(dirs):
    """parses given CSV files into a data structure"""
    data = []
    for dirname in dirs:

        # get basic information
        try:
            file, filename = syslog.open_compressed("%s/usage.csv" % dirname)
        except IOError, e:
            error_exit("unable to open %s/usage.csv: %s" % (dirname, e))
        except RuntimeError, e:
            error_exit("unable to open %s/usage.csv: %s" % (dirname, e))
        print >>sys.stderr, "Parsing '%s'..." % filename
        items = parse_csv(file, filename)
        if not items:
            error_exit("CSV parsing failed")

        # filename without the extension
        items['basedir'] = dirname

        filename = "%s/step.txt" % dirname
        if os.path.exists(filename):
            # use-case step description
            try:
                items['description'] = open(filename).read().strip()
            except IOError, e:
                sys.stderr.write("WARNING: unable to read %s: %s\n" % (filename, e))

        try:
            file, filename = syslog.open_compressed("%s/smaps.cap" % dirname)
        except IOError, e:
            error_exit("unable to open %s/smaps.cap: %s" % (dirname, e))
        except RuntimeError, e:
            error_exit("unable to open %s/smaps.cap: %s" % (dirname, e))
        if file:
            print >>sys.stderr, "Parsing '%s'..." % filename
            items['smaps'], items['private_code'] = parse_smaps(file)
            if not items['smaps']:
                error_exit("SMAPS data parsing failed")

        try:
            file, filename = syslog.open_compressed("%s/syslog" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['logfile'] = filename
                items['syslog_errors_by_category'] = syslog.get_errors_by_category(
                        file, logparser_config_syslog.regexps)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/stat" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['/proc/stat'] = parse_proc_stat(file)
                if not items['/proc/stat']:
                    error_exit("/proc/stat parsing failed")
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/ifconfig" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['transfers'] = parse_ifconfig(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/cgroups" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['pid2cgroup'], items['tid2group'], items['cgroups'] = parse_cgroups(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        dsme_rich_cores = get_dsme_rich_cores(dirname)
        if dsme_rich_cores:
            items['dsme_rich_cores'] = dsme_rich_cores

        try:
            file, filename = syslog.open_compressed("%s/upstart_jobs_respawned" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['upstart_jobs_respawned'] = get_upstart_jobs_respawned(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/xmeminfo" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['xmeminfo'] = get_xres_usage(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/df" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['mounts'] = get_filesystem_usage_df(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/component_version" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['component_version'] = get_component_version(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        try:
            file, filename = syslog.open_compressed("%s/bmestat" % dirname)
            if file:
                print >>sys.stderr, "Parsing '%s'..." % filename
                items['bmestat'] = get_bmestat(file)
        except RuntimeError: pass
        except IOError, e:
            sys.stderr.write("WARNING: %s\n" % e)

        data.append(items)
    return data


if __name__ == "__main__":
    help = False
    first_arg = 1
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            help = True
        elif sys.argv[1] == "--show-all":
            show_all_processes = True
            first_arg += 1

    if help or (len(sys.argv) - first_arg < 2):
        msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
        error_exit(msg)

    # Use psyco if available. Gives 2-3x speed up.
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass

    try:
        logparser_config_syslog = syslog.LogParserConfig(configfile =
                syslog.LogParserConfig.DEFAULT_CONFIG_SYSLOG)
    except RuntimeError, e:
        error_exit(str(e))
    if not logparser_config_syslog:
        error_exit("failed to initialize syslog parser configuration")

    stats = parse_syte_stats(sys.argv[first_arg:])
    output_html_report(stats)
