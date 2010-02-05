#!/bin/sh -e
tmpdir=sp-endurance-data-tmp-dir
report=$tmpdir/endurance-report

exit_cleanup ()
{
	rm -rf $tmpdir
}
trap exit_cleanup EXIT

# create data snapshots with sp-endurance tools
save-incremental-endurance-stats $tmpdir
save-incremental-endurance-stats $tmpdir
save-incremental-endurance-stats $tmpdir

# parse the snaphosts with sp-endurance-postproc tools
parse-endurance-measurements --report=$report $tmpdir/1*

# HTML report generation finished?
fgrep -q '</body>' $report.html
