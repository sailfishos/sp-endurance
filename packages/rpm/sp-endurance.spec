Name: sp-endurance
Version: 2.2.11
Release: 1%{?dist}
Summary:  memory usage reporting tools
Group: Development/Tools
License: GPLv2	
URL: http://www.gitorious.org/+maemo-tools-developers/maemo-tools/sp-endurance
Source: %{name}_%{version}.tar.gz
BuildRoot:	%{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
#BuildRequires: xorg-x11-devel xorg-x11-libX11-devel

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
%defattr(755,root,root,-)
%{_bindir}/proc2csv
%{_bindir}/endurance-mem-overview
%{_bindir}/save-incremental-endurance-stats
%defattr(644,root,root,-)
%{_mandir}/man1/proc2csv.1.gz
%{_mandir}/man1/endurance-mem-overview.1.gz
%{_mandir}/man1/save-incremental-endurance-stats.1.gz
%if %is_x11
    %defattr(755,root,root,-)
    %{_bindir}/xmeminfo
    %defattr(644,root,root,-)
    %{_mandir}/man1/xmeminfo.1.gz
%endif
%doc COPYING README

%package postproc
Summary: Postprocessing for endurance data
Group: Development/Tools
BuildArch: noarch

%description postproc
 Postprocessing scripts to parse and generate a report from the endurance
 measurement data.  The report lists logged errors and resource usage
 between the data sets.  This can be used to find reasons (leakage)
 explaining why the device stops working when used for a longer time.
 It also provides error parser for the syslog files.

%files postproc
%defattr(755,root,root,-)
%{_bindir}/endurance_plot
%{_bindir}/endurance_report.py
%{_bindir}/syslog_parse.py
%{_bindir}/parse-endurance-measurements
%{_bindir}/split-endurance-measurements
%{_bindir}/extract-endurance-process-smaps
%{_bindir}/extract-endurance-process-cgroups
%defattr(644,root,root,-)
%{_mandir}/man1/endurance_plot.1.gz
%{_mandir}/man1/endurance_report.py.1.gz
%{_mandir}/man1/syslog_parse.py.1.gz
%{_mandir}/man1/parse-endurance-measurements.1.gz
%{_mandir}/man1/split-endurance-measurements.1.gz
%{_mandir}/man1/extract-endurance-process-smaps.1.gz
%{_datadir}/%{name}-postproc/logparser-config
%{_datadir}/%{name}-postproc/harmattan
%{_defaultdocdir}/%{name}-postproc/README

%package tests
Summary: CI tests for sp-endurance
Group: Development/Tools

%description tests
 CI tests for sp-endurance

%files tests
%defattr(-,root,root,-)
 %{_datadir}/%{name}-tests
 
