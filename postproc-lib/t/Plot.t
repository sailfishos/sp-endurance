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
use Data::Dumper;
use strict;

BEGIN { use_ok('SP::Endurance::Plotter'); }
BEGIN { use_ok('SP::Endurance::Plot');    }

my $plotter = SP::Endurance::Plotter->new(
    global_label => 'SW=ABC_1.2.3\nHW=DEF-123',
    rounds => 3,
);

{
    my $plot = $plotter->new_linespoints(
        label => 'System-level memory 1',
    );
    $plot->push(
        [ 1, 2, 3 ],
        lw => 3,
        lc => 'FFFFFF',
        title => 'Swap Used',
    );

    my @cmds = $plot->cmd();
    like($cmds[-6], qr/plot \[\d+:\d+\]\\/, '1x entry - check plot [...]');
    is_deeply([@cmds[-5 .. -1]],
        [
            q/    '-' lt rgb '#FFFFFF' lw 3 title 'Swap Used'/,
            q/0, 1/,
            q/1, 2/,
            q/2, 3/,
            q/end 'Swap Used'/,
        ],
        '1x entry - check plotting command and inline data');

    my $cmd = $plot->cmd;
    like($cmd, qr/^end 'Swap Used'/m, '1x entry - check "end Swap Used" in scalar context');
    like($cmd, qr/^set label "System-level memory 1\\nSW=ABC_1.2.3\\nHW=DEF-123"/m, 'check label');

    is_deeply($plot->json, {
        entries => [
            {
                __data => [1,2,3],
                lw => 3,
                lc => 'FFFFFF',
                title => 'Swap Used',
            },
        ],
        type => 'linespoints',
        rounds => 3,
        label => 'System-level memory 1',
        global_label => 'SW=ABC_1.2.3\\nHW=DEF-123',
    }, '1x entry - linespoints - check json');
}

{
    my $plot = $plotter->new_linespoints(
        label => 'System-level memory 1',
    );
    $plot->push(
        [ 1, 2, 3 ],
        lw => 3,
        lc => 'FFFFFF',
        title => 'Swap Used',
    );
    $plot->push(
        [ 4, 5, 6 ],
        lw => 6,
        lc => '000000',
        title => 'Cached',
    );

    my @cmds = $plot->cmd;
    like($cmds[-11], qr/plot \[\d+:\d+\]\\/, '2x entry - check plot [...]');
    is_deeply([@cmds[-10 .. -1]],
        [
            q/    '-' lt rgb '#FFFFFF' lw 3 title 'Swap Used',\\/,
            q/    '-' lt rgb '#000000' lw 6 title 'Cached'/,
            q/0, 1/,
            q/1, 2/,
            q/2, 3/,
            q/end 'Swap Used'/,
            q/0, 4/,
            q/1, 5/,
            q/2, 6/,
            q/end 'Cached'/,
        ],
        '2x entry - check plotting command and inline data');

    like($plot->cmd, qr/end 'Cached'$/, '2x entry - cmd return value ends with "end Cached" in scalar context');

    is_deeply($plot->json, {
        entries => [
            {
                __data => [1,2,3],
                lw => 3,
                lc => 'FFFFFF',
                title => 'Swap Used',
            },
            {
                __data => [4,5,6],
                lw => 6,
                lc => '000000',
                title => 'Cached',
            },
        ],
        type => 'linespoints',
        rounds => 3,
        label => 'System-level memory 1',
        global_label => 'SW=ABC_1.2.3\\nHW=DEF-123',
    }, '2x entry - linespoints - check json');
}

{
    my $plot = $plotter
        ->new_linespoints
        ->push([ 1, undef, 3 ]);

    my @cmds = $plot->cmd;
    is_deeply([@cmds[-3 .. -1]],
        [
            q/0, 1/,
            q/2, 3/,
            q/end ''/,
        ],
        'undef in linespoints data');
}

{
    my @cmds = $plotter
        ->new_linespoints
        ->push([ 100, 100, 1 ])
        ->push([ 100, 100, 1 ])
        ->scale(to => 100)
        ->cmd;

    is_deeply([@cmds[-8,-7,-6,-4,-3,-2]],
        [
            q/0, 50/, q/1, 50/, q/2, 50/,
            q/0, 50/, q/1, 50/, q/2, 50/,
        ],
        'scale(to => 100): 3 columns');
}

{
    my @cmds = $plotter
        ->new_linespoints
        ->push([ 100, 0 ])
        ->push([ 100, 100 ])
        ->scale(to => 100)
        ->cmd;

    is_deeply([@cmds[-6,-5,-3,-2]],
        [
            q/0, 50/, q/1, 0/,
            q/0, 50/, q/1, 100/,
        ],
        'scale(to => 100): 2 columns, zero in one cell');
}

{
    my @cmds = $plotter
        ->new_linespoints
        ->push([ 100, undef ])
        ->push([ 100, 1000 ])
        ->scale(to => 100)
        ->cmd;

    is_deeply([@cmds[-5,-3,-2]],
        [
            q/0, 50/,
            q/0, 50/, q/1, 100/,
        ],
        'scale(to => 100): 2 columns, undef in one cell');
}

{
    my @cmds = $plotter
        ->new_linespoints
        ->push([ 1, undef, 1 ])
        ->push([ 1, undef, 1 ])
        ->scale(to => 10)
        ->cmd;

    #print STDERR Dumper(\@cmds);
    is_deeply([@cmds[-6,-5,-3,-2]],
        [
            q/0, 5/, q/2, 5/,
            q/0, 5/, q/2, 5/,
        ],
        'scale(to => 100): 3 columns, undefs in one column');
}

{
    my @cmds = $plotter
        ->new_linespoints
        ->push([ 10 ])
        ->push([ 10, 1000 ])
        ->scale(to => 100)
        ->cmd;

    #print STDERR Dumper(\@cmds);
    is_deeply([@cmds[-5,-3,-2]],
        [
            q/0, 50/,
            q/0, 50/, q/1, 100/,
        ],
        'scale(to => 100): 2 columns, one partial');
}

{
    my @cmds = $plotter
        ->new_linespoints(exclude_nonchanged => 1)
        ->push([ undef, undef, undef ])
        ->push([ 0, 0, 0 ])
        ->push([ 10, 10, 10 ])
        ->cmd;

    is_deeply(\@cmds, [], 'exclude_nonchanged => 1: 3x nonchanged entries');
}

{
    my $plot = $plotter
        ->new_linespoints
        ->push([ 1, 2, 3 ])
        ->push([ 99.99, 88.88, 77.77,
                # extra entries:
                123,123,123,123,123,123,123,123 ])
        ->push(undef)
        ->push([]);

    my @cmds = $plot->cmd;
    like($cmds[-11], qr/^plot \[\d+:\d+\]\\/, '1x entry - check plot [...]');
    like($cmds[-10], qr/^    '-' lt rgb '#\S{6}' lw 3,\\/, '1x entry - check plot arg 1');
    like($cmds[-9],  qr/^    '-' lt rgb '#\S{6}' lw 3/,    '1x entry - check plot arg 2');
    is_deeply([@cmds[-8 .. -1]],
        [
            q/0, 1/,
            q/1, 2/,
            q/2, 3/,
            q/end ''/,
            q/0, 99.99/,
            q/1, 88.88/,
            q/2, 77.77/,
            q/end ''/,
        ],
        '2x valid, 2x invalid entry - check plotting command and inline data');
}

{
    my $plot = $plotter
        ->new_linespoints(
            label => 'label here',
            xlabel => 'xlabel here',
            ylabel => 'ylabel here',
            xtics => [
                'xtick one',
                'xtick two',
                'xtick three',
            ],
        )
        ->push([ 1, 2, 3 ], lc => '123DEF');

    my $cmd = $plot->cmd;
    like($cmd, qr/'-' lt rgb '#123DEF' lw 3/);
    like($cmd, qr/^set label "label here/m, 'set label');
    like($cmd, qr/^set xlabel 'xlabel here'/m, 'set xlabel');
    like($cmd, qr/^set ylabel 'ylabel here'/m, 'set ylabel');
    like($cmd, qr/^set xtics \('xtick one' 0, 'xtick two' 1, 'xtick three' 2\)/m, 'set xtics');
}

{
    my $plot = $plotter
        ->new_yerrorbars(
            xmax => 10,
        )
        ->push([ [0,2], [2,4], [4,6] ]);

    my $cmd = $plot->cmd;
    like($cmd, qr/ with yerrorbars/m, 'with yerrorbars');
    like($cmd, qr/^plot \[-1:10\]\\$/m, 'xmax => 10');
    like($cmd, qr/^0, 1, 0, 2$/m, 'data entry 0');
    like($cmd, qr/^1, 3, 2, 4$/m, 'data entry 1');
    like($cmd, qr/^2, 5, 4, 6$/m, 'data entry 2');

    is_deeply($plot->json, {
        entries => [
            {
                __data => [ [0,2], [2,4], [4,6] ],
            },
        ],
        xmax => 10,
        type => 'yerrorbars',
        rounds => 3,
        global_label => 'SW=ABC_1.2.3\\nHW=DEF-123',
    }, '1x entry - yerrorbars - check json');
}

done_testing;
# vim: ts=4:sw=4:et
