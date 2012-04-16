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

package SP::Endurance::MultiPlot;

use base 'SP::Endurance::Plot';

use List::Util qw/max sum/;
use Data::Dumper;

no warnings 'uninitialized';
eval 'use common::sense';
use strict;

sub new {
    my $class = shift;
    my $self = {@_};
    #print Dumper($self);
    bless $self, $class;
}

sub done_plotting {
    my $self = shift;
    $self->sort($self->{multiple}->{split_f});

    my @split_f = map { $self->{multiple}->{split_f}->($_->{__data}) } @{$self->{entries}};

    return () unless @{$self->{entries}} > 0;

    # Split the available data in arrays, one per graph, and store the
    # arrayrefs in @split_data.
    my @split_data = [$self->{entries}->[0]];
    my $prev_split_f = $split_f[0];
    foreach my $idx (1 .. @split_f-1) {
        if (@split_data < $self->{multiple}->{max_plots} and
                (@{$split_data[-1]} >= $self->{multiple}->{max_per_plot} or
                $prev_split_f > $self->{multiple}->{split_factor} * $split_f[$idx])) {
            CORE::push @split_data, [];
            $prev_split_f = $split_f[$idx];
        }
        CORE::push @{$split_data[-1]}, $self->{entries}->[$idx];
    }

    #print Dumper(\@split_data);
    my @plots;
    foreach my $idx (0 .. @split_data-1) {
        my $plot = $self->{__plotter}->new_linespoints(
            key => sprintf($self->{key}, $idx+1),
            label => $self->{label},
            #legend => sprintf($self->{legend}, $idx+1),
            legend => $self->{multiple}->{legend_f}->($split_data[$idx]->[0]->{__data}),
            ylabel => $self->{ylabel},
            y2label => $self->{y2label},
        );
        foreach (@{$split_data[$idx]}) {
            $plot->push($_->{__data}, %{$_});
        }
        CORE::push @plots, $plot->done_plotting;
    }

    undef $self->{entries};

    return @plots;
}

1;
