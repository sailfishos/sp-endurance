/*
 * This file is part of sp-endurance package.
 *
 * Copyright (C) 2011 by Nokia Corporation
 *
 * Contact: Eero Tamminen <eero.tamminen@nokia.com>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
 * 02110-1301 USA
 */
#define _GNU_SOURCE

#include <stdio.h>
#include <getopt.h>
#include <errno.h>
#include <signal.h>
#include <stdbool.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/types.h>
#include <string.h>
#include <unistd.h>

static volatile sig_atomic_t file_abort = 0;

static ssize_t(*write_buffer)(int, const char*, size_t) = (ssize_t (*)(int, const char*, size_t))write;

#define msg_error(format, ...)  fprintf(stderr, "Error: " format, ##__VA_ARGS__)
#define msg_warning(format, ...)  fprintf(stderr, "Warning: " format, ##__VA_ARGS__)

/**
 * Block the sigint from aborting the program execution.
 *
 * @param sig
 */
static void sigint_handler(int sig __attribute((unused)))
{
	file_abort = 1;
}

/**
 * Display the usage information.
 */
static void display_usage(void)
{
	printf(
			"The sp-save-noncached utility writes the data from standard input\n"
			"into the specified file, instructing kernel to not keep the data\n"
			"cached.\n"
			"  <app> | sp-save-noncached <filename>\n"
			"  sp-save-noncached <filename> < <app>\n"
			"Where:\n"
			"  <app> - an application writing into standard output\n"
			"  <filename> - the filename to write the <app> output\n"
			);
}


/**
 * Reads standard input, optionally compresses it and stores
 * into the specified file.
 * @param filename
 */
static void save_file(const char* filename)
{
	int fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0666);
	if (fd == -1) {
		msg_error("failed to open file %s (%s)\n", filename, strerror(errno));
		exit (-1);
	}
	posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED);

	char buffer[4096];
	int n = -1;
	while (!file_abort && n) {
		n = read(STDIN_FILENO, buffer, sizeof(buffer));
		if (n < 0) {
			if (errno == EINTR) continue;
			msg_error("failed to read from standard input (%s)\n", strerror(errno));
			break;
		}
		if (write_buffer(fd, buffer, n) == -1) {
			msg_error("failed to write data (%s)\n", strerror(errno));
			break;
		}
	}

	close(fd);
}


/**
 *
 * @param argc
 * @param argv
 * @return
 */
int main(int argc, char* argv[])
{

	/* install interrupt handler */
	struct sigaction sa = {.sa_flags = 0, .sa_handler = sigint_handler};
	sigemptyset(&sa.sa_mask);
	if (sigaction(SIGINT, &sa, NULL) == -1) {
		msg_error("failed to install SIGINT handler\n");
		return -1;
	}
	/* command line options */
	struct option long_options[] = {
			 {"help", 0, 0, 'h'},
			 {0, 0, 0, 0},
	};
	char* short_options = "h";

	/* parse command line options */
	int opt;
	opterr = 0;

	while ( (opt = getopt_long(argc, argv, short_options, long_options, NULL)) != -1) {
		switch(opt) {
		case 'h':
			display_usage();
			exit (0);

		case '?':
			msg_error("unknown sp-file option: %c\n", optopt);
			display_usage();
			exit (-1);
		}
	}
	if (optind >= argc) {
		msg_error("no output file name given\n");
		exit (-1);
	}

	save_file(argv[optind]);

	return 0;
}
