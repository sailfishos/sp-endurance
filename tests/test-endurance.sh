#!/bin/sh -e
tmpdir=sp-endurance-data-tmp-dir
report=$tmpdir/endurance-report

exit_cleanup ()
{
	rm -rf $tmpdir
}
trap exit_cleanup EXIT

# create data snapshots with sp-endurance tools
endurance-snapshot $tmpdir
endurance-snapshot $tmpdir
endurance-snapshot $tmpdir

# parse the snaphosts with sp-endurance-postproc tools
endurance-parse-snapshots --report=$report $tmpdir/[0-9][0-9][0-9]

# HTML report generation finished?
fgrep -q '</body>' $report.html
