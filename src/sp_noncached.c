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
#include <sys/wait.h>
#include <pthread.h>


static volatile sig_atomic_t copy_abort = 0;

static bool copy_read = false;
static bool copy_write = false;

#define msg_error(format, ...)  fprintf(stderr, "Error: " format, ##__VA_ARGS__)
#define msg_warning(format, ...)  fprintf(stderr, "Warning: " format, ##__VA_ARGS__)

/**
 * Gracefully exit on SIGINT.
 *
 * @param sig
 */
static void sigint_handler(int sig __attribute((unused)))
{
	copy_abort = 1;
}

/**
 * Display the usage information.
 */
static void display_usage(void)
{
	printf(
			"The sp-file-noncached utility reads/writes files without keeping data\n"
			"cached to avoid 'poisoning' kernel page cache.\n"
			"  sp-save-noncached -(r|w) <file1> [<file2>...]\n"
			"Where:\n"
			"  <options>:\n"
			"    -w (--write)  writes standard input into file <file1>.\n"
			"    -r (--read)   reads files <file1>, <file2>... into standard output.\n"
			"    -h (--help)   this help page.\n"
			);
}


/**
 * Copies data from one file to other.
 *
 * @param fd_in   the input file descriptor.
 * @param fd_out  the output file descriptor.
 * @return
 */
static int copy_data(int fd_in, int fd_out)
{
	char buffer[64 * 1024];
	size_t offset = 0;
	while (!copy_abort) {
		int size = read(fd_in, buffer, sizeof(buffer));
		if (size == -1) {
			msg_error("while waiting for input data (%s)\n", strerror(errno));
			return -1;
		}
		if (size == 0) break;
		posix_fadvise(fd_in, offset, size, POSIX_FADV_DONTNEED);
		int buffer_offset = 0;
		while (buffer_offset < size) {
			int n = write(fd_out, buffer + buffer_offset, size - buffer_offset);
			if (n == -1) {
				msg_error("failed to write data (%s)\n", strerror(errno));
				return -1;
			}
			buffer_offset += n;
		}
		offset += size;
		posix_fadvise(fd_out, 0, 0, POSIX_FADV_DONTNEED);
	}
	fsync(fd_out);
	posix_fadvise(fd_out, 0, 0, POSIX_FADV_DONTNEED);
	return 0;
}

/**
 * Writes standard input into file.
 *
 * @param filename  the output file name.
 * @return   0 - success,
 *          -1 - error
 */
static int write_file(const char* filename)
{
	int fd = open(filename, O_WRONLY | O_CREAT | O_TRUNC, 0666);
	if (fd == -1) {
		msg_error("failed to create output file %s (%s)\n", filename, strerror(errno));
		return -1;
	}
	int rc = copy_data(STDIN_FILENO, fd);
	close(fd);
	return rc;
}

/**
 * Reads file into standard output.
 *
 * @param filename  the input file name.
 * @return   0 - success,
 *          -1 - error
 */
static int read_file(const char* filename)
{
	int fd = open(filename, O_RDONLY);
	if (fd == -1) {
		msg_error("failed to open input file %s (%s)\n", filename, strerror(errno));
		return -1;
	}
	int rc = copy_data(fd, STDOUT_FILENO);
	close(fd);
	return rc;
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
			 {"write", 0, 0, 'w'},
			 {"read", 0, 0, 'r'},
			 {0, 0, 0, 0},
	};
	char short_options[] = "hwr";

	/* parse command line options */
	int opt;
	opterr = 0;

	while ( (opt = getopt_long(argc, argv, short_options, long_options, NULL)) != -1) {
		switch(opt) {
		case 'h':
			display_usage();
			exit (0);

		case 'w':
			copy_write = true;
			break;

		case 'r':
			copy_read = true;
			break;

		case '?':
			msg_error("unknown sp-file option: %c\n", optopt);
			display_usage();
			exit (-1);
		}
	}
	if (optind >= argc) {
		msg_error("Not enough parameters given.\n");
		display_usage();
		exit (1);
	}
	if (copy_write) {
		write_file(argv[optind]);
	}
	else if (copy_read) {
		while (optind < argc) {
			read_file(argv[optind++]);
		}
	}
	else {
		msg_error("Either copy or write option must be given.\n");
		display_usage();
		exit (1);
	}
	return 0;
}
