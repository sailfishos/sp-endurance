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

static volatile sig_atomic_t copy_abort = 0;

static bool copy_lzo = false;

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
			"The sp-copy-noncached utility copies files without keeping data\n"
			"cached to avoid 'poisoning' kernel page cache.\n"
			"  sp-save-noncached [<options>] <filein> <fileout>\n"
			"Where:\n"
			"  <options>:"
			"    -z    invoke lzop to compress the input file.\n"
			"    -h    this help page.\n"
			"  <filein>/<fileout> - input/output filenames. Standard input/output\n"
			"    streams are used if '-' is specified as an input/output file names.\n"
			);
}

/**
 * Copy data from one file into other.
 *
 * This function can be used to either directly copy data from one file into
 * other or optionally pipe it through an external tool reading standard input
 * and writing data into standard output (used to compress the data with an
 * external compressing utility).
 * 1) direct copy mode
 * @param fd_in            the input stream.
 * @param fd_ou            the output stream.
 * @param fd_filter_in     the pipe to the standard input of an external tool
 *                         (-1 if data is not piped through an external tool).
 * @param fd_filter_out    the pipe from the standard output of an external tool.
 *                         (-1 if data is not piped through an external tool).
 *
 * @return  0 - the data was copied successfully.
 *         -1 - an error occurred during data transfer.
 */
static int copy_data(int fd_in, int fd_out, int fd_filter_in, int fd_filter_out)
{
	char buffer[4096];
	int size;
	fd_set fds_read;
	fd_set fds_write;
	bool wait_for_write = false;
	int stream_out = fd_filter_in == -1 ? fd_out : fd_filter_in;
	int offset = 0;

	/* prepare read/write descriptor set */
	int fdmax = fd_in;
	if (fd_filter_out > fdmax) fdmax = fd_filter_out;
	if (stream_out > fdmax) fdmax = stream_out;
	fdmax++;
	FD_ZERO(&fds_read);
	FD_ZERO(&fds_write);


	/*
	 * First wait for data in the input stream (fd_in), then wait for the first
	 * output stream (stream_out) to be able to accept data.
	 * At the same time if the data is being piped through and external tool
	 * (fd_filter_in/fd_filter_out are not -1) check the filter output (fd_filter_out)
	 * for data and write it to the output stream (fd_out).
	 */
	while (!copy_abort) {
		/* prepare select() descriptor sets */
		if (wait_for_write) {
			FD_SET(stream_out, &fds_write);
		}
		else {
			if (fd_in != -1) FD_SET(fd_in, &fds_read);
		}
		if (fd_filter_out != -1) FD_SET(fd_filter_out, &fds_read);

		int rc = select(fdmax, &fds_read, &fds_write, NULL, NULL);

		if (rc == -1) {
			if (errno == EINTR) continue;
			msg_error("while waiting for input data (%s)\n", strerror(errno));
			return -1;
		}
		/* if input stream contains data set wait_for_write flag */
		if (fd_in != -1 && FD_ISSET(fd_in, &fds_read)) {
			FD_CLR(fd_in, &fds_read);
			wait_for_write = true;
		}
		/* if output stream can accept data, read buffer from input stream
		 * (it will always contain some data as output stream is checked only
		 * if input stream has data) and write it to output stream. */
		if (FD_ISSET(stream_out, &fds_write)) {
			FD_CLR(stream_out, &fds_write);
			wait_for_write = false;
			size = read(fd_in, buffer, sizeof(buffer));
			if (size < 0) {
				msg_error("failed to read input data (%s)\n", strerror(errno));
				return -1;
			}
			/* input stream was closed */
			if (size == 0) {
				/* data was written directly to output - stop work loop */
				if (stream_out == fd_out) break;
				/* otherwise data was piped to standard input of an external tool. Close the pipe */
				close(stream_out);
				fd_in = -1;
			}

			/* write the data to output stream */
			offset = 0;
			while (offset < size) {
				int n = write(stream_out, buffer + offset, size - offset);
				if (n == -1) {
					msg_error("failed to write data (%s)\n", strerror(errno));
					return -1;
				}
				offset += n;
			}
		}
		/* if data is piped through an external tool - check it's output pipe */
		if (fd_filter_out != -1  && FD_ISSET(fd_filter_out, &fds_read)) {
			FD_CLR(fd_filter_out, &fds_read);
			size = read(fd_filter_out, buffer, sizeof(buffer));
			if (size < 0) {
				msg_error("failed to read lzop output data (%s)\n", strerror(errno));
				return -1;
			}
			/* external tool was closed, stop work loop */
			if (size == 0) {
				break;
			}

			/* write the data to output */
			offset = 0;
			while (offset < size) {
				int n = write(fd_out, buffer + offset, size - offset);
				if (n == -1) {
					msg_error("failed to write data (%s)\n", strerror(errno));
					return -1;
				}
				offset += n;
			}
		}
	}
	return 0;
}

/**
 * Copies a file.
 *
 * If destination file exists it's overwritten.
 * If copy_lzo flag is set then the input file is compressed by
 * piping it through lzop -c before writing the resulting data into
 * the specified destination file.
 * @param file_in   the source file name or '-' for standard input.
 * @param file_out  the destination file name or '-' for standard output.
 * @return
 */
static int copy_file_noncached(const char* file_in, const char* file_out)
{
	int fd_in = -1;
	int fd_out = -1;
	int fd_filter_in = -1;
	int fd_filter_out = -1;
	int pid_lzop = 0;

	/* open input file */
	if (strcmp(file_in, "-")) {
		fd_in = open(file_in, O_RDONLY);
		if (fd_in == -1) {
			msg_error("failed to open input file %s (%s)\n", file_in, strerror(errno));
			return -1;
		}
		posix_fadvise(fd_in, 0, 0, POSIX_FADV_DONTNEED);
	}
	else {
		fd_in = STDIN_FILENO;
	}
	/* open output file */
	if (strcmp(file_out, "-")) {
		fd_out = open(file_out, O_WRONLY | O_CREAT | O_TRUNC, 0666);
		if (fd_out == -1) {
			msg_error("failed to create output file %s (%s)\n", file_out, strerror(errno));
			return -1;
		}
		posix_fadvise(fd_out, 0, 0, POSIX_FADV_DONTNEED);
	}
	else {
		fd_out = STDOUT_FILENO;
	}

	if (copy_lzo) {
		/* setup pipes and launch lzop */
		int pipe_to[2], pipe_from[2];
		if (pipe(pipe_to) != 0 || pipe(pipe_from) != 0) {
			msg_error("failed to create lzop pipe (%s)\n", strerror(errno));
			return -1;
		}
		pid_lzop = fork();
		if (pid_lzop == 0) {
			const char* args[] = {"lzop", "-c", NULL};
			close(pipe_to[1]);
			if (dup2(pipe_to[0], STDIN_FILENO) == -1) {
				msg_error("failed to dup stdin (%s)\n", strerror(errno));
				exit(1);
			}
			close(pipe_from[0]);
			if (dup2(pipe_from[1], STDOUT_FILENO) == -1) {
				msg_error("failed to dup stdout (%s)\n", strerror(errno));
				exit(1);
			}
			execvp(args[0], (char * const*)(void*)args);
			msg_error("failed to execute lzop packer (%s)\n", strerror(errno));
			exit(1);
		}
		close(pipe_to[0]);
		close(pipe_from[1]);
		fd_filter_in = pipe_to[1];
		fd_filter_out = pipe_from[0];
	}

	fprintf(stderr, "Copying file: %s -> %s\n", file_in, file_out);
	copy_data(fd_in, fd_out, fd_filter_in, fd_filter_out);

	/* close input/output/filter file descriptors */
	if (fd_in != -1 && fd_in != STDIN_FILENO) close(fd_in);
	if (fd_out != -1 && fd_out != STDOUT_FILENO) close(fd_out);
	if (fd_filter_in != -1) close(fd_filter_in);
	if (fd_filter_out != -1) close(fd_filter_out);
	/* wait for lzop process to be finished properly*/
	if (copy_lzo) wait(NULL);

	return 0;
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
			 {"lzo", 0, 0, 'z'},
			 {0, 0, 0, 0},
	};
	char short_options[] = "hz";

	/* parse command line options */
	int opt;
	opterr = 0;

	while ( (opt = getopt_long(argc, argv, short_options, long_options, NULL)) != -1) {
		switch(opt) {
		case 'h':
			display_usage();
			exit (0);

		case 'z':
			copy_lzo = true;
			break;

		case '?':
			msg_error("unknown sp-file option: %c\n", optopt);
			display_usage();
			exit (-1);
		}
	}
	if (optind >= argc - 1) {
		msg_error("Not enough parameters given.\n");
		display_usage();
		exit (1);
	}

	copy_file_noncached(argv[optind], argv[optind + 1]);

	return 0;
}
