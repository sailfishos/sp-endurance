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

package SP::Endurance::Util;

require Exporter;
@ISA = qw/Exporter/;
@EXPORT_OK = qw/GRAPHS_DIR plot_filename plot_thumbname b2mb kb2mb nonzero
        has_changes max_change cumulative_to_changes uptimes total_duration
        sw_versions hw_string xtics dur_to_str round_durations
        change_per_second/;

use List::Util qw/min max/;
use List::MoreUtils qw/any minmax uniq/;
use Data::Dumper;

no warnings 'uninitialized';
eval 'use common::sense';
use strict;

sub GRAPHS_DIR()   { 'graphs' }
sub plot_filename  { GRAPHS_DIR . '/' . shift() . '.png' }
sub plot_thumbname { GRAPHS_DIR . '/' . shift() . '_thumb.jpg' }

sub b2mb {
    my @ret;
    push @ret, defined $_ ? $_ / (1024*1024) : $_ foreach @_;
    return @ret;
}

sub kb2mb {
    my @ret;
    if (ref $_[0] eq 'ARRAY') {
        foreach (@_) {
            my @inner;
            push @inner, defined $_ ? $_ / 1024 : $_ foreach @$_;
            push @ret, [@inner];
        }
    } else {
        push @ret, defined $_ ? $_ / 1024 : $_ foreach @_;
    }
    return @ret;
}

sub nonzero {
    if (ref $_[0] eq 'ARRAY') {
        foreach (@_) {
            any { $_ } @$_ and return @_;
        }
    } else {
        any { $_ } @_ and return @_;
    }
    return;
}

sub has_changes {
    my $prev;
    foreach (@_) {
        $prev = $_, next
            if not defined $prev and defined $_;
        return @_
            if $prev != $_ and defined $_;
    }
    return;
}

sub max_change {
    my $arg = shift;
    return unless ref $arg eq 'ARRAY';
    my ($min, $max) = minmax @$arg;
    return $max - $min;
}

sub cumulative_to_changes {
    my @ret;
    my $prev;
    foreach (@_) {
        if (not defined $prev) {
            push @ret, undef;
            next;
        }
        if (not defined $_) {
            push @ret, undef;
        } elsif ($_ < $prev) {
            push @ret, undef;
        } else {
            push @ret, $_ - $prev;
        }
    } continue {
        $prev = $_;
    }
    return @ret;
}

sub uptimes {
    my $masterdb = shift;

    cumulative_to_changes map {
        exists $_->{'/proc/uptime'} &&
        exists $_->{'/proc/uptime'}->{uptime} ?
               $_->{'/proc/uptime'}->{uptime} : undef
    } @$masterdb;
}

sub change_per_second {
    my $masterdb = shift;

    my @uptimes = uptimes $masterdb;

    my $idx = -1;
    map { $idx++;
        defined $uptimes[$idx] && $uptimes[$idx] > 0 && defined $_ ?
           $_ / $uptimes[$idx] : undef
    } @_;
}

sub total_duration {
    my $masterdb = shift;

    my @uptimes = grep { defined } map {
        exists $_->{'/proc/uptime'} &&
        exists $_->{'/proc/uptime'}->{uptime} ?
               $_->{'/proc/uptime'}->{uptime} : undef
    } @$masterdb;

    return unless @uptimes >= 2;
    return $uptimes[-1] - $uptimes[0];
}

sub sw_versions {
    my $masterdb = shift;

    return uniq grep { defined && length } map { exists $_->{sw_version} ? $_->{sw_version} : undef } @$masterdb;
}

sub hw_string {
    my $masterdb = shift;

    my @hw_products = uniq sort grep { defined && length } map {
        exists $_->{component_version} &&
        exists $_->{component_version}->{product} ?
               $_->{component_version}->{product} : undef
    } @$masterdb;

    my @hw_builds = uniq sort grep { defined && length } map {
        exists $_->{component_version} &&
        exists $_->{component_version}->{hw_build} ?
               $_->{component_version}->{hw_build} : undef
    } @$masterdb;

    return join ':',
        join(' / ', @hw_products),
        join(' / ', @hw_builds);
}

sub xtics {
    my $plot_width = shift;
    my $masterdb = shift;

    my @xtics;

    foreach my $idx (0 .. @$masterdb-1) {
        my $entry = $masterdb->[$idx];
        my $desc = substr $entry->{dirname}, -7;
        push @xtics, qq/$desc: [$entry->{date}]/;
    }

    return \@xtics;
}

sub dur_to_str {
    my $secs = shift;
    my $hours = int($secs / 3600);
    my $minutes = int(($secs % 3600) / 60);

    $secs = int $secs;

    return "${hours}h ${minutes}min" if $hours > 0;
    return "${minutes}min" if $minutes > 0;
    return "${secs}s";
}

sub round_durations {
    my $masterdb = shift;

    my @uptimes = grep { defined } uptimes $masterdb;
    my $total_duration = total_duration $masterdb;

    return {
        avg => dur_to_str($total_duration / (@$masterdb-1)),
        min => dur_to_str(min @uptimes),
        max => dur_to_str(max @uptimes),
    };
}

1;
