Name: sp-endurance
Version: 3.0
Release: 1%{?dist}
Summary:  Memory usage reporting tools
Group: Development/Tools
License: GPLv2	
URL: http://www.gitorious.org/+maemo-tools-developers/maemo-tools/sp-endurance
Source: %{name}_%{version}.tar.gz
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-build
BuildRequires: python
# optional build dependencies required for X resource usage tracking
#BuildRequires: xorg-x11-devel xorg-x11-libX11-devel

Requires: lzop, sp-smaps-measure

%description
 Endurance measurement tools save system and process information from /proc
 and other places; the memory, file descriptors, X resources, flash space,
 errors in syslog etc.  The data can be later used to see logged application
 errors, memory usage and resource leakages and leakage trends under
 long time use-case.
      
%define is_x11 %{?_with_x11:1}%{!?_with_x11:0}

%prep
%setup -q -n sp-endurance

%build
make %{!?_with_x11: NO_X=1}

%install
rm -rf %{buildroot}
make install DESTDIR=%{buildroot} %{!?_with_x11: NO_X=1}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{_bindir}/proc2csv
%{_bindir}/sp-noncached
%{_bindir}/endurance-mem-overview
%{_bindir}/save-incremental-endurance-stats
%{_mandir}/man1/proc2csv.1.gz
%{_mandir}/man1/sp-noncached.1.gz
%{_mandir}/man1/endurance-mem-overview.1.gz
%{_mandir}/man1/save-incremental-endurance-stats.1.gz
%if %is_x11
    %{_bindir}/xmeminfo
    %{_mandir}/man1/xmeminfo.1.gz
%endif
%doc COPYING README

%package postproc
Summary: Postprocessing for endurance data
Group: Development/Tools
BuildArch: noarch
# HTML report generation dependencies
Requires: python, lzop
# graph report generation dependencies
#Requires: perl, gnuplot, netpbm
# misc helper script dependencies
#Requires: perl-List-MoreUtils, xz

%description postproc
 Postprocessing scripts to parse and generate a report from the endurance
 measurement data.  The report lists logged errors and resource usage
 between the data sets.  This can be used to find reasons (leakage)
 explaining why the device stops working when used for a longer time.
 It also provides error parser for the syslog files.

%files postproc
%defattr(-,root,root,-)
%{_bindir}/endurance_plot
%{_bindir}/endurance_report.py
%{_bindir}/syslog_parse.py
%{_bindir}/parse-endurance-measurements
%{_bindir}/split-endurance-measurements
%{_bindir}/extract-endurance-process-smaps
%{_bindir}/extract-endurance-process-cgroups
%{_bindir}/recompress-endurance-measurements
%{_mandir}/man1/endurance_plot.1.gz
%{_mandir}/man1/endurance_report.py.1.gz
%{_mandir}/man1/syslog_parse.py.1.gz
%{_mandir}/man1/parse-endurance-measurements.1.gz
%{_mandir}/man1/split-endurance-measurements.1.gz
%{_mandir}/man1/extract-endurance-process-smaps.1.gz
%{_mandir}/man1/recompress-endurance-measurements.1.gz
%{_datadir}/%{name}-postproc/
%{_datadir}/%{name}-postproc/logparser-syslog
%{_datadir}/%{name}-postproc/harmattan-syslog
%{_defaultdocdir}/%{name}-postproc/
%{_defaultdocdir}/%{name}-postproc/README
%{_defaultdocdir}/%{name}-postproc/endurance.pdf

%package tests
Summary: CI tests for sp-endurance
Group: Development/Tools
BuildArch: noarch
Requires: ci-testing, sp-endurance, sp-endurance-postproc

%description tests
 CI tests for sp-endurance

%files tests
%defattr(-,root,root,-)
 %{_datadir}/%{name}-tests
 

%changelog
* Tue Nov 22 2011 Eero Tamminen <eero.tamminen@nokia.com> 3.0
 * X support/dependency is optional in build, measuring and post-processing.
 * Endurance snapshot data is changed to store "xmeminfo" (X resource usage)
   and "df" (disk usage) output into separate files so that usage.csv
   contains just proc2csv output + data version/date info.

* Thu Oct 27 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.3
 * extract-endurance-process-cgroups:
   - New utility that can be used to extract process Cgroup information from
     endurance data. Produces results in either text or HTML format.
 * endurance_report.py:
   - Parse the DSME rich-core data that we collect and report process crashes.
   - Fix some endurance report creation failures with invalid/incomplete data.
 * endurance_plot:
   - New histogram plot `CPU time in state', that shows the distribution of
     CPU frequencies.
 * save-incremental-endurance-stats:
   - Collect `/sys/devices/system/cpu' recursively.
   - Collect `/sys/fs' recursively.
   - Collect `/var/lib/upstart/jobs_respawned'.
   - Collect `/proc/*/wchan'.
   - Collect kernel ring buffer content with `dmesg' if no syslogs found.

* Thu Oct 20 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.11
 * endurance_report.py:
   - Report now shows changes in Cgroup memory usage. Additionally, for each
     new process the Cgroup for the process is shown.
 * endurance_plot:
   - Small improvement in smaps data parsing performance.
   - Heap and #smaps plots are now dynamically divided into several subplots
     for improved readability.

* Thu Oct 06 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.10
 * endurance_plot:
   - Switch from ImageMagick to Netpbm for thumbnail generation. Improves
     performance on ARM.
   - Networking plots added.
   - Exit with non-zero return value on error.
   - Add support for XZ compressed smaps.cap.

* Wed Sep 07 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.9
 * endurance_report.py: improve report generation speed.
 * endurance_plot:
   - Visualize collected Cgroup information.
   - CPU utilization histogram added.

* Mon Aug 15 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.8
 * Fix the sp-endurance-postproc debian packaging to depend on perl instead of
   perl-base.

* Thu Jun 23 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.7
 * save-incremental-endurance-stats:
   - Collect /syspart recursively for Cgroup information.
   - Collect ramzswap statistics.

* Mon Jun 20 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.6
 * extract-endurance-process-smaps: fix bashisms, fix zero return value when
   no processes matching the user given string is found.
 * endurance_report.py: fix div-by-zero seen with incomplete smaps capture
   file
 * endurance_plot: new graphs, and several small fixes.

* Mon Apr 18 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.5
 * save-incremental-endurance-stats:
   - Collect /var/log/messages.
   - Collect /proc/pagetypeinfo.
   - If xprop or xmeminfo report a failure, give a warning about Xauthority
     settings.

* Fri Apr 15 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.4
  * endurance_report.py: fix disproportional graph visualization when using
    browser zoom

* Thu Apr 14 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.3
  * syslog_parse.py: fix kernel OOM message detection

* Mon Mar 07 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.2
  * extract-endurance-process-smaps accepts a subset of snapshot dirs
  * endurance_plot:
    - Fixed cases where endurance_plot used gigabytes of memory.
    - Battery information (bmestat) visualization.
    - Compressed swap (ramzswap) visualization.

* Mon Feb 28 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2.1
  * replace support for obsolete memory limits in old Maemo releases
    with hard-coded Linux kernel OOM limit (with dummy data output by
    proc2csv for compatiblity to old sp-endurance-postproc versions).
  * Replace the use of sysinfo-tool with sysinfoclient. 
  * Do not pass arguments to echo(1), they are not portable. 
  * Invoke df(1) with POSIX locale and "-k -P" for portability.
  * Add battery information to endurance data snapshot. 

* Wed Jan 19 2011 Eero Tamminen <eero.tamminen@nokia.com> 2.2
  * endurance_report.py: fix IndexError with more than 4 network interfaces.

* Tue Dec 28 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.9
  * save-incremental-endurance-stats: collect /proc/diskstats and
    /proc/zoneinfo. 
  * endurance_plot:
    - New IO plots based on /proc/diskstats.
    - Various small tweaks.

* Fri Dec 03 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.8
  * New post-processing tool `endurance_plot'. 
    - endurance_plot creates a large variety of (RAM, swap, CPU, X resource
      usage, interrupt, context switch etc) graphs from sp-endurance collected
      data for trend analysis.
  * Get bootreason from sysinfo. 
  * Fix proc2csv errors with long lines. 
  * Fix unnecessary sysinfoclient output parsing. 

* Wed Nov 17 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.7
  * Remove use of deprecated /proc/component_version and /proc/bootreason
    interfaces. 

* Tue Oct 26 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.6
  * endurance_report.py: track DRI2Drawable resource atom count changes.
  * save-incremental-endurance-stats: provide default value for DISPLAY.

* Thu Oct 21 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.5
  * xmeminfo: add support for new X resource types. This changes the CSV
    output format produced by xmeminfo.
  * xmeminfo: optionally report only specified atoms: add new parameter
    -a/-atom.
  * endurance_report.py: add support for new xmeminfo CSV format.
  * Add dependency to sysinfo-tool to fix useless release identification in
    usage.csv produced by save-incremental-endurance-stats. 

* Tue Oct 05 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.4
  * endurance_report.py: report change from initial state - 

* Tue Aug 31 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.3
  * endurance-mem-overview: take SwapCached into account.
  * endurance_report.py: Improve the heuristics for selecting processes for
    the 'Process memory usage' section:
        i) Prune processes that do not use any CPU ticks.
       ii) Include processes that used at least 0.5% of total CPU time during
           the first and last round.

* Mon Aug 23 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.2
  * Update save-incremental-endurance-stats for Harmattan. 

* Tue May 18 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1.1
  * Prominent notice about reboots in endurance reports. 

* Wed Apr 21 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.1
  * Handle X client names with commas and df filesystem usage output
    spanning multiple lines. 
  * Store focused/topmost application name if use-case step description
    is missing.  
  * Improved heuristics for removing memove graphs for non-interesting
    processes, with a fix for swap+dirty accounting and a new --show-all
    option to get graphs for all processes.  

* Fri Mar 05 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.0.3
  * Use "-a" option for ifconfig.  
  * Correct swap/page in/out, interrupt and context switch counts,
    they were 100x off. 

* Thu Jan 21 2010 Eero Tamminen <eero.tamminen@nokia.com> 2.0.2
  * Fix the post-processing exception when network interfaces are
    active, but have no traffic.  
  * Add CI test script.

* Thu Nov 12 2009 Eero Tamminen <eero.tamminen@nokia.com> 2.0.1
  * Do not mangle the last character in the process command line.
  * Proper error handling in case low memory limits are missing from the data.

* Fri Oct 30 2009 Eero Tamminen <eero.tamminen@nokia.com> 2.0
  * "proc2csv" stores the whole process command line; this makes the data
    format incompatible with older sp-endurance-postproc versions.
    , NB#144586
  * "endurance-mem-overview" takes swap into account and it's now possible
    to specify the shown memory usage range. 
  * Show X resource count differencies in addition to X resource memory usage
    in the summary at the end. 
  * Show network interface transfers graph in the beginning. 
  * Add "extract-endurance-process-smaps" helper script. 
  * Support Fremantle low memory limits scheme. 
  * Update documentation

* Tue Jun 09 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.24
  * Give more detailed X resource usage information and log use of unknown
    X resources. Data format change is incompatible with previous
    sp-endurance-postproc versions

* Tue Jun 09 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.23
  * Fix harmless Coverity reported leak on error exit + set freed
    namelist entries NULL in proc2csv. 

* Mon Jun 01 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.22
  * Fix divide-by-zero error on identical (copied) data. 

* Tue May 19 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.21
  * CPU/swap/interrups/context switch statistics added. 

* Tue May 05 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.20
  * Fix endurance_report.py to work with Scratchbox Python v2.3.

* Tue Apr 28 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.19
  * More statistics added. 
  * : sp-endurance/syslog parser doesn't catch upstart reported
    crash/restart messages
  * : sp-endurance uses obsolete /etc/osso_software_version

* Thu Apr 16 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.18
  * Add PSS and SWAP support to endurance_report.py

* Tue Mar 03 2009 Eero Tamminen <eero.tamminen@nokia.com> 1.17
  * Syslog parser now recognizes and reports D-BUS warnings about
    applications having too wide signal matching rules. 

* Thu Dec 04 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.16
  * The shared memory segment stats are now included in the main report
    page. 

* Thu Aug 21 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.15
  * Fixed a Lintian warning.

* Thu Aug 21 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.14
  * Remove support for SleepAVG as newer kernels don't support it.

* Wed Jun 25 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.13
  * The message output introduced by the fix in version 1.12 has been
    tweaked slightly.

* Wed Jun 25 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.12
  * Parse kernel BUG and onenand_wait issues. 

* Fri May 30 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.11
  * Compatibility issue with older endurance data was fixed. Fixes:
    NB#86013

* Wed Apr 30 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.10
  * Support for adding use-case test descriptions has been implemented.

* Wed Apr 16 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.9
  * Fixed broken detection of kernel OOM messages caused by change in
    case. 

* Fri Apr 04 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.8
  * Fixed endurance parsing failure when process smaps data had no
    private dirty memory. 

* Tue Apr 01 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.7
  * Fixed syslog rotation handling issue. 

* Fri Feb 22 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.6
  * Fixed empty DSME files not being handled gracefully. 

* Wed Feb 20 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.5
  * A rare warning message also triggered an exception in endurance
    report script. 

* Mon Jan 14 2008 Eero Tamminen <eero.tamminen@nokia.com> 1.4
  * save-incremental-endurance-stats: argument handling robustness has
    been improved. 

* Wed Nov 28 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.3
  * save-incremental-endurance-stats: when sp_smaps_snapshot is
    missing, produces (about) same data with few lines of shell
  * parse-endurance-measurements: handle compressed smaps files
  * endurance_report.py: show smaps private-dirty information
    in application memory usage graphs
  * update/fix README

* Tue Nov 06 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.2
  * save-incremental-endurance-stats: save open file descriptors,
    use proc2csv in permissive mode so that also non-root can get
    data required in postprocessing. 
  * endurance_report.py: link open-fds and smaps.cap files, include
    SwapCached to system free and show swap change in summary,
    show differences in process thread counts
  * compress smaps.cap in save-incremental-endurance-stats and
    handle that in endurance_report.py. 
  * endurance_report.py: Fail more gracefully when encountering mixed-
    version endurance data. 

* Tue Oct 02 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.18
  * syslog_parse.py: handle syslog read failures gracefully.
    Fix to 66123 got dates in Glib errors duplicated, fixed.

* Fri Aug 31 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.17
  * Added a missing a comma in a dictionary declaration at
    syslog_parse.py. 

* Thu Jul 12 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.16
  * Include day to the errors parsed from syslog. 

* Thu Jul 12 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.15
  * Parse bootup reason from syslog. 

* Thu May 24 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.14
  * Parse kernel I/O errors from syslog

* Wed May 09 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.13
  * Have complete license text in the source package instead of just
    referring to system GPL-2 license file. Add copyright and license
    information to manpages. 

* Thu May 03 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.12
  * Sort resource usage tables according to changes, not total
  * Fix to python exception in get_pid_usage_diffs()

* Thu Apr 26 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.11
  * Ignore all resources (i.e. also private memory and FDs)
    used by extra threads processes have. 
  * Add endurance-mem-overview Awk script giving a quick memory usage
    overview ASCII-graph from the endurance data which can be run on
    the target device (as it doesn't need Python)

* Tue Apr 17 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.10
  * List also changes in kernel threads and zombie processes
  * Fold the script save-incremental-endurance-stats calls back
  * Fix to new thread ignore code. 

* Mon Apr 16 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.9
  * Do not ignore any processes, even my own
  * Cope with missing SMAPS data in endurance_report.py. 

* Thu Apr 12 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.8
  * Fix how threads are indentified for removal from memory usage graphs.

* Wed Apr 04 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.7
  * Added manual pages for all the tools and include README to postproc
    binary package. 

* Tue Mar 13 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.6
  * endurance script now parses amount of dirty code pages from smaps
    data (which indicates incorrectly compiled libraries) and there's
    a separate sum-dirty-code-pages script for doing the same on the device

* Thu Mar 01 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.5
  * syslog_parse.py: Check each syslog line for all recognized messages
    in case device boots in middle of line and check SysRq messages
  * endurance_report.py: Do not show bars for repeating process memory
    values and sort processes better, cleanup SMAPS parsing
  * *.sh: Remove file name extension to make Lintian happy
  * Add sum-smaps-private and split-endurance-measurements scripts
  * sp-smaps-measure is now also optional
  * Prepare for Open Source release, add proper copyrights etc

* Thu Feb 08 2007 Eero Tamminen <eero.tamminen@nokia.com> 1.1.4
  * Parse private/dirty values from SMAPS data myself instead of relying
    on sp-smaps-visualize as it was way too slow
  * Add several options to parse-endurance-measurements.sh for controlling
    which measurements are parsed, whether to call sp-smaps-visualize and
    whether to split reports at reboots
  * Further improvements to the memory usage graphs

* Tue Dec 20 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.1.3
  * Ignore immediately repeated errors in error counts
  * Fix error message that gave Python exeption
  * Show FS usage instead of free (as the table title says)
  * Major improvements and fixes to process memory usage graphs
  * Use tables for colorbars instead of images so that
    the HTML can be attached to mails or bugzilla

* Wed Dec 20 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.1.2
  * Fix another bug in case syslogs didn't have any errors
  * Parse Glib ERRORs + kernel OOMs and alloc denials from syslog
  * Add contents list to error HTML file
  * Don't remove SMAPS diff file

* Tue Nov 28 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.1.1
  * Fix bug in case syslogs didn't have any errors

* Fri Nov 24 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.1
  * Packaging:
    - devel package, postproc is "Architecture: all" + relevant rules fixes
  * Measurements:
    - compress whole syslog and remove syslog grepping
    - save the measurement files in to separate directories
    - proc2csv parses also /proc/vmstat
    - add /sbin/ifconfig and interrupts/slabinfo/stat files from /proc
    - save DSME statistics
  * Syslog errors postprocessing:
    - separated syslog parsing to separate syslog_parse.py file so that
      it can be used also standalone
    - parse normal/separate syslog files instead of CSV endurance file
    - add support for gzipped syslog files
    - separate different types of DSME and Glib errors
    - parse and count kernel Oopses, reboots, DSP errors and
      connectivity errors&warnings from syslogs
    - support both HTML and ASCII output
    - parsing debug option
    - error summary
    - fix bug in syslog parsing with appended syslogs
  * SMAPS data parsing:
    - Don't redo SMAPS CSV files if they already exist
  * Other endurance data postprocessing:
    - rename endurance-report.py to endurance_report.py
    - always print error message before failing exit
    - arguments are directories instead of file names
    - syslog data is now parsed from file separate from the CSV file
      and parsing put the separate file (see above)
    - output disk free changes (for '/' and '/tmp')
    - show whole device /proc/sys/fs/file-nr changes
    - output also X resource usage decreases
    - save errors to separate HTML pages
    - output statistics and summary of different error types
    - output summary of disk/memory/X resource/FD usage changes
    - add process changed/total counts with started/exited processes
      listed side by side
    - remove "sleep" from all the lists
    - color code tables containing different data
    - add change totals to all tables
    - HTML comment summary of all statistics for maturity metrics
    - parse process statistics from /proc/PID/status files
    - add bars of RSS memory changes per process (for processes
      which max. RSS usage changes between tests)
    - add contents and otherwise fine-tune report output
  * Documentation:
    - Update README according to changes

* Thu Sep 14 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-7
  * save also full syslog and /proc/slabinfo data
  * shows the warnings from syslog although syslogs don't seem to match
  * fix to Browser X client name idiocy

* Thu Jul 06 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-6
  * fix bug in memory calculation introduced by last update

* Fri Jun 09 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-5
  * I fixed a bug that didn't always handle correctly processes that exited when proc2csv was running
  * now also takes the memory limits from /proc i.e. the bargraphs take now also swap into account

* Tue May 16 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-4
  * With this you'll get again correct names in the report for
    the maemo-launched binaries (smaps diff never before contained them,
    but earlier my own script could map the names itself because earlier
    diff file used real PIDs)

* Thu May 04 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-3
  * Updated endurance parser to support the new smaps format 

* Thu May 04 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-2
  * Updated package to include changes to path's in script
  * Removed .svn dirs
  * Improved README
  * changelog
  * debian/changelog

* Fri Mar 24 2006 Eero Tamminen <eero.tamminen@nokia.com> 1.0-1
  * Initial release 
