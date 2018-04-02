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

package SP::Endurance::GraphGenerators;

require Exporter;
@ISA = qw/Exporter/;
@EXPORT_OK = qw/graph_generators get_plots/;

use SP::Endurance::Parser;
use SP::Endurance::Util qw/b2mb kb2mb nonzero has_changes max_change
    cumulative_to_changes change_per_second/;

use List::Util qw/max sum/;
use List::MoreUtils qw/uniq zip any/;
use POSIX qw/ceil/;
use Data::Dumper;

no warnings 'uninitialized';
eval 'use common::sense';
use strict;

sub CGROUP_UNLIMITED()     { 9223372036854775807 }
sub CLK_TCK()              { 100 }
sub PAGE_SIZE()            { 4096 }
sub SECTOR_SIZE()          { 512 }
sub SHM_LOCKED()           { 02000 }

my @plots;
my @generators;

sub graph_generators { @generators }
sub get_plots        { sort { $a->{key} cmp $b->{key} } @plots }

sub register_generator {
    my $g = shift;
    return unless ref $g eq 'CODE';
    push @generators, $g;
}

our $done_plotting_cb;

sub done_plotting {
    my $plot = shift;
    foreach ($plot->done_plotting) {
        push @plots, $_;
        $done_plotting_cb->($_) if ref $done_plotting_cb eq 'CODE';
    }
}

my %pid_to_cmdline;

sub pid_to_cmdline {
    my $masterdb = shift;
    my $pid = shift;

    return unless $pid;

    unless (defined $pid_to_cmdline{$pid}) {
        my @cmdlines = uniq grep { defined && length } map {
            if (exists $_->{'/proc/pid/cmdline'} and exists $_->{'/proc/pid/cmdline'}->{$pid}) {
                $_->{'/proc/pid/cmdline'}->{$pid}
            } elsif (exists $_->{'/proc/pid/smaps'}->{$pid} and exists $_->{'/proc/pid/smaps'}->{$pid}->{'#Name'}) {
                $_->{'/proc/pid/smaps'}->{$pid}->{'#Name'}
            } else {
                undef
            }
        } @$masterdb;

        $pid_to_cmdline{$pid} = join(' / ', @cmdlines);
    }

    join(': ', $pid, $pid_to_cmdline{$pid})
}

sub sum_smaps {
    my $masterdb = shift;
    my $smaps_key = shift;

    return map {
        my $entry = $_;
        if (exists $entry->{'/proc/pid/smaps'}) {
            sum map {
                my $pid = $_;
                exists $entry->{'/proc/pid/smaps'}->{$pid} &&
                exists $entry->{'/proc/pid/smaps'}->{$pid}->{"total_${smaps_key}"} ?
                       $entry->{'/proc/pid/smaps'}->{$pid}->{"total_${smaps_key}"} : undef
            } keys %{$entry->{'/proc/pid/smaps'}}
        } else { undef }
    } @$masterdb;
}

sub generate_plot_system_memory_1 {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2200_system_memory_1',
        label => 'System-level memory 1',
        legend => 'SYSTEM MEMORY 1',
        ylabel => 'MB',
    );

    $plot->push(
        [kb2mb nonzero map { $_->{'/proc/meminfo'}->{SwapTotal} -
            $_->{'/proc/meminfo'}->{SwapFree} } @$masterdb],
        lw => 5, lc => 'FF0000', title => 'Swap used',
    );
    $plot->push(
        [kb2mb nonzero sum_smaps($masterdb, 'Swap')],
        lc => 'FF0000', title => 'Sum of swapped in applications',
    );
    foreach my $key (qw/SwapCached MemFree MemAvailable AnonPages Cached
                    Active(file) Inactive(file) Active(anon) Inactive(anon)
                    Shmem/) {
        $plot->push(
            [kb2mb nonzero map { $_->{'/proc/meminfo'}->{$key} } @$masterdb],
            title => $key,
        );
    }
    $plot->push(
        [kb2mb nonzero sum_smaps($masterdb, 'Pss')],
        title => 'Sum of PSS',
    );

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_system_memory_1; }

sub generate_plot_system_memory_2 {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2200_system_memory_2',
        label => 'System-level memory 2',
        legend => 'SYSTEM MEMORY 2',
        ylabel => 'MB',
    );

    foreach my $key (qw/Dirty Buffers Mlocked PageTables KernelStack
                SReclaimable SUnreclaim/) {
        $plot->push(
            [kb2mb nonzero map { $_->{'/proc/meminfo'}->{$key} } @$masterdb],
            title => {
                SReclaimable => 'SlabReclaimable',
                SUnreclaim   => 'SlabUnreclaimable',
            }->{$key} // $key,
        );
    }

    $plot->push(
        [b2mb nonzero map {
            my $sum;
            if (exists $_->{'/usr/bin/xmeminfo'}) {
                foreach my $xmem_entry (@{$_->{'/usr/bin/xmeminfo'}}) {
                    $sum += $xmem_entry->{Pixmap_mem}
                }
            }
            $sum;
        } @$masterdb],
        title => 'Pixmaps',
    );

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_system_memory_2; }

sub generate_plot_slab_sizes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2255_slabs',
        label => 'Kernel slab memory',
        legend => 'KERNEL SLABS',
        ylabel => 'MB',
    );

    my @slabs = uniq sort map { keys %{$_->{'/proc/slabinfo'}} } @$masterdb;

    foreach my $slab (@slabs) {
        $plot->push(
            [nonzero kb2mb map { $_->{'/proc/slabinfo'}->{$slab} } @$masterdb],
            title => $slab,
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_slab_sizes; }

sub generate_plot_slab_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2256_slabs_changes',
        label => 'Kernel slab memory (changed only)',
        legend => 'KERNEL SLABS CHANGES',
        ylabel => 'MB',
    );

    my @slabs = uniq sort map { keys %{$_->{'/proc/slabinfo'}} } @$masterdb;

    foreach my $slab (@slabs) {
        $plot->push(
            [has_changes kb2mb nonzero map { $_->{'/proc/slabinfo'}->{$slab} } @$masterdb],
            title => $slab,
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_slab_changes; }

sub generate_plot_kgsl {
    my $plotter = shift;
    my $masterdb = shift;

    my @memories = ("ashmem", "ion", "kernel", "user", "pmem", "inside");

    foreach my $mem (@memories) {
        my @kgsl_data = uniq map { keys %{$_->{'/sys/devices/virtual/kgsl/kgsl/proc'}} } @$masterdb;

        foreach my $gpu_mem (@kgsl_data) {
            next if ($gpu_mem ne $mem);

            my $mem_uc = uc $mem; 
            my $plot = $plotter->new_linespoints(
                key => "1015_kgsl_$mem",
                label => "GPU memory $mem",
                legend => "GPU MEM $mem_uc",
                ylabel => 'MB',
            );

            my @kernel_pids = uniq map { keys %{$_->{'/sys/devices/virtual/kgsl/kgsl/proc'}->{$mem}} } @$masterdb;
            my @all_kernel_pids = map { keys %{$_->{'/sys/devices/virtual/kgsl/kgsl/proc'}->{$mem}} } @$masterdb;
            my @pids_values = map { values %{$_->{'/sys/devices/virtual/kgsl/kgsl/proc'}->{$mem}} } @$masterdb;

            foreach my $pid (@kernel_pids) {
                # skip snapshot separator
                next if ($pid eq "#####");
                my @pid_values = ();
                my $snapshot_count = 1;

                for (my $i = 0; $i < scalar @pids_values; ++$i) {
                    # check snapshot separator
                    if ($all_kernel_pids[$i] eq "#####") {
                        # add zero if we do not have value
                        if ( scalar @pid_values < $snapshot_count) {
                            push (@pid_values, int 0);
                        }
                        $snapshot_count++;
                    }

                    next if ($all_kernel_pids[$i] ne $pid);
                    push (@pid_values, $pids_values[$i]);
                }

                $plot->push(
                    [nonzero b2mb @pid_values],
                    title => pid_to_cmdline($masterdb, $pid));
            }

            $plot->sort(sub { shift->[-1] });

            done_plotting $plot;
        }
    }
}
BEGIN { register_generator \&generate_plot_kgsl; }

sub generate_plot_ctx_total {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1165_ctx_total',
        label => 'Voluntary + non-voluntary context switches per second per process',
        legend => 'CTX TOTAL',
        ylabel => 'count per second',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @total_ctx = map {
            if (exists $_->{'/proc/pid/status'}->{$pid}) {
                my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                exists $entry{voluntary_ctxt_switches} &&
                exists $entry{nonvoluntary_ctxt_switches} ?
                       $entry{voluntary_ctxt_switches} + $entry{nonvoluntary_ctxt_switches} :
                       undef
            } else { undef }
        } @$masterdb;
        $plot->push(
            [nonzero change_per_second $masterdb, cumulative_to_changes @total_ctx],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_ctx_total; }

sub generate_plot_ctx_nonvol {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1166_ctx_nonvolunt',
        label => 'Non-voluntary context switches per second per process',
        legend => 'CTX NON-VOLUNTARY',
        ylabel => 'count per second',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @ctx = map {
            if (exists $_->{'/proc/pid/status'}->{$pid}) {
                my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                exists $entry{nonvoluntary_ctxt_switches} ?
                       $entry{nonvoluntary_ctxt_switches} : undef
            } else { undef }
        } @$masterdb;
        $plot->push(
            [nonzero change_per_second $masterdb, cumulative_to_changes @ctx],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_ctx_nonvol; }

sub generate_plot_ctx_vol {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1166_ctx_volunt',
        label => 'Voluntary context switches per second per process',
        legend => 'CTX VOLUNTARY',
        ylabel => 'count per second',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @ctx = map {
            if (exists $_->{'/proc/pid/status'}->{$pid}) {
                my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                exists $entry{nonvoluntary_ctxt_switches} ?
                       $entry{nonvoluntary_ctxt_switches} : undef
            } else { undef }
        } @$masterdb;
        $plot->push(
            [nonzero change_per_second $masterdb, cumulative_to_changes @ctx],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_ctx_vol; }

sub generate_plot_ctx_global {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2060_ctx_global',
        label => 'left: total number of context switches\nright: number of processes in system',
        legend => 'CTX-SW,PROC-NUM',
        ylabel => 'context switches per second',
        y2label => 'number of processes',
    );

    $plot->push(
        [nonzero change_per_second $masterdb, cumulative_to_changes map {
            exists $_->{'/proc/stat'} &&
            exists $_->{'/proc/stat'}->{ctxt} ?
                   $_->{'/proc/stat'}->{ctxt} : undef
        } @$masterdb],
        axes => 'x1y1', title => 'Context switches',
    );

    $plot->push(
        [nonzero map {
            exists $_->{'/proc/loadavg'} &&
            exists $_->{'/proc/loadavg'}->{all} ?
                   $_->{'/proc/loadavg'}->{all} : undef
        } @$masterdb],
        axes => 'x2y2', title => 'Process and thread count',
    );

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_ctx_global; }

sub generate_plot_loadavg {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2005_loadavg',
        label => 'Load average',
        legend => 'LOAD AVERAGE',
        ylabel => 'load average',
    );

    foreach my $avg (qw/min1 min5 min15/) {
        $plot->push(
            [map { $_->{'/proc/loadavg'}->{$avg} } @{$masterdb}],
            title => {
                min1 => '1 minute average',
                min5 => '5 minute average',
                min15 => '15 minute average',
            }->{$avg},
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_loadavg; }

sub generate_plot_processes_global {
    my $plotter = shift;
    my $masterdb = shift;

    done_plotting $plotter->new_linespoints(
        key => '2050_processes_created',
        label => 'Processes and threads created',
        legend => 'PROC/THREADS CREATED',
        ylabel => 'count',
    )->push(
        [cumulative_to_changes map { $_->{'/proc/stat'}->{processes} } @$masterdb],
        title => 'Processes and threads created');
}
BEGIN { register_generator \&generate_plot_processes_global; }

sub generate_plot_major_pagefaults {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1010_majorfault_%d',
        label => 'Major page faults per second',
        ylabel => 'count per second',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'MAJOR PAGE FAULTS &mdash; MAX ' . ceil(max @{shift()}) },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/stat'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero change_per_second $masterdb, cumulative_to_changes map {
                if (exists $_->{'/proc/pid/stat'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/stat'}->{$pid};
                    exists $entry{majflt} ? $entry{majflt} : undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_major_pagefaults; }

sub generate_plot_minor_pagefaults {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1011_minorfault_%d',
        label => 'Minor page faults per second',
        ylabel => 'count per second',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'MINOR PAGE FAULTS &mdash; MAX ' . ceil(max @{shift()}) },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/stat'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero change_per_second $masterdb, cumulative_to_changes map {
                if (exists $_->{'/proc/pid/stat'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/stat'}->{$pid};
                    exists $entry{minflt} ? $entry{minflt} : undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_minor_pagefaults; }

my @proc_stat_cpu_key_order = qw/idle iowait nice user softirq irq sys steal guest guest_nice/;
my %proc_stat_cpu_key2lc = (
    user    => "3149BD",
    nice    => "4265FF",
    sys     => "DE2821",
    idle    => "ADE739",
    iowait  => "EE00FF",
    irq     => "FF0000",
    softirq => "EF0000",
    steal   => "FFFF00",
    guest   => "FF00B4",
    guest_nice => "00FF4B",
);
sub proc_stat_cpu_hash {
    my $values = shift;
    my @values = @{$values // []};
    my @datakeys  = qw/user nice sys idle iowait irq softirq steal guest guest_nice/;
    my %keyidx = (
        user => 0,
        nice => 1,
        sys => 2,
        idle => 3,
        iowait => 4,
        irq => 5,
        softirq => 6,
        steal => 7,
        guest => 8,
        guest_nice => 9,
    );
    if ($values[$keyidx{guest}] > 0) {
        # deduct 'guest' from 'user', kernel adds it to both for
        # compat reasons.
        $values[$keyidx{user}] = max(0, $values[$keyidx{user}] - $values[$keyidx{guest}]);
    }
    if ($values[$keyidx{guest_nice}] > 0) {
        # deduct 'guest_nice' from 'nice', kernel adds it to both
        # for compat reasons.
        $values[$keyidx{nice}] = max(0, $values[$keyidx{nice}] - $values[$keyidx{guest_nice}]);
    }
    my $h = { zip @datakeys, @values };
    return $h;
}

sub generate_plot_cpu {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2015_cpu',
        label => 'CPU utilization',
        legend => 'CPU UTILIZATION',
        ylabel => 'percent',
    );

    foreach my $key (@proc_stat_cpu_key_order) {
        $plot->push(
            [nonzero cumulative_to_changes map {
                proc_stat_cpu_hash($_->{'/proc/stat'}->{cpu})->{$key}
            } @$masterdb],
            lc => $proc_stat_cpu_key2lc{$key}, title => $key,
        );
    }

    $plot->scale(to => 100);

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_cpu; }

sub generate_plot_per_cpu {
    my $plotter = shift;
    my $masterdb = shift;

    my @cpus = sort { $a <=> $b } map { /^cpu([0-9]+)$/ ; $1 }
        uniq grep { /^cpu[0-9]/ } map { keys %{$_->{'/proc/stat'} // {}} } @$masterdb;
    #print Dumper \@cpus;
    return if @cpus <= 1;

    foreach my $cpu_num (@cpus) {
        my $plot = $plotter->new_histogram(
            key => sprintf('2016_cpu_%04d', $cpu_num),
            label => "cpu$cpu_num utilization",
            legend => "CPU$cpu_num UTILIZATION",
            ylabel => 'percent',
        );
        foreach my $key (@proc_stat_cpu_key_order) {
            $plot->push(
                [nonzero cumulative_to_changes map {
                    proc_stat_cpu_hash($_->{'/proc/stat'}->{"cpu$cpu_num"})->{$key}
                } @$masterdb],
                lc => $proc_stat_cpu_key2lc{$key}, title => $key,
            );
        }
        $plot->scale(to => 100);
        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_per_cpu; }

sub generate_plot_cpu_freq {
    my $plotter = shift;
    my $masterdb = shift;

    my @cpus = uniq map { keys %{$_->{'/sys/devices/system/cpu'} // {}} } @$masterdb;

    foreach my $cpu_num (@cpus) {
        my $plot = $plotter->new_histogram(
            key => "2010_cpu${cpu_num}_time_in_state",
            label => "CPU${cpu_num} time in state",
            legend => "CPU${cpu_num} TIME IN STATE",
            ylabel => 'percent',
        );

        my @freqs = uniq map { keys %{$_->{'/sys/devices/system/cpu'}->{$cpu_num}->{cpufreq}->{stats}->{time_in_state}} } @$masterdb;

        foreach my $freq (sort { $b <=> $a } @freqs) {
            $plot->push(
            [cumulative_to_changes
                map { $_->{'/sys/devices/system/cpu'}->{$cpu_num}->{cpufreq}->{stats}->{time_in_state}->{$freq} } @$masterdb],
            title => int($freq/1000) . 'MHz',
            );
        }

        $plot->scale(to => 100);

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_cpu_freq; }

sub fs_to_mountpoint {
    my $fs = shift;
    my $masterdb = shift;

    my @mountpoints = uniq map { keys %{$_->{'/bin/df'} // {}} } @$masterdb;

    foreach my $mountpoint (@mountpoints) {
        my ($filesystem) = uniq map { $_->{'/bin/df'}->{$mountpoint}->{filesystem} } @$masterdb;
        if ($filesystem =~ /\b\Q$fs\E\b/) {
            return $fs . ': ' . $mountpoint;
        }
    }

    return $fs;
}

sub generate_plot_fs_written {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2102_ext4_written',
        label => 'Bytes written to ext4 partitions (excluding non-changed)',
        legend => 'EXT4 WRITES',
        ylabel => 'MB',
    );

    my @filesystems = uniq map { keys %{$_->{'/sys/fs/ext4'}} } @$masterdb;

    foreach my $fs (@filesystems) {
        $plot->push(
            [kb2mb nonzero has_changes cumulative_to_changes map {
                exists $_->{'/sys/fs/ext4'}->{$fs} ? $_->{'/sys/fs/ext4'}->{$fs}->{lifetime_write_kbytes} : undef
            } @$masterdb],
            title => fs_to_mountpoint($fs, $masterdb),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_fs_written; }

sub generate_plot_cputime {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1150_cpu_user_sys_time_%d',
        label => 'CPU user+sys time',
        ylabel => 'percent',
        multiple => {
            max_plots => 2,
            max_per_plot => 20,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'CPU TIME &mdash; USER+SYS &mdash; MAX ' . ceil(max @{shift()}) . '%' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/stat'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @entry = change_per_second $masterdb, cumulative_to_changes map {
                if (exists $_->{'/proc/pid/stat'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/stat'}->{$pid};
                    exists $entry{utime} && exists $entry{stime} ?
                    $entry{utime} + $entry{stime} : undef
                } else { undef }
            } @$masterdb;

        next unless any { defined && $_ > 0 } @entry;

        if (CLK_TCK != 100) {
            foreach (0 .. @entry-1) {
                $entry[$_] /= CLK_TCK;
                $entry[$_] *= 100;
            }
        }

        $plot->push([nonzero @entry], title => pid_to_cmdline($masterdb, $pid));
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_cputime; }

sub generate_plot_cputime_user {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1160_cpu_usertime_%d',
        label => 'CPU user time',
        ylabel => 'percent',
        multiple => {
            max_plots => 2,
            max_per_plot => 20,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'CPU TIME &mdash; USER &mdash; MAX ' . ceil(max @{shift()}) . '%' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/stat'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @entry = change_per_second $masterdb, cumulative_to_changes map {
                if (exists $_->{'/proc/pid/stat'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/stat'}->{$pid};
                    exists $entry{utime} ? $entry{utime} : undef
                } else { undef }
            } @$masterdb;

        next unless any { defined && $_ > 0 } @entry;

        if (CLK_TCK != 100) {
            foreach (0 .. @entry-1) {
                $entry[$_] /= CLK_TCK;
                $entry[$_] *= 100;
            }
        }

        $plot->push([nonzero @entry], title => pid_to_cmdline($masterdb, $pid));
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_cputime_user; }

sub generate_plot_cputime_sys {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1162_cpu_systime_%d',
        label => 'CPU sys time',
        ylabel => 'percent',
        multiple => {
            max_plots => 2,
            max_per_plot => 20,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'CPU TIME &mdash; SYS &mdash; MAX ' . ceil(max @{shift()}) . '%' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/stat'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @entry = change_per_second $masterdb, cumulative_to_changes map {
            if (exists $_->{'/proc/pid/stat'}->{$pid}) {
                my %entry = split ',', $_->{'/proc/pid/stat'}->{$pid};
                exists $entry{stime} ? $entry{stime} : undef
            } else { undef }
        } @$masterdb;

        next unless any { defined && $_ > 0 } @entry;

        if (CLK_TCK != 100) {
            foreach (0 .. @entry-1) {
                $entry[$_] /= CLK_TCK;
                $entry[$_] *= 100;
            }
        }

        $plot->push([nonzero @entry], title => pid_to_cmdline($masterdb, $pid));
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_cputime_sys; }

sub sysvipc {
    my $masterdb = shift;
    my $type = shift;
    my $key = shift;
    map {
        exists $_->{"/proc/sysvipc/$type"} &&
        exists $_->{"/proc/sysvipc/$type"}->{$key} ?
               $_->{"/proc/sysvipc/$type"}->{$key} : undef
    } @$masterdb;
}

sub generate_plot_sysvipc_count {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2241_sysvipc_count',
        label => 'SysV IPC object counts:\n-Shared memory segments (SHM)\n-Message queues (MSG)\n-Semaphore sets (SEM)',
        legend => 'SYSV SHM+MSG+SEM COUNT',
        ylabel => 'count',
    );

    my @nattch0 = sysvipc $masterdb, 'shm', 'nattch0';
    my @nattch1 = sysvipc $masterdb, 'shm', 'nattch1';
    my @nattch2 = sysvipc $masterdb, 'shm', 'nattch2';
    my @nattch3 = sysvipc $masterdb, 'shm', 'nattch3';
    my @msg     = sysvipc $masterdb, 'msg', 'count';
    my @sem     = sysvipc $masterdb, 'sem', 'count';

    if (nonzero(@nattch0) > 0 or nonzero(@nattch1) > 0 or nonzero(@nattch2) > 0 or
            nonzero(@nattch3) > 0 or nonzero(@msg) > 0 or nonzero(@sem) > 0) {
        $plot->push([nonzero @nattch0], title => 'SHM - 0 processes attached');
        $plot->push([nonzero @nattch1], title => 'SHM - 1 process attached');
        $plot->push([nonzero @nattch2], title => 'SHM - 2 processes attached');
        $plot->push([nonzero @nattch3], title => 'SHM - 3+ processes attached');
        $plot->push([nonzero @msg],     title => 'MSG');
        $plot->push([nonzero @sem],     title => 'SEM');
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sysvipc_count; }

sub generate_plot_sysvipc_locked_size {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2240_sysvipc_locked_unlocked_size',
        label => 'SysV shared memory locked+unlocked Size sum',
        legend => 'SYSV SHM LOCKED+UNLOCKED',
        ylabel => 'MB',
    );

    my @locked   = sysvipc $masterdb, 'shm', 'size_locked';
    my @unlocked = sysvipc $masterdb, 'shm', 'size_unlocked';

    if (nonzero(@locked) > 0 or nonzero(@unlocked) > 0) {
        $plot->push([b2mb @locked],   title => 'Locked to memory');
        $plot->push([b2mb @unlocked], title => 'Unlocked');
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sysvipc_locked_size; }

sub generate_plot_sysvipc_shm_cpid {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1052_sysvipc_shm_cpid',
        label => 'SysV shared memory Size per Creator PID (CPID)',
        legend => 'SYSV SHM SIZE PER CPID',
        ylabel => 'MB',
    );

    my @cpids = uniq grep { defined && length } map {
        exists $_->{'/proc/sysvipc/shm'} &&
        exists $_->{'/proc/sysvipc/shm'}->{cpid_to_size} ?
        keys %{$_->{'/proc/sysvipc/shm'}->{cpid_to_size}} : undef
    } @$masterdb;

    foreach my $cpid (@cpids) {
        $plot->push(
            [nonzero b2mb map {
                exists $_->{'/proc/sysvipc/shm'} &&
                exists $_->{'/proc/sysvipc/shm'}->{cpid_to_size} &&
                exists $_->{'/proc/sysvipc/shm'}->{cpid_to_size}->{$cpid} ?
                       $_->{'/proc/sysvipc/shm'}->{cpid_to_size}->{$cpid} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $cpid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sysvipc_shm_cpid; }

sub generate_plot_mlocked {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1020_locked',
        label => 'VmLck per process',
        legend => 'LOCKED',
        ylabel => 'MB',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero map {
                if (exists $_->{'/proc/pid/status'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                    exists $entry{VmLck} ? $entry{VmLck} : undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_mlocked; }

sub generate_plot_vmsize {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1040_vmsize_%d',
        label => 'Process virtual memory size (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 4,
            max_per_plot => 15,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'VMSIZE &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero kb2mb has_changes map {
                if (exists $_->{'/proc/pid/status'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                    exists $entry{VmSize} ? $entry{VmSize} : undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_vmsize; }

sub generate_plot_memory_map_count {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1045_num_mmaps_%d',
        label => 'Number of memory maps (virtual memory areas)',
        ylabel => 'count',
        multiple => {
            max_plots => 3,
            max_per_plot => 15,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { '#MEMORY MAPS &mdash; MAX ' . max @{shift()} },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero has_changes map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{vmacount} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{vmacount} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_memory_map_count; }

sub private_dirty_collect_data {
    my $plot = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;
    #print Dumper \@pids;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero map {
                if (exists $_->{'/proc/pid/smaps'}->{$pid} &&
                   (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty} or
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap})) {

                    my $private_dirty = 0;
                    my $swap = 0;

                    if (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty}) {
                        $private_dirty = $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty};
                    }

                    if (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap}) {
                        $swap = $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap};
                    }

                    $private_dirty + $swap
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    return $plot;
}

sub generate_plot_private_dirty_only {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1009_private_dirty',
        label => 'Private dirty',
        legend => 'PRIVATE DIRTY',
        ylabel => 'MB',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' processes';
        },
    );

    private_dirty_collect_data $plot, $masterdb;

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
sub generate_plot_private_dirty_plus_swap {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1009_private_dirty_plus_swap',
        label => 'Private dirty + swap',
        legend => 'PRIVATE DIRTY+SWAP',
        ylabel => 'MB',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' processes';
        },
    );

    private_dirty_collect_data $plot, $masterdb;

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
sub generate_plot_private_dirty {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $entry (@$masterdb) {
        foreach my $pid (@pids) {
            goto swap if exists $entry->{'/proc/pid/smaps'}->{$pid} and
                         exists $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap} and
                                $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap};
        }
    }

    return generate_plot_private_dirty_only $plotter, $masterdb;

swap:
    return generate_plot_private_dirty_plus_swap $plotter, $masterdb;
}
BEGIN { register_generator \&generate_plot_private_dirty; }

sub generate_plot_private_dirty_only_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1009_private_dirty_%d',
        label => 'Private dirty (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 4,
            max_per_plot => 15,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'PRIVATE DIRTY &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
        exclude_nonchanged => 1,
    );

    private_dirty_collect_data $plot, $masterdb;

    done_plotting $plot;
}

sub generate_plot_private_dirty_plus_swap_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1009_private_dirty_plus_swap_%d',
        label => 'Private dirty + swap (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 4,
            max_per_plot => 15,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'PRIVATE DIRTY+SWAP &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
        exclude_nonchanged => 1,
    );

    private_dirty_collect_data $plot, $masterdb;

    done_plotting $plot;
}
sub generate_plot_private_dirty_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $entry (@$masterdb) {
        foreach my $pid (@pids) {
            goto swap if exists $entry->{'/proc/pid/smaps'}->{$pid} and
                         exists $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap} and
                                $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap};
        }
    }

    return generate_plot_private_dirty_only_changes $plotter, $masterdb;

swap:
    return generate_plot_private_dirty_plus_swap_changes $plotter, $masterdb;
}
BEGIN { register_generator \&generate_plot_private_dirty_changes; }

sub generate_plot_heap_histogram {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1001_heap',
        label => 'Heap Size per process',
        legend => 'HEAP SIZE',
        ylabel => 'MB',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' process heaps';
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push([kb2mb nonzero map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_heap_histogram; }

sub generate_plot_heap_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1001_heap_changes_%d',
        label => 'Heap Size per process (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 5,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'HEAP SIZE &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push([kb2mb has_changes nonzero map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_heap_changes; }

sub generate_plot_sysvipc_shm_size {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1050_sysvipc_shm_size',
        label => 'SysV shared memory segment total Size per process',
        legend => 'SYSV SHM SIZE',
        ylabel => 'MB',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'/SYSV'} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'/SYSV'}->{total_Size} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{'/SYSV'}->{total_Size} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_sysvipc_shm_size; }

sub generate_plot_posix_shm_size {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1051_posixipc_shm_size',
        label => 'POSIX shared memory segment total Size per process',
        legend => 'POSIX SHM SIZE',
        ylabel => 'MB',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'/dev/shm/'} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{'/dev/shm/'}->{total_Size} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{'/dev/shm/'}->{total_Size} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_posix_shm_size; }

sub generate_plot_gfx_mmap_size {
    my $plotter = shift;
    my $masterdb = shift;

    foreach my $gfx_mmap (@SP::Endurance::Parser::GFX_MMAPS) {
        my $plot = $plotter->new_histogram(
            key => '1060_gfx_mmap_size' . (($_ = $gfx_mmap) =~ s#/#_#g, $_),
            label => "Total Size of $gfx_mmap memory mappings per process",
            legend => "$gfx_mmap MMAP SIZE",
            ylabel => 'MB',
        );

        my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

        foreach my $pid (@pids) {
            $plot->push([kb2mb nonzero map {
                    exists $_->{'/proc/pid/smaps'}->{$pid} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{total_Size} ?
                           $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{total_Size} : undef
                } @$masterdb],
                title => pid_to_cmdline($masterdb, $pid),
            );
        }

        $plot->sort(sub { shift->[-1] });

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_gfx_mmap_size; }

sub generate_plot_gfx_mmap_count {
    my $plotter = shift;
    my $masterdb = shift;

    foreach my $gfx_mmap (@SP::Endurance::Parser::GFX_MMAPS) {
        my $plot = $plotter->new_linespoints(
            key => '1061_gfx_mmap_count' . (($_ = $gfx_mmap) =~ s#/#_#g, $_),
            label => "Count of $gfx_mmap memory mappings per process (excluding non-changed)",
            legend => "$gfx_mmap MMAP COUNT",
            ylabel => 'count',
        );

        my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

        foreach my $pid (@pids) {
            $plot->push([has_changes nonzero map {
                    exists $_->{'/proc/pid/smaps'}->{$pid} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{vmacount} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{vmacount} : undef
                } @$masterdb],
                title => pid_to_cmdline($masterdb, $pid),
            );
        }

        $plot->sort(sub { shift->[-1] });

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_gfx_mmap_count; }

sub generate_plot_rwxp_mmap_size {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1030_rwxp_mmap_size',
        label => q/Total Size of memory mappings with 'rwxp' protection flags./,
        legend => 'WRITABLE-EXEC MMAP SIZE',
        ylabel => 'MB',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push([kb2mb nonzero map { my $entry = $_;
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{rwxp} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{rwxp}->{total_Size} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{rwxp}->{total_Size} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_rwxp_mmap_size; }

sub generate_plot_pss {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1006_pss',
        label => 'Proportional Set Size (PSS) total per process',
        legend => 'PSS',
        ylabel => 'MB',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' process PSS';
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_pss; }

sub generate_plot_pss_only_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1006_pss_changes_%d',
        label => 'Proportional Set Size (PSS) per process (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 4,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'PSS &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero has_changes map {
                exists $_->{'/proc/pid/smaps'}->{$pid} &&
                exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} ?
                       $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} : undef
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}

sub generate_plot_pss_swap_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1006_pss_swap_changes_%d',
        label => 'Proportional Set Size (PSS) + Swap per process (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 4,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'PSS+SWAP &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [kb2mb nonzero has_changes map {
                if (exists $_->{'/proc/pid/smaps'}->{$pid} and
                        (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} or
                         exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap})) {
                    (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} ?
                            $_->{'/proc/pid/smaps'}->{$pid}->{total_Pss} : 0) +
                    (exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap} ?
                            $_->{'/proc/pid/smaps'}->{$pid}->{total_Swap} : 0)
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}

sub generate_plot_pss_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

    foreach my $entry (@$masterdb) {
        foreach my $pid (@pids) {
            goto swap if exists $entry->{'/proc/pid/smaps'}->{$pid} and
                         exists $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap} and
                                $entry->{'/proc/pid/smaps'}->{$pid}->{total_Swap};
        }
    }

    return generate_plot_pss_only_changes $plotter, $masterdb;

swap:
    return generate_plot_pss_swap_changes $plotter, $masterdb;
}
BEGIN { register_generator \&generate_plot_pss_changes; }

sub generate_plot_threads {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '1200_threads_count',
        label => 'Number of threads per process (single threaded processes excluded)',
        legend => 'THREAD COUNT',
        ylabel => 'thread count',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' process threads';
        },
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @threads = map {
                if (exists $_->{'/proc/pid/status'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                    exists $entry{Threads} ? $entry{Threads} : undef
                } else { undef }
            } @$masterdb;

        next unless any { defined and $_ > 1 } @threads;

        $plot->push(
            [nonzero @threads],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_threads; }

sub generate_plot_threads_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1201_threads_changes',
        label => 'Number of threads per process (non-changed and single threaded processes excluded)',
        legend => 'THREAD CHANGES',
        ylabel => 'thread count',
    );

    my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

    foreach my $pid (@pids) {
        my @threads = map {
                if (exists $_->{'/proc/pid/status'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                    exists $entry{Threads} ? $entry{Threads} : undef
                } else { undef }
            } @$masterdb;

        next unless any { defined and $_ > 1 } @threads;

        $plot->push(
            [has_changes nonzero @threads],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot->sort(sub { shift->[-1] });
}
BEGIN { register_generator \&generate_plot_threads_changes; }

sub x11_pid_to_identifier {
    my $pid = shift;
    my $masterdb = shift;

    uniq sort grep { defined && length } map { my $entry = $_;
        exists $entry->{'/usr/bin/xmeminfo'} ?
            (map { $_->{Identifier} } grep { $_->{PID} == $pid } @{$entry->{'/usr/bin/xmeminfo'}}) :
            undef
    } @$masterdb;
}

sub generate_plot_x11_resource_count {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1071_x11_resource_count_%d',
        label => 'X11 total resource count per process (excluding non-changed)',
        ylabel => 'count',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'X11 RESOURCE COUNT &mdash; MAX ' . max @{shift()} },
        },
    );

    my @pids = uniq grep { defined && length } map { $_->{PID} } map {
        exists $_->{'/usr/bin/xmeminfo'} ? @{$_->{'/usr/bin/xmeminfo'} // []} : undef
    } @$masterdb;

    foreach my $pid (@pids) {
        my @total_resource_count = map { my $entry = $_;
            exists $entry->{'/usr/bin/xmeminfo'} ?
            (sum map { $_->{total_resource_count} } grep { $_->{PID} == $pid } @{$entry->{'/usr/bin/xmeminfo'}}) :
            undef
        } @$masterdb;

        my $identifier = join ' / ', x11_pid_to_identifier($pid, $masterdb);

        $plot->push([nonzero has_changes @total_resource_count],
            title => pid_to_cmdline($masterdb, $pid) . ': ' . $identifier);
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_x11_resource_count; }

sub generate_plot_x11_pixmap_size {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1071_x11_pixmap_size_%d',
        label => 'X11 pixmaps total size per process (excluding non-changed)',
        ylabel => 'MB',
        multiple => {
            max_plots => 2,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'X11 PIXMAPS &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
        },
    );

    my @pids = uniq grep { defined && length } map { $_->{PID} } map {
        exists $_->{'/usr/bin/xmeminfo'} ? @{$_->{'/usr/bin/xmeminfo'} // []} : undef
    } @$masterdb;

    foreach my $pid (@pids) {
        my @pixmap_mem = map { my $entry = $_;
            exists $entry->{'/usr/bin/xmeminfo'} ?
            (sum map { $_->{Pixmap_mem} } grep { $_->{PID} == $pid } @{$entry->{'/usr/bin/xmeminfo'}}) :
            undef
        } @$masterdb;

        my $identifier = join ' / ', x11_pid_to_identifier($pid, $masterdb);

        $plot->push([nonzero has_changes b2mb @pixmap_mem],
            title => pid_to_cmdline($masterdb, $pid) . ': ' . $identifier);
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_x11_pixmap_size; }

sub generate_plot_df {
    my $plotter = shift;
    my $masterdb = shift;

    my @mountpoints = uniq map { keys %{$_->{'/bin/df'}} } @$masterdb;
    #print Dumper(\@mountpoints);

    my $plot = $plotter->new_linespoints(
        key => '2001_diskspace',
        label => '1. Disk space usage per mount point\n2. Global file descriptor usage %',
        legend => 'DISK USED, GLOBAL FD %',
        ylabel => 'percentage used',
    );

    my $maxtitle = max map { length } @mountpoints;

    foreach my $mountpoint (sort @mountpoints) {
        my ($filesystem) = uniq map { $_->{'/bin/df'}->{$mountpoint}->{filesystem} } @$masterdb;
        $plot->push(
            [nonzero map { $_->{'/bin/df'}->{$mountpoint}->{capacity} } @$masterdb],
            title => $filesystem ? sprintf("%-${maxtitle}s \t[$filesystem]", $mountpoint) : $mountpoint,
        );
    }

    $plot->push(
        [nonzero map {
            $_->{'/proc/sys/fs/file-nr'}->{max_fds} > 0 ?
                ($_->{'/proc/sys/fs/file-nr'}->{allocated_fds} /
                 $_->{'/proc/sys/fs/file-nr'}->{max_fds}) * 100
            : undef
            } @$masterdb],
        lw => 5, title => 'Global FD usage %',
    );

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_df; }

sub generate_plot_fd {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/fd_count'}} } @$masterdb;

    my $plot = $plotter->new_histogram(
        key => '1080_fdcount',
        label => 'File descriptors per process',
        legend => 'FILE DESCRIPTORS',
        ylabel => 'count',
        column_limit => 1,
        reduce_f => sub {
            my @leftovers;

            foreach my $idx (0 .. @$masterdb-1) {
                push @leftovers, sum map {
                    exists $_->{__data} &&
                    exists $_->{__data}->[$idx] ?
                           $_->{__data}->[$idx] : undef
                } @_;
            }

            return [nonzero @leftovers],
                   title => 'Sum of ' . scalar(@_) . ' process FDs';
        },
    );

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero map { $_->{'/proc/pid/fd_count'}->{$pid} } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;
    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_fd; }

sub generate_plot_fd_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/fd_count'}} } @$masterdb;

    my $plot = $plotter->new_linespoints(
        key => '1080_fdcount_changes',
        label => 'File descriptors per process (excluding non-changed)',
        legend => 'FILE DESCRIPTOR CHANGES',
        ylabel => 'count',
    );

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero has_changes map { $_->{'/proc/pid/fd_count'}->{$pid} } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_fd_changes; }

sub generate_plot_pid_fd {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/fd'}} } @$masterdb;

    foreach my $fdtype (keys %SP::Endurance::Parser::fdtypemap) {
        my $plot = $plotter->new_histogram(
            key => "1081_fdcount_$fdtype",
            label => ucfirst($fdtype) . ' file descriptor use per process',
            legend => 'FILE DESCRIPTORS &mdash; ' . uc $fdtype,
            ylabel => 'count',
            column_limit => 1,
            reduce_f => sub {
                my @leftovers;

                foreach my $idx (0 .. @$masterdb-1) {
                    push @leftovers, sum map {
                        exists $_->{__data} &&
                        exists $_->{__data}->[$idx] ?
                               $_->{__data}->[$idx] : undef
                    } @_;
                }

                return [nonzero @leftovers],
                       title => 'Sum of ' . scalar(@_) . ' process FDs';
            },
        );

        foreach my $pid (@pids) {
            $plot->push(
                [nonzero map {
                    if (exists $_->{'/proc/pid/fd'}->{$pid}) {
                        my @entry = split ',', $_->{'/proc/pid/fd'}->{$pid};
                        exists $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}] ?
                               $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}] : undef
                    } else { undef }
                } @$masterdb],
                title => pid_to_cmdline($masterdb, $pid),
            );
        }

        $plot->sort(sub { max @{shift()} });
        $plot->reduce;
        $plot->sort(\&max_change, sub { max @{shift()} });

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_pid_fd; }

sub generate_plot_pid_fd_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/fd'}} } @$masterdb;

    foreach my $fdtype (keys %SP::Endurance::Parser::fdtypemap) {
        my $plot = $plotter->new_linespoints(
            key => "1081_fdcount_${fdtype}_changes",
            label => ucfirst($fdtype) . ' file descriptor use per process (excluding non-changed)',
            legend => 'FILE DESCRIPTOR CHANGES &mdash; ' . uc $fdtype,
            ylabel => 'count',
        );

        foreach my $pid (@pids) {
            $plot->push(
                [nonzero has_changes map {
                    if (exists $_->{'/proc/pid/fd'}->{$pid}) {
                    my @entry = map { int } split ',', $_->{'/proc/pid/fd'}->{$pid};
                    exists $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}] ?
                           $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}] : undef
                    } else { undef }
                } @$masterdb],
                title => pid_to_cmdline($masterdb, $pid),
            );
        }

        $plot->sort(sub { shift->[-1] });

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_pid_fd_changes; }

sub generate_plot_interrupts {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2070_interrupts',
        label => 'Interrupts.',
        legend => 'INTERRUPTS',
        ylabel => 'count per second',
        y2label => 'total count per second',
    );

    my @interrupts = uniq grep { defined && length } map { keys %{$_->{'/proc/interrupts'} // {}} } @$masterdb;
    return unless @interrupts > 0;

    foreach my $interrupt (@interrupts) {
        my ($desc) = uniq grep { defined && length } map {
            exists $_->{'/proc/interrupts'}->{$interrupt} &&
            exists $_->{'/proc/interrupts'}->{$interrupt}->{desc} ?
            $_->{'/proc/interrupts'}->{$interrupt}->{desc} : undef
        } @$masterdb;

        my $idx = 0;
        $plot->push(
            [nonzero change_per_second $masterdb,
                cumulative_to_changes map {
                    exists $_->{'/proc/interrupts'}->{$interrupt} &&
                    exists $_->{'/proc/interrupts'}->{$interrupt}->{count} ?
                           $_->{'/proc/interrupts'}->{$interrupt}->{count} : undef
            } @$masterdb],
            axes => 'x1y1', title => sprintf("%-4s %s", $interrupt . ':', $desc),
        );
    }

    my @total_interrupts = map {
        my $entry = $_;
        sum map { exists $_->{count} ? $_->{count} : undef } values %{$entry->{'/proc/interrupts'}}
    } @$masterdb;

    $plot->push(
        [nonzero change_per_second $masterdb, cumulative_to_changes @total_interrupts],
        lw => 5, axes => 'x2y2', title => 'Total interrupts');

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_interrupts; }

sub generate_plot_softirqs {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2071_softirqs',
        label => 'Softirqs.',
        legend => 'SOFTIRQS',
        ylabel => 'count per second',
    );

    my @softirqs = uniq grep { defined && length } map { keys %{$_->{'/proc/softirqs'} // {}} } @$masterdb;
    return unless @softirqs > 0;

    foreach my $interrupt (@softirqs) {
        $plot->push(
            [nonzero change_per_second $masterdb,
                cumulative_to_changes map {
                    exists $_->{'/proc/softirqs'}->{$interrupt} ?
                     sum(@{$_->{'/proc/softirqs'}->{$interrupt}}) : undef
            } @$masterdb],
            title => $interrupt,
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_softirqs; }

sub generate_plot_diskstats_reads_mb {
    my $plotter = shift;
    my $masterdb = shift;

    my @devices = uniq map { keys %{$_->{'/proc/diskstats'} // {}} } @$masterdb;
    return unless @devices > 0;

    my $plot = $plotter->new_linespoints(
        key => '2100_diskstats_reads_mb',
        label => 'Bytes read from device',
        legend => 'DISK READS &mdash; MB',
        ylabel => 'MB',
    );

    foreach my $device (@devices) {
        $plot->push(
            [b2mb nonzero cumulative_to_changes map {
                exists $_->{'/proc/diskstats'}->{$device} &&
                exists $_->{'/proc/diskstats'}->{$device}->{sectors_read} ?
                    $_->{'/proc/diskstats'}->{$device}->{sectors_read} * SECTOR_SIZE :
                    undef
                } @$masterdb],
            title => fs_to_mountpoint($device, $masterdb),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_diskstats_reads_mb; }

sub generate_plot_diskstats_reads_mb_per_second {
    my $plotter = shift;
    my $masterdb = shift;

    my @devices = uniq map { keys %{$_->{'/proc/diskstats'} // {}} } @$masterdb;
    return unless @devices > 0;

    my $plot = $plotter->new_linespoints(
        key => '2100_diskstats_reads_mb_per_second',
        label => 'Bytes read from device per second',
        legend => 'DISK READS &mdash; MB/s',
        ylabel => 'MB per second',
    );

    foreach my $device (@devices) {
        $plot->push(
            [b2mb nonzero change_per_second $masterdb, cumulative_to_changes map {
                exists $_->{'/proc/diskstats'}->{$device} &&
                exists $_->{'/proc/diskstats'}->{$device}->{sectors_read} ?
                       $_->{'/proc/diskstats'}->{$device}->{sectors_read} * SECTOR_SIZE :
                       undef
            } @$masterdb],
            title => fs_to_mountpoint($device, $masterdb),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_diskstats_reads_mb_per_second; }

sub generate_plot_diskstats_written_mb {
    my $plotter = shift;
    my $masterdb = shift;

    my @devices = uniq map { keys %{$_->{'/proc/diskstats'} // {}} } @$masterdb;
    return unless @devices > 0;

    my $plot = $plotter->new_linespoints(
        key => '2100_diskstats_written_mb',
        label => 'Bytes written to device',
        legend => 'DISK WRITES &mdash; MB',
        ylabel => 'MB',
    );

    foreach my $device (@devices) {
        $plot->push(
            [b2mb nonzero cumulative_to_changes map {
                exists $_->{'/proc/diskstats'}->{$device} &&
                exists $_->{'/proc/diskstats'}->{$device}->{sectors_written} ?
                    $_->{'/proc/diskstats'}->{$device}->{sectors_written} * SECTOR_SIZE :
                    undef
            } @$masterdb],
            title => fs_to_mountpoint($device, $masterdb),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_diskstats_written_mb; }

sub generate_plot_diskstats_written_mb_per_second {
    my $plotter = shift;
    my $masterdb = shift;

    my @devices = uniq map { keys %{$_->{'/proc/diskstats'} // {}} } @$masterdb;
    return unless @devices > 0;

    my $plot = $plotter->new_linespoints(
        key => '2100_diskstats_written_mb_per_second',
        label => 'Bytes written to device per second',
        legend => 'DISK WRITES &mdash; MB/s',
        ylabel => 'MB per second',
    );

    foreach my $device (@devices) {
        $plot->push(
            [b2mb nonzero change_per_second $masterdb, cumulative_to_changes map {
                exists $_->{'/proc/diskstats'}->{$device} &&
                exists $_->{'/proc/diskstats'}->{$device}->{sectors_written} ?
                       $_->{'/proc/diskstats'}->{$device}->{sectors_written} * SECTOR_SIZE :
                       undef
            } @$masterdb],
            title => fs_to_mountpoint($device, $masterdb),
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_diskstats_written_mb_per_second; }

sub generate_plot_bmestat {
    my $plotter = shift;
    my $masterdb = shift;

    my ($type) = uniq map { $_->{'/usr/bin/bmestat'}->{battery_type} } @$masterdb;
    $type = " (type: $type)" if length $type;

    my $plot = $plotter->new_linespoints(
        key => '2000_bmestat',
        label => "Battery$type\\n  Left: charge %, temperature\\n  Right: voltage",
        legend => 'BATTERY',
        ylabel => 'charge %, temperature in celsius',
        y2label => 'V',
    );

    $plot->push(
        [nonzero map { $_->{'/usr/bin/bmestat'}->{battery_pct_level} } @$masterdb],
        axes => 'x1y1', lw => 5, title => 'Charge % left',
    );

    $plot->push(
        [nonzero map { $_->{'/usr/bin/bmestat'}->{battery_temperature} } @$masterdb],
        axes => 'x1y1', title => 'Temperature',
    );

    $plot->push(
        [nonzero map { $_->{'/usr/bin/bmestat'}->{battery_cur_voltage} / 1_000 } @$masterdb],
        axes => 'x2y2', title => 'Voltage',
    );

    if ($plot->count) {
        my @backlights = uniq map { keys %{$_->{'/sys/class/backlight'}} } @$masterdb;

        foreach my $bldev (@backlights) {
            $plot->push(
                [nonzero map {
                    exists $_->{'/sys/class/backlight'}->{$bldev} ?
                        ($_->{'/sys/class/backlight'}->{$bldev}->{actual_brightness} /
                         $_->{'/sys/class/backlight'}->{$bldev}->{max_brightness}) * 100
                             : undef
                } @$masterdb],
                axes => 'x1y1', title => "Backlight $bldev brightness %",
            );
        }
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_bmestat; }

sub generate_plot_ramzswap_1 {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2111_ramzswap_1',
        label => 'ramzswap (compressed swap) reads and writes',
        legend => 'COMPR-SWAP READS/WRITES',
        ylabel => 'MB',
    );

    foreach my $key (qw/NumReads NumWrites BDevNumReads BDevNumWrites/) {
        my @counts = map {
            exists $_->{ramzswap} &&
            exists $_->{ramzswap}->{'/dev/ramzswap0'} &&
            exists $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} ?
                   $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} : undef
        } @$masterdb;
        # Convert "reads" and "writes" to megabytes. I'm assuming that they are
        # always page sized operations...
        @counts = map { $_ * PAGE_SIZE } @counts;
        $plot->push([nonzero cumulative_to_changes b2mb @counts],
            title => $key);
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_ramzswap_1; }

sub generate_plot_ramzswap_2 {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2111_ramzswap_2',
        label => 'ramzswap (compressed swap) memory usage',
        legend => 'COMPR-SWAP MEM USAGE',
        ylabel => 'GoodCompress and NoCompress %',
        y2label => 'MB',
    );

    foreach my $key (qw/OrigDataSize ComprDataSize MemUsedTotal/) {
        $plot->push(
            [nonzero kb2mb map {
                exists $_->{ramzswap} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} ?
                       $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} : undef
            } @$masterdb],
            lw => 5, axes => 'x2y2', title => $key,
        );
    }
    $plot->push(
        [nonzero b2mb map { $_ * PAGE_SIZE } map {
            exists $_->{ramzswap} &&
            exists $_->{ramzswap}->{'/dev/ramzswap0'} &&
            exists $_->{ramzswap}->{'/dev/ramzswap0'}->{ZeroPages} ?
                   $_->{ramzswap}->{'/dev/ramzswap0'}->{ZeroPages} : undef
        } @$masterdb],
        lw => 5, axes => 'x2y2', title => 'ZeroPages',
    );

    foreach my $key (qw/GoodCompress NoCompress/) {
        $plot->push(
            [nonzero map {
                exists $_->{ramzswap} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} ?
                       $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} : undef
            } @$masterdb],
            axes => 'x1y1', title => $key,
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_ramzswap_2; }

sub generate_plot_ramzswap_3 {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2111_ramzswap_3',
        label => 'ramzswap (compressed swap) errors',
        legend => 'COMPR-SWAP ERRORS',
        ylabel => 'count',
    );

    foreach my $key (qw/FailedReads FailedWrites InvalidIO/) {
        $plot->push(
            [nonzero cumulative_to_changes map {
                exists $_->{ramzswap} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'} &&
                exists $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} ?
                       $_->{ramzswap}->{'/dev/ramzswap0'}->{$key} : undef
            } @$masterdb],
            title => $key,
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_ramzswap_3; }

sub generate_plot_cgroups {
    my $plotter = shift;
    my $masterdb = shift;

    my @cgroups = uniq grep { defined && length } map { keys %{$_->{cgroups} // {}} } @$masterdb;
    return unless @cgroups > 0;

    my $tmp = 0;
    my %cgroup_colors = map { $_ => $SP::Endurance::Plot::line_colors[$tmp++ % scalar @SP::Endurance::Plot::line_colors] } @cgroups;

    foreach my $key (qw/memory.usage_in_bytes memory.memsw.usage_in_bytes/) {
        my $plot;

        $plot = $plotter->new_linespoints(
            key => '2300_cgroups-memory',
            label => 'Memory usage per cgroup.',
            legend => 'CGROUPS MEMORY',
            ylabel => 'MB',
        ) if $key eq 'memory.usage_in_bytes';

        $plot = $plotter->new_linespoints(
            key => '2301_cgroups-memsw',
            label => 'Memory+Swap usage per cgroup.',
            legend => 'CGROUPS MEMORY+SWAP',
            ylabel => 'MB',
        ) if $key eq 'memory.memsw.usage_in_bytes';

        foreach my $cgroup (sort @cgroups) {
            $plot->push([b2mb nonzero map {
                    exists $_->{cgroups} &&
                    exists $_->{cgroups}->{$cgroup} &&
                    exists $_->{cgroups}->{$cgroup}->{$key} ?
                        $_->{cgroups}->{$cgroup}->{$key} :
                        undef
                } @$masterdb],
                lc => $cgroup_colors{$cgroup},
                title => $cgroup,
            );
        }

        my $limit_key = $key;
        $limit_key =~ s/usage/limit/;

        foreach my $cgroup (sort @cgroups) {
            $plot->push([b2mb nonzero map {
                    exists $_->{cgroups} &&
                    exists $_->{cgroups}->{$cgroup} &&
                    exists $_->{cgroups}->{$cgroup}->{$limit_key} &&
                           $_->{cgroups}->{$cgroup}->{$limit_key} != CGROUP_UNLIMITED ?
                           $_->{cgroups}->{$cgroup}->{$limit_key} : undef
                } @$masterdb],
                lc => $cgroup_colors{$cgroup}, lw => 5,
                title => 'Limit for: ' . $cgroup,
            );
        }

        done_plotting $plot;
    }

    foreach my $memory_stat (qw/cache rss mapped_file swap inactive_anon
                active_anon inactive_file active_file unevictable
                pgpgin pgpgout/) {

        my $plot = $plotter->new_linespoints(
            key => "2302_cgroups-$memory_stat",
            label => {
                cache         => 'Page cache per cgroup.',
                rss           => 'RSS (anonymous + swap cache) per cgroup.',
                mapped_file   => 'Mapped file per cgroup.',
                swap          => 'Swap usage per cgroup.',
                inactive_anon => 'Anon + swap cache on inactive LRU list per cgroup.',
                active_anon   => 'Anon + swap cache on active LRU list per cgroup.',
                inactive_file => 'File-backed memory on inactive LRU list per cgroup.',
                active_file   => 'File-backed memory on active LRU list per cgroup.',
                unevictable   => 'Unevictable memory per cgroup.',
                pgpgin        => 'Number of charging events to the memory cgroup.\n' .
                                 '(Charging event = page accounted as mapped anon page or cache page.)',
                pgpgout       => 'Number of uncharging events to the memory cgroup.\n' .
                                 '(Uncharging event = page unaccounted from the cgroup.)',
            }->{$memory_stat},
            legend => 'CGROUPS ' . uc $memory_stat,
            ylabel => ($memory_stat eq 'pgpgin' or $memory_stat eq 'pgpgout') ?
                'count' : 'MB',
        );

        foreach my $cgroup (sort @cgroups) {
            my @dataset = map {
                    exists $_->{cgroups} &&
                    exists $_->{cgroups}->{$cgroup} &&
                    exists $_->{cgroups}->{$cgroup}->{'memory.stat'} &&
                    exists $_->{cgroups}->{$cgroup}->{'memory.stat'}->{$memory_stat} ?
                           $_->{cgroups}->{$cgroup}->{'memory.stat'}->{$memory_stat} :
                           undef
                } @$masterdb;

            if ($memory_stat eq 'pgpgin' or $memory_stat eq 'pgpgout') {
                $plot->push([b2mb nonzero cumulative_to_changes @dataset], title => $cgroup);
            } else {
                $plot->push([b2mb nonzero @dataset], title => $cgroup);
            }
        }

        done_plotting $plot;
    }

    foreach my $key (qw/cgroup.procs tasks/) {
        my $plot = $plotter->new_linespoints(
            key => { 'cgroup.procs' => '2305_cgroups-procs',
                     tasks          => '2305_cgroups-tasks' }->{$key},
            label => { 'cgroup.procs' => 'Process count per cgroup.',
                       tasks          => 'Task count per cgroup.' }->{$key},
            legend => { 'cgroup.procs' => 'CGROUPS PROCESS COUNT',
                        tasks          => 'CGROUPS TASK COUNT' }->{$key},
            ylabel => 'count',
        );

        foreach my $cgroup (sort @cgroups) {
            $plot->push([nonzero map {
                    exists $_->{cgroups} &&
                    exists $_->{cgroups}->{$cgroup} &&
                    exists $_->{cgroups}->{$cgroup}->{$key} ?
                           $_->{cgroups}->{$cgroup}->{$key} :
                           undef
                } @$masterdb],
                title => $cgroup,
            );
        }

        done_plotting $plot;
    }

    foreach my $key (qw/memory.failcnt memory.memsw.failcnt/) {
        my $plot = $plotter->new_linespoints(
            key => { 'memory.failcnt'       => '2306_cgroups-memory_failcnt',
                     'memory.memsw.failcnt' => '2306_cgroups-memsw_failcnt' }->{$key},
            label => { 'memory.failcnt'       => 'Memory fail count per cgroup.',
                       'memory.memsw.failcnt' => 'Memory+Swap fail count per cgroup.' }->{$key},
            legend => { 'memory.failcnt'       => 'CGROUPS MEMORY FAIL COUNT',
                        'memory.memsw.failcnt' => 'CGROUPS MEMORY+SWAP FAIL COUNT' }->{$key},
            ylabel => 'count',
        );

        foreach my $cgroup (sort @cgroups) {
            $plot->push([nonzero cumulative_to_changes map {
                    exists $_->{cgroups} &&
                    exists $_->{cgroups}->{$cgroup} &&
                    exists $_->{cgroups}->{$cgroup}->{$key} ?
                        $_->{cgroups}->{$cgroup}->{$key} :
                        undef
                } @$masterdb],
                title => $cgroup,
            );
        }

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_cgroups; }

sub generate_plot_networking {
    my $plotter = shift;
    my $masterdb = shift;

    my @interfaces = uniq map { keys %{$_->{'/sbin/ifconfig'} // {}} } @$masterdb;

    foreach my $interface (sort @interfaces) {
        foreach my $key (qw/bytes packets/) {
            my $plot = $plotter->new_linespoints(
                key => "2090_networking-$key-$interface",
                label => "RX and TX $key for networking interface $interface",
                legend => 'NET RX/TX ' . uc($key) . ' &mdash; ' . $interface,
                ylabel => { bytes => 'kB', packets => 'packets' }->{$key},
            );

            foreach my $rxtx (qw/RX TX/) {
                my @dataset = cumulative_to_changes map {
                            exists $_->{'/sbin/ifconfig'}->{$interface} &&
                            exists $_->{'/sbin/ifconfig'}->{$interface}->{$rxtx} &&
                            exists $_->{'/sbin/ifconfig'}->{$interface}->{$rxtx}->{$key} ?
                                   $_->{'/sbin/ifconfig'}->{$interface}->{$rxtx}->{$key} :
                                   undef
                    } @$masterdb;

                if ($key eq 'bytes') {
                    foreach (@dataset) {
                        $_ /= 1_000 if defined;
                    }
                }

                $plot->push([nonzero @dataset], title => $rxtx . ': ' . $interface);
            }

            done_plotting $plot;
        }
    }
}
BEGIN { register_generator \&generate_plot_networking; }

sub generate_plot_pagetypeinfo {
    my $plotter = shift;
    my $masterdb = shift;

    my @pagetypes = uniq map { keys %{$_->{'/proc/pagetypeinfo'}->{0}->{Normal}} } @{$masterdb};

    foreach my $pagetype (@pagetypes) {
        my $ok = 0;
        foreach my $ordernum (0 .. 10) {
            foreach my $entry (map { $_->{'/proc/pagetypeinfo'}->{0}->{Normal}->{$pagetype} } @{$masterdb}) {
                if (any { $_ } @$entry) {
                    $ok = 1;
                    last;
                }
            }
        }
        next unless $ok;

        my $plot = $plotter->new_histogram(
            key => '2274_pagetypeinfo_' . lc $pagetype,
            label => "Free memory in $pagetype migrate type block pool (from /proc/pagetypeinfo)",
            legend => 'PAGETYPE &mdash; ' . uc $pagetype,
            ylabel => 'MB',
        );

        foreach my $ordernum (reverse (0 .. 10)) {
            my @values;
            foreach my $entry (map { $_->{'/proc/pagetypeinfo'}->{0}->{Normal}->{$pagetype} } @{$masterdb}) {
                push @values, $entry->[$ordernum] * (1 << $ordernum) * PAGE_SIZE
            }

            $plot->push([b2mb @values],
                title => ucfirst($pagetype) . " order 2^$ordernum",
            );
        }

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_pagetypeinfo; }

sub generate_plot_process_state_count {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2065_nonsleeping_process_count',
        label => 'Number of processes in non-sleep states.',
        legend => 'NON-SLEEP PROCESS COUNT',
        ylabel => 'count',
    );

    # Note that sleeping and idle task states are skipped when parsing data.
    my %states;
    foreach my $entry (@$masterdb) {
        next unless exists $entry->{'/proc/pid/stat'};
        foreach (values %{$entry->{'/proc/pid/stat'}}) {
            my %stat = split ',';
            next unless exists $stat{state};
            $states{$stat{state}} = 1;
        }
    }

    foreach my $state (keys %states) {
        my @count;

        foreach my $entry (@$masterdb) {
            my $cnt = grep { $_ eq $state } map {
                my %stat = split ',';
                exists $stat{state} ? $stat{state} : undef
            } values %{$entry->{'/proc/pid/stat'} // {}};

            push @count, $cnt;
        }

        $plot->push([nonzero @count],
            title => $state . {
                R => ' (running)',
                #S => skipped
                D => ' (disk sleep)',
                T => ' (stopped)',
                t => ' (tracing stop)',
                X => ' (dead)',
                Z => ' (zombie)',
                P => ' (parked)',
                #I => skipped
            }->{$state},
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_process_state_count; }

my %wchan_suffix = (0 => ' (in user space)');

sub generate_plot_wchan_count {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2350_wchan-count',
        label => 'Process count per wait channel',
        legend => 'WAIT CHANNEL COUNT',
        ylabel => 'process count',
    );

    my @wchans = uniq map { keys %{$_->{'/proc/pid/wchan'}} } @$masterdb;

    foreach my $wchan (@wchans) {
        $plot->push([nonzero map {
                exists $_->{'/proc/pid/wchan'} &&
                exists $_->{'/proc/pid/wchan'}->{$wchan} ?
                       $_->{'/proc/pid/wchan'}->{$wchan} : undef
            } @$masterdb],
            title => $wchan . $wchan_suffix{$wchan},
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_wchan_count; }

sub generate_plot_wchan_changes {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2351_wchan-changes',
        label => 'Process count per wait channel (only changed shown)',
        legend => 'WAIT CHANNEL CHANGES',
        ylabel => 'process count',
    );

    my @wchans = uniq map { keys %{$_->{'/proc/pid/wchan'}} } @$masterdb;

    foreach my $wchan (@wchans) {
        $plot->push([has_changes nonzero map {
                exists $_->{'/proc/pid/wchan'} &&
                exists $_->{'/proc/pid/wchan'}->{$wchan} ?
                       $_->{'/proc/pid/wchan'}->{$wchan} : undef
            } @$masterdb],
            title => $wchan . $wchan_suffix{$wchan},
        );
    }

    $plot->sort(sub { shift->[-1] });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_wchan_changes; }

sub generate_plot_power_supply {
    my $plotter = shift;
    my $masterdb = shift;

    my @power_supplies = uniq map { keys %{$_->{'/sys/class/power_supply'}} } @$masterdb;
    my @backlights = uniq map { keys %{$_->{'/sys/class/backlight'}} } @$masterdb;

    foreach my $dev (@power_supplies) {
        my ($type) = uniq map { $_->{'/sys/class/power_supply'}->{$dev}->{type} } @$masterdb;
        $type = '\nType: ' . $type if length $type;

        my ($technology) = uniq map { $_->{'/sys/class/power_supply'}->{$dev}->{technology} } @$masterdb;
        $technology = '\nTechnology: ' . $technology if length $technology;

        my ($model_name) = uniq map { $_->{'/sys/class/power_supply'}->{$dev}->{model_name} } @$masterdb;
        $model_name = '\nModel: ' . $model_name if length $model_name;

        my ($manufacturer) = uniq map { $_->{'/sys/class/power_supply'}->{$dev}->{manufacturer} } @$masterdb;
        $manufacturer = '\nManufacturer: ' . $manufacturer if length $manufacturer;

        my $plot = $plotter->new_linespoints(
            key => "2000_power_supply-$dev",
            label => "Power supply: ${dev}${type}${technology}${model_name}${manufacturer}",
            legend => "POWER SUPPLY &mdash; $dev",
            ylabel => 'charge-percent, temp-C',
            y2label => 'V',
        );

        $plot->push(
            [nonzero map { $_->{'/sys/class/power_supply'}->{$dev}->{capacity} } @$masterdb],
            axes => 'x1y1', lw => 5, title => 'Charge % left',
        );

        $plot->push(
            [nonzero map { $_->{'/sys/class/power_supply'}->{$dev}->{temp} } @$masterdb],
            axes => 'x1y1', title => 'Temperature',
        );

        $plot->push(
            [nonzero map { $_->{'/sys/class/power_supply'}->{$dev}->{voltage_now} / 1e6 } @$masterdb],
            axes => 'x2y2', title => 'Voltage',
        );

        if ($plot->count) {
            foreach my $bldev (@backlights) {
                $plot->push(
                    [nonzero map {
                        exists $_->{'/sys/class/backlight'}->{$bldev} ?
                            ($_->{'/sys/class/backlight'}->{$bldev}->{actual_brightness} /
                             $_->{'/sys/class/backlight'}->{$bldev}->{max_brightness}) * 100 :
                             undef
                    } @$masterdb],
                    axes => 'x1y1', title => "Backlight $bldev brightness %",
                );
            }
        }

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_power_supply; }

sub proc_pid_io_collect_data {
    my $plot = shift;
    my $masterdb = shift;
    my $pids = shift;
    my $key = shift;

    my $idx = {
        read_bytes => 4,
        write_bytes => 5,
        cancelled_write_bytes => 6,
    }->{$key};

    die "Invalid $key" unless defined $idx;

    foreach my $pid (@$pids) {
        $plot->push(
            [nonzero cumulative_to_changes b2mb map {
                if (exists $_->{'/proc/pid/io'}->{$pid}) {
                    my @entry = unpack "d*", $_->{'/proc/pid/io'}->{$pid};
                    defined $entry[$idx] ? $entry[$idx] : undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    return $plot;
}

sub generate_plot_pid_io {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/io'}} } @$masterdb;

    # Not generating the line graphs for 'cancelled_write_bytes' on purpose,
    # the histogram is enough for now.
    foreach my $key (qw/read_bytes write_bytes/) {
        my $plot = $plotter->new_linespoints(
            key => {
                    read_bytes => '1300_pid_io_read_bytes_%d',
                    write_bytes => '1301_pid_io_write_bytes_%d',
                    cancelled_write_bytes => '1302_pid_io_cancelled_write_bytes_%d',
                }->{$key},
            label => {
                    read_bytes => 'Per process disk reads.',
                    write_bytes => 'Per process disk writes.',
                    cancelled_write_bytes => 'Per process cancelled disk writes.',
                }->{$key},
            ylabel => 'MB',
            multiple => {
                max_plots => 3,
                max_per_plot => 10,
                split_f => sub { max @{shift()} },
                split_factor => 5,
                legend_f => sub {
                    { read_bytes => 'DISK READS',
                      write_bytes => 'DISK WRITES',
                      cancelled_write_bytes => 'CANCELLED DISK WRITES',
                      }->{$key} .
                    ' &mdash; MAX ' . ceil(max @{shift()}) . 'MB' },
            },
        );

        proc_pid_io_collect_data $plot, $masterdb, \@pids, $key;

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_pid_io; }

sub generate_plot_pid_io_histogram {
    my $plotter = shift;
    my $masterdb = shift;

    my @pids = uniq map { keys %{$_->{'/proc/pid/io'}} } @$masterdb;

    foreach my $key (qw/read_bytes write_bytes cancelled_write_bytes/) {
        my $plot = $plotter->new_histogram(
            key => {
                    read_bytes => '1300_pid_io_read_bytes',
                    write_bytes => '1301_pid_io_write_bytes',
                    cancelled_write_bytes => '1302_pid_io_cancelled_write_bytes',
                }->{$key},
            label => {
                    read_bytes => 'Per process disk reads.',
                    write_bytes => 'Per process disk writes.',
                    cancelled_write_bytes => 'Per process cancelled disk writes.',
                }->{$key},
            legend => {
                    read_bytes => 'DISK READS',
                    write_bytes => 'DISK WRITES',
                    cancelled_write_bytes => 'CANCELLED DISK WRITES',
                }->{$key},
            ylabel => 'MB',
        );

        proc_pid_io_collect_data $plot, $masterdb, \@pids, $key;

        $plot->sort(\&max_change, sub { max @{shift()} });

        done_plotting $plot;
    }
}
BEGIN { register_generator \&generate_plot_pid_io_histogram; }

sub generate_plot_upstart_jobs_respawned {
    my $plotter = shift;
    my $masterdb = shift;

    my @jobs = uniq grep { defined and length } map { keys %{$_->{upstart_jobs_respawned}} } @$masterdb;

    my $plot = $plotter->new_histogram(
        key => '1400_upstart_jobs_respawned',
        label => 'Jobs respawned by Upstart',
        legend => 'UPSTART JOBS RESPAWNED',
        ylabel => 'count',
    );

    foreach my $job (@jobs) {
        $plot->push(
            [nonzero cumulative_to_changes map {
                exists $_->{upstart_jobs_respawned} &&
                exists $_->{upstart_jobs_respawned}->{$job} ?
                       $_->{upstart_jobs_respawned}->{$job} : undef
            } @$masterdb],
            title => $job,
        );
    }

    $plot->sort(\&max_change, sub { max @{shift()} });

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_upstart_jobs_respawned; }

sub generate_plot_sched_wakeups {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1500_sched_wakeups_%d',
        label => 'Number of times the process was woken up.',
        ylabel => 'count',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'SCHED &mdash; WAKEUPS &mdash; MAX ' . ceil(max @{shift()}) },
        },
    );

    my @pids = uniq grep { defined and length } map { keys %{$_->{'/proc/pid/sched'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero cumulative_to_changes map {
                if (exists $_->{'/proc/pid/sched'} && exists $_->{'/proc/pid/sched'}->{$pid}) {
                    my @entry = unpack('d*', $_->{'/proc/pid/sched'}->{$pid});
                    exists $entry[$SP::Endurance::Parser::schedmap{'se.statistics.nr_wakeups'}] ?
                           $entry[$SP::Endurance::Parser::schedmap{'se.statistics.nr_wakeups'}] :
                           undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sched_wakeups; }

sub generate_plot_sched_iowait {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1501_sched_iowait_%d',
        label => 'Time spent waiting for I/O.',
        ylabel => 'ms',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'SCHED &mdash; I/O WAIT &mdash; MAX ' . ceil(max @{shift()}) . 'MS'},
        },
    );

    my @pids = uniq grep { defined and length } map { keys %{$_->{'/proc/pid/sched'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero cumulative_to_changes map {
                if (exists $_->{'/proc/pid/sched'} && exists $_->{'/proc/pid/sched'}->{$pid}) {
                    my @entry = unpack('d*', $_->{'/proc/pid/sched'}->{$pid});
                    exists $entry[$SP::Endurance::Parser::schedmap{'se.statistics.iowait_sum'}] ?
                           $entry[$SP::Endurance::Parser::schedmap{'se.statistics.iowait_sum'}] :
                           undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sched_iowait; }

sub generate_plot_sched_block_max {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1502_sched_block_max_%d',
        label => 'Maximum time the process has been blocked in uninterruptible sleep.',
        ylabel => 'ms',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'SCHED &mdash; BLOCK_MAX &mdash; ' . ceil(max @{shift()}) . 'MS'},
        },
    );

    my @pids = uniq grep { defined and length } map { keys %{$_->{'/proc/pid/sched'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero map {
                if (exists $_->{'/proc/pid/sched'} && exists $_->{'/proc/pid/sched'}->{$pid}) {
                    my @entry = unpack('d*', $_->{'/proc/pid/sched'}->{$pid});
                    exists $entry[$SP::Endurance::Parser::schedmap{'se.statistics.block_max'}] ?
                           $entry[$SP::Endurance::Parser::schedmap{'se.statistics.block_max'}] :
                           undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sched_block_max; }

sub generate_plot_sched_wait_max {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '1503_sched_wait_max_%d',
        label => 'Maximum time the process waited in kernel runqueue before entering CPU.',
        ylabel => 'ms',
        multiple => {
            max_plots => 3,
            max_per_plot => 10,
            split_f => sub { max @{shift()} },
            split_factor => 5,
            legend_f => sub { 'SCHED &mdash; WAIT_MAX &mdash; ' . ceil(max @{shift()}) . 'MS'},
        },
    );

    my @pids = uniq grep { defined and length } map { keys %{$_->{'/proc/pid/sched'}} } @$masterdb;

    foreach my $pid (@pids) {
        $plot->push(
            [nonzero map {
                if (exists $_->{'/proc/pid/sched'} && exists $_->{'/proc/pid/sched'}->{$pid}) {
                    my @entry = unpack('d*', $_->{'/proc/pid/sched'}->{$pid});
                    exists $entry[$SP::Endurance::Parser::schedmap{'se.statistics.wait_max'}] ?
                           $entry[$SP::Endurance::Parser::schedmap{'se.statistics.wait_max'}] :
                           undef
                } else { undef }
            } @$masterdb],
            title => pid_to_cmdline($masterdb, $pid),
        );
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_sched_wait_max; }

sub generate_plot_display_state {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_histogram(
        key => '2000_display_time_in_state',
        label => 'Display time in state',
        legend => 'DISPLAY TIME IN STATE',
        ylabel => 'percent',
    );

    my @snapshot_states = map { $_->{'display_state'} } @$masterdb;
    my @blanked = map {
        defined $_->{'statefs'} ? $_->{'statefs'}->{'namespaces/Screen/Blanked'} : undef;
    } @$masterdb;

    # Try to fill data gaps in snapshots that had no display events in journal.
    for (my $i = @snapshot_states - 1; $i > -1; --$i) {
        my $state = $snapshot_states[$i];
        if (!defined $state->{'on_percent'}) {
            # Journal wasn't available in the snapshot.
            next;
        }
        if (defined $state->{'exit_state'}) {
            # It was possible to calculate display state from journal entries.
            next;
        }

        # If we won't be able to determine the value, don't plot it.
        $state->{'on_percent'} = undef;

        # Try peeking statefs for the display state.
        if (defined $blanked[$i]) {
            $state->{'on_percent'} = ($blanked[$i] == 0) ? 100 : 0;
            next;
        }

        # Still no data; try to fill the gaps in the data with a knowledge of
        # adjacent snapshots.
        for (my $j = $i - 1; $j > -1; --$j) {
            my $previous_state = $snapshot_states[$j];
            if (!exists $previous_state->{'exit_state'}) {
                # Journal not available from the previous snapshot.
                last;
            }
            if (defined $previous_state->{'exit_state'}) {
                $state->{'exit_state'} = $previous_state->{'exit_state'};
                $state->{'on_percent'} = ($state->{'exit_state'} eq "unsleep") ? 100 : 0;
                last;
            }
        }
    }

    my @values = map { $_->{'on_percent'} } @snapshot_states;

    if (any { defined } @values) {
        $plot->push([map { defined $_ ? (100 - $_) : undef } @values], title => 'off');
        $plot->push([@values], title => 'on');
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_display_state; }

sub generate_plot_cpu_suspend_time {
    my $plotter = shift;
    my $masterdb = shift;

    my $plot = $plotter->new_linespoints(
        key => '2025_cpu_suspend_time',
        label => 'CPU suspend time',
        legend => 'CPU SUSPEND TIME',
        ylabel => '%',
    );

    my @durations = map { $_->{suspend_stats}->{'uptime'} } @$masterdb;
    for (my $i = @durations - 1; $i != 0; --$i) {
        $durations[$i] -= $durations[$i - 1];
    }

    my @values = map { $_->{suspend_stats}->{'suspend_time'} } @$masterdb;

    if (@values == 0) {
        # No data, add dummy series to have at least an empty graph rendered.
        $plot->push([ ( 0 ) ], title => 'NO DATA');
    }
    else {
        for (my $i = @values - 1; $i != 0; --$i) {
            $values[$i] -= $values[$i - 1];
        }

        for (my $i = 0; $i != @durations; ++$i) {
            $values[$i] /= $durations[$i] / 100;
        }

        $plot->push([@values], title => 'Suspend time %');
    }

    done_plotting $plot;
}
BEGIN { register_generator \&generate_plot_cpu_suspend_time; }

1;
