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

use Data::Dumper;
use Test::More;

eval 'use common::sense';
use strict;
no warnings;

BEGIN {
    use_ok('SP::Endurance::Util', qw/b2mb kb2mb nonzero has_changes max_change
        uptimes cumulative_to_changes change_per_second/);
}

foreach ([[], []],
         [[1*1024*1024], [1]],
         [[1*1024*1024, 1*1024*1024], [1, 1]],
         [[0, 256*1024*1024, 1*1024*1024, 2*1024*1024], [0, 256, 1, 2]],
         [[0, undef, 1*1024*1024, undef], [0, undef, 1, undef]],
         #[['a'], [0]],
         ) {
    my @input = @{$_->[0]};
    my @expected = @{$_->[1]};
    my @got = b2mb @input;
    is_deeply(\@got, \@expected,
        'b2mb(' . join(', ', @input) . ')' .
        ' => (' . join(', ', @got) . ')');
}

foreach ([[], []],
         [[1*1024], [1]],
         [[1*1024, 1*1024], [1, 1]],
         [[0, 256*1024, 1*1024, 2*1024], [0, 256, 1, 2]],
         [[0, undef, 1*1024, undef], [0, undef, 1, undef]],
         #[['a'], [0]],
         ) {
    my @input = @{$_->[0]};
    my @expected = @{$_->[1]};
    my @got = kb2mb @input;
    is_deeply(\@got, \@expected,
        'kb2mb(' . join(', ', @input) . ')' .
        ' => (' . join(', ', @got) . ')');
}

foreach ([[0], []],
         [[undef], []],
         [[0,0], []],
         [[undef,0,0], []],
         [[0,1,undef], [0,1,undef]],
         [[undef,123123,0,321321], [undef,123123,0,321321]],
         ) {
    my @input = @{$_->[0]};
    my $expected = $_->[1];
    my @got = nonzero @input;
    is_deeply(\@got, $expected,
        'nonzero(' . join(', ', @input) . ')' .
        ' => (' . join(', ', @got) . ')');
}

foreach ([[], []],
         [[undef], [undef]],
         [[1], [undef]],
         [[1,1], [undef,0]],
         [[1,2], [undef,1]],
         [[1,1,1], [undef,0,0]],
         [[1,2,3], [undef,1,1]],
         [[1,2,3,4,5], [undef,1,1,1,1]],
         [[1,2,3,undef,undef], [undef,1,1,undef,undef]],
         [[1,undef,3], [undef,undef,undef]],
         [[undef,1,2], [undef,undef,1]],
         [[undef,1,2,undef,3,4,5], [undef,undef,1,undef,undef,1,1]],
         [[1,2,3,1,2,3], [undef,1,1,undef,1,1]],
         ) {
    my @input = @{$_->[0]};
    my @expected = @{$_->[1]};
    my @got = cumulative_to_changes @input;
    is_deeply(\@got, \@expected,
        'cumulative_to_changes(' . join(', ', @input) . ')' .
        ' => (' . join(', ', @got) . ')');
}

foreach ([[], 0-0],
         [[undef], 0-0],
         [[1], 1-1],
         [[1,1], 1-1],
         [[1,2], 2-1],
         [[10,undef], 10-0],
         [[10,0], 10-0],
         [[10,1], 10-1],
         [[1,10], 10-1],
         [[1,1,1], 1-1],
         [[1,2,3], 3-1],
         [[3,2,1], 3-1],
         [[1,2,3,4,5], 5-1],
         [[1,2,3,undef,undef], 3-0],
         [[1,undef,3], 3-0],
         [[undef,1,2], 2-0],
         [[undef,1,2,undef,3,4,5], 5-0],
         ) {
    my $input    = $_->[0];
    my $expected = $_->[1];
    my $got = max_change $input;
    is($got, $expected, 'max_change(' . join(', ', @$input) . ") => $got");
}

{
    my $masterdb = [
        { '/proc/uptime' => { uptime => 0  }, },
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 20 }, },
        { '/proc/uptime' => { uptime => 40 }, },
        { '/proc/uptime' => { uptime => 50 }, },
    ];

    my @uptimes = uptimes $masterdb;
    is_deeply(\@uptimes, [undef, 10-0, 20-10, 40-20, 50-40], 'uptimes() - 5x /proc/uptime entries');
}

{
    my $masterdb = [
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 10 }, },
    ];

    my @uptimes = uptimes $masterdb;
    is_deeply(\@uptimes, [undef, 0, 0, 0], 'uptimes() - 4x /proc/uptime entries');
}

{
    my $masterdb = [
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 0  }, },
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 20 }, },
    ];

    my @uptimes = uptimes $masterdb;
    is_deeply(\@uptimes, [undef, undef, 10-0, 20-10], 'uptimes() - 4x /proc/uptime entries, 1x reboot');
}

{
    my $masterdb = [
        { '/proc/uptime' => { uptime => 40 }, },
        { '/proc/uptime' => { uptime => 30 }, },
        { '/proc/uptime' => { uptime => 20 }, },
        { '/proc/uptime' => { uptime => 10 }, },
    ];

    my @uptimes = uptimes $masterdb;
    is_deeply(\@uptimes, [undef, undef, undef, undef], 'uptimes() - 4x /proc/uptime entries, reboots');
}

{
    my $masterdb = [
        { '/proc/uptime' => { uptime => 0  }, },
        { '/proc/uptime' => { uptime => 10 }, },
        { '/proc/uptime' => { uptime => 20 }, },
        { '/proc/uptime' => { uptime => 40 }, },
        { '/proc/uptime' => { uptime => 50 }, },
    ];

    foreach ([[],                        []],
             [[undef],                   [undef]],
             [[undef,undef],             [undef,undef]],
             [[0],                       [undef]],
             [[1],                       [undef]],
             [[0,0],                     [undef,0]],
             [[1,10],                    [undef,10/10]],
             [[1,20],                    [undef,20/10]],
             [[1,10,10],                 [undef,10/10,10/10]],
             [[1,2000,10,40],            [undef,2000/10,10/10,40/20]],
             [[0,0,0,0],                 [undef,0,0,0]],
             [[undef,20,30,undef,undef], [undef,20/10,30/10,undef,undef]],
             [[10,undef,30],             [undef,undef,30/10]],
             [[undef,10,undef],          [undef,10/10,undef]],
             [[undef,10,20,undef,400],   [undef,10/10,20/10,undef,400/10]],
             [[10,20,30,20,20],          [undef,20/10,30/10,20/20,20/10]],
             ) {
        my @input = @{$_->[0]};
        my @expected = @{$_->[1]};
        my @got = change_per_second $masterdb, @input;
        is_deeply(\@got, \@expected,
            'change_per_second(' . join(', ', @input) . ')' .
            ' => (' . join(', ', @got) . ')');
    }
}

done_testing;
# vim: ts=4:sw=4:et
