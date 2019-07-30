Name: sp-endurance
Version: 4.3.0
Release: 1
Summary:  Memory usage reporting tools
Group: Development/Tools
License: GPLv2+
URL: https://github.com/mer-tools/sp-rich-core
Source: %{name}-%{version}.tar.gz
BuildRequires: python
Requires: lzop
Requires: sp-smaps
Requires: mce-tools
Requires: findutils
# awk used by measure/endurance-mem-overview and measure/endurance-snapshot
Requires: gawk
# which is used by measure/endurance-mem-overview
Requires: which

%description
 Endurance measurement tools save system and process information from /proc
 and other places; the memory, file descriptors, X resources, flash space,
 errors in syslog etc.  The data can be later used to see logged application
 errors, memory usage and resource leakages and leakage trends under
 long time use-case.
      
%define is_x11 %{?_with_x11:1}%{!?_with_x11:0}

%prep

%setup -q

%build
make %{!?_with_x11: NO_X=1}

%install
rm -rf %{buildroot}
make install DESTDIR=%{buildroot} DOCDIR=%{_defaultdocdir} %{!?_with_x11: NO_X=1}
make install-compat-symlinks DESTDIR=%{buildroot}
# Remove common Perl files which we don't package
rm -f $RPM_BUILD_ROOT%{perl_archlib}/perllocal.pod
rm -f $RPM_BUILD_ROOT%{perl_vendorarch}/auto/SP/Endurance/.packlist

mkdir -p $RPM_BUILD_ROOT%{_docdir}/%{name}-%{version}
install -m0644 README $RPM_BUILD_ROOT%{_docdir}/%{name}-%{version}

%clean
rm -rf %{buildroot}

%files
%defattr(-,root,root,-)
%{_bindir}/proc2csv
%{_bindir}/sp-noncached
%{_bindir}/endurance-mem-overview
%{_bindir}/endurance-snapshot
# This is the compat symlink:
%{_bindir}/save-incremental-endurance-stats
# ...
%if %is_x11
    %{_bindir}/xmeminfo
%endif
%license COPYING

%package postproc
Summary: Postprocessing for endurance data
Group: Development/Tools
BuildArch: noarch
BuildRequires: perl(ExtUtils::MakeMaker)
# HTML report generation dependencies
Requires: python
Requires: lzop
Requires: gnuplot
Requires: netpbm-progs
Requires: perl
Requires: perl(JSON)
Requires: perl(JSON::XS)
# which is used by syslog_parse.py, endurance-parse-snapshots and
# endurance-extract-process-smaps
Requires: which

%description postproc
 Postprocessing scripts to parse and generate a report from the endurance
 measurement data.  The report lists logged errors and resource usage
 between the data sets.  This can be used to find reasons (leakage)
 explaining why the device stops working when used for a longer time.
 It also provides error parser for the syslog files.

%files postproc
%defattr(-,root,root,-)
%{_bindir}/endurance-plot
%{_bindir}/endurance-multiplot
%{_bindir}/endurance-report
%{_bindir}/endurance-parse-snapshots
%{_bindir}/endurance-split-snapshots
%{_bindir}/endurance-extract-process-smaps
%{_bindir}/endurance-extract-process-cgroups
%{_bindir}/endurance-recompress-snapshots
%{_bindir}/syslog_parse.py
# These are the compat symlinks:
%{_bindir}/endurance_plot
%{_bindir}/endurance_report.py
%{_bindir}/parse-endurance-measurements
%{_bindir}/split-endurance-measurements
%{_bindir}/extract-endurance-process-smaps
%{_bindir}/extract-endurance-process-cgroups
%{_bindir}/recompress-endurance-measurements
# ...
%{perl_vendorlib}/SP/
%{_datadir}/%{name}-postproc/
%{_defaultdocdir}/%{name}-postproc/

%package tests
Summary: CI tests for sp-endurance
Group: Development/Tools
BuildArch: noarch
Requires: sp-endurance
Requires: sp-endurance-postproc
# From mer-qa project
Requires: blts-tools

%description tests
 CI tests for sp-endurance

%files tests
%defattr(-,root,root,-)
%{_datadir}/%{name}-tests/

%package doc
Summary:   Documentation for %{name}
Group:     Documentation
Requires:  %{name} = %{version}-%{release}

%description doc
Man pages for %{name}.

%files doc
%defattr(-,root,root,-)
%{_mandir}/man*/*.*
%{_docdir}/%{name}-%{version}
