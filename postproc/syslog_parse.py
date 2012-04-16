#!/usr/bin/python
# vim: et:ts=4:sw=4:
#
# This file is part of sp-endurance.
#
# Copyright (C) 2006-2009,2011 by Nokia Corporation
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
#
# CHANGES:
# - See git and project changelog file.

"""
NAME
        <TOOL_NAME>

SYNOPSIS
        <TOOL_NAME> <syslog1> [syslog2 ...]

DESCRIPTION

This script parses different kinds of issues from given syslog files, and gives
a report in textual format. The detection is based on a separate configuration
file that contains the patterns to match from the syslogs.

EXAMPLES
        <TOOL_NAME> syslog1 | less
"""

import sys, os, re, string, gzip

# Config syntax:
# [category/sub-category] "Optional human-readable description"
# regular-expression1-for-matching-these-items
# regular-expression2-for-matching-these-items
# ...

class LogParserConfig:
    categories = []
    regexps = []
    category_description = {}
    DEFAULT_CONFIG_SYSLOG = "/usr/share/sp-endurance-postproc/logparser-syslog"
    def __init__(self, configfile):
        conf = open(configfile)
        for line in conf:
            line = line.strip()
            if not line:
                continue
            if line[0] == '#':
                continue
            m = re.search("^\[(\S+)\]\s*\"(.*)\"", line)
            if m:
                cat, desc = m.groups()
                if cat in self.categories:
                    raise RuntimeError("Category '%s' was already specified: '%s'" % (cat, line))
                self.categories.append(cat)
                try:
                    self.category_description[cat] = desc
                except IndexError: pass
                continue
            m = re.search("^\[(\S+)\]$", line)
            if m:
                self.categories.append(m.group(1))
                continue
            try:
                regexp = re.compile(line)
            except re.error, e:
                raise RuntimeError("Invalid regular expression: '%s': %s" % (line, e.message))
            except: pass
            if not regexp:
                raise RuntimeError("Invalid regular expression: '%s'" % line)
            self.regexps.append((regexp, self.categories[-1]))
        conf.close()

def get_errors_by_category(logfile, regexps, category_max = 1000):
    errors_by_category = {}
    for line in logfile:
        if line[-1] == '\n': line = line.rstrip()
        for (regexp, category) in regexps:
            if regexp.search(line):
                if not category in errors_by_category:
                    errors_by_category[category] = []
                errors_by_category[category].append(line)
                if len(errors_by_category[category]) > category_max:
                    errors_by_category[category].pop(0)
                break
    return errors_by_category


def open_compressed(filename):
    """Open potentially compressed file and return its name and handle.
       First checks whether there is a compressed version
       of the file and if not, assumes file to be non-compressed.
       May throw e.g. RuntimeError in case of problems.
    """
    for suffix in ("", ".gz", ".lzo", ".xz"):
        tmp = filename + suffix
        if os.path.exists(tmp):
            filename = tmp
            break

    if not os.path.exists(filename):
        raise RuntimeError("%s missing" % filename)

    if filename.endswith(".gz"):
        # Unfortunately the python gzip module is slow. Using /bin/zcat and
        # popen() gives 2-3x speed up.
        if os.system("which zcat >/dev/null") == 0:
            file = os.popen("zcat '%s'" % filename)
        else:
            file = gzip.open(filename, "r")

    elif filename.endswith(".lzo"):
        if os.system("which lzop >/dev/null") == 0:
            file = os.popen("lzop -dc '%s'" % filename)
        else:
            raise RuntimeError("file '%s' was compressed with lzop, but decompression program not available" % filename)

    elif filename.endswith(".xz"):
        if os.system("which xzcat >/dev/null") == 0:
            file = os.popen("xzcat '%s'" % filename)
        else:
            raise RuntimeError("file '%s' was compressed with XZ, but decompression program not available" % filename)

    else:
        file = open(filename, "r")

    return file, filename

def __output_text_report(files, config):
    print "Syslog report"
    print "============="
    for path in files:
        print
        print path
        print "-" * len(path)
        try:
            syslog_file = open_compressed(path)[0]
        except RuntimeError, e:
            print >>sys.stderr, "ERROR: unable to open '%s': %s" % \
                    (path, str(e))
            sys.exit(1)
        errors_by_category = get_errors_by_category(syslog_file, config.regexps)
        if not errors_by_category:
            print
            print "No notifiable log items identified."
            continue
        for category in config.categories:
            if not category in errors_by_category or len(errors_by_category[category]) <= 0:
                continue
            if category in config.category_description and config.category_description[category]:
                print "[%s] %s:" % (category, config.category_description[category])
            else:
                print "[%s]:" % category
            for message in errors_by_category[category]:
                print message
            print ""
        print "Summary:"
        print "--------"
        for category in config.categories:
            count = 0
            if category in errors_by_category:
                count = len(errors_by_category[category])
            desc = ""
            if category in config.category_description and config.category_description[category]:
                desc = config.category_description[category]
            print "- %d [%s] %s" % (count, category, desc)

def __help(error=''):
    msg = __doc__.replace("<TOOL_NAME>", sys.argv[0].split('/')[-1])
    sys.stderr.write(msg)
    if error:
        sys.stderr.write("\n\nERROR: %s\n\n" % error)
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        __help()
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    if sys.argv[1][0] == "-":
        if sys.argv[1] == "-h" or sys.argv[1] == "--help":
            __help()
        else:
            __help("unknown option: %s" % sys.argv[1])
    else:
        config = LogParserConfig(configfile = LogParserConfig.DEFAULT_CONFIG_SYSLOG)
        __output_text_report(sys.argv[1:], config)
