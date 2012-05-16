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

package SP::Endurance::GnuplotWorker;

use SP::Endurance::Util qw/plot_filename plot_thumbname/;

use POSIX qw/WIFSIGNALED WTERMSIG SIGINT SIGTERM SIGKILL/;
use Data::Dumper;

#no warnings 'uninitialized';
eval 'use common::sense';
use strict;

# Fork separate worker process and pipe the plot "keys" to it. We do this for
# couple of reasons:
# - Calling system() in perl process that has several hundred of MB data
#   structures is slow.
# - We can start plotting as soon as we have some gnuplot data available,
#   improving parallellization (compared to first generating all the gnuplot
#   input data, and plotting after that).
sub worker {
    my $pipe = shift;
    my $config = shift;

    die "Invalid config" unless ref $config eq 'HASH';

    my $forkmanager;

    if (exists $config->{flag_j} and $config->{flag_j} > 1) {
        require Parallel::ForkManager;
        $forkmanager = new Parallel::ForkManager($config->{flag_j});
    }

    while (<$pipe>) {
        chomp;
        next unless /^(\S+)$/;

        my $key = $1;
        my $graph = plot_filename $key;
        my $thumb = plot_thumbname $key;
        my $cmd = "gnuplot 'e/$key.cmd' > '$graph'";

        $forkmanager->start() and next if $forkmanager;
        print " > $cmd\n";
        system $cmd;

        if (WIFSIGNALED($?)) {
            my $sig = WTERMSIG($?);
            # Ignore gnuplot problems (SIGSEGV etc), but stop processing if it
            # looks like the users wants to abort the plot generation.
            if ($sig == SIGINT or $sig == SIGTERM or $sig == SIGKILL) {
                kill($sig, $$);
            }
        }

        system "pngtopnm $graph |" .
               'pnmscalefixed' .
                    ' -width=' . $config->{thumb_width} .
                    ' -height=' . $config->{thumb_height} . '|' .
               "pnmtojpeg > $thumb";

        if (WIFSIGNALED($?)) {
            my $sig = WTERMSIG($?);
            # Ignore thumnail generation problems (SIGSEGV etc), but stop
            # processing if it looks like the users wants to abort the plot
            # generation.
            if ($sig == SIGINT or $sig == SIGTERM or $sig == SIGKILL) {
                kill($sig, $$);
            }
        }

        $forkmanager->finish() if $forkmanager;
    }

    $forkmanager->wait_all_children() if $forkmanager;

    return 0;
}

1;
