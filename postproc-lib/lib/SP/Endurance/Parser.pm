# This file is part of sp-endurance.
#
# vim: ts=4:sw=4:et
#
# Copyright (C) 2010-2012 by Nokia Corporation
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

use v5.10;

package SP::Endurance::Parser;

use SP::Endurance;

require Exporter;
@ISA = qw/Exporter/;
@EXPORT_OK = qw/parse_openfds FD_DISK FD_EPOLL FD_EVENTFD FD_INOTIFY FD_PIPE
    FD_SIGNALFD FD_SOCKET FD_TIMERFD FD_TMPFS parse_smaps parse_smaps_pp
    parse_slabinfo parse_cgroups parse_interrupts parse_bmestat parse_ramzswap
    parse_proc_stat parse_pagetypeinfo parse_diskstats parse_sysfs_fs
    parse_sysfs_power_supply parse_sysfs_backlight parse_sysfs_cpu
    parse_component_version parse_step parse_usage_csv parse_df parse_ifconfig
    parse_upstart_jobs_respawned parse_sched parse_dir parse_pidfilter copen/;

use File::Basename qw/basename/;
use List::MoreUtils qw/uniq zip all any none firstidx/;
use List::Util qw/sum min/;
use IO::File;
use Data::Dumper;
use JSON qw/decode_json/;

eval 'use common::sense';
use strict;

eval q/use Inline C => 'DATA', VERSION => $SP::Endurance::VERSION, NAME => 'SP::Endurance::Parser'/;

my @process_blacklist = qw/
    sp-noncached
    save-incrementa
    sp_smaps_snapshot
    lzop
/;

sub copen {
    my $file = shift;

    return IO::File->new("lzop -dc '$file.lzo' |")   if -e $file . '.lzo';
    return IO::File->new("zcat '$file.gz' |")        if -e $file . '.gz';
    return IO::File->new("xzcat '$file.xz' |")       if -e $file . '.xz';
    return IO::File->new($file);
}

sub FD_DISK()       { 0 }
sub FD_EPOLL()      { 1 }
sub FD_EVENTFD()    { 2 }
sub FD_INOTIFY()    { 3 }
sub FD_PIPE()       { 4 }
sub FD_SIGNALFD()   { 5 }
sub FD_SOCKET()     { 6 }
sub FD_TIMERFD()    { 7 }
sub FD_TMPFS()      { 8 }
sub FD_COUNT()      { 9 }

our %fdtypemap = (
    disk       => FD_DISK,
    epoll      => FD_EPOLL,
    eventfd    => FD_EVENTFD,
    inotify    => FD_INOTIFY,
    pipe       => FD_PIPE,
    signalfd   => FD_SIGNALFD,
    socket     => FD_SOCKET,
    timerfd    => FD_TIMERFD,
    tmpfs      => FD_TMPFS,
);

sub parse_openfds {
    my $fh = shift;

    return {} unless defined $fh;

    my %openfds;
    my $pid;

    while (<$fh>) {
        my $arrow = index $_, ' -> ';
        if ($pid and $arrow > 0) {
            chomp;
            my $target = substr $_, $arrow + 4;
            if ($target eq 'inotify' or $target eq 'anon_inode:inotify') {
                $openfds{$pid}->[FD_INOTIFY]++;
            } elsif ($target eq 'anon_inode:[eventfd]') {
                $openfds{$pid}->[FD_EVENTFD]++;
            } elsif ($target eq 'anon_inode:[eventpoll]') {
                $openfds{$pid}->[FD_EPOLL]++;
            } elsif ($target eq 'anon_inode:[signalfd]') {
                $openfds{$pid}->[FD_SIGNALFD]++;
            } elsif ($target eq 'anon_inode:[timerfd]') {
                $openfds{$pid}->[FD_TIMERFD]++;
            } elsif (index($target, 'pipe:[') != -1) {
                $openfds{$pid}->[FD_PIPE]++;
            } elsif (index($target, 'socket:[') != -1) {
                $openfds{$pid}->[FD_SOCKET]++;
            } elsif ($target =~ m#^/(?:dev|sys|syspart|proc|tmp|run|var/run)/#) {
                $openfds{$pid}->[FD_TMPFS]++;
            } elsif ($target =~ m#^/#) {
                $openfds{$pid}->[FD_DISK]++;
            } else {
                #print STDERR "UNCLASSIFIED open-fds entry: $_";
            }
        } elsif (m#^/proc/(\d+)/fd/?:#) {
            $pid = $1;
            $openfds{$pid}->[FD_COUNT-1] = undef;
        }
    }

    foreach my $pid (keys %openfds) {
        my $values = $openfds{$pid};
        if (none { defined } @$values) {
            $openfds{$pid} = undef;
        } else {
            $openfds{$pid} = join ',', map { defined $_ ? $_ : '' } @$values;
        }
    }

    #print Dumper \%openfds;
    return \%openfds;
}

our @GFX_MMAPS = (
    '/dev/pvrsrvkm',     # Harmattan
    '/dev/nvidia',       # Desktop Linux with NVIDIA graphics
);

my @WANTED_MMAPS = (
    @GFX_MMAPS,
    qw(
        [heap]
        /SYSV
        /dev/shm/
        rwxp
    ));

sub parse_smaps {
    my $fh = shift;

    return {} unless defined $fh;

    my $ret;

    eval {
        $ret = parse_smaps_inline($fh, \@WANTED_MMAPS);
    };

    if ($@) {
        $ret = parse_smaps_pp($fh);
    }

    #print STDERR Dumper $ret;
    return $ret;
}

# Also ship a "pure perl" implementation for those users that do not have
# Inline installed. This should return exactly same results as
# parse_smaps_inline().
sub parse_smaps_pp {
    my $fh = shift;

    return {} unless defined $fh;

    my %keyval;
    my $smaps_vma_ref;
    my $name;
    my $pid;
    while (<$fh>) {
        chomp;
        next if $_ eq '';
        if (/^([A-Z]\S+):\s+(\d+) kB/) {
            next unless defined $pid and $2;
            next unless $1 eq 'Size' or $1 eq 'Pss' or $1 eq 'Private_Dirty' or $1 eq 'Swap';

            $keyval{$pid}->{"total_$1"} += $2;
            $smaps_vma_ref->{"total_$1"} += $2 if defined $smaps_vma_ref and $1 eq 'Size';
        } elsif (/^[\dabcdef]{8}/) {
            next unless defined $pid;

            $keyval{$pid}->{vmacount}++;

            $smaps_vma_ref = undef;
            foreach my $want (@WANTED_MMAPS) {
                next if index($_, $want) == -1;
                $keyval{$pid}->{$want} = {} unless exists $keyval{$pid}->{$want};
                $smaps_vma_ref = $keyval{$pid}->{$want};
                $smaps_vma_ref->{vmacount}++;
                last;
            }
        } elsif (/^#Name: (.*)$/) {
            $name = $1;
            $pid = undef;
            $smaps_vma_ref = undef;
        } elsif (/^#Pid: (\d+)/) {
            $pid = int $1;
            $keyval{$pid}->{'#Name'} = $name
                if defined $name;
            undef $name;
        }
    }

    return \%keyval;
}

sub parse_slabinfo {
    my $fh = shift;

    return {} unless defined $fh;

    my %slabsizes;

    while (<$fh>) {
        chomp;
        next if /^slabinfo/ or /^# name/ or $_ eq '';
        my @entry = split ' ', $_, 16;
        $slabsizes{$entry[0]} = ($entry[1] * $entry[3]) / 1024;
    }

    return \%slabsizes;
}

sub CGROUP_UNLIMITED() { 9223372036854775807 }

sub parse_cgroups {
    my $fh = shift;

    return {} unless defined $fh;

    my %cgroups;

    while (<$fh>) {
        if (m#^==> /syspart(\S*/)(cgroup\.procs|tasks) <==#) {
            my $cgroup = $1;
            my $key = $2;
            my @list;
            while (<$fh> =~ m#^(\d+)$#) {
                push @list, int $1;
            }
            $cgroups{$cgroup}->{$key} = scalar uniq @list;
        } elsif (m#^==> /syspart(\S*/)memory\.stat <==#) {
            my $cgroup = $1;
            # ==> /syspart/system/desktop/memory.stat <==
            # cache 49410048
            # rss 68714496
            # mapped_file 45260800
            # ...
            my %keyval;
            while (<$fh> =~ m#^([a-z_]+) (\d+)$#) {
                $keyval{$1} = int $2
                    unless $1 =~ /^total_|^hierarchical_/;
            }
            $cgroups{$cgroup}->{'memory.stat'} = \%keyval;
        } elsif (m#^==> /syspart(\S*/)([a-z_\.]+) <==#) {
            my $cgroup = $1;
            my $key = $2;
            my $value = <$fh>;

            next if $key =~ /memory\.oom_control/;
            next if $key =~ /soft_limit_in_bytes/;
            next if $key =~ /limit_in_bytes/ and $value == CGROUP_UNLIMITED;

            $cgroups{$cgroup}->{$key} = int $value;
        }
    }

    return \%cgroups;
}

sub parse_interrupts {
    my $fh = shift;

    return {} unless defined $fh;

    my %interrupts;

    my @cpus = split ' ', <$fh>;
    my $cpus = @cpus;

    return \%interrupts unless $cpus > 0;

    while (<$fh>) {
        chomp;
        next unless /^\s*(\S+):((?:\s+\d+){1,$cpus})\s*(.*)/;
        my $interrupt = $1;

        my $cnt = sum split ' ', $2;
        next unless $cnt;

        my $desc = $3;
        $desc =~ s/\s+/ /g;
        $interrupts{$interrupt}->{count} = $cnt;
        $interrupts{$interrupt}->{desc} = $desc if length $desc;
    }

    return \%interrupts;
}

sub parse_suspend_stats {
    my $fh = shift;

    return {} unless defined $fh;

    my %suspend_stats;

    while (<$fh>) {
        chomp;
        next unless /([a-z\_]+):\s+(\S+)/;
        my $key = $1;
        my $value = $2;
        $suspend_stats{$key} = $value;
    }

    return \%suspend_stats;
}

sub parse_bmestat {
    my $fh = shift;

    return {} unless defined $fh;

    my %bmestat;

    while (<$fh>) {
        chomp;
        next unless /\s+([a-z\. ]+):\s+(\S+)/;
        my $key = $1;
        my $value = $2;
        $key =~ s/\.//g;
        $key =~ s/ /_/g;
        $bmestat{$key} = $value;
    }

    return \%bmestat;
}

sub parse_ramzswap {
    my $fh = shift;

    return {} unless defined $fh;

    my %ramzswap;
    my $device;

    while (<$fh>) {
        $device = $1 if /^==> (\S+) <==/;
        $ramzswap{$device}->{$1} = int($2) if $device and /^(\S+):\s*(\d+)/;
    }

    return \%ramzswap;
}

sub parse_proc_stat {
    my $fh = shift;

    return {} unless defined $fh;

    my %stat;

    while (<$fh>) {
        next unless /^(\S+)\s+(..*)$/;
        my $key = $1;
        my $data = $2;

        # Take only what we really need.
        next unless $key =~ /^(?:cpu|ctxt|processes)$/;

        my @ints = map { int } grep { /\d+/ } split ' ', $data;
        next unless @ints;

        if (@ints == 1) {
            $stat{$key} = $ints[0];
        } else {
            $stat{$key} = \@ints;
        }
    }

    return \%stat;
}

sub parse_pagetypeinfo {
    my $fh = shift;

    return {} unless defined $fh;

    my %pagetypeinfo;

    while (<$fh>) {
        chomp;
        next unless m#^Node\s+(\d+), zone\s+(\S+), type\s+(\S+)(.*)$#;
        my $node = $1;
        my $zone = $2;
        my $type = $3;
        my @free_pages = split ' ', $4;
        next unless @free_pages == 11;
        $pagetypeinfo{$node}->{$zone}->{$type} = \@free_pages;
    }

    return \%pagetypeinfo;
}

sub parse_diskstats {
    my $fh = shift;

    return {} unless defined $fh;

    my %diskstats;

    my @keys = qw/majdev mindev device reads_completed reads_merged
        sectors_read ms_spent_reading writes_completed writes_merged
        sectors_written ms_spent_writing ios_in_progress ms_spent_io
        ms_spent_io_weighted/;

    while (<$fh>) {
        chomp;

        my @values = split;
        next unless @values == @keys;

        my %entry = zip @keys, @values;

        # Ignore all-zero entries.
        next if all { $_ == 0 } @values[3,-1];

        my $device = $entry{device};

        # Take only what we really use to save some memory.
        $diskstats{$device} = {
            sectors_read    => $entry{sectors_read},
            sectors_written => $entry{sectors_written},
        };
    }

    return \%diskstats;
}

sub parse_sysfs_fs {
    my $fh = shift;

    return {} unless defined $fh;

    my %fs;

    while (<$fh>) {
        next unless m#^==> /sys/fs/ext4/(\S+)/(\S+) <==#;
        my $key1 = $1;
        my $key2 = $2;
        my $value = <$fh>;
        chomp $value;
        next unless length $value;
        $value = int $value;
        $fs{$key1}->{$key2} = $value;
    }

    return \%fs;
}

sub parse_sysfs_kgsl {
    my $fh = shift;

    return {} unless defined $fh;

    use Tie::IxHash;
    my %kgsl;
    tie %kgsl, 'Tie::IxHash';

    while (<$fh>) {
        next unless m#^==> /sys/devices/virtual/kgsl/kgsl/proc/(\S+)/(\S+) <==#;
        my $key1 = $1;
        my $key2 = $2;
        my $value = <$fh>;
        chomp $value;
        next unless length $value;
        $value = int $value;
        if ( ! exists $kgsl{$key2} ) {
            $kgsl{$key2} = {};
            tie ( %{$kgsl{$key2}}, 'Tie::IxHash' );
        }
        $kgsl{$key2}->{$key1} = $value;
    }

    # add separator between snapshots
    foreach my $key (keys %kgsl) {
        $kgsl{$key}->{"#####"} = 0;
    }

    return \%kgsl;
}

sub parse_sysfs_power_supply {
    my $fh = shift;

    return {} unless defined $fh;

    my %ps;
    while (<$fh>) {
        next unless m#^==> /sys/class/power_supply/(\S+)/(\S+) <==#;
        my $key1 = $1;
        my $key2 = $2;
        my $value = <$fh>;
        chomp $value;
        next unless length $value;
        next if $key1 =~ m#/# or $key2 =~ m#/# or $key2 eq 'uevent';
        $ps{$key1}->{$key2} = $value;
    }

    return \%ps;
}

sub parse_sysfs_backlight {
    my $fh = shift;

    return {} unless defined $fh;

    my %backlight;

    while (<$fh>) {
        next unless m#^==> /sys/class/backlight/(\S+)/(\S+) <==#;
        my $key1 = $1;
        my $key2 = $2;

        my $value = <$fh>;
        next unless defined $value;

        chomp $value;
        next unless length $value;
        next if $key1 =~ m#/# or $key2 =~ m#/# or $key2 eq 'uevent';

        $backlight{$key1}->{$key2} = $value;
    }

    return \%backlight;
}

sub parse_sysfs_cpu {
    my $fh = shift;

    return {} unless defined $fh;

    my %cpu;

    while (<$fh>) {
        if (m#^==> /sys/devices/system/cpu/cpu(\d+)/cpufreq/stats/time_in_state <==#) {
            my $cpu = $1;
            while (<$fh>) {
                last unless /^(\d+)\s+(\d+)/;
                $cpu{$cpu}->{cpufreq}->{stats}->{time_in_state}->{$1} = int $2;
            }
        }
    }

    return \%cpu;
}

sub parse_component_version {
    my $fh = shift;

    return {} unless defined $fh;

    my %cv;

    while (<$fh>) {
        next unless /(\S+)\s+(\S.*)/;
        my $key = $1;
        my $value = $2;
        $key =~ s/-/_/g;
        $cv{$key} = $value;
    }

    return \%cv;
}

sub parse_step {
    my $fh = shift;

    return [] unless defined $fh;

    my @step;

    while (<$fh>) {
        chomp;
        push @step, $_ if length $_;
    }

    return \@step;
}

sub csv_loadavg {
    my $fh = shift;

    return {} unless defined $fh;

    my $line = <$fh>;
    chomp $line;

    my @keys = qw/min1 min5 min15 running all last_pid/;
    my @values = split m#,|/#, $line, scalar @keys;

    return {} unless @values == @keys;
    return { zip @keys, @values };
}

sub csv_proc_meminfo {
    my $fh = shift;
    my $keys = shift;

    return {} unless defined $fh;

    chomp $keys;
    $keys =~ s/:$//;
    my @keys = split ',', $keys;

    my $values = <$fh>;
    chomp $values;
    my @values = split ',', $values;
    @values = map { /(\d+)/ && int $1 } @values;

    return {} unless @keys == @values;
    return { zip @keys, @values };
}

sub csv_keyval {
    my $fh = shift;
    my $keys = shift;

    return {} unless defined $fh;

    chomp $keys;
    $keys =~ s/:$//;
    my @keys = split ',', $keys;

    my $values = <$fh>;
    chomp $values;
    my @values = split ',', $values;
    @values = map { /(\d+)/ && $1 } @values;

    return {} unless @keys == @values;
    return { zip @keys, @values };
}

sub csv_wchan {
    my $fh = shift;

    return {} unless defined $fh;

    my %wchan;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        next unless /^(\d+),(\S+)/;
        $wchan{$2}++;
    }

    return \%wchan;
}

sub csv_proc_pid_stat {
    my $fh = shift;

    return {} unless defined $fh;

    my %stat;
    while (<$fh>) {
        chomp;
        last if $_ eq '';

        # The process name may contains arbitrary characters, so naive
        # splitting will not work reliably.
        my $curl_start = index $_, '(';
        my $curl_end   = rindex $_, ')';
        next if $curl_start == -1 or $curl_end == -1 or $curl_start > $curl_end;

        my $pid = substr $_, 0, $curl_start-1;
        my $name = substr $_, $curl_start+1, ($curl_end-$curl_start)-1;
        my @values = split(',', substr($_, $curl_end+2));

        unshift @values, $pid, $name;

        my $entry = '';
        $entry .= 'minflt,' . int($values[9])   . ',' if defined $values[9];
        $entry .= 'majflt,' . int($values[11])  . ',' if defined $values[11];
        $entry .= 'utime,'  . int($values[13])  . ',' if defined $values[13];
        $entry .= 'stime,'  . int($values[14])  . ',' if defined $values[14];
        $entry .= 'state,'  . $values[2]        . ','
            if defined $values[2] and length $values[2] and $values[2] ne 'S';

        $entry = substr $entry, 0, -1;

        next unless length $entry;

        $stat{$pid} = $entry;
    }

    return \%stat;
}

sub csv_proc_pid_status {
    my $fh = shift;
    my $keys = shift;

    return {} unless defined $fh;

    $keys =~ s/:$//;
    my @keys = split ',', $keys;

    my $idx_Name    = firstidx { $_ eq 'Name' } @keys;
    my $idx_Pid     = firstidx { $_ eq 'Pid' } @keys;
    my $idx_Threads = firstidx { $_ eq 'Threads' } @keys;
    my $idx_VmLck   = firstidx { $_ eq 'VmLck' } @keys;
    my $idx_VmSize  = firstidx { $_ eq 'VmSize' } @keys;
    my $idx_voluntary_ctxt_switches    = firstidx { $_ eq 'voluntary_ctxt_switches' } @keys;
    my $idx_nonvoluntary_ctxt_switches = firstidx { $_ eq 'nonvoluntary_ctxt_switches' } @keys;

    return {} if $idx_Pid == -1;

    my %stat;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        my @values = split ',';
        next unless @keys == @values;

        my $pid = $values[$idx_Pid];
        next unless defined $pid and $pid =~ /^\d+$/ and $pid > 0;

        my $entry = '';

        if ($idx_Name != -1 and defined $values[$idx_Name] and
               length $values[$idx_Name]) {
            $entry .= 'Name,' . $values[$idx_Name] . ',';
        }

        if ($idx_VmSize != -1 and defined $values[$idx_VmSize] and
               $values[$idx_VmSize] =~ /^(\d+) kB$/) {
            $entry .= 'VmSize,' . int($1) . ',';
        }

        if ($idx_VmLck != -1 and defined $values[$idx_VmLck] and
                $values[$idx_VmLck] =~ /^(\d+) kB$/) {
            $entry .= 'VmLck,' . int($1) . ',';
        }

        $entry .= 'voluntary_ctxt_switches,' . int($values[$idx_voluntary_ctxt_switches]) . ','
            if $idx_voluntary_ctxt_switches != -1 and
               defined $values[$idx_voluntary_ctxt_switches] and
               $values[$idx_voluntary_ctxt_switches] =~ /^\d+$/;

        $entry .= 'nonvoluntary_ctxt_switches,' . int($values[$idx_nonvoluntary_ctxt_switches]) . ','
            if $idx_nonvoluntary_ctxt_switches != -1 and
               defined $values[$idx_nonvoluntary_ctxt_switches] and
               $values[$idx_nonvoluntary_ctxt_switches] =~ /^\d+$/;

        $entry .= 'Threads,' . int($values[$idx_Threads]) . ','
            if $idx_Threads != -1 and
               defined $values[$idx_Threads] and
               $values[$idx_Threads] =~ /^\d+/;

        $entry = substr $entry, 0, -1;
        next unless length $entry;

        $stat{$pid} = $entry;
    }

    return \%stat;
}

sub csv_sysvipc_count {
    my $fh = shift;
    my $keys = shift;

    return {} unless defined $fh and length $keys;

    chomp $keys;
    my @keys = split ',', $keys;
    return {} unless @keys;

    my $count = 0;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        my @values = split ',';
        next unless @keys == @values;
        ++$count;
    }

    return {
        count => $count,
    };
}

sub SHM_LOCKED() { 02000 }

sub csv_sysvipc_shm {
    my $fh = shift;

    return {} unless defined $fh;

    my $keys = <$fh>;
    chomp $keys;
    return {} unless length $keys;

    my @keys = split ',', $keys;
    return {} unless @keys;

    my $count = 0;
    my $size_locked = 0;
    my $size_unlocked = 0;
    my @nattch;
    my %cpid_to_size;

    my $idx_nattch = firstidx { $_ eq 'nattch' } @keys;
    my $idx_cpid   = firstidx { $_ eq 'cpid'   } @keys;
    my $idx_size   = firstidx { $_ eq 'size'   } @keys;
    my $idx_perms  = firstidx { $_ eq 'perms'  } @keys;

    while (<$fh>) {
        chomp;
        last if $_ eq '';
        my @values = split ',';
        next unless @keys == @values;
        ++$count;

        $nattch[min($values[$idx_nattch], 3)]++
            if exists $values[$idx_nattch];

        $cpid_to_size{$values[$idx_cpid]} += $values[$idx_size]
            if exists $values[$idx_size];

        if (exists $values[$idx_perms]) {
            $size_locked   += $values[$idx_size]     if oct($values[$idx_perms]) & SHM_LOCKED;
            $size_unlocked += $values[$idx_size] unless oct($values[$idx_perms]) & SHM_LOCKED;
        }
    }

    return {
        count         => $count,
        size_locked   => $size_locked,
        size_unlocked => $size_unlocked,
        nattch0       => $nattch[0],
        nattch1       => $nattch[1],
        nattch2       => $nattch[2],
        nattch3       => $nattch[3],
        cpid_to_size  => \%cpid_to_size,
    };
}

sub csv_sysvipc_msg {
    my $fh = shift;
    return csv_sysvipc_count($fh, scalar <$fh>);
}

sub csv_sysvipc_sem {
    my $fh = shift;
    return csv_sysvipc_count($fh, scalar <$fh>);
}

sub csv_file_nr {
    my $fh = shift;

    return {} unless defined $fh;

    my $line = <$fh>;
    chomp $line;

    my @keys = qw/allocated_fds free_fds max_fds/;
    my @values = split ',', $line;

    return {} unless @values == @keys;
    return { zip @keys, @values };
}

sub csv_pid_fd {
    my $fh = shift;

    return {}, {} unless defined $fh;

    my %cmdline;
    my %fdcount;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        next unless /^(\d+),(\d+),(.*)/;

        my $pid     = int $1;
        my $fdcount = int $2;
        my $cmdline = $3;

        $fdcount{$pid} = $fdcount if $fdcount > 0;

        if (length $cmdline) {
            if ($cmdline =~ /^(\S+)\s/) { $cmdline = $1; }
            $cmdline = basename $cmdline;
            #$cmdline = substr $cmdline, 0, 30;
            $cmdline{$pid} = $cmdline;
        }
    }

    return \%cmdline, \%fdcount;
}

sub csv_proc_pid_io {
    my $fh = shift;
    my $keys = shift;

    $keys =~ s/:$//;
    my @keys = split ',', $keys;

    my %stat;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        my @values = split ',';
        next unless @keys == @values;
        foreach (0 .. @values-1) {
            $values[$_] = undef unless length $values[$_];
        }
        my %keyval = zip @keys, @values;

        # Packing "doubles" here due to limited availability of quads.
        $stat{$keyval{PID}} = pack "d*", (
            $keyval{rchar},
            $keyval{wchar},
            $keyval{syscr},
            $keyval{syscw},
            $keyval{read_bytes},
            $keyval{write_bytes},
            $keyval{cancelled_write_bytes},
        );
    }

    return \%stat;
}

sub csv_df {
    my $fh = shift;

    my @keys = qw/filesystem blocks_kb used_kb available_kb
        capacity mounted_on/;

    my %df;
    while (<$fh>) {
        chomp;
        last if $_ eq '';

        my @entry;
        @entry = split ',', $_, scalar @keys;
        @entry = split '\s+', $_, scalar @keys if @entry != @keys;
        next unless @entry == @keys;

        my %entry = zip @keys, @entry;
        my $mounted_on = $entry{mounted_on};
        next unless $mounted_on;

        $entry{capacity} =~ s/%$//;

        $df{$mounted_on} = {
            filesystem => $entry{filesystem},
            capacity   => $entry{capacity},
        };
    }

    return \%df;
}

sub csv_xmeminfo {
    my $fh = shift;
    my $keys = shift;

    return [] unless defined $fh;

    chomp $keys;
    my @keys = split ',', $keys;
    return [] unless @keys;

    foreach (0 .. @keys-1) {
        $keys[$_] =~ s/-/_/g;
        $keys[$_] =~ s/\s/_/g;
    }

    my @xmeminfo;
    while (<$fh>) {
        chomp;
        last if $_ eq '';
        my @values = split ',', $_, scalar @keys;
        next unless @keys == @values;
        @values = map { s/B$// ; $_ } @values;
        my %entry = zip @keys, @values;
        #$entry->{res_base} = '0x' . $entry->{res_base} if $entry->{res_base};
        push @xmeminfo, {
            PID                     => int($entry{PID}),
            total_resource_count    => int($entry{total_resource_count}),
            Pixmap_mem              => int($entry{Pixmap_mem}),
            Identifier              => $entry{Identifier},
        };
    }

    return \@xmeminfo;
}

sub csv_uptime {
    my $fh = shift;
    my $line = <$fh>;
    chomp $line;
    my @entry = split ',', $line, 2;
    return {} unless @entry == 2;
    return { uptime => $entry[0], idletime => $entry[1] };
}

sub parse_usage_csv {
    my $fh = shift;

    return {} unless defined $fh;

    my %csv;

    while (<$fh>) {
        chomp;

        if (/^generator = (\S.*)/)         { $csv{generator}  = $1 }
        elsif (/^SW-version = (\S.*)/)     { $csv{sw_version} = $1 }
        elsif (/^date = (\S.*)/)           { $csv{date} = $1 }
        elsif (/^Uptime,Idletime/)         { $csv{'/proc/uptime'} = csv_uptime($fh, $_) }
        elsif (/^Loadavg /)                { $csv{'/proc/loadavg'} = csv_loadavg($fh, $_) }
        elsif (/^Allocated FDs,/)          { $csv{'/proc/sys/fs/file-nr'} = csv_file_nr($fh, $_) }
        elsif (/^Message queues:/)         { $csv{'/proc/sysvipc/msg'} = csv_sysvipc_msg($fh, $_) }
        elsif (/^Semaphore arrays:/)       { $csv{'/proc/sysvipc/sem'} = csv_sysvipc_sem($fh, $_) }
        elsif (/^Shared memory segments:/) { $csv{'/proc/sysvipc/shm'} = csv_sysvipc_shm($fh, $_) }
        elsif (/^MemTotal/)                { $csv{'/proc/meminfo'} = csv_proc_meminfo($fh, $_) }
        elsif (/^Process status:/)         { $csv{'/proc/pid/stat'} = csv_proc_pid_stat($fh, $_) }
        elsif (/^Name,State,/)             { $csv{'/proc/pid/status'} = csv_proc_pid_status($fh, $_) }
        elsif (/^PID,wchan:/)              { $csv{'/proc/pid/wchan'} = csv_wchan($fh, $_) }
        elsif (/^PID,rchar,/)              { $csv{'/proc/pid/io'} = csv_proc_pid_io($fh, $_) }
        elsif (/^PID,FD count,Command/)    { ($csv{'/proc/pid/cmdline'},
                                             $csv{'/proc/pid/fd_count'}) = csv_pid_fd($fh, $_) }
        elsif (/^res-base,/)               { $csv{'/usr/bin/xmeminfo'} = csv_xmeminfo($fh, $_) }
        elsif (/^Filesystem,/)             { $csv{'/bin/df'} = csv_df($fh, $_) }

        # Unused for now:
        #elsif (/^nr_free_pages/)           { $csv{'/proc/vmstat'} = csv_keyval($fh, $_) }
    }

    return \%csv;
}

sub parse_df {
    my $fh = shift;
    return csv_df($fh, scalar <$fh>);
}

sub parse_xmeminfo {
    my $fh = shift;
    return csv_xmeminfo($fh, scalar <$fh>);
}

sub parse_ifconfig {
    my $fh = shift;

    return {} unless defined $fh;

    my %ifconfig;
    my $iface;
    while (<$fh>) {
        if (/^(\S+)\s+/) {
            $iface = $1;
        } elsif (/RX packets:(\d+)/) {
            $ifconfig{$iface}->{RX}->{packets} = int $1 if defined $iface;
        } elsif (/TX packets:(\d+)/) {
            $ifconfig{$iface}->{TX}->{packets} = int $1 if defined $iface;
        } elsif (/RX bytes:(\d+) .* TX bytes:(\d+) /) {
            $ifconfig{$iface}->{RX}->{bytes} = int $1 if defined $iface;
            $ifconfig{$iface}->{TX}->{bytes} = int $2 if defined $iface;
        }
    }

    #print Dumper \%ifconfig;
    return \%ifconfig;
}

sub parse_upstart_jobs_respawned {
    my $fh = shift;

    return {} unless defined $fh;

    my %jobs;
    while (<$fh>) {
        chomp;
        next unless /^(\S+):\s*(\d+)$/;
        $jobs{$1} = int $2;
    }

    #print Dumper \%jobs;
    return \%jobs;
}

our %schedmap = (
    'se.statistics.block_max'  => 0,
    'se.statistics.wait_max'   => 1,
    'se.statistics.iowait_sum' => 2,
    'se.statistics.nr_wakeups' => 3,
);

sub parse_sched {
    my $fh = shift;

    return {} unless defined $fh;

    my %sched;
    my $pid;

    while (<$fh>) {
        if (/^\S+ \((\d+), #threads:/) {
            $pid = $1;
        } elsif (defined $pid and /^(se\.statistics\.(?:block_max|iowait_sum|wait_max|nr_wakeups))\s*:\s*(\d.*)$/) {
            $sched{$pid}->{$1} = $2;
        }
    }

    my %ret;
    foreach my $pid (keys %sched) {
        $ret{$pid} = pack('d*',
            $sched{$pid}->{'se.statistics.block_max'}  // 0,
            $sched{$pid}->{'se.statistics.wait_max'}   // 0,
            $sched{$pid}->{'se.statistics.iowait_sum'} // 0,
            $sched{$pid}->{'se.statistics.nr_wakeups'} // 0,
        );
    }

    return \%ret;
}

sub parse_pidfilter {
    my $entry = shift;

    return $entry unless ref $entry eq 'HASH';

    my @filter_pids;

    if (exists $entry->{'/proc/pid/cmdline'}) {
        foreach my $pid (keys %{$entry->{'/proc/pid/cmdline'}}) {
            my $cmdline = $entry->{'/proc/pid/cmdline'}->{$pid};
            if (any { $_ eq $cmdline } @process_blacklist) {
                push @filter_pids, $pid;
            }
        }
    }

    if (exists $entry->{'/proc/pid/smaps'}) {
        foreach my $pid (keys %{$entry->{'/proc/pid/smaps'}}) {
            my $name = $entry->{'/proc/pid/smaps'}->{$pid}->{'#Name'};
            if (any { $_ eq $name } @process_blacklist) {
                push @filter_pids, $pid;
            }
        }
    }

    if (exists $entry->{'/proc/pid/status'}) {
        foreach my $pid (keys %{$entry->{'/proc/pid/status'}}) {
            my %data = split ',', $entry->{'/proc/pid/status'}->{$pid};
            if (any { $_ eq $data{Name} } @process_blacklist) {
                push @filter_pids, $pid;
            }
        }
    }

    #print Dumper \@filter_pids;
    foreach my $pid (uniq @filter_pids) {
        delete $entry->{'/proc/pid/cmdline'}->{$pid}  if exists $entry->{'/proc/pid/cmdline'};
        delete $entry->{'/proc/pid/fd_count'}->{$pid} if exists $entry->{'/proc/pid/fd_count'};
        delete $entry->{'/proc/pid/io'}->{$pid}       if exists $entry->{'/proc/pid/io'};
        delete $entry->{'/proc/pid/smaps'}->{$pid}    if exists $entry->{'/proc/pid/smaps'};
        delete $entry->{'/proc/pid/stat'}->{$pid}     if exists $entry->{'/proc/pid/stat'};
        delete $entry->{'/proc/pid/status'}->{$pid}   if exists $entry->{'/proc/pid/status'};
        delete $entry->{'/proc/pid/wchan'}->{$pid}    if exists $entry->{'/proc/pid/wchan'};
    }

    return $entry;
}

sub snapshot_separator {
    my $entry = shift;

    if ($entry->{"SYSLOG_IDENTIFIER"} eq "endurance-snapshot" &&
        $entry->{"MESSAGE"} =~ /End of snapshot (?<case_name>[^\/]*)\/\d\d\d/) {
        return $+{case_name};
    }

    return undef;
}

sub parse_display_state {
    my $fh = shift;

    return { "on_percent" => undef } unless defined $fh;

    my $string = do { local $/; <$fh> };

    # Journal messages can contain tab characters which aren't allowed in JSON.
    # Get rid of them before trying to decode the string.
    $string =~ s/\t/ /g;

    my $json = undef;

    if ($string =~ /^\[/) {
        # Older journalctl json format - a single array.
        $json = eval { decode_json($string) };
    } else {
        # Newer format - one JSON object per line.
        my @array = ();
        foreach my $line (split(/\n/, $string)) {
            my $object = eval { decode_json($line) };
            if (defined $object) {
                push(@array, $object);
            }
        }
        $json = \@array unless @array == 0;
    }

    return { "on_percent" => undef } unless defined $json;

    my $i = @$json;
    my %state_changes;
    my $case_name;

    while ($i != 0 && !($case_name = snapshot_separator($json->[--$i]))) {}

    $state_changes{$json->[$i--]->{"__REALTIME_TIMESTAMP"}} = "end";

    # Now we're standing at the last log entry within the snapshot.

    while (($i != -1) && (snapshot_separator($json->[$i]) ne $case_name)) {
        my $entry = $json->[$i--];
        if ($entry->{"_COMM"} ne "lipstick") {
            next;
        }

        if ($entry->{"MESSAGE"} =~ m/unsleepDisplay/) {
            $state_changes{$entry->{"__REALTIME_TIMESTAMP"}} = "unsleep";
        } elsif ($entry->{"MESSAGE"} =~ m/sleepDisplay/) {
            $state_changes{$entry->{"__REALTIME_TIMESTAMP"}} = "sleep";
        }
    }

    $state_changes{$json->[$i == -1 ? 0 : $i]->{"__REALTIME_TIMESTAMP"}} = "begin";

    my %result = ( "on_percent" => 0, "exit_state" => undef );
 
    if (keys(%state_changes) <= 2) {
        # No change during this snapshot.
        return \%result;
    }

    my @timestamps = sort keys %state_changes;
    for my $i (1..(@timestamps - 2)) {
        my $timestamp = $timestamps[$i];

        if ($state_changes{$timestamp} eq "sleep") {
            $result{"on_percent"} += $timestamp - $timestamps[$i - 1];
        }
    }

    $result{"exit_state"} = $state_changes{$timestamps[@timestamps - 2]};
    if ($result{"exit_state"} eq "unsleep") {
        $result{"on_percent"} += $timestamps[@timestamps - 1] - $timestamps[@timestamps - 2];
    }

    $result{"on_percent"} /= ($timestamps[@timestamps - 1] - $timestamps[0]) / 100.0;

    return \%result;
}

sub parse_statefs {
    my $fh = shift;

    my %result;

    while (<$fh>) {
        if (/^(?<path>[^=]+)=(?<value>.+)$/) {
            $result{$+{path}} = $+{value};
        }
    }

    return \%result;
}

sub parse_dir {
    my $name = shift;

    return {} unless defined $name;

    my $result = {
        dirname                    => $name,
        cgroups                    => parse_cgroups(copen $name . '/cgroups'),
        component_version          => parse_component_version(copen $name . '/component_version'),
        ramzswap                   => parse_ramzswap(copen $name . '/ramzswap'),
        step                       => parse_step(copen $name . '/step.txt'),
        upstart_jobs_respawned     => parse_upstart_jobs_respawned(copen $name . '/upstart_jobs_respawned'),
        suspend_stats              => parse_suspend_stats(copen $name . '/suspend-stats'),
        '/bin/df'                  => parse_df(copen $name . '/df'),
        '/proc/diskstats'          => parse_diskstats(copen $name . '/diskstats'),
        '/proc/interrupts'         => parse_interrupts(copen $name . '/interrupts'),
        '/proc/pagetypeinfo'       => parse_pagetypeinfo(copen $name . '/pagetypeinfo'),
        '/proc/pid/fd'             => parse_openfds(copen $name . '/open-fds'),
        '/proc/pid/sched'          => parse_sched(copen $name . '/sched'),
        '/proc/pid/smaps'          => parse_smaps(copen $name . '/smaps.cap'),
        '/proc/slabinfo'           => parse_slabinfo(copen $name . '/slabinfo'),
        '/proc/stat'               => parse_proc_stat(copen $name . '/stat'),
        '/sbin/ifconfig'           => parse_ifconfig(copen $name . '/ifconfig'),
        '/sys/class/backlight'     => parse_sysfs_backlight(copen $name . '/sysfs_backlight'),
        '/sys/class/power_supply'  => parse_sysfs_power_supply(copen $name . '/sysfs_power_supply'),
        '/sys/devices/system/cpu'  => parse_sysfs_cpu(copen $name . '/sysfs_cpu'),
        '/sys/fs/ext4'             => parse_sysfs_fs(copen $name . '/sysfs_fs'),
        '/usr/bin/bmestat'         => parse_bmestat(copen $name . '/bmestat'),
        '/usr/bin/xmeminfo'        => parse_xmeminfo(copen $name . '/xmeminfo'),
        display_state              => parse_display_state(copen $name . '/journal'),
        statefs                    => parse_statefs(copen $name . '/statefs'),
        '/sys/devices/virtual/kgsl/kgsl/proc'	=> parse_sysfs_kgsl(copen $name . '/sysfs_kgsl')
    };

    # The CSV parsing creates a bunch of hashes, so let's add them straight to
    # the resulting hash to remove one level of indirection.
    my $csv = parse_usage_csv(copen $name . '/usage.csv');
    foreach (keys %$csv) {
        $result->{$_} = $csv->{$_};
    }

    return parse_pidfilter $result;
}

1;

__DATA__

__C__

static void sv_iv_inc(SV *sv, IV inc) {
    if (!sv)
        return;
    IV val = SvIV(sv);
    val += inc;
    sv_setiv(sv, val);
}

HV *parse_smaps_inline(PerlIO *fh, AV *wanted_mmaps) {
    HV *ret = newHV();
    if (!ret || !fh)
        return ret;

    int wanted_mmaps_count = av_len(wanted_mmaps);

    SV *line_sv = NEWSV(0, 0);
    if (!line_sv)
        goto out;

    char *name = NULL;
    HV *pid_hv = NULL;
    SV *vmacount = NULL;
    HV *wanted_mmap = NULL;

    while (1) {
        char *line = NULL;
        STRLEN line_len = 0;

        if (sv_gets(line_sv, fh, 0) == NULL) {
            goto out;
        }

        line = SvPV(line_sv, line_len);

        if (line_len > 0 && line[line_len-1] == '\n') {
            line[line_len-1] = '\0';
            --line_len;
        }

        if (line_len == 0)
            continue;

        //fprintf(stderr, " >> '%s'\n", line);

        if (line[0] == '#') {
            if (strncmp(&line[1], "Name: ", 6) == 0) {
                name = strdup(&line[7]);
            } else if (strncmp(&line[1], "Pid: ", 5) == 0) {
                vmacount = NULL;
                wanted_mmap = NULL;

                pid_hv = newHV();
                if (!pid_hv)
                    goto out;
                hv_store(ret,
                    &line[6], line_len - 6,
                    newRV_noinc((SV*) pid_hv), 0);
                if (name) {
                    hv_store(pid_hv,
                        "#Name", 5,
                        newSVpv(name, strlen(name)), 0);
                    free(name);
                    name = NULL;
                }
            }
            /* Additional metadata not needed for now.
            else {
                if (!pid_hv)
                    continue;

                char *colon = index(line, ':');
                if (!colon || colon[1] == '\0')
                    continue;
                *colon = '\0';

                char *key = &line[1];
                size_t key_len = (colon - line) - 1;
                if (key_len == 0)
                    continue;

                char *value = &colon[2];
                hv_store(pid_hv,
                    key, key_len,
                    newSVpv(value, strlen(value)), 0);
            }
            */
        } else if (isupper(line[0])) {
            if (!pid_hv)
                continue;

            char *colon = index(line, ':');
            if (!colon || colon[1] == '\0')
                continue;

            *colon = '\0';
            char *key = line;
            size_t key_len = colon - line;

            static const struct {
                const char *key;
                const char *store_key;
                size_t store_key_len;
            } keys[] = {
                { "Private_Dirty", "total_Private_Dirty", sizeof("total_Private_Dirty")-1 },
                { "Pss",           "total_Pss",           sizeof("total_Pss")-1           },
                { "Size",          "total_Size",          sizeof("total_Size")-1          },
                { "Swap",          "total_Swap",          sizeof("total_Swap")-1          },
            };

            size_t i;
            for (i=0; i < sizeof(keys) / sizeof(keys[0]); ++i) {
                int value;

                if (strcmp(key, keys[i].key))
                    continue;

                if (sscanf(&colon[2], "%d kB", &value) != 1 || value <= 0)
                    break;

                SV **total_sv = hv_fetch(pid_hv,
                    keys[i].store_key, keys[i].store_key_len, 0);

                if (total_sv && *total_sv) {
                    sv_iv_inc(*total_sv, value);
                } else {
                    SV *total = newSViv(value);
                    if (!total)
                        goto out;
                    hv_store(pid_hv,
                        keys[i].store_key, keys[i].store_key_len,
                        total, 0);
                }

                if (wanted_mmap) {
                    total_sv = hv_fetch(wanted_mmap,
                        keys[i].store_key, keys[i].store_key_len, 0);

                    if (total_sv && *total_sv) {
                        sv_iv_inc(*total_sv, value);
                    } else {
                        SV *total = newSViv(value);
                        if (!total)
                            goto out;
                        hv_store(wanted_mmap,
                            keys[i].store_key, keys[i].store_key_len,
                            total, 0);
                    }
                }

                break;
            }

        } else if (isdigit(line[0]) || islower(line[0])) {
            size_t i;

            if (!pid_hv)
                continue;

            if (!vmacount) {
                vmacount = newSViv(0);
                if (!vmacount)
                    goto out;
                hv_store(pid_hv, "vmacount", strlen("vmacount"), vmacount, 0);
            }
            sv_iv_inc(vmacount, 1);

            wanted_mmap = NULL;

            for (i=0; i <= wanted_mmaps_count; ++i) {
                SV **mmap = av_fetch(wanted_mmaps, i, 0);
                if (!mmap)
                    continue;

                char *mmap_str = SvPV_nolen(*mmap);
                if (!mmap_str)
                    continue;

                if (strstr(line, mmap_str) == NULL)
                    continue;

                SV **w = hv_fetch(pid_hv, mmap_str, strlen(mmap_str), 0);
                if (w && *w) {
                    wanted_mmap = (HV *)SvRV(*w);
                    if (!wanted_mmap)
                        goto out;
                } else {
                    wanted_mmap = newHV();
                    if (!wanted_mmap)
                        goto out;
                    hv_store(pid_hv,
                        mmap_str, strlen(mmap_str),
                        newRV_noinc((SV*) wanted_mmap), 0);
                }

                SV **cnt = hv_fetch(wanted_mmap, "vmacount", strlen("vmacount"), 0);
                if (cnt && *cnt) {
                    sv_iv_inc(*cnt, 1);
                } else {
                    SV *c = newSViv(1);
                    if (c == NULL)
                        goto out;
                    hv_store(wanted_mmap, "vmacount", strlen("vmacount"), c, 0);
                }

                break;
            }
        }
    }

out:
    if (line_sv)
        sv_free(line_sv);
    return ret;
}
