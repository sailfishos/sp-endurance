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

package SP::Endurance::MultiGraphGenerators;

require Exporter;
@ISA = qw/Exporter/;
@EXPORT_OK = qw/system_graph_generators process_graph_generators
        process_summary_graph_generators get_plots/;

use SP::Endurance::Parser;
use SP::Endurance::Util qw/kb2mb nonzero/;

use POSIX qw/ceil/;
use List::Util qw/max/;
use List::MoreUtils qw/uniq minmax/;
use Data::Dumper;

no warnings 'uninitialized';
eval 'use common::sense';
use strict;

my @system_generators;
my @process_generators;
my @process_summary_generators;
my @plots;

sub system_graph_generators          { @system_generators }
sub process_graph_generators         { @process_generators }
sub process_summary_graph_generators { @process_summary_generators }
sub get_plots { sort { $a->{key} cmp $b->{key} } @plots }

sub register_system_generator {
    my $g = shift;
    return unless ref $g eq 'CODE';
    push @system_generators, $g;
}

sub register_process_generator {
    my $g = shift;
    return unless ref $g eq 'CODE';
    push @process_generators, $g;
}

sub register_process_summary_generator {
    my $g = shift;
    return unless ref $g eq 'CODE';
    push @process_summary_generators, $g;
}

our $done_plotting_cb;

sub done_plotting {
    my $plot = shift;
    foreach ($plot->done_plotting) {
        push @plots, $_;
        $done_plotting_cb->($_) if ref $done_plotting_cb eq 'CODE';
    }
}

sub pid_to_cmdline {
    my $masterdb = shift;
    my $pid = shift;

    return unless $pid;

    my %pid_to_cmdline;

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

sub pidfilter {
    my $masterdb = shift;

    my @ret;
    foreach my $pid (@_) {
        my $cmdline = pid_to_cmdline $masterdb, $pid;

        # Filter out some of the processes that are involved in the
        # sp-endurance snapshotting.
        push @ret, $pid
            unless $cmdline eq "$pid: sp-noncached" or
                   $cmdline eq "$pid: sp_smaps_snapshot" or
                   $cmdline eq "$pid: lzop"
    }

    return @ret;
}

sub process2pid {
    my $masterdb = shift;
    my $process = shift;

    foreach (@$masterdb) {
        my %h = reverse %{$_->{'/proc/pid/cmdline'}};
        return $h{$process} if defined $h{$process};
    }

    return;
}

sub generate_plot_command_heap {
    my $plotter = shift;
    my $superdb = shift;
    my $process = shift;

    my $plot = $plotter->new_yerrorbars(
        key => "1001_heap_$process",
        process => $process,
        label => "Total heap Size min & max per usecase for '$process'",
        legend => 'HEAP SIZE',
        ylabel => 'MB',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        push @total, [minmax map {
            my $pid = process2pid($masterdb, $process);
            defined $pid &&
                    exists $_->{'/proc/pid/smaps'}->{$pid} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} ?
                           $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size} :
                           undef
        } @$masterdb];
    }

    $plot->push([kb2mb nonzero @total]);

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_process_generator \&generate_plot_command_heap; }

sub generate_plot_command_private_dirty {
    my $plotter = shift;
    my $superdb = shift;
    my $process = shift;

    my $plot = $plotter->new_yerrorbars(
        key => "1001_private_dirty_$process",
        process => $process,
        label => "Total Private Dirty min & max per usecase for '$process'",
        legend => 'PRIVATE DIRTY',
        ylabel => 'MB',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        push @total, [minmax map {
            my $pid = process2pid($masterdb, $process);
            defined $pid &&
                    exists $_->{'/proc/pid/smaps'}->{$pid} &&
                    exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty} ?
                           $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty} :
                           undef
        } @$masterdb];
    }

    $plot->push([kb2mb nonzero @total]);

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_process_generator \&generate_plot_command_private_dirty; }

sub generate_plot_process_summary_private_dirty {
    my $plotter = shift;
    my $superdb = shift;
    my $processes = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '0001_private_dirty_%d',
        label => 'Total Private Dirty min & max per usecase',
        #legend => 'PRIVATE DIRTY',
        ylabel => 'MB',
        multiple => {
            max_plots => 100,
            max_per_plot => 8,
            split_f => sub { max map { $_->[1] } @{shift()} },
            split_factor => 5,
            legend_f => sub { 'PRIVATE DIRTY &mdash; MAX ' . ceil(max map { $_->[1] } @{shift()}) . 'MB' },
        },
    );

    foreach my $process (@$processes) {
        my @total;

        foreach my $masterdb (@$superdb) {
            push @total, [minmax map {
                my $pid = process2pid($masterdb, $process);
                defined $pid &&
                        exists $_->{'/proc/pid/smaps'}->{$pid} &&
                        exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty} ?
                               $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty} :
                               undef
            } @$masterdb];
        }

        $plot->push([kb2mb nonzero @total], title => $process);
    }

    $plot->sort(sub { max @{shift()} });
    $plot->reduce;

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_process_summary_generator \&generate_plot_process_summary_private_dirty; }

sub generate_plot_command_fd_count {
    my $plotter = shift;
    my $superdb = shift;
    my $process = shift;

    my $plot = $plotter->new_yerrorbars(
        key => "1080_fdcount_$process",
        process => $process,
        label => "File descriptors in use min & max per usecase for '$process'",
        legend => 'FILE DESCRIPTORS',
        ylabel => 'count',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        push @total, [minmax map {
            my $pid = process2pid($masterdb, $process);
            defined $pid &&
                    exists $_->{'/proc/pid/fd_count'} &&
                    exists $_->{'/proc/pid/fd_count'}->{$pid} ?
                           $_->{'/proc/pid/fd_count'}->{$pid} : undef
        } @$masterdb];
    }

    $plot->push([nonzero @total]);

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_process_generator \&generate_plot_command_fd_count; }

sub generate_plot_heap_size {
    my $plotter = shift;
    my $superdb = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '2001_heap',
        label => 'Total heap Size min & max per usecase',
        legend => 'HEAP SIZE',
        ylabel => 'MB',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        my ($min, $max);

        my @pids = pidfilter $masterdb, uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

        foreach (@$masterdb) {
            my $total;
            foreach my $pid (@pids) {
                $total += $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size}
                    if exists $_->{'/proc/pid/smaps'}->{$pid} &&
                       exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'} &&
                       exists $_->{'/proc/pid/smaps'}->{$pid}->{'[heap]'}->{total_Size};
            }
            ($min, $max) = minmax grep { defined } $min, $max, $total;
        }

        push @total, [$min, $max];
    }

    $plot->push([kb2mb nonzero @total]);

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_heap_size; }

sub generate_plot_private_dirty {
    my $plotter = shift;
    my $superdb = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '2010_private_dirty',
        label => 'Total private dirty min & max per usecase',
        legend => 'PRIVATE DIRTY',
        ylabel => 'MB',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        my ($min, $max);

        my @pids = pidfilter $masterdb, uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

        foreach (@$masterdb) {
            my $total;
            foreach my $pid (@pids) {
                $total += $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty}
                    if exists $_->{'/proc/pid/smaps'}->{$pid} &&
                       exists $_->{'/proc/pid/smaps'}->{$pid}->{total_Private_Dirty};
            }
            ($min, $max) = minmax grep { defined } $min, $max, $total;
        }

        push @total, [$min, $max];
    }

    $plot->push([kb2mb nonzero @total]);
    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_private_dirty; }

sub generate_plot_mlocked {
    my $plotter = shift;
    my $superdb = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '2030_locked',
        label => 'VmLck (Size of memory locked to RAM) min & max per usecase',
        legend => 'LOCKED',
        ylabel => 'MB',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        my ($min, $max);

        my @pids = uniq map { keys %{$_->{'/proc/pid/status'}} } @$masterdb;

        foreach (@$masterdb) {
            my $total;
            foreach my $pid (@pids) {
                if (exists $_->{'/proc/pid/status'}->{$pid}) {
                    my %entry = split ',', $_->{'/proc/pid/status'}->{$pid};
                    $total += $entry{VmLck} if exists $entry{VmLck};
                }
            }
            ($min, $max) = minmax grep { defined } $min, $max, $total;
        }

        push @total, [$min, $max];
    }

    $plot->push([kb2mb nonzero @total]);
    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_mlocked; }

sub generate_plot_gfx_mmap_size {
    my $plotter = shift;
    my $superdb = shift;

    foreach my $gfx_mmap (@SP::Endurance::Parser::GFX_MMAPS) {
        my $plot = $plotter->new_yerrorbars(
            key => '2060_gfx_mmap_size' . (($_ = $gfx_mmap) =~ s#/#_#g, $_),
            label => "Total Size of $gfx_mmap memory mappings min & max per usecase",
            legend => "$gfx_mmap MMAP SIZE",
            ylabel => 'MB',
        );

        my @total;

        foreach my $masterdb (@$superdb) {
            my ($min, $max);

            my @pids = pidfilter $masterdb, uniq map { keys %{$_->{'/proc/pid/smaps'} // {}} } @$masterdb;

            foreach (@$masterdb) {
                my $total;
                foreach my $pid (@pids) {
                    if (exists $_->{'/proc/pid/smaps'}->{$pid} &&
                        exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap} &&
                        exists $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{total_Size}) {
                        $total += $_->{'/proc/pid/smaps'}->{$pid}->{$gfx_mmap}->{total_Size};
                    }
                }
                ($min, $max) = minmax grep { defined } $min, $max, $total;
            }

            push @total, [$min, $max];
        }

        $plot->push([kb2mb nonzero @total]);

        done_plotting $plot;
    }
}
BEGIN { register_system_generator \&generate_plot_gfx_mmap_size; }

sub generate_plot_fd {
    my $plotter = shift;
    my $superdb = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '2080_fdcount',
        label => 'File descriptors in use min & max per usecase',
        legend => 'FILE DESCRIPTORS',
        ylabel => 'count',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        my ($min, $max);

        my @pids = pidfilter $masterdb, uniq map { keys %{$_->{'/proc/pid/fd_count'}} } @$masterdb;

        foreach (@$masterdb) {
            my $total;
            foreach my $pid (@pids) {
                if (exists $_->{'/proc/pid/fd_count'} and exists $_->{'/proc/pid/fd_count'}->{$pid}) {
                    $total += $_->{'/proc/pid/fd_count'}->{$pid};
                }
            }
            ($min, $max) = minmax grep { defined } $min, $max, $total;
        }

        push @total, [$min, $max];
    }

    $plot->push([nonzero @total]);
    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_fd; }

sub generate_plot_fdtype {
    my $plotter = shift;
    my $superdb = shift;

    foreach my $fdtype (keys %SP::Endurance::Parser::fdtypemap) {
        my $plot = $plotter->new_yerrorbars(
            key => "2081_fdcount_$fdtype",
            label => ucfirst($fdtype) . ' file descriptor use min & max per usecase',
            legend => 'FILE DESCRIPTORS &mdash;<br> ' . uc $fdtype,
            ylabel => 'count',
        );

        my @total;

        foreach my $masterdb (@$superdb) {
            my ($min, $max);

            my @pids = pidfilter $masterdb, uniq map { keys %{$_->{'/proc/pid/fd'}} } @$masterdb;

            foreach (@$masterdb) {
                my $total;
                foreach my $pid (@pids) {
                    if (exists $_->{'/proc/pid/fd'}->{$pid}) {
                        my @entry = split ',', $_->{'/proc/pid/fd'}->{$pid};
                        if (exists $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}]) {
                            $total += $entry[$SP::Endurance::Parser::fdtypemap{$fdtype}];
                        }
                    }
                }
                ($min, $max) = minmax grep { defined } $min, $max, $total;
            }

            push @total, [$min, $max];
        }

        $plot->push([nonzero @total]);
        done_plotting $plot;
    }
}
BEGIN { register_system_generator \&generate_plot_fdtype; }

sub generate_plot_loadavg {
    my $plotter = shift;
    my $superdb = shift;

    foreach my $avg (qw/min1 min5 min15/) {
        my $plot = $plotter->new_yerrorbars(
            key => '2505_loadavg_' . {
                min1 => 'min01',
                min5 => 'min05',
                min15 => 'min15',
            }->{$avg},
            label => 'Load average: ' . {
                min1 => '1 minute average',
                min5 => '5 minute average',
                min15 => '15 minute average',
            }->{$avg},
            legend => 'LOAD AVERAGE &mdash; <br>' . {
                min1 => '1 MIN',
                min5 => '5 MIN',
                min15 => '15 MIN',
            }->{$avg},
            ylabel => 'load average',
        );

        my @total;

        foreach my $masterdb (@$superdb) {
            my ($min, $max);
            foreach (@$masterdb) {
                if (exists $_->{'/proc/loadavg'} && exists $_->{'/proc/loadavg'}->{$avg}) {
                    ($min, $max) = minmax grep { defined } $min, $max, $_->{'/proc/loadavg'}->{$avg};
                }
            }
            push @total, [$min, $max];
        }

        $plot->push([nonzero @total]);
        done_plotting $plot;
    }
}
BEGIN { register_system_generator \&generate_plot_loadavg; }

sub generate_plot_task_count {
    my $plotter = shift;
    my $superdb = shift;

    my $plot = $plotter->new_yerrorbars(
        key => '2560_task_count',
        label => 'Task count min & max per usecase.',
        legend => 'TASK COUNT',
        ylabel => 'number of processes',
    );

    my @total;

    foreach my $masterdb (@$superdb) {
        my ($min, $max);
        foreach (@$masterdb) {
            if (exists $_->{'/proc/loadavg'} && exists $_->{'/proc/loadavg'}->{all}) {
                ($min, $max) = minmax grep { defined } $min, $max, $_->{'/proc/loadavg'}->{all};
            }
        }
        push @total, [$min, $max];
    }

    $plot->push([nonzero @total]);

    #print Dumper $plot;
    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_task_count; }

sub generate_plot_ext4_written {
    my $plotter = shift;
    my $superdb = shift;

    my @filesystems = uniq map {
        my $masterdb = $_;
        map { keys %{$_->{'/sys/fs/ext4'}} } @$masterdb
    } @$superdb;

    foreach my $fs (@filesystems) {
        my $plot = $plotter->new_histogram(
            key => "2602_ext4_written_$fs",
            label => "Bytes written to ext4 partition at $fs since boot",
            legend => "EXT4 WRITES &mdash;<br> $fs",
            ylabel => 'MB',
        );

        my @total;

        foreach my $masterdb (@$superdb) {
            my ($min, $max) = minmax map { $_->{'/sys/fs/ext4'}->{$fs}->{session_write_kbytes} } @$masterdb;
            push @total, $max - $min;
        }

        $plot->push([kb2mb nonzero @total], title => $fs);
        done_plotting $plot;
    }
}
BEGIN { register_system_generator \&generate_plot_ext4_written; }

sub generate_plot_system_memory {
    my $plotter = shift;
    my $superdb = shift;

    foreach my $key (qw/SwapCached MemFree Cached Active(file)
                Inactive(file) Active(anon) Inactive(anon) Shmem Dirty Buffers
                Mlocked PageTables KernelStack SReclaimable SUnreclaim/) {

        my $plot = $plotter->new_yerrorbars(
            key => '2800_system_memory_' . (($_ = $key, y/()/_/), lc $_),
            label => q/System-level memory '/ . $key . q/' min & max per usecase/,
            legend => 'SYSTEM MEMORY &mdash;<br> ' . uc $key,
            ylabel => 'MB',
        );

        my @total;
        foreach my $masterdb (@$superdb) {
            push @total, [minmax map { $_->{'/proc/meminfo'}->{$key} } @$masterdb];
        }
        $plot->push([kb2mb nonzero @total]);

        #print STDERR Dumper $plot;
        done_plotting $plot;
    }

    my $plot = $plotter->new_linespoints(
        key => '2800_system_memory_swap_total',
        label => q/System-level memory: 'Total Swap Used' min & max per usecase/,
        legend => 'SYSTEM MEMORY &mdash;<br> SWAP TOTAL',
        ylabel => 'MB',
    );

    my @total;
    foreach my $masterdb (@$superdb) {
        push @total, [minmax map {
            $_->{'/proc/meminfo'}->{SwapTotal} - $_->{'/proc/meminfo'}->{SwapFree}
        } @$masterdb];
    }
    $plot->push([kb2mb nonzero @total]);

    done_plotting $plot;
}
BEGIN { register_system_generator \&generate_plot_system_memory; }

1;
