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

package SP::Endurance::Plotter;

use SP::Endurance::MultiPlot;
use SP::Endurance::Plot;

use Data::Dumper;

eval 'use common::sense';
use strict;

sub new {
    my $class = shift;
    my $self = {@_};
    bless $self, $class;
}

sub new_linespoints {
    my $self = shift;
    my %args = @_;

    my $plot;

    if ($args{multiple}) {
        $plot = SP::Endurance::MultiPlot->new(
            __plotter => $self,
            type => 'linespoints',
            %{$self},
            %args,
        );
    } else {
        $plot = SP::Endurance::Plot->new(
            __plotter => $self,
            type => 'linespoints',
            %{$self},
            %args,
        );
    }

    return $plot;
}

sub new_histogram {
    my $self = shift;
    my %args = @_;

    my $plot = SP::Endurance::Plot->new(
        __plotter => $self,
        type => 'histogram',
        %{$self},
        %args,
    );

    return $plot;
}

sub new_yerrorbars {
    my $self = shift;
    my %args = @_;

    my $plot;

    if ($args{multiple}) {
        $plot = SP::Endurance::MultiPlot->new(
            __plotter => $self,
            type => 'yerrorbars',
            %{$self},
            %args,
        );
    } else {
        $plot = SP::Endurance::Plot->new(
            __plotter => $self,
            type => 'yerrorbars',
            %{$self},
            %args,
        );
    }

    return $plot;
}

1;
