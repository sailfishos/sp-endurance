/*
 * A tiny '/proc information output' utility.
 *
 * Compile with: gcc -o proc2csv -W -Wall -Os -s proc2csv.c
 * 
 * This reads the PIDs of all processes at startup and then outputs
 * the status of those processes.  Kernel processes and processes which
 * have exited, are silently ignored.  Then some system info from
 * other /proc files is output.  All output is in CSV format.
 * 
 * Files that are processed from /proc:
 * - uptime
 * - loadavg
 * - meminfo
 * - vmstat
 * - sysvipc/msg
 * - sysvipc/sem
 * - sysvipc/shm
 * - sys/fs/file-nr
 * - PID/cmdline
 * - PID/fds/ (just the count of open FDs)
 * - PID/stat
 * - PID/status
 * - sys/vm/lowmem_deny_watermark_pages
 * - sys/vm/lowmem_notify_high_pages
 * - sys/vm/lowmem_notify_low_pages
 * - sys/vm/lowmem_deny_watermark
 * - sys/vm/lowmem_notify_high
 * - sys/vm/lowmem_notify_low
 * If the last six do not exist, their values will be zero.
 * 
 * NOTES:
 * - Originally this was a 'top' utility contributed by Eero
 *   to Busybox, but it is now severely re-factored & generalized,
 *   reading of many other proc files is added and output changed
 *   to CSV and to happen only once
 * - At startup this changes to /proc, all the reads are then
 *   relative to that
 * 
 * Copyright (C) 2003 by Eero Tamminen
 * Copyright (C) 2006,2007,2009 by Nokia Corporation
 * 
 * Contact: Eero Tamminen <eero.tamminen@nokia.com>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License 
 * version 2 as published by the Free Software Foundation. 
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <dirent.h>
#include <string.h>
#include <sys/types.h>
#include <dirent.h>
#include <libgen.h>	/* basename() */
#include <assert.h>
#include <errno.h>

#define CSV_SEPARATOR ","

/* process information taken from /proc,
 * The code takes into account how long the fields below are.
 */
typedef struct {
	int skip;	/* whether to skip this item */
	char cmd[78];	/* command line[read/show size] */
	char pid[6];	/* Pid */
} status_t;

/* return values for process types */
typedef enum {
	PID_OK,
	PID_SKIP,
	PID_EXITED
} pid_type_t;

/* whether to show /proc file fields or values */
enum {
	SHOW_FIELDS,
	SHOW_VALUES
};

static int ignore_user_errors = 0;


static inline void newline(void)  { fputs("\n", stdout); }

/* show the related error messages and exit unless
 * ignore_user_errors is set
 */
static void error_exit(const char *fun, const char *msg, const char *file)
{
	int error = errno;
	
	perror(fun);
	fprintf(stderr, "  ERROR: %s for '%s'\n", msg, file);
	if (ignore_user_errors && error == EACCES) {
		return;
	} else {
		exit(-1);
	}
}

/* converts contents of given file to CSV so that all whitespace
 * and control characters are compressed and replaced with ','.
 * For example "foo    bar" -> "foo,bar"
 * 
 * Only count columns from 'start'th one are output.
 */
static void show_as_csv(const char *filename, int start, int count)
{
	char buffer[256], *buf, *value;
	int field, fields_out;
	FILE *fp;

	fp = fopen(filename, "r");
	if (!fp) {
		error_exit("show_as_csv()", "file open failed", filename);
		return;
	}
	
	while (fgets(buffer, sizeof(buffer), fp)) {
		buf = buffer;
		fields_out = 0;
		for (field = 0; fields_out < count; field++) {
			while (*buf && *buf <= ' ') {
				buf++;
			}
			if (*buf) {
				value = buf;
			} else {
				break;
			}
			while (*buf && *buf > ' ') {
				buf++;
			}
			if (field < start) {
				continue;
			}
			if (*buf) {
				*buf++ = '\0';
			}
			if (fields_out) {
				fputs(CSV_SEPARATOR, stdout);
			} else {
				fields_out = 1;
			}
			fputs(value, stdout);
		}
		newline();
	}
	fclose(fp);
}


/* splits the given buffer into 'sep' separated key and value strings
 * which are stripped of white space & control chars from both ends.
 * Returns zero on success and -1 on error.
 */
static int split_key_value(char *buf, char **key, char **value, char sep)
{
	assert(buf);
	while (*buf && *buf <= ' ') {
		buf++;
	}
	*key = buf;
	while (*buf && *buf != sep) {
		buf++;
	}
	if (*buf != sep) {
		*value = buf;
		return -1;
	}
	*buf++ = '\0';
	while (*buf && *buf <= ' ') {
		buf++;
	}
	*value = buf;
	while (*buf) {
		buf++;
	}
	while (buf > *value) {
		buf--;
		if (*buf <= ' ') {
			*buf-- = '\0';
		} else {
			break;
		}
	}
	return 0;
}


/* split the given line at 'separator' char to key and value
 * and print either of them according to 'show'
 */
static void output_fields(FILE *fp, int show, char separator)
{
	char buf[128], *key, *value;
	int fields = 0;
	
	while (fgets(buf, sizeof(buf), fp)) {
		if (buf[0] <= ' ') {
			/* lines starting with whitespace don't have
			 * proper key/value pairs
			 */
			continue;
		}
		if (fields) {
			fputs(CSV_SEPARATOR, stdout);
		} else {
			fields = 1;
		}
		if (split_key_value(buf, &key, &value, separator) < 0) {
			fprintf(stderr, "ERROR: buffer '%s' didn't contain '%c'!\n", buf, separator);
			continue;
		}
		if (show == SHOW_FIELDS) {
			fputs(key, stdout);
		} else {
			fputs(value, stdout);
		}
	}
	if (show == SHOW_FIELDS) {
		fputs(":", stdout);
	}
	newline();
}


static void show_keyvalue_file(const char *filename, char separator)
{
	FILE *fp;

	fp = fopen(filename, "r");
	if (!fp) {
		error_exit("show_keyvalue_file()", "file open failed", filename);
		return;
	}
	output_fields(fp, SHOW_FIELDS, separator);
	rewind(fp);
	output_fields(fp, SHOW_VALUES, separator);
	fclose(fp);
}


/* output lowmem limits if the co. files exist */
static void show_lowmem_limits(void)
{
	typedef struct {
		const char *name;
		int value;
	} lowmem_t;
	lowmem_t files[] = {
		{ "lowmem_notify_low", 0 },
		{ "lowmem_notify_high", 0 },
		{ "lowmem_deny_watermark", 0 },
		{ "lowmem_notify_low_pages", 0 },
		{ "lowmem_notify_high_pages", 0 },
		{ "lowmem_deny_watermark_pages", 0 },
		{ NULL, 0 }
	};
	char *tmp, buf[8];
	FILE *fp;
	int i;
	
	for (i = 0; files[i].name; i++) {
		if (i) {
			fputc(',', stdout);
		}
		fputs(files[i].name, stdout);
	}
	fputs(":\n", stdout);

	if (chdir("sys/vm") < 0) {
		perror("chdir(sys/vm)");
		/* not available: zero for the values */
		for (;;) {
			fputc('0', stdout);
			if (--i <= 0) {
				newline();
				break;
			}
			fputc(',', stdout);
		}
		return;
	}

	for (i = 0; files[i].name; i++) {
		fp = fopen(files[i].name, "r");
		if (i) {
			fputc(',', stdout);
		}
		if (!fp) {
			fprintf(stderr,
				"Warning: show_lowmem_limits() file open failed for: %s\n",
				files[i].name);
			fputc('0', stdout);
			continue;
		}
		fgets(buf, sizeof(buf), fp);
		for (tmp = buf; *tmp; tmp++) {
			if (*tmp == '\n') {
				*tmp = '\0';
				break;
			}
		}
		fputs(buf, stdout);
		fclose(fp);
	}
	newline();
	if (chdir("../..") < 0) {
		perror("chdir(../..)");
	}
}


static pid_type_t show_status(status_t *s, int show)
{
	char status[20];
	FILE *fp;

	if (s->skip) {
		return PID_SKIP;
	}
	/* read the process info from 'status' in PID dir */
	snprintf(status, sizeof(status), "%s/status", s->pid);
	fp = fopen(status, "r");
	if (!fp) {
		if (errno != ENOENT) {
			error_exit("show_status()",
				   "file open failed", status);
		}
		/* skip already exited processes */
		s->skip = 1;
		return PID_EXITED;
	}
	output_fields(fp, show, ':');
	fclose(fp);
	return PID_OK;
}


/* read process statuses */
static void show_statuses(int num, status_t *statuslist)
{
	int idx, exited = 0;
	status_t *s;
	
	/* output CSV header for status file fields... */
	for (s = statuslist, idx = 0; idx < num; idx++, s++) {
		if (show_status(s, SHOW_FIELDS) == PID_OK) {
			/* fields printed OK from one status file */
			break;
		}
	}
	/* ...and the status file field values */
	for (s = statuslist, idx = 0; idx < num; idx++, s++) {
		switch (show_status(s, SHOW_VALUES)) {
		case PID_EXITED:
			exited++;
			break;
		case PID_SKIP:
		case PID_OK:
			break;
		}
	}
	if (exited) {
		fprintf(stderr,
			"%d (more) processes had exited in the meanwhile.\n",
			exited);
	}
}


/* read /proc/pid/stat */
static void show_proc_pid_stat(int num, status_t *statuslist)
{
	char stat[20];
	int i;
	status_t *s;
	for (i=0; i < num; ++i) {
		s = &statuslist[i];
		if (s->skip) {
			continue;
		}
		snprintf(stat, sizeof(stat), "%s/stat", s->pid);
		show_as_csv(stat, 0, 128);
	}
}


/* read fd counts for each process in statuslist */
static void show_fd_counts(int num, status_t *statuslist)
{
	int fds, idx, exited = 0;
	char fddir[20];
	status_t *s;
	DIR *dir;

	fputs("PID,FD count,Command line:\n", stdout);
	for (s = statuslist, idx = 0; idx < num; idx++, s++) {

		if (s->skip) {
			continue;
		}
		/* open the dir containing process FDs */
		snprintf(fddir, sizeof(fddir), "%s/fd", s->pid);
		dir = opendir(fddir);
		if (!dir) {
			if (errno != ENOENT) {
				error_exit("show_fd_counts()",
					   "directory open failed", fddir);
			}
			/* skip already exited processes */
			s->skip = 1;
			exited++;
			continue;
		}
		/* count files in the fd/ subdirectory */
		for (fds = 0; readdir(dir); fds++)
		  ;
		closedir(dir);

		/* ignore current and parent dir entries */
		fds -= 2;
		assert(fds >= 0);
		fprintf(stdout, "%s%s%d%s%s\n",
			s->pid, CSV_SEPARATOR, fds, CSV_SEPARATOR, s->cmd);
	}
	if (exited) {
		fprintf(stderr,
			"%d (more) processes had exited in the meanwhile.\n",
			exited);
	}
}


/* allocs statuslist and reads process command lines, frees namelist
 * (which was allocated by scandir()), returns filled statuslist or
 * NULL in case of error.  In case of an error, namelist may be only
 * half freed.
 */
static status_t *read_info(int num, struct dirent **namelist)
{	
	FILE *fp;
	struct dirent **n;
	status_t *statuslist, *s;
	int i, idx, count, exited = 0;
	char filename[20], *cmdline;
	
	/* allocate & zero status for each of the processes */
	statuslist = calloc(num, sizeof(status_t));
	if (!statuslist) {
		return NULL;
	}

	/* go through the processes */
	n = namelist;
	s = statuslist;
	for (idx = 0; idx < num; idx++, s++, n++) {

		/* copy PID string to status struct and free name */
		if (strlen((*n)->d_name) > sizeof(s->pid)-1) {
			fprintf(stderr, "PID '%s' too long\n", (*n)->d_name);
			free(statuslist);
			return NULL;
		}
		strncpy(s->pid, (*n)->d_name, sizeof(s->pid));
		s->pid[sizeof(s->pid)-1] = '\0';
		free((*n));
		*n = NULL;

		/* read the command line from 'cmdline' in PID dir */
		snprintf(filename, sizeof(filename), "%s/cmdline", s->pid);
		fp = fopen(filename, "r");
		if (!fp) {
			/* skip already exited processes */
			s->skip = 1;
			exited++;
			continue;
		}
		count = fread(s->cmd, 1, sizeof(s->cmd), fp);
		fclose(fp);
		
		cmdline = s->cmd;
		for (i = 0; i < count-1; i++) {
			if (cmdline[i] < ' ') {
				cmdline[i] = ' ';
			}
		}
		cmdline[i] = '\0';
	}
	free(namelist);
	if (exited) {
		fprintf(stderr,
			"%d processes had exited in the meanwhile.\n",
			exited);
	}
	return statuslist;
}


/* returns true for file names which are PID dirs
 * (i.e. start with number)
 */
static int filter_pids(const struct dirent *dir)
{
	status_t dummy;
	const char *name = dir->d_name;

	if (*name >= '0' && *name <= '9') {
		if (strlen(name) > sizeof(dummy.pid)-1) {
			fprintf(stderr, "PID name '%s' too long\n", name);
			return 0;
		}
		if (atoi(name) == getpid()) {
			/* ignore myself */
			return 0;
		}
		return 1;
	}
	return 0;
}


/* compares two directory entry names as numeric strings
 */
static int num_sort(const void *a, const void *b)
{
	int ia = atoi((*(struct dirent * const *)a)->d_name);
	int ib = atoi((*(struct dirent * const *)b)->d_name);
	
	if (ia == ib) {
		return 0;
	}
	/* NOTE: by switching the check, you change the process sort order */
	if (ia < ib) {
		return -1;
	} else {
		return 1;
	}
}


static void usage(char *name)
{
	printf("\nusage: %s [-t|-p]\n\n"
"First this reads all PIDs in proc, then it will read their status\n"
"and some other system information and output that in CSV format to\n"
"the standard output.\n\n"
"Without '-t' (test) option, the system /proc directory is used.\n"
"With it, the 'proc' subdirectory in current directory is used.\n\n"
"With -p option you can run this as normal user, as then all\n"
"permission denied errors are ignored.\n",
	       name);
	exit(-1);
}


int main(int argc, char *argv[])
{
	status_t *statuslist;
	const char *proc = "/proc", *arg;
	struct dirent **namelist;
	int lines;

	/* which dir to use for "proc" directory */
	if (argc > 1) {
		arg = argv[1];
		if (argc == 2 && arg[0] == '-' && arg[1] && !arg[2]) {
			switch (arg[1]) {
			case 't':
				proc = "proc";
				break;
			case 'p':
				ignore_user_errors = 1;
				break;
			default:
				usage(argv[0]);
			}
		} else {
			usage(argv[0]);
		}
	}
	
	/* change to proc */
	if (chdir(proc) < 0) {
		perror("chdir('proc')");
		return -1;
	}

	/* show some system information */
	fputs("\nUptime,Idletime (secs):\n", stdout);
	show_as_csv("uptime", 0, 2);
	fputs("\nLoadavg 1min,5min,15min,Running/all,Last PID:\n", stdout);
	show_as_csv("loadavg", 0, 5);

	/* memory usage, vmstat and lowmem limits */
	newline();
	show_keyvalue_file("meminfo", ':');
	newline();
	show_keyvalue_file("vmstat", ' ');
	newline();
	show_lowmem_limits();

	/* sysV IPC memory usage */
	fputs("\nMessage queues:\n", stdout);
	show_as_csv("sysvipc/msg", 2, 6);
	fputs("\nSemaphore arrays:\n", stdout);
	show_as_csv("sysvipc/sem", 2, 4);
	fputs("\nShared memory segments:\n", stdout);
	show_as_csv("sysvipc/shm", 2, 6);

	/* do this before scanning PIDs so that count is not disturbed */
	fputs("\nAllocated FDs,Freed FDs,Max FDs:\n", stdout);
	show_as_csv("sys/fs/file-nr", 0, 3);
	
	/* read process IDs for all the processes from the procfs */
	lines = scandir(".", &namelist, filter_pids, num_sort);
	if (lines < 0) {
		perror("scandir('proc')");
		return -1;
	}
	if (!lines) {
		fprintf(stderr, "No /proc/PID/ entries\n");
		return -1;
	}

	/* read command line for each of the processes */
	statuslist = read_info(lines, namelist);
	if (!statuslist) {
		fprintf(stderr, "Error in reading proccesses information");
		return -1;
	}

	/* show how many file descriptors each process is using */
	newline();
	show_fd_counts(lines, statuslist);
	
	/* read and show status for each of the processes */
	newline();
	show_statuses(lines, statuslist);

	/* show /proc/pid/stat for each process */
	fputs("\nProcess status:\n", stdout);
	show_proc_pid_stat(lines, statuslist);
	
	free(statuslist);
	return 0;
}
