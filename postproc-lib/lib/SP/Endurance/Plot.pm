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

package SP::Endurance::Plot;

use List::MoreUtils qw/any/;
use List::Util qw/max sum/;
use Data::Dumper;

use SP::Endurance::Util qw/has_changes/;

no warnings 'uninitialized';
eval 'use common::sense';
use strict;

# The gnuplot pngcairo color palette seems to be limited, so use our own
# colors. Based on the X11 color set.
our @line_colors = qw/
FF0000 66CDAA DEB887 00FF00 87CEEB B22222 D8BFD8 2F4F4F C71585 E9967A 90EE90
8FBC8F 9370DB 48D1CC 008080 0000CD 483D8B 9932CC E0FFFF 808000 98FB98 B8860B
A52A2A 20B2AA 556B2F DC143C 808080 800080 6A5ACD 000080 A0522D 00FFFF BA55D3
00FF00 7CFC00 800000 008B8B 708090 4682B4 8B4513 2E8B57 87CEFA DA70D6 3CB371
4169E1 6B8E23 AFEEEE B0C4DE 5F9EA0 7FFFD4 BC8F8F D2691E 32CD32 9ACD32 000000
C0C0C0 00CED1 696969 EE82EE 228B22 8A2BE2 6495ED 006400 ADD8E6 CD5C5C 8B008B
D3D3D3 D2B48C 40E0D0 BDB76B 1E90FF 191970 DDA0DD 7B68EE 00BFFF 4B0082 A9A9A9
7FFF00 0000FF 778899 B0E0E6 9400D3 00FF7F 008000 CD853F 00008B 8B0000 DB7093/;

sub COLUMN_LIMIT { 66 }

sub new {
    my $class = shift;
    my $self = {@_};

    if (exists $self->{key}) {
        $self->{key} =~ s/\W/_/g;
    }

    #print Dumper($self);
    bless $self, $class;
}

sub push {
    my $self = shift;
    my $entry = shift;
    my %args = @_;

    return $self unless ref $entry eq 'ARRAY';

    if ($self->{exclude_nonchanged}) {
        @$entry = has_changes @$entry;
    }

    return $self unless @{$entry} > 0;

    $args{__data} = $entry;

    CORE::push @{$self->{entries}}, \%args;

    return $self;
}

sub splice {
    my $self = shift;
    my $offset = shift;
    return CORE::splice @{$self->{entries}}, $offset;
}

sub count {
    my $self = shift;
    return 0 unless $self->{entries};
    return scalar @{$self->{entries}};
}

sub sort {
    my $self = shift;
    my $code1 = shift;
    my $code2 = shift;

    die "invalid coderef1 '$code1'" if ref $code1 ne 'CODE';
    die "invalid coderef2 '$code2'" if defined $code2 and ref $code2 ne 'CODE';

    if ($self->{entries}) {
        if ($code2) {
            @{$self->{entries}} = reverse CORE::sort {
                    $code1->($a->{__data}) <=> $code1->($b->{__data}) ||
                    $code2->($a->{__data}) <=> $code2->($b->{__data})
                } @{$self->{entries}};
        } else {
            @{$self->{entries}} = reverse CORE::sort {
                    $code1->($a->{__data}) <=> $code1->($b->{__data})
                } @{$self->{entries}};
        }
    }

    return $self;
}

sub scale {
    my $self = shift;
    my %args = @_;
    my $to = $args{to};
    return $self unless $to;

    my $lastidx;
    foreach (@{$self->{entries}}) {
        $lastidx = max $lastidx, scalar @{$_->{__data}};
    }
    return $self unless defined $lastidx;

    foreach my $idx (0 .. $lastidx) {
        my $sum = sum map { $_->{__data}->[$idx] } @{$self->{entries}};
        next unless $sum;

        foreach my $entry (@{$self->{entries}}) {
            next unless $entry->{__data}->[$idx];
            $entry->{__data}->[$idx] = ($entry->{__data}->[$idx] / $sum) * $to;
        }
    }

    return $self;
}

sub reduce {
    my $self = shift;

    return $self unless exists $self->{column_limit} and
                        exists $self->{reduce_f} and
                        ref $self->{reduce_f} eq 'CODE';

    return $self unless exists $self->{entries} and
                        @{$self->{entries}} > ($self->{column_limit} * COLUMN_LIMIT);

    my @leftovers = $self->splice($self->{column_limit} * COLUMN_LIMIT);

    $self->push($self->{reduce_f}->(@leftovers));

    return $self;
}

sub cmd {
    my $self = shift;

    return $self->{__cmd} if $self->{__cmd};
    return unless $self->{entries};

    my @cmd;
    my @data;

    my $label = $self->{label} // '';
    $label .= (length $label ? '\n' : '') . $self->{global_label} if $self->{global_label};
    CORE::push @cmd, qq/set label "$label" at graph 0.02,0.98/ if length $label;

    CORE::push @cmd, qq/set xlabel '/ . ($self->{xlabel} // 'rounds') . qq/'/;
    CORE::push @cmd, qq/set ylabel '$self->{ylabel}'/ if length $self->{ylabel};
    CORE::push @cmd,  q/set grid xtics ytics/;
    CORE::push @cmd, qq/set term $self->{terminal}/ if $self->{terminal};

    my $xmax;

    if (exists $self->{xmax}) {
        $xmax = $self->{xmax};
    } elsif ($self->{type} eq 'linespoints' or $self->{type} eq 'histogram') {
        $xmax = $self->{rounds} + max(25, $self->{rounds} / 3);
    }

    if (defined $self->{y2label} and length $self->{y2label}) {
        CORE::push @cmd, qq/set y2label '$self->{y2label}'/;
        CORE::push @cmd,  q/set ytics nomirror/;
        CORE::push @cmd,  q/set y2tics/;
        CORE::push @cmd,  q/set yrange [0 : ]/;
        CORE::push @cmd,  q/set y2range [0 : ]/;
        CORE::push @cmd, qq/set x2range [0 : $xmax]/;
    }

    if ($self->{xtics}) {
        my $idx = 0;
        my @xtics = map { "'$_' " . $idx++ } @{$self->{xtics}};

        my $pick = 0;
        if ($self->{rounds} > 100) {
            @xtics = grep { not ($pick++ % 8) } @xtics;
        } elsif ($self->{rounds} > 50) {
            @xtics = grep { not ($pick++ % 4) } @xtics;
        } elsif ($self->{rounds} > 20) {
            @xtics = grep { not ($pick++ % 2) } @xtics;
        }

        CORE::push @cmd, 'set xtics (' .  join(', ', @xtics) .  ') rotate by -25';
    }

    if ($self->{type} eq 'linespoints') {
        CORE::push @cmd, qq/set style data linespoints/;
        CORE::push @cmd, q/set key autotitle reverse Left/;
        CORE::push @cmd, qq/plot [0:$xmax]\\/;
    } elsif ($self->{type} eq 'histogram') {
        CORE::push @cmd, q/set style data histograms/;
        CORE::push @cmd, q/set key invert autotitle reverse Left/;
        CORE::push @cmd, q/set style histogram rowstacked/;
        CORE::push @cmd, q/set style fill solid 1.00 border -1/;
        CORE::push @cmd, q/set yrange [0 : ]/;
        CORE::push @cmd, q/set xrange [-1 : ]/;
        CORE::push @cmd, qq/plot [-1:$xmax]\\/;
    } elsif ($self->{type} eq 'yerrorbars') {
        CORE::push @cmd, q/set key off/
            unless any { defined $_->{title} } @{$self->{entries}};

        CORE::push @cmd, q/set yrange [0 : ]/;
        CORE::push @cmd, qq/plot [-1:$xmax]\\/;
    } else {
        die "Unknown plot type '$self->{type}'";
    }

    my $valid_cnt = 0;
    foreach my $entry ($self->{type} eq 'histogram' ? reverse @{$self->{entries}} : @{$self->{entries}}) {
        next unless @{$entry->{__data}} > 0;

        my $using = $self->{type} eq 'histogram' ? ' using 2' : undef;
        my $title = length ($entry->{title} // '') ? " title '$entry->{title}'" : '';

        my $lc = exists $entry->{lc} && length $entry->{lc} ?
                    " lt rgb '#$entry->{lc}'" :
                    " lt rgb '#$line_colors[$valid_cnt % @line_colors]'";

        my $lw = length ($entry->{lw} // '') ? " lw $entry->{lw}" : undef;
        $lw = ' lw 3' if not defined $lw and $self->{type} eq 'linespoints';
        $lw = ' lw 4' if not defined $lw and $self->{type} eq 'yerrorbars';

        my $axes = length ($entry->{axes} // '') ? " axes $entry->{axes}" : undef;

        my $with = $self->{type} eq 'yerrorbars' ? ' with yerrorbars' : undef;

        CORE::push @cmd, qq/    '-'${using}${lc}${lw}${axes}${with}${title},\\/;

        foreach (0 .. $self->{rounds}-1) {
            if (not defined $entry->{__data}->[$_]) {
                if ($self->{type} eq 'histogram') {
                    CORE::push @data, qq/$_, 0/;
                }
            } elsif ($self->{type} eq 'yerrorbars') {
                CORE::push @data, join ', ',
                    $_,                                   # x
                   ($entry->{__data}->[$_]->[0] +
                    $entry->{__data}->[$_]->[1]) / 2,     # y
                    $entry->{__data}->[$_]->[0] // 0,     # ylow
                    $entry->{__data}->[$_]->[1] // 0      # yhigh
                        if defined $entry->{__data}->[$_]->[0] or
                           defined $entry->{__data}->[$_]->[1];
            } else {
                CORE::push @data, qq/$_, $entry->{__data}->[$_]/;
            }
        }

        CORE::push @data, qq/end '$entry->{title}'/;
        ++$valid_cnt;
    }

    return if @data == 0;

    $cmd[-1] =~ s/,\\$//;
    @cmd = (@cmd, @data);

    return @cmd if wantarray;
    return (join "\n", @cmd) . "\n";
}

sub json {
    my $self = shift;

    my $result = {};

    foreach (keys %{$self}) {
        $result->{$_} = $self->{$_}
            unless /^(__plotter|__cmd)$/ or
                ref $self->{$_} eq 'CODE';
    }

    return $result;
}

sub done_plotting {
    my $self = shift;
    $self->{__cmd} = $self->cmd;
    return ($self);
}

1;
