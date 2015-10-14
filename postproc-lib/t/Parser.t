# This file is part of sp-endurance.
#
# vim: ts=4:sw=4:et
#
# Copyright (C) 2012 by Nokia Corporation
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

use Test::More;
use IO::String;
use strict;
use Fcntl qw/SEEK_SET/;

BEGIN {
    use_ok('SP::Endurance::Parser', qw/parse_openfds parse_smaps parse_smaps_pp
        parse_slabinfo parse_cgroups parse_interrupts parse_bmestat
        parse_ramzswap parse_proc_stat parse_pagetypeinfo parse_diskstats
        parse_sysfs_fs parse_sysfs_power_supply parse_sysfs_backlight
        parse_sysfs_cpu parse_component_version parse_step parse_usage_csv
        parse_ifconfig parse_upstart_jobs_respawned parse_sched parse_pidfilter
        copen/);
}

###### parse_openfds ######

is_deeply(parse_openfds, {}, 'parse_openfds - undef input');

{
    my $content = '';
    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {}, 'parse_openfds - empty input file');
}
{
    my $content = "\n\n\n";
    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {}, 'parse_openfds - input file with only newlines');
}

{
    my $content = <<'END';
/proc/12/fd/:
total 0

/proc/1205/fd/:
total 0
lrwx------    1 user     users           64 Feb  4 01:57 0 -> /dev/console
lrwx------    1 user     users           64 Feb  4 01:57 1 -> /dev/console
lrwx------    1 user     users           64 Feb  4 01:57 2 -> /dev/console
lrwx------    1 user     users           64 Feb  4 01:57 3 -> socket:[9304]
lrwx------    1 user     users           64 Feb  4 01:57 4 -> socket:[9307]

/proc/1213/fd/:
total 0
lrwx------    1 user     users           64 Feb  4 01:57 0 -> /dev/console
lrwx------    1 user     users           64 Feb  4 01:57 1 -> /dev/console
lr-x------    1 user     users           64 Feb  4 01:57 10 -> inotify
lr-x------    1 user     users           64 Feb  4 01:57 12 -> inotify
lr-x------    1 user     users           64 Feb  4 01:57 13 -> pipe:[9718]
l-wx------    1 user     users           64 Feb  4 01:57 14 -> pipe:[9718]
lr-x------    1 user     users           64 Feb  4 01:57 15 -> pipe:[9719]
l-wx------    1 user     users           64 Feb  4 01:57 16 -> pipe:[9719]
lrwx------    1 user     users           64 Feb  4 01:57 17 -> socket:[9735]
lr-x------    1 user     users           64 Feb  4 01:57 18 -> pipe:[9740]
l-wx------    1 user     users           64 Feb  4 01:57 19 -> pipe:[9740]
lrwx------    1 user     users           64 Feb  4 01:57 2 -> /dev/console
END

    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {
        12   => undef,
        1205 => ',,,,,,2,,3',
        1213 => ',,,2,6,,1,,3',
    }, 'parse_openfds - tmpfs, socket, pipe, inotify');
}

{
    my $content = <<'END';
/proc/1454/fd:
total 0
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventpoll]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventpoll]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[signalfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[signalfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[timerfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[timerfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> inotify
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:inotify
END

    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {
        1454 => ',2,2,2,,2,,2,',
    }, 'parse_openfds - inotify, eventfd, epoll, signalfd, timerfd');
}

{
    my $content = <<'END';
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventfd]
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> anon_inode:[eventpoll]
END
    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {}, 'parse_openfds - input missing PID');
}

{
    my $content = <<'END';
/proc/999999/fd:
total 0
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /some/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /another/file/somewhere

/proc/123/fd:
total 0
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /some/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /another/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /third/file/somewhere

/proc/321/fd:
total 0
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /some/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /another/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /third/file/somewhere
lrwx------ 1 mongodb nogroup 64 12.4. 09:54 0 -> /4th/file
END

    open my $fh, '<', \$content;
    is_deeply(parse_openfds($fh), {
        999999 => '2,,,,,,,,',
        123    => '3,,,,,,,,',
        321    => '4,,,,,,,,',
    }, 'parse_openfds - disk fd');
}

###### parse_smaps ######

is_deeply(parse_smaps,    {}, 'parse_smaps - undef input');
is_deeply(parse_smaps_pp, {}, 'parse_smaps_pp - undef input');

{
    my $content = '';
    open my $fh, '<', \$content;
    is_deeply(parse_smaps($fh),    {}, 'parse_smaps - empty input file');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), {}, 'parse_smaps_pp - empty input file');
}

{
    my $content = "\n\n\n";
    open my $fh, '<', \$content;
    is_deeply(parse_smaps($fh),    {}, 'parse_smaps - input file with only newlines');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), {}, 'parse_smaps_pp - input file with only newlines');
}

{
    my $content = << 'END';
==> /proc/1/smaps <==
#Name: init
#Pid: 1
#PPid: 0
#Threads: 1
#FDSize: 32
#VmPeak: 3496
#VmSize: 3488
#VmLck: 0
#VmHWM: 2056
#VmRSS: 1908
#VmData: 820
#VmStk: 88
#VmExe: 124
#VmLib: 2052
#VmPTE: 8

==> /proc/999/smaps <==
#Name: /some/command/goes/here --and-some-argument --another
#Pid: 999
#QWERTY:     123
END

    open my $fh, '<', \$content;
    my $expected = {
        1   => { '#Name' => 'init' },
        999 => { '#Name' => '/some/command/goes/here --and-some-argument --another' },
    };
    is_deeply(parse_smaps($fh),    $expected, 'parse_smaps - metadata parsing');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), $expected, 'parse_smaps_pp - metadata parsing');
}

{
    my $content = << 'END';
==> /proc/1/smaps <==
#Pid: 1
00008000-00027000 r-xp 00000000 b3:02 84         /sbin/init
0002e000-0002f000 r--p 0001e000 b3:02 84         /sbin/init
END

    open my $fh, '<', \$content;
    my $expected = {
        1 => {
            vmacount => 2,
        },
    };
    is_deeply(parse_smaps($fh),    $expected, 'parse_smaps - 1x process, 2x vmas');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), $expected, 'parse_smaps_pp - 1x process, 2x vmas');
}

{
    my $content = << 'END';
==> /proc/1/smaps <==
#Pid: 1
#PPid: 0
00008000-00027000 r-xp 00000000 b3:02 84         /sbin/init
Size:                124 kB
Rss:                 100 kB
Pss:                 100 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:       100 kB
Private_Dirty:         0 kB
Referenced:           64 kB
Anonymous:             0 kB
Swap:                  0 kB
KernelPageSize:        4 kB
MMUPageSize:           4 kB
Locked:                0 kB
0002e000-0002f000 r--p 0001e000 b3:02 84         /sbin/init
Size:                  4 kB
Rss:                   4 kB
Pss:                   4 kB
Shared_Clean:          0 kB
Shared_Dirty:          0 kB
Private_Clean:         0 kB
Private_Dirty:         4 kB
Referenced:            4 kB
Anonymous:             4 kB
Swap:                  4 kB
KernelPageSize:        4 kB
MMUPageSize:           4 kB
Locked:                4 kB
END

    open my $fh, '<', \$content;
    my $expected = {
        1 => {
            vmacount => 2,
            total_Size          => 124+4,
            total_Pss           => 100+4,
            total_Private_Dirty => 0+4,
            total_Swap          => 0+4,
        },
    };
    is_deeply(parse_smaps($fh),    $expected, 'parse_smaps - 1x process, 2x vmas');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), $expected, 'parse_smaps_pp - 1x process, 2x vmas');
}

{
    my $content = << 'END';
#Name: first
#Pid: 1
00008000-00009000 r-xp 00000000 b3:02 84         /sbin/init
Size:                  4 kB
0002d000-0002f000 r--p 0001e000 b3:02 84         /sbin/init
Size:                  8 kB
00030000-00034000 r--p 0001e000 b3:02 84         /sbin/init
Size:                 16 kB
00040000-00048000 r--p 0001e000 b3:02 84         /sbin/init
Size:                 32 kB

#Name: second
#Pid: 2
a0000000-a000a000 r-xp 00000000 b3:02 84         /drm mm object (deleted)
Size:  40 kB
b0000000-b0028000 r--p 0001e000 b3:02 84         [heap]
Size: 160 kB
c0000000-c0014000 r--p 0001e000 b3:02 84         /path/to/binary
Size:  80 kB
d0000000-d0050000 rw-p 0001e000 b3:02 84         [heap]
Size: 320 kB
e0000000-e001bc00 rwxp 0001e000 b3:02 84
Size: 111 kB

END

    open my $fh, '<', \$content;
    my $expected = {
        1 => {
            '#Name' => 'first',
            vmacount => 4,
            total_Size => 4+8+16+32,
        },
        2 => {
            '#Name' => 'second',
            vmacount => 5,
            total_Size => 40+80+160+320+111,
            '/drm mm object' => { total_Size => 40, vmacount => 1 },
            '[heap]' => { total_Size => 160+320, vmacount => 2 },
            'rwxp'   => { total_Size => 111,     vmacount => 1 },
        },
    };
    is_deeply(parse_smaps($fh),    $expected, 'parse_smaps - 2x process, 2x4 vmas');
    seek $fh, 0, SEEK_SET;
    is_deeply(parse_smaps_pp($fh), $expected, 'parse_smaps_pp - 2x process, 2x4 vmas');
}

###### parse_slabinfo ######

is_deeply(parse_slabinfo, {}, 'parse_slabinfo - undef input');
is_deeply(parse_slabinfo(IO::String->new('')), {}, 'parse_slabinfo - empty input file');
is_deeply(parse_slabinfo(IO::String->new("\n\n\n")), {}, 'parse_slabinfo - input file with only newlines');

is_deeply(parse_slabinfo(IO::String->new(<< 'END'
slabinfo - version: 2.1
# name            <active_objs> <num_objs> <objsize> <objperslab> <pagesperslab> : tunables <limit> <batchcount> <sharedfactor> : slabdata <active_slabs> <num_slabs> <sharedavail>
ext2_inode_cache       1      0    1024    0    1 : tunables    0    0    0 : slabdata      0      0      0
dm_crypt_io            2      0    2048    0    1 : tunables    0    0    0 : slabdata      0      0      0
kcopyd_job             3      0    4096    0    1 : tunables    0    0    0 : slabdata      0      0      0
END
)), {
    ext2_inode_cache => 1*1,
    dm_crypt_io => 2*2,
    kcopyd_job => 3*4,
}, 'parse_slabinfo - 3x slabs');

###### parse_cgroups ######

is_deeply(parse_cgroups(IO::String->new('')), {}, 'parse_cgroups - empty input file');

is_deeply(parse_cgroups(IO::String->new(<< 'END'
==> /syspart/memory.memsw.failcnt <==
0

==> /syspart/memory.memsw.limit_in_bytes <==
9223372036854775807

==> /syspart/memory.memsw.max_usage_in_bytes <==
372678656

==> /syspart/memory.memsw.usage_in_bytes <==
380030976

==> /syspart/memory.oom_control <==
oom_kill_disable 0
under_oom 0

==> /syspart/memory.stat <==
cache 36675584
rss 1896448
mapped_file 35921920
pgpgin 138182
pgpgout 128765
swap 1421312
inactive_anon 1531904
active_anon 610304
inactive_file 5496832
active_file 24125440
unevictable 6807552
hierarchical_memory_limit 9223372036854775807
hierarchical_memsw_limit 9223372036854775807
total_cache 146591744
total_rss 197787648
total_mapped_file 95322112
total_pgpgin 441577
total_pgpgout 357500
total_swap 35651584
total_inactive_anon 103444480
total_active_anon 103878656
total_inactive_file 51920896
total_active_file 51277824
total_unevictable 33857536

==> /syspart/memory.failcnt <==
0

==> /syspart/memory.soft_limit_in_bytes <==
9223372036854775807

==> /syspart/memory.limit_in_bytes <==
9223372036854775807

==> /syspart/memory.max_usage_in_bytes <==
359731200

==> /syspart/memory.usage_in_bytes <==
344379392

==> /syspart/cgroup.procs <==
458
569
573
574
1151

==> /syspart/tasks <==
111
222
333
111
222
333

END
)), {
    '/' => {
        'memory.memsw.failcnt' => 0,
        'memory.memsw.max_usage_in_bytes' => 372678656,
        'memory.memsw.usage_in_bytes' => 380030976,
        'memory.stat' => {
            'cache' => 36675584,
            'rss' => 1896448,
            'mapped_file' => 35921920,
            'pgpgin' => 138182,
            'pgpgout' => 128765,
            'swap' => 1421312,
            'inactive_anon' => 1531904,
            'active_anon' => 610304,
            'inactive_file' => 5496832,
            'active_file' => 24125440,
            'unevictable' => 6807552,
        },
        'memory.failcnt' => 0,
        'memory.max_usage_in_bytes' => 359731200,
        'memory.usage_in_bytes' => 344379392,
        'cgroup.procs' => 5,
        'tasks' => 3,
    },
}, 'parse_cgroups - 1x cgroup');

is_deeply(parse_cgroups(IO::String->new(<< 'END'
==> /syspart/memory.memsw.failcnt <==
0
==> /syspart/memory.memsw.usage_in_bytes <==
1

==> /syspart/system/memory.memsw.failcnt <==
2
==> /syspart/system/memory.memsw.usage_in_bytes <==
3

==> /syspart/system/applications/memory.memsw.failcnt <==
4
==> /syspart/system/applications/memory.memsw.usage_in_bytes <==
5
END
)), {
    '/' => {
        'memory.memsw.failcnt' => 0, 'memory.memsw.usage_in_bytes' => 1,
    },
    '/system/' => {
        'memory.memsw.failcnt' => 2, 'memory.memsw.usage_in_bytes' => 3,
    },
    '/system/applications/' => {
        'memory.memsw.failcnt' => 4, 'memory.memsw.usage_in_bytes' => 5,
    },
}, 'parse_cgroups - 3x cgroup');

###### parse_interrupts ######

is_deeply(parse_interrupts, {}, 'parse_interrupts - undef input');
is_deeply(parse_interrupts(IO::String->new('')), {}, 'parse_interrupts - empty input file');
is_deeply(parse_interrupts(IO::String->new("\n\n\n")), {}, 'parse_interrupts - input file with only newlines');

is_deeply(parse_interrupts(IO::String->new(<< 'END'
           CPU0
  7:        575        INTC  interrupt description 1
 11:      14955        INTC  interrupt description 2
 12:      22222     1111111
384:          0     xxxxxxx  descXXX
Err:          0
END
)), {
      7 => { count => 575, desc => 'INTC interrupt description 1' },
     11 => { count => 14955, desc => 'INTC interrupt description 2' },
     12 => { count => 22222, desc => '1111111' },
}, 'parse_interrupts - 1x CPU');

is_deeply(parse_interrupts(IO::String->new(<< 'END'
            CPU0       CPU1       CPU2       CPU3       CPU4       CPU5       CPU6       CPU7       
   0:         73          0          0  505773539          0          0          0          0   IO-APIC-edge      timer
 PMI:      10552          0      10495      34469       3907       3357       3437          0   Performance monitoring interrupts
 RES:   16770322   15932281          0   15195215    2920639          0          0    2963192   Rescheduling interrupts
 ERR:          0
 MIS:         10
END
)), {
      0 => { count => 73+505773539, desc => 'IO-APIC-edge timer' },
    PMI => { count => 10552+10495+34469+3907+3357+3437, desc => 'Performance monitoring interrupts' },
    RES => { count => 16770322+15932281+15195215+2920639+2963192, desc => 'Rescheduling interrupts' },
    MIS => { count => 10 },
}, 'parse_interrupts - 8x CPU');

###### parse_bmestat ######

is_deeply(parse_bmestat, {}, 'parse_bmestat - undef input');
is_deeply(parse_bmestat(IO::String->new('')), {}, 'parse_bmestat - empty input file');
is_deeply(parse_bmestat(IO::String->new("\n\n\n")), {}, 'parse_bmestat - input file with only newlines');

is_deeply(parse_bmestat(IO::String->new(<< 'END'
++ BME stat
   charger state:         DISCONNECTED
   charger type:          NONE
   charging state:        STOPPED
   charging type:         NONE
   charging time:         0
   battery state:         OK
   battery type:          LI4V2
   battery temperature:   31.85
   battery max. level:    8
   battery cur. level:    5
   battery pct. level:    55
   battery max. capacity: 1200
   battery cur. capacity: 671
   battery last full cap: 826
   battery max. voltage:  4200
   battery cur. voltage:  3803
   battery current:       134
   battery condition:     UNKNOWN
END
)), {
   'charger_state' =>         'DISCONNECTED',
   'charger_type' =>          'NONE',
   'charging_state' =>        'STOPPED',
   'charging_type' =>         'NONE',
   'charging_time' =>         '0',
   'battery_state' =>         'OK',
   'battery_type' =>          'LI4V2',
   'battery_temperature' =>   '31.85',
   'battery_max_level' =>     '8',
   'battery_cur_level' =>     '5',
   'battery_pct_level' =>     '55',
   'battery_max_capacity' =>  '1200',
   'battery_cur_capacity' =>  '671',
   'battery_last_full_cap' => '826',
   'battery_max_voltage' =>   '4200',
   'battery_cur_voltage' =>   '3803',
   'battery_current' =>       '134',
   'battery_condition' =>     'UNKNOWN',
}, 'parse_bmestat');

###### parse_ramzswap ######

is_deeply(parse_ramzswap, {}, 'parse_ramzswap - undef input');
is_deeply(parse_ramzswap(IO::String->new('')), {}, 'parse_ramzswap - empty input file');
is_deeply(parse_ramzswap(IO::String->new("\n\n\n")), {}, 'parse_ramzswap - input file with only newlines');

is_deeply(parse_ramzswap(IO::String->new("==> /dev/ramzswap0 <==\n")),
    {}, 'parse_ramzswap - empty /dev/ramzswap0');

is_deeply(parse_ramzswap(IO::String->new("DiskSize: 123 kB\n")),
    {}, 'parse_ramzswap - invalid input');

is_deeply(parse_ramzswap(IO::String->new(<< 'END'
==> /dev/ramzswap0 <==
DiskSize:	   65536 kB
NumReads:	    3252
NumWrites:	    9536
FailedReads:	       0
FailedWrites:	       0
InvalidIO:	       0
NotifyFree:	       0
ZeroPages:	     253
GoodCompress:	      75 %
NoCompress:	       4 %
PagesStored:	    9283
PagesUsed:	    3321
OrigDataSize:	   37132 kB
ComprDataSize:	   13057 kB
MemUsedTotal:	   13284 kB
END
)), {
    '/dev/ramzswap0' => {
        'DiskSize' => 65536,
        'NumReads' => 3252,
        'NumWrites' => 9536,
        'FailedReads' => 0,
        'FailedWrites' => 0,
        'InvalidIO' => 0,
        'NotifyFree' => 0,
        'ZeroPages' => 253,
        'GoodCompress' => 75,
        'NoCompress' => 4,
        'PagesStored' => 9283,
        'PagesUsed' => 3321,
        'OrigDataSize' => 37132,
        'ComprDataSize' => 13057,
        'MemUsedTotal' => 13284,
    },
}, 'parse_ramzswap - /dev/ramzswap0');

is_deeply(parse_ramzswap(IO::String->new(<< 'END'
==> /dev/ramzswap0 <==
DiskSize:	   65536 kB
NumReads:	    3252
==> /dev/ramzswap1 <==
DiskSize:	   11111 kB
NumReads:	   22222
END
)), {
    '/dev/ramzswap0' => {
        'DiskSize' => 65536,
        'NumReads' => 3252,
    },
    '/dev/ramzswap1' => {
        'DiskSize' => 11111,
        'NumReads' => 22222,
    },
}, 'parse_ramzswap - /dev/ramzswap0, /dev/ramzswap1');

###### parse_proc_stat ######

is_deeply(parse_proc_stat, {}, 'parse_proc_stat - undef input');
is_deeply(parse_proc_stat(IO::String->new('')), {}, 'parse_proc_stat - empty input file');
is_deeply(parse_proc_stat(IO::String->new("\n\n\n")), {}, 'parse_proc_stat - input file with only newlines');

is_deeply(parse_proc_stat(IO::String->new(<< 'END'
cpu  33416 1806 11546 15350 3714 212 16 0 0
cpu0 33416 1806 11546 15350 3714 212 16 0 0
intr 469046 0 0 0 0 0 0 0 575 0 0 0 14955 97232 0 0 0 0 0 1 1 0 20074
ctxt 1239044
btime 1324049575
processes 4414
procs_running 2
procs_blocked 0
softirq 182351 2255 64305 3 213 0 0 21403 0 27 94145
END
)), {
    'cpu' =>  [ 33416, 1806, 11546, 15350, 3714, 212, 16, 0, 0 ],
    #'cpu0' => [ 33416, 1806, 11546, 15350, 3714, 212, 16, 0, 0 ],
    #'intr' => [ 469046, 0, 0, 0, 0, 0, 0, 0, 575, 0, 0, 0, 14955, 97232, 0, 0, 0, 0, 0, 1, 1, 0, 20074 ],
    'ctxt' => 1239044,
    #'btime' => 1324049575,
    'processes' => 4414,
    #'procs_running' => 2,
    #'procs_blocked' => 0,
    #'softirq' => [ 182351, 2255, 64305, 3, 213, 0, 0, 21403, 0, 27, 94145 ],
}, 'parse_proc_stat - 1x CPU');

is_deeply(parse_proc_stat(IO::String->new(<< 'END'
cpu  2175726 732308 734523 1010007255 1139610 324 5713 0 0 0
cpu0 422430 127647 147258 126148712 31629 0 1099 0 0 0
cpu1 428545 102638 146221 126166690 17830 3 1012 0 0 0
cpu2 381561 129317 144999 126200639 13708 0 276 0 0 0
cpu3 434220 98836 143584 125510251 13983 320 241 0 0 0
cpu4 133241 68444 37233 126743478 4665 0 205 0 0 0
cpu5 98827 60411 24858 126811064 5007 0 107 0 0 0
cpu6 99532 64579 30560 126804167 4125 0 46 0 0 0
cpu7 177367 80431 59807 125622251 1048659 0 2724 0 0 0
intr 1097444528 528956480 2
ctxt 1387646639
btime 1333024007
processes 257609
procs_running 1
procs_blocked 0
softirq 128253506 0 36745780
END
)), {
    'cpu' =>  [ 2175726, 732308, 734523, 1010007255, 1139610, 324, 5713, 0, 0, 0 ],
    #'cpu0' => [ 422430, 127647, 147258, 126148712, 31629, 0, 1099, 0, 0, 0 ],
    #'cpu1' => [ 428545, 102638, 146221, 126166690, 17830, 3, 1012, 0, 0, 0 ],
    #'cpu2' => [ 381561, 129317, 144999, 126200639, 13708, 0, 276, 0, 0, 0 ],
    #'cpu3' => [ 434220, 98836, 143584, 125510251, 13983, 320, 241, 0, 0, 0 ],
    #'cpu4' => [ 133241, 68444, 37233, 126743478, 4665, 0, 205, 0, 0, 0 ],
    #'cpu5' => [ 98827, 60411, 24858, 126811064, 5007, 0, 107, 0, 0, 0 ],
    #'cpu6' => [ 99532, 64579, 30560, 126804167, 4125, 0, 46, 0, 0, 0 ],
    #'cpu7' => [ 177367, 80431, 59807, 125622251, 1048659, 0, 2724, 0, 0, 0 ],
    #'intr' => [ 1097444528, 528956480, 2 ],
    'ctxt' => 1387646639,
    #'btime' => 1333024007,
    'processes' => 257609,
    #'procs_running' => 1,
    #'procs_blocked' => 0,
    #'softirq' => [ 128253506, 0, 36745780 ],
}, 'parse_proc_stat - 8x CPU');

###### parse_pagetypeinfo ######

is_deeply(parse_pagetypeinfo, {}, 'parse_pagetypeinfo - undef input');
is_deeply(parse_pagetypeinfo(IO::String->new('')), {}, 'parse_pagetypeinfo - empty input file');
is_deeply(parse_pagetypeinfo(IO::String->new("\n\n\n")), {}, 'parse_pagetypeinfo - input file with only newlines');

is_deeply(parse_pagetypeinfo(IO::String->new(<< 'END'
Page block order: 10
Pages per block:  1024

Free pages count per migrate type at order       0      1      2      3      4      5      6      7      8      9     10 
Node    0, zone   Normal, type    Unmovable      1      0      0      0      0      0      0      0      0      0      0 
Node    0, zone   Normal, type  Reclaimable   1532     43      0      0      0      0      0      0      0      0      0 
Node    0, zone   Normal, type      Movable   1813   1881    393      0      0      0      0      0      0      0      0 
Node    0, zone   Normal, type      Reserve      2      0      1      1      1      0      0      0      0      0      0 
Node    0, zone   Normal, type      Isolate      0      0      0      0      0      0      0      0      0      0      0 

Number of blocks type     Unmovable  Reclaimable      Movable      Reserve      Isolate 
Node 0, zone   Normal           13            5          105            1            0 
END
)), {
    0 => {
        Normal => {
            'Unmovable'   => [ 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
            'Reclaimable' => [ 1532, 43, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
            'Movable'     => [ 1813, 1881, 393, 0, 0, 0, 0, 0, 0, 0, 0 ],
            'Reserve'     => [ 2, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0 ],
            'Isolate'     => [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ],
        },
    },
}, 'parse_pagetypeinfo - 1x node, 1x zone, 5x pagetype');

is_deeply(parse_pagetypeinfo(IO::String->new(<< 'END'
Free pages count per migrate type at order       0      1      2      3      4      5      6      7      8      9     10 
Node    0, zone      DMA, type    Unmovable      0      0      0      0      0      0      0      0      0      0      0 
Node    0, zone   Normal, type    Unmovable    272    188     11      0      0      0      0      0      0      0      0 
Node    0, zone  HighMem, type    Unmovable    181    248     91     38     15      9      1      1      1      0      0 
Node    1, zone      DMA, type    Unmovable    777      0      0      0      0      0      0      0      0      0      0 
Node    1, zone   Normal, type    Unmovable    888    188     11      0      0      0      0      0      0      0      0 
Node    1, zone  HighMem, type    Unmovable    999    248     91     38     15      9      1      1      1      0      0 
END
)), {
    0 => {
        DMA     => { 'Unmovable' => [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ] },
        Normal  => { 'Unmovable' => [ 272, 188, 11, 0, 0, 0, 0, 0, 0, 0, 0 ] },
        HighMem => { 'Unmovable' => [ 181, 248, 91, 38, 15, 9, 1, 1, 1, 0, 0 ] },
    },
    1 => {
        DMA     => { 'Unmovable' => [ 777, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ] },
        Normal  => { 'Unmovable' => [ 888, 188, 11, 0, 0, 0, 0, 0, 0, 0, 0 ] },
        HighMem => { 'Unmovable' => [ 999, 248, 91, 38, 15, 9, 1, 1, 1, 0, 0 ] },
    },
}, 'parse_pagetypeinfo - 2x node, 3x zone, 1x pagetype');

###### parse_diskstats ######

is_deeply(parse_diskstats, {}, 'parse_diskstats - undef input');
is_deeply(parse_diskstats(IO::String->new('')), {}, 'parse_diskstats - empty input file');
is_deeply(parse_diskstats(IO::String->new("\n\n\n")), {}, 'parse_diskstats - input file with only newlines');

is_deeply(parse_diskstats(IO::String->new(<< 'END'
   8      16 sdb 2181841 970541 45107598 10074568 224702 466148 11030291 9761856 0 8827440 19869896
   8       2 sda2 2 0 4 0 0 0 0 0 0 0 0
   8       5 sda5 161868 14587 1405729 820588 21474 339504 2904552 1493396 0 188536 2314196
  11       0 sr0 0 0 0 0 0 0 0 0 0 0 0
END
)), {
    sdb => {
        #majdev => 8,
        #mindev => 16,
        #reads_completed => 2181841,
        #reads_merged => 970541,
        sectors_read => 45107598,
        #ms_spent_reading => 10074568,
        #writes_completed => 224702,
        #writes_merged => 466148,
        sectors_written => 11030291,
        #ms_spent_writing => 9761856,
        #ios_in_progress => 0,
        #ms_spent_io => 8827440,
        #ms_spent_io_weighted => 19869896,
    },
    sda2 => {
        #majdev => 8,
        #mindev => 2,
        #reads_completed => 2,
        #reads_merged => 0,
        sectors_read => 4,
        #ms_spent_reading => 0,
        #writes_completed => 0,
        #writes_merged => 0,
        sectors_written => 0,
        #ms_spent_writing => 0,
        #ios_in_progress => 0,
        #ms_spent_io => 0,
        #ms_spent_io_weighted => 0,
    },
    sda5 => {
        #majdev => 8,
        #mindev => 5,
        #reads_completed => 161868,
        #reads_merged => 14587,
        sectors_read => 1405729,
        #ms_spent_reading => 820588,
        #writes_completed => 21474,
        #writes_merged => 339504,
        sectors_written => 2904552,
        #ms_spent_writing => 1493396,
        #ios_in_progress => 0,
        #ms_spent_io => 188536,
        #ms_spent_io_weighted => 2314196,
    },
}, 'parse_diskstats - 1x node, 1x zone, 5x pagetype');

is_deeply(parse_diskstats(IO::String->new(<< 'END'
END
)), {
}, 'parse_diskstats - 2x node, 3x zone, 1x pagetype');


###### parse_sysfs_fs ######

is_deeply(parse_sysfs_fs, {}, 'parse_sysfs_fs - undef input file');
is_deeply(parse_sysfs_fs(IO::String->new('')), {}, 'parse_sysfs_fs - empty input file');
is_deeply(parse_sysfs_fs(IO::String->new("\n\n\n")), {}, 'parse_sysfs_fs - input file with only newlines');

is_deeply(parse_sysfs_fs(IO::String->new(<< 'END'
==> /sys/fs/ext4/mmcblk0p2/delayed_allocation_blocks <==
27

==> /sys/fs/ext4/mmcblk0p2/session_write_kbytes <==
23120

==> /sys/fs/ext4/mmcblk0p2/lifetime_write_kbytes <==
32533

==> /sys/fs/ext4/mmcblk0p2/inode_readahead_blks <==
32

==> /sys/fs/ext4/mmcblk0p2/inode_goal <==
0

==> /sys/fs/ext4/mmcblk0p2/mb_stats <==
0

==> /sys/fs/ext4/mmcblk0p2/mb_max_to_scan <==
200

==> /sys/fs/ext4/mmcblk0p2/mb_min_to_scan <==
10

==> /sys/fs/ext4/mmcblk0p2/mb_order2_req <==
2

==> /sys/fs/ext4/mmcblk0p2/mb_stream_req <==
16

==> /sys/fs/ext4/mmcblk0p2/mb_group_prealloc <==
512

==> /sys/fs/ext4/mmcblk0p2/max_writeback_mb_bump <==
128

==> /sys/fs/ext4/mmcblk0p3/delayed_allocation_blocks <==
0

==> /sys/fs/ext4/mmcblk0p3/session_write_kbytes <==
27920

==> /sys/fs/ext4/mmcblk0p3/lifetime_write_kbytes <==
69746

==> /sys/fs/ext4/mmcblk0p3/inode_readahead_blks <==
32

==> /sys/fs/ext4/mmcblk0p3/inode_goal <==
0

==> /sys/fs/ext4/mmcblk0p3/mb_stats <==
0

==> /sys/fs/ext4/mmcblk0p3/mb_max_to_scan <==
200

==> /sys/fs/ext4/mmcblk0p3/mb_min_to_scan <==
10

==> /sys/fs/ext4/mmcblk0p3/mb_order2_req <==
2

==> /sys/fs/ext4/mmcblk0p3/mb_stream_req <==
16

==> /sys/fs/ext4/mmcblk0p3/mb_group_prealloc <==
512

==> /sys/fs/ext4/mmcblk0p3/max_writeback_mb_bump <==
128
END
)), {
    'mmcblk0p2' => {
        delayed_allocation_blocks => 27,
        session_write_kbytes => 23120,
        lifetime_write_kbytes => 32533,
        inode_readahead_blks => 32,
        inode_goal => 0,
        mb_stats => 0,
        mb_max_to_scan => 200,
        mb_min_to_scan => 10,
        mb_order2_req => 2,
        mb_stream_req => 16,
        mb_group_prealloc => 512,
        max_writeback_mb_bump => 128,
    },
    'mmcblk0p3' => {
        delayed_allocation_blocks => 0,
        session_write_kbytes => 27920,
        lifetime_write_kbytes => 69746,
        inode_readahead_blks => 32,
        inode_goal => 0,
        mb_stats => 0,
        mb_max_to_scan => 200,
        mb_min_to_scan => 10,
        mb_order2_req => 2,
        mb_stream_req => 16,
        mb_group_prealloc => 512,
        max_writeback_mb_bump => 128,
    },
}, 'parse_sysfs_fs - mmcblk0p2, mmcblk0p3');

is_deeply(parse_sysfs_fs(IO::String->new(<< 'END'
==> /sys/fs/ext4/features/lazy_itable_init <==

==> /sys/fs/ext4/features/batched_discard <==

==> /sys/fs/ext4/sdb1/delayed_allocation_blocks <==
0

==> /sys/fs/ext4/sdb1/session_write_kbytes <==
1274712

==> /sys/fs/ext4/sdb1/lifetime_write_kbytes <==
128924941

==> /sys/fs/ext4/sdb2/delayed_allocation_blocks <==
0

==> /sys/fs/ext4/sdb2/session_write_kbytes <==
1203784

==> /sys/fs/ext4/sdb2/lifetime_write_kbytes <==
24745656

==> /sys/fs/ext4/sdb2/extent_cache_hits <==
0

==> /sys/fs/ext4/sdb2/extent_cache_misses <==
0

==> /sys/fs/ext4/sdb2/inode_readahead_blks <==
32

==> /sys/fs/ext4/sdb2/inode_goal <==
0
END
)), {
    sdb1 => {
        delayed_allocation_blocks => 0,
        session_write_kbytes => 1274712,
        lifetime_write_kbytes => 128924941,
    },
    sdb2 => {
        delayed_allocation_blocks => 0,
        session_write_kbytes => 1203784,
        lifetime_write_kbytes => 24745656,
        extent_cache_hits => 0,
        extent_cache_misses => 0,
        inode_readahead_blks => 32,
        inode_goal => 0,
    },
}, 'parse_sysfs_fs - sdb1, sdb2');

###### parse_sysfs_power_supply ######

is_deeply(parse_sysfs_power_supply, {}, 'parse_sysfs_power_supply - undef input');
is_deeply(parse_sysfs_power_supply(IO::String->new('')), {}, 'parse_sysfs_power_supply - empty input file');
is_deeply(parse_sysfs_power_supply(IO::String->new("\n\n\n")), {}, 'parse_sysfs_power_supply - input file with only newlines');

is_deeply(parse_sysfs_power_supply(IO::String->new(<< 'END'
==> /sys/class/power_supply/usb/uevent <==
POWER_SUPPLY_NAME=usb
POWER_SUPPLY_TYPE=USB
POWER_SUPPLY_PRESENT=0
POWER_SUPPLY_CURRENT_NOW=0

==> /sys/class/power_supply/usb/power/wakeup <==


==> /sys/class/power_supply/usb/type <==
USB

==> /sys/class/power_supply/usb/present <==
0

==> /sys/class/power_supply/usb/current_now <==
0

==> /sys/class/power_supply/vac/uevent <==
POWER_SUPPLY_NAME=vac
POWER_SUPPLY_TYPE=Mains
POWER_SUPPLY_PRESENT=0
POWER_SUPPLY_CURRENT_NOW=0

==> /sys/class/power_supply/vac/power/wakeup <==


==> /sys/class/power_supply/vac/type <==
Mains

==> /sys/class/power_supply/vac/present <==
0

==> /sys/class/power_supply/vac/current_now <==
0
END
)), {
    'usb' => {
        type => 'USB',
        present => 0,
        current_now => 0,
    },
    'vac' => {
        type => 'Mains',
        present => 0,
        current_now => 0,
    },
}, 'parse_sysfs_power_supply - usb, vac');

is_deeply(parse_sysfs_power_supply(IO::String->new(<< 'END'
==> /sys/class/power_supply/BAT0/uevent <==
POWER_SUPPLY_NAME=BAT0
POWER_SUPPLY_STATUS=Discharging
POWER_SUPPLY_TECHNOLOGY=Li-ion
POWER_SUPPLY_MODEL_NAME=lithium-battery
POWER_SUPPLY_VOLTAGE_MAX=4179000
POWER_SUPPLY_VOLTAGE_MIN=3640000
POWER_SUPPLY_VOLTAGE_NOW=3679000
POWER_SUPPLY_CURRENT_NOW=-166000
POWER_SUPPLY_CHARGE_FULL_DESIGN=1563000
POWER_SUPPLY_CHARGE_FULL=1563000
POWER_SUPPLY_CHARGE_NOW=246508
POWER_SUPPLY_CHARGE_COUNTER=-5833
POWER_SUPPLY_CAPACITY=15
POWER_SUPPLY_CAPACITY_LEVEL=Normal
POWER_SUPPLY_TIME_TO_FULL_AVG=0
POWER_SUPPLY_TEMP=30

==> /sys/class/power_supply/BAT0/status <==
Discharging

==> /sys/class/power_supply/BAT0/technology <==
Li-ion

==> /sys/class/power_supply/BAT0/voltage_max <==
4179000

==> /sys/class/power_supply/BAT0/voltage_min <==
3640000

==> /sys/class/power_supply/BAT0/voltage_now <==
3679000

==> /sys/class/power_supply/BAT0/current_now <==
-166000

==> /sys/class/power_supply/BAT0/charge_full_design <==
1563000

==> /sys/class/power_supply/BAT0/charge_full <==
1563000

==> /sys/class/power_supply/BAT0/charge_now <==
246508

==> /sys/class/power_supply/BAT0/charge_counter <==
-5833

==> /sys/class/power_supply/BAT0/capacity <==
15

==> /sys/class/power_supply/BAT0/capacity_level <==
Normal

==> /sys/class/power_supply/BAT0/temp <==
30

==> /sys/class/power_supply/BAT0/time_to_full_avg <==
0

==> /sys/class/power_supply/BAT0/type <==
Battery

==> /sys/class/power_supply/BAT0/model_name <==
lithium-battery

==> /sys/class/power_supply/BAT0/power/runtime_status <==
unsupported

==> /sys/class/power_supply/BAT0/power/control <==
auto

==> /sys/class/power_supply/BAT0/power/runtime_suspended_time <==
0

==> /sys/class/power_supply/BAT0/power/runtime_active_time <==
0

==> /sys/class/power_supply/BAT0/power/autosuspend_delay_ms <==

==> /sys/class/power_supply/USB0/uevent <==
POWER_SUPPLY_NAME=USB0
POWER_SUPPLY_TYPE=USB
POWER_SUPPLY_PRESENT=1
POWER_SUPPLY_CURRENT_MAX=500000

==> /sys/class/power_supply/USB0/present <==
1

==> /sys/class/power_supply/USB0/current_max <==
500000

==> /sys/class/power_supply/USB0/type <==
USB

==> /sys/class/power_supply/USB0/power/runtime_status <==
unsupported

==> /sys/class/power_supply/USB0/power/control <==
auto

==> /sys/class/power_supply/USB0/power/runtime_suspended_time <==
0

==> /sys/class/power_supply/USB0/power/runtime_active_time <==
0

==> /sys/class/power_supply/USB0/power/autosuspend_delay_ms <==

END
)), {
    BAT0 => {
        status => 'Discharging',
        technology => 'Li-ion',
        voltage_max => 4179000,
        voltage_min => 3640000,
        voltage_now => 3679000,
        current_now => -166000,
        charge_full_design => 1563000,
        charge_full => 1563000,
        charge_now => 246508,
        charge_counter => -5833,
        capacity => 15,
        capacity_level => 'Normal',
        temp => 30,
        time_to_full_avg => 0,
        type => 'Battery',
        model_name => 'lithium-battery',
    },
    USB0 => {
        present => 1,
        current_max => 500000,
        type => 'USB',
    },
}, 'parse_sysfs_power_supply - BAT0, USB0');

###### parse_sysfs_backlight ######

is_deeply(parse_sysfs_backlight, {}, 'parse_sysfs_backlight - undef input');
is_deeply(parse_sysfs_backlight(IO::String->new('')), {}, 'parse_sysfs_backlight - empty input file');
is_deeply(parse_sysfs_backlight(IO::String->new("\n\n\n")), {}, 'parse_sysfs_backlight - input file with only newlines');

is_deeply(parse_sysfs_backlight(IO::String->new(<< 'END'
==> /sys/class/backlight/display0/uevent <==

==> /sys/class/backlight/display0/bl_power <==
0

==> /sys/class/backlight/display0/brightness <==
127

==> /sys/class/backlight/display0/actual_brightness <==
127

==> /sys/class/backlight/display0/max_brightness <==
255

==> /sys/class/backlight/display0/power/wakeup <==
END
)), {
    display0 => {
        bl_power => 0,
        brightness => 127,
        actual_brightness => 127,
        max_brightness => 255,
    },
}, 'parse_sysfs_backlight - display0');

###### parse_sysfs_cpu ######

is_deeply(parse_sysfs_cpu, {}, 'parse_sysfs_cpu - undef input');
is_deeply(parse_sysfs_cpu(IO::String->new('')), {}, 'parse_sysfs_cpu - empty input file');
is_deeply(parse_sysfs_cpu(IO::String->new("\n\n\n")), {}, 'parse_sysfs_cpu - input file with only newlines');

is_deeply(parse_sysfs_cpu(IO::String->new(<< 'END'
==> /sys/devices/system/cpu/online <==
0

==> /sys/devices/system/cpu/possible <==
0

==> /sys/devices/system/cpu/present <==
0

==> /sys/devices/system/cpu/kernel_max <==
0

==> /sys/devices/system/cpu/offline <==


==> /sys/devices/system/cpu/cpufreq/ondemand/sampling_rate_max <==
4294967295

==> /sys/devices/system/cpu/cpufreq/ondemand/sampling_rate_min <==
30000

==> /sys/devices/system/cpu/cpufreq/ondemand/sampling_rate <==
300000

==> /sys/devices/system/cpu/cpufreq/ondemand/up_threshold <==
95

==> /sys/devices/system/cpu/cpufreq/ondemand/ignore_nice_load <==
0

==> /sys/devices/system/cpu/cpufreq/ondemand/powersave_bias <==
0

==> /sys/devices/system/cpu/cpuidle/current_driver <==
omap3_idle

==> /sys/devices/system/cpu/cpuidle/current_governor_ro <==
menu

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/name <==
C1

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/latency <==
102

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/power <==
4294967295

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/usage <==
43668

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/time <==
76261929

==> /sys/devices/system/cpu/cpu0/cpuidle/state0/flags <==
time valid

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/name <==
C2

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/latency <==
146

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/power <==
4294967294

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/usage <==
30572

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/time <==
106870596

==> /sys/devices/system/cpu/cpu0/cpuidle/state1/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/name <==
C3

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/latency <==
252

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/power <==
4294967293

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/usage <==
313

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/time <==
34308

==> /sys/devices/system/cpu/cpu0/cpuidle/state2/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/name <==
C4

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/latency <==
2309

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/power <==
4294967292

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/usage <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/time <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state3/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/name <==
C5

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/latency <==
5611

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/power <==
4294967291

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/usage <==
7

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/time <==
578

==> /sys/devices/system/cpu/cpu0/cpuidle/state4/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/name <==
C6

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/latency <==
7685

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/power <==
4294967290

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/usage <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/time <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state5/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/name <==
C7

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/latency <==
15818

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/power <==
4294967289

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/usage <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/time <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state6/flags <==
time valid, BM check, disabled

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/name <==
C8

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/desc <==
<null>

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/latency <==
22258

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/power <==
4294967288

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/usage <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/time <==
0

==> /sys/devices/system/cpu/cpu0/cpuidle/state7/flags <==
time valid, BM check

==> /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq <==
300000

==> /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq <==
1000000

==> /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_transition_latency <==
300000

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq <==
300000

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq <==
1000000

==> /sys/devices/system/cpu/cpu0/cpufreq/affected_cpus <==
0

==> /sys/devices/system/cpu/cpu0/cpufreq/related_cpus <==
0

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor <==
ondemand

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver <==
omap

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors <==
userspace ondemand performance 

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_setspeed <==
<unsupported>

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_frequencies <==
1000000 800000 600000 300000 

==> /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq <==
1000000

==> /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq <==
1000000

==> /sys/devices/system/cpu/cpu0/cpufreq/stats/total_trans <==
996

==> /sys/devices/system/cpu/cpu0/cpufreq/stats/time_in_state <==
1000000 42775
800000 3997
600000 8828
300000 10554

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/sampling_rate_max <==
4294967295

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/sampling_rate_min <==
30000

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/sampling_rate <==
300000

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/up_threshold <==
95

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/ignore_nice_load <==
0

==> /sys/devices/system/cpu/cpu0/cpufreq/ondemand/powersave_bias <==
0
END
)), {
    0 => {
        cpufreq => {
            stats => {
                time_in_state => {
                    '1000000' => 42775,
                    '800000' => 3997,
                    '600000' => 8828,
                    '300000' => 10554,
                },
            },
        },
    },
}, 'parse_sysfs_cpu - cpu0');

is_deeply(parse_sysfs_cpu(IO::String->new(<< 'END'
==> /sys/devices/system/cpu/cpu0/cpufreq/stats/time_in_state <==
1111 16361
2222 934
3333 5406
4444 5555
END
)), {
    0 => {
        cpufreq => {
            stats => {
                time_in_state => {
                    '1111' => 16361,
                    '2222' => 934,
                    '3333' => 5406,
                    '4444' => 5555,
                },
            },
        },
    },
}, 'parse_sysfs_cpu - cpu0');

###### parse_component_version ######

is_deeply(parse_component_version, {}, 'parse_component_version - undef input');
is_deeply(parse_component_version(IO::String->new('')), {}, 'parse_component_version - empty input file');
is_deeply(parse_component_version(IO::String->new("\n\n\n")), {}, 'parse_component_version - input file with only newlines');

is_deeply(parse_component_version(IO::String->new(<< 'END'
product     ABCDEF-12345
hw-build    0000
nolo        1.2.3.4.5
boot-mode   normal
END
)), {
    product     => 'ABCDEF-12345',
    hw_build    => '0000',
    nolo        => '1.2.3.4.5',
    boot_mode   => 'normal',
}, 'parse_component_version - 4x key-value pair');

###### parse_step ######

is_deeply(parse_step, [], 'parse_step - undef input');
is_deeply(parse_step(IO::String->new('')), [], 'parse_step - empty input file');
is_deeply(parse_step(IO::String->new("\n\n\n")), [], 'parse_step - input file with only newlines');

is_deeply(parse_step(IO::String->new('Single line step description'
)), [
    'Single line step description'
], 'parse_step - multi-line step description');

is_deeply(parse_step(IO::String->new(<< 'END'
Multi-line step desc, line 1

Multi-line step desc, line 2

Multi-line step desc, line 3
Multi-line step desc, line 4
END
)), [
    'Multi-line step desc, line 1',
    'Multi-line step desc, line 2',
    'Multi-line step desc, line 3',
    'Multi-line step desc, line 4',
], 'parse_step - multi-line step description');

###### parse_usage_csv ######

is_deeply(parse_usage_csv, {}, 'parse_usage_csv - undef input');
is_deeply(parse_usage_csv(IO::String->new('')), {}, 'parse_usage_csv - empty input file');
is_deeply(parse_usage_csv(IO::String->new("\n\n\n")), {}, 'parse_usage_csv - input file with only newlines');

is_deeply(parse_usage_csv(IO::String->new(<< 'END'
generator = syte-endurance-stats v3.0

SW-version = SW_VERSION_GOES_HERE 1.2.3-4.5.6
date = 2011-12-16 17:43:56

Uptime,Idletime (secs):
661.03,153.50

Loadavg 1min,5min,15min,Running/all,Last PID:
1.16,1.49,1.04,2/324,4410

MemTotal,MemFree,Buffers,Cached,SwapCached:
491412 kB,36044 kB,23724 kB,118608 kB,7664 kB

nr_free_pages,nr_inactive_anon,nr_active_anon,nr_inactive_file:
9011,26790,25361,12494

lowmem_maemo,dummy2,dummy3:
0,0,0

Message queues:
perms,cbytes,qnum
invalid line goes,here
1,2,3

Semaphore arrays:
perms,nsems,uid
invalid line goes,here
666,1,29999
666,10,99999

Shared memory segments:
perms,size,cpid,nattch
3666,10,600,0
3666,20,600,1
666,30,300,2
666,40,300,3
3666,50,300,4

Allocated FDs,Freed FDs,Max FDs:
9297,0,32768

PID,FD count,Command line:
1,8,/sbin/init
476,21,/usr/sbin/bme_RX-71 -u -l syslog -v 5 -c /usr/lib/hwi/hw/rx71.so
544,17,/usr/sbin/hald --verbose=no --daemon=no --use-syslog --retain-privileges
567,4,hald-runner
569,0,
600,45,/usr/bin/Xorg -logfile /tmp/Xorg.0.log -core -background none -logverbose 1 -si

Name,State,Tgid,Pid,VmSize,VmLck,voluntary_ctxt_switches,nonvoluntary_ctxt_switches,Threads:
invalid,line,goes,here
init,S (sleeping),1,1,1 kB,5 kB,10,11,0
booster-m,S (sleeping),2777,2777,2 kB,6 kB,12,13,555
sh,S (sleeping),,,3 kB,7 kB,14,15,666
budaemon,S (sleeping),,2847,4 kB,8 kB,,0,777
foobar,S (sleeping),10,10,0,0,0,0,888
foobar,S (sleeping),10,11,0 kB,0 kB,0,0,999

Process status:
invalid,line,goes,here
1,(init),S,0,1,1,0,0,0,1,0,5,0,9,13
2,(kthreadd),S,0,0,0,0,0,0,2,0,6,0,10,14
1082,(dnsmasq),R,1,1082,1082,0,0,0,3,0,7,0,11,15
99999,(,.!/_ )))()()),D,1,9999,8888,0,0,0,4,0,8,0,12,16

PID,wchan:
invalid line goes here
1,poll_schedule_timeout
19,watchdog
1481,poll_schedule_timeout

PID,rchar,wchar,syscr,syscw,read_bytes,write_bytes,cancelled_write_bytes:
invalid,line,goes,here
1,3902402,2561614,10441,3790,30710784,860160,0
2,0,0,0,0,0,0,0
841,27259171939,16002570026,2024951,868371,14218063872,2447728640,73728

Filesystem,1024-blocks,Used,Available,Capacity,Mounted,on
/dev/root,4128448,1738124,2180612,44%,/
devtmpfs,10240,248,9992,2%,/dev
tmpfs,512,148,364,29%,/var/run
<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
/dev/mmcblk0p3,2064208,57176,1902176,3%,/home
aegisfs,4128448,1720856,2197880,44%,/home/user/.mms/private
/dev/mapper/signonfs,6935,41,6536,1%,/home/user/.signon/signonfs-mnt

res-base,WINDOW,FONT,CURSOR,total_resource_count,Pixmap mem,Misc mem,Total mem,PID,Identifier
invalid,line,goes,here
0400000,2,1,1,890,5266939B,10600B,5277539B,750,mthemedaemon
0600000,9,1,1,244,2152032B,6712B,2158744B,-1,MCompositor
1000000,5,1,1,115,455838B,3688B,459526B,933,Quick,Launch,Bar,
END
)), {
    generator => 'syte-endurance-stats v3.0',
    sw_version => 'SW_VERSION_GOES_HERE 1.2.3-4.5.6',
    date => '2011-12-16 17:43:56',
    '/proc/uptime' => {
        uptime => '661.03',
        idletime => '153.50',
    },
    '/proc/loadavg' => {
        min1 => 1.16,
        min5 => 1.49,
        min15 => 1.04,
        running => 2,
        all => 324,
        last_pid => 4410,
    },
    '/proc/meminfo' => {
        MemTotal => 491412,
        MemFree => 36044,
        Buffers => 23724,
        Cached => 118608,
        SwapCached => 7664,
    },
    #'/proc/vmstat' => {
    #nr_free_pages => 9011,
    #nr_inactive_anon => 26790,
    #nr_active_anon => 25361,
    #nr_inactive_file => 12494,
    #},
    '/proc/sysvipc/msg' => {
        count => 1,
    },
    '/proc/sysvipc/sem' => {
        count => 2,
    },
    '/proc/sysvipc/shm' => {
        count           => 5,
        size_locked     => 10+20+50,
        size_unlocked   => 30+40,
        nattch0         => 1,
        nattch1         => 1,
        nattch2         => 1,
        nattch3         => 2,
        cpid_to_size    => { 300 => 30+40+50, 600 => 10+20 },
    },
    '/proc/sys/fs/file-nr' => {
        allocated_fds => 9297,
        free_fds => 0,
        max_fds => 32768,
    },
    '/proc/pid/cmdline' => {
        1   => 'init',
        476 => 'bme_RX-71',
        544 => 'hald',
        567 => 'hald-runner',
        600 => 'Xorg',
    },
    '/proc/pid/fd_count' => {
        1   => 8,
        476 => 21,
        544 => 17,
        567 => 4,
        600 => 45,
    },
    '/proc/pid/status' => {
        1    => 'Name,init,VmSize,1,VmLck,5,voluntary_ctxt_switches,10,nonvoluntary_ctxt_switches,11,Threads,0',
        2777 => 'Name,booster-m,VmSize,2,VmLck,6,voluntary_ctxt_switches,12,nonvoluntary_ctxt_switches,13,Threads,555',
        2847 => 'Name,budaemon,VmSize,4,VmLck,8,nonvoluntary_ctxt_switches,0,Threads,777',
        10   => 'Name,foobar,voluntary_ctxt_switches,0,nonvoluntary_ctxt_switches,0,Threads,888',
        11   => 'Name,foobar,VmSize,0,VmLck,0,voluntary_ctxt_switches,0,nonvoluntary_ctxt_switches,0,Threads,999',
    },
    '/proc/pid/stat' => {
        1     => 'minflt,1,majflt,5,utime,9,stime,13',
        2     => 'minflt,2,majflt,6,utime,10,stime,14',
        1082  => 'minflt,3,majflt,7,utime,11,stime,15,state,R',
        99999 => 'minflt,4,majflt,8,utime,12,stime,16,state,D',
    },
    '/proc/pid/wchan' => {
        poll_schedule_timeout => 2,
        watchdog              => 1,
    },
    '/proc/pid/io' => {
        1 => (pack "d*",3902402,2561614,10441,3790,30710784,860160,0),
        2 => (pack "d*",0,0,0,0,0,0,0),
        841 => (pack "d*",27259171939,16002570026,2024951,868371,14218063872,2447728640,73728),
    },
    '/bin/df' => {
        '/' => {
            filesystem => '/dev/root',
            #blocks_kb => 4128448,
            #used_kb => 1738124,
            #available_kb => 2180612,
            capacity => 44,
        },
        '/dev' => {
            filesystem => 'devtmpfs',
            #blocks_kb => 10240,
            #used_kb => 248,
            #available_kb => 9992,
            capacity => 2,
        },
        '/var/run' => {
            filesystem => 'tmpfs',
            #blocks_kb => 512,
            #used_kb => 148,
            #available_kb => 364,
            capacity => 29,
        },
        '/home' => {
            filesystem => '/dev/mmcblk0p3',
            #blocks_kb => 2064208,
            #used_kb => 57176,
            #available_kb => 1902176,
            capacity => 3,
        },
        '/home/user/.mms/private' => {
            filesystem => 'aegisfs',
            #blocks_kb => 4128448,
            #used_kb => 1720856,
            #available_kb => 2197880,
            capacity => 44,
        },
        '/home/user/.signon/signonfs-mnt' => {
            filesystem => '/dev/mapper/signonfs',
            #blocks_kb => 6935,
            #used_kb => 41,
            #available_kb => 6536,
            capacity => 1,
        },
    },
    '/usr/bin/xmeminfo' => [
        {
            #res_base => '0x0400000',
            #WINDOW => 2,
            #FONT => 1,
            #CURSOR => 1,
            total_resource_count => 890,
            Pixmap_mem => 5266939,
            #Misc_mem => 10600,
            #Total_mem => 5277539,
            PID => 750,
            Identifier => 'mthemedaemon',
        },
        {
            #res_base => '0x0600000',
            #WINDOW => 9,
            #FONT => 1,
            #CURSOR => 1,
            total_resource_count => 244,
            Pixmap_mem => 2152032,
            #Misc_mem => 6712,
            #Total_mem => 2158744,
            PID => -1,
            Identifier => 'MCompositor',
        },
        {
            #res_base => '0x1000000',
            #WINDOW => 5,
            #FONT => 1,
            #CURSOR => 1,
            total_resource_count => 115,
            Pixmap_mem => 455838,
            #Misc_mem => 3688,
            #Total_mem => 459526,
            PID => 933,
            Identifier => 'Quick,Launch,Bar,',
        },
    ],
}, 'parse_usage_csv');

###### parse_ifconfig ######

is_deeply(parse_ifconfig, {}, 'parse_ifconfig - undef input');
is_deeply(parse_ifconfig(IO::String->new('')), {}, 'parse_ifconfig - empty input file');
is_deeply(parse_ifconfig(IO::String->new("\n\n\n")), {}, 'parse_ifconfig - input file with only newlines');

is_deeply(parse_ifconfig(IO::String->new(<< 'END'
eth0      Link encap:Ethernet  HWaddr 00:24:e8:48:4c:1a  
          inet addr:172.21.81.237  Bcast:172.21.81.255  Mask:255.255.254.0
          inet6 addr: fe80::224:e8ff:fe48:4c1a/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:34081833 errors:0 dropped:0 overruns:0 frame:0
          TX packets:1584936 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000 
          RX bytes:6783082580 (6.3 GiB)  TX bytes:243353875 (232.0 MiB)
          Interrupt:17 

lo        Link encap:Local Loopback  
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:16436  Metric:1
          RX packets:1191333 errors:0 dropped:0 overruns:0 frame:0
          TX packets:1191333 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0 
          RX bytes:10079963165 (9.3 GiB)  TX bytes:10079963165 (9.3 GiB)

pan0      Link encap:Ethernet  HWaddr 36:e9:79:32:dd:eb  
          BROADCAST MULTICAST  MTU:1500  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0 
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

END
)), {
    eth0 => {
        RX => { bytes => 6783082580, packets => 34081833 },
        TX => { bytes => 243353875,  packets => 1584936  },
    },
    lo => {
        RX => { bytes => 10079963165, packets => 1191333 },
        TX => { bytes => 10079963165, packets => 1191333 },
    },
    pan0 => {
        RX => { bytes => 0, packets => 0 },
        TX => { bytes => 0, packets => 0 },
    },
}, 'parse_ifconfig - eth0, lo, pan0');

###### parse_upstart_jobs_respawned ######

is_deeply(parse_upstart_jobs_respawned, {}, 'parse_upstart_jobs_respawned - undef input');

{
    my $content = '';
    open my $fh, '<', \$content;
    is_deeply(parse_upstart_jobs_respawned($fh), {}, 'parse_upstart_jobs_respawned - empty input file');
}
{
    my $content = "\n\n\n";
    open my $fh, '<', \$content;
    is_deeply(parse_upstart_jobs_respawned($fh), {}, 'parse_upstart_jobs_respawned - input file with only newlines');
}

{
    my $content = <<'END';
pulseaudio: 4
xsession/conndlgs: 11
xsession/meego-im-uiserver: 85
END

    open my $fh, '<', \$content;
    is_deeply(parse_upstart_jobs_respawned($fh), {
        pulseaudio => 4,
        'xsession/conndlgs' => 11,
        'xsession/meego-im-uiserver' => 85,
    }, 'parse_upstart_jobs_respawned - 4x entry');
}

{
    my $content = <<'END';
                    foobar: 2
:
: 1
x:
y: -1
z: a

invalid_line_goes_here
END

    open my $fh, '<', \$content;
    is_deeply(parse_upstart_jobs_respawned($fh), {
    }, 'parse_upstart_jobs_respawned - invalid entries');
}

###### parse_sched ######

is_deeply(parse_sched, {}, 'parse_sched - undef input');

{
    my $content = '';
    open my $fh, '<', \$content;
    is_deeply(parse_sched($fh), {}, 'parse_sched - empty input file');
}
{
    my $content = "\n\n\n";
    open my $fh, '<', \$content;
    is_deeply(parse_sched($fh), {}, 'parse_sched - input file with only newlines');
}

{
    my $content = <<'END';
==> /proc/1/sched <==
init (1, #threads: 1)
---------------------------------------------------------
se.exec_start                      :        586901.275634
se.vruntime                        :        198573.908325
se.sum_exec_runtime                :          1831.054666
se.statistics.wait_start           :             0.000000
se.statistics.sleep_start          :        586901.275634
se.statistics.block_start          :             0.000000
se.statistics.sleep_max            :         60034.576416
se.statistics.block_max            :           747.497558
se.statistics.exec_max             :            10.009765
se.statistics.slice_max            :            12.573242
se.statistics.wait_max             :            30.487061
se.statistics.wait_sum             :          1176.849356
se.statistics.wait_count           :                 7442
se.statistics.iowait_sum           :           952.331547
se.statistics.iowait_count         :                  146
se.nr_migrations                   :                    0
se.statistics.nr_migrations_cold   :                    0
se.statistics.nr_failed_migrations_affine:                    0
se.statistics.nr_failed_migrations_running:                    0
se.statistics.nr_failed_migrations_hot:                    0
se.statistics.nr_forced_migrations :                    0
se.statistics.nr_wakeups           :                 5451
se.statistics.nr_wakeups_sync      :                  768
se.statistics.nr_wakeups_migrate   :                    0
se.statistics.nr_wakeups_local     :                    0
se.statistics.nr_wakeups_remote    :                    0

==> /proc/140/sched <==
syslogd (140, #threads: 1)
---------------------------------------------------------
se.exec_start                      :        593137.054443
se.vruntime                        :        198686.896359
se.sum_exec_runtime                :           206.878649
se.statistics.wait_start           :             0.000000
se.statistics.sleep_start          :        593137.054443
se.statistics.block_start          :             0.000000
se.statistics.sleep_max            :         27414.459228
se.statistics.block_max            :           222.351074
se.statistics.exec_max             :             4.272461
se.statistics.slice_max            :             4.394531
se.statistics.wait_max             :            10.620117
se.statistics.wait_sum             :           222.290054
se.statistics.wait_count           :                 1526
se.statistics.iowait_sum           :           160.308836
se.statistics.iowait_count         :                   10
se.nr_migrations                   :                    0
se.statistics.nr_migrations_cold   :                    0
se.statistics.nr_failed_migrations_affine:                    0
se.statistics.nr_failed_migrations_running:                    0
se.statistics.nr_failed_migrations_hot:                    0
se.statistics.nr_forced_migrations :                    0
se.statistics.nr_wakeups           :                 1297
se.statistics.nr_wakeups_sync      :                 1260
se.statistics.nr_wakeups_migrate   :                    0
se.statistics.nr_wakeups_local     :                    0
se.statistics.nr_wakeups_remote    :                    0

==> /proc/9999/sched <==
foobar (9999, #threads: 1)
---------------------------------------------------------
se.statistics.block_max            :           123.456789
END

    open my $fh, '<', \$content;
    is_deeply(parse_sched($fh), {
        1 => pack('d*',
            '747.497558', # se.statistics.block_max
            '30.487061',  # se.statistics.wait_max
            '952.331547', # se.statistics.iowait_sum
            '5451',       # se.statistics.nr_wakeups
        ),
        140 => pack('d*',
            '222.351074', # se.statistics.block_max
            '10.620117',  # se.statistics.wait_max
            '160.308836', # se.statistics.iowait_sum
            '1297',       # se.statistics.nr_wakeups
        ),
        9999 => pack('d*',
            '123.456789', # se.statistics.block_max
            '0',          # se.statistics.wait_max
            '0',          # se.statistics.iowait_sum
            '0',          # se.statistics.nr_wakeups
        ),
    }, 'parse_sched - 2x entry');
}

{
    my $content = <<'END';
                    foobar: 2
:
: 1
x:
y: -1
z: a

invalid_line_goes_here
# missing PID before this line:
se.statistics.block_max            :           222.351074
END

    open my $fh, '<', \$content;
    is_deeply(parse_sched($fh), {
    }, 'parse_sched - invalid entries');
}

###### parse_pidfilter ######

is_deeply(parse_pidfilter, undef, 'parse_pidfilter - undef input');
is_deeply(parse_pidfilter({}), {}, 'parse_pidfilter - empty input');
is_deeply(parse_pidfilter([]), [], 'parse_pidfilter - wrong input type');

is_deeply(parse_pidfilter({
    '/proc/pid/cmdline' => {
        1 => 'init',
    },
}), {
    '/proc/pid/cmdline' => {
        1 => 'init',
    },
}, 'parse_pidfilter - /proc/pid/cmdline');

is_deeply(parse_pidfilter({
    '/proc/pid/cmdline' => {
        1 => 'init',
        2 => 'fubar',
        10 => 'sp-noncached',
        11 => 'sp_smaps_snapshot',
        12 => 'lzop',
    },
}), {
    '/proc/pid/cmdline' => {
        1 => 'init',
        2 => 'fubar',
    },
}, 'parse_pidfilter - /proc/pid/cmdline');

is_deeply(parse_pidfilter({
    '/proc/pid/smaps' => {
        1 => { '#Name' => 'init' },
        13 => { '#Name' => 'sp-noncached' },
    },
    '/proc/pid/fd_count' => {
        1 => 1,
        2 => 2,
        10 => 10,
        11 => 11,
        12 => 12,
        13 => 13,
    },
}), {
    '/proc/pid/smaps' => {
        1 => { '#Name' => 'init' },
    },
    '/proc/pid/fd_count' => {
        1 => 1,
        2 => 2,
        10 => 10,
        11 => 11,
        12 => 12,
    },
}, 'parse_pidfilter - /proc/pid/smaps, /proc/pid/fd_count');

is_deeply(parse_pidfilter({
    '/proc/pid/status' => {
        1 => 'Name,init',
        14 => 'Name,save-incrementa',
    },
    '/proc/pid/wchan' => {
        2 => '2',
        3 => '3',
        11 => '11',
        14 => '14',
    },
    '/proc/pid/io' => {
        10 => 'y',
        11 => 'z',
        13 => 'k',
        14 => 'o',
    },
}), {
    '/proc/pid/status' => {
        1 => 'Name,init',
    },
    '/proc/pid/wchan' => {
        2 => '2',
        3 => '3',
        11 => '11',
    },
    '/proc/pid/io' => {
        10 => 'y',
        11 => 'z',
        13 => 'k',
    },
}, 'parse_pidfilter - /proc/pid/{status,wchan,io}');

is_deeply(parse_pidfilter({
    '/proc/pid/cmdline' => {
        1 => 'init',
        2 => 'fubar',
        10 => 'sp-noncached',
        11 => 'sp_smaps_snapshot',
        12 => 'lzop',
    },
    '/proc/pid/smaps' => {
        1 => { '#Name' => 'init' },
        13 => { '#Name' => 'sp-noncached' },
    },
    '/proc/pid/status' => {
        1 => 'Name,init',
        14 => 'Name,save-incrementa',
    },
    '/proc/pid/fd_count' => {
        1 => 1,
        2 => 2,
        10 => 10,
        11 => 11,
        12 => 12,
        13 => 13,
    },
    '/proc/pid/wchan' => {
        2 => '2',
        3 => '3',
        11 => '11',
        14 => '14',
    },
    '/proc/pid/io' => {
        10 => 'y',
        11 => 'z',
        13 => 'k',
        14 => 'o',
    },
}), {
    '/proc/pid/cmdline' => {
        1 => 'init',
        2 => 'fubar',
    },
    '/proc/pid/smaps' => {
        1 => { '#Name' => 'init' },
    },
    '/proc/pid/status' => {
        1 => 'Name,init',
    },
    '/proc/pid/fd_count' => {
        1 => 1,
        2 => 2,
    },
    '/proc/pid/wchan' => {
        2 => '2',
        3 => '3',
    },
    '/proc/pid/io' => {},
}, 'parse_pidfilter - /proc/pid/{cmdline,smaps,status,fd_count,wchan,io}');

done_testing;
# vim: ts=4:sw=4:et
