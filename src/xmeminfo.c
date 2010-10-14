/*
 * XMemInfo -- output X client X resource usage as CSV data
 * 
 * Compile with:
 *   gcc -I/usr/X11R6/include -W -Wall -Os -s -o xmeminfo xmeminfo.c -lXRes
 * 
 * Based on XResTop code by Matthew Allum.
 * 
 * Changes:
 * 2006-01-30:
 * - output the information only once, as CSV
 * - do not use ncurses
 *
 *  Copyright (C) 2003 by Matthew Allum
 *  Copyright (C) 2006-2007,2009-2010 by Nokia Corporation
 * 
 * Contact: Eero Tamminen <eero.tamminen@nokia.com>
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2, or (at your option)
 *  any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xatom.h>
#include <X11/extensions/XRes.h>

#define DEBUG 1

#ifdef __GNUC__
#ifdef DEBUG
#define DBG(txt, args... ) fprintf(stderr, txt , ##args )
#else
#define DBG(txt, args... ) /* nothing */
#endif
#endif

enum {
  /* non-resource atoms */
  ATOM_NET_WM_PID,
  ATOM_NET_WM_NAME,
  ATOM_UTF8_STRING,
  ATOM_COUNT
};

static const char *AtomNames[] =
  {
    "_NET_WM_PID",
    "_NET_WM_NAME",
    "UTF8_STRING"
  };


typedef struct XResTopClient
{
  XID            resource_base, resource_mask;
  pid_t          pid;
  unsigned char *identifier;
  unsigned long  pixmap_bytes;
  unsigned long  other_bytes;
  XResType      *resources;
  int            n_resources;

} XResTopClient;

#define MAX_CLIENTS 1024  /* XXX find out max connections per server */

typedef struct XResTopApp 
{
  Display    *dpy;
  char       *dpy_name;
  int         screen;
  Window      win_root, win_dummy;
  Atom        atoms[ATOM_COUNT];
  char      **resource_atom_names;
  Atom       *resource_atoms;
  int         resource_atoms_cnt;

  XResTopClient *clients[MAX_CLIENTS];
  int         n_clients;
  
  Bool        want_batch_mode;
  int         delay;
  int         n_xerrors;

  char      **atoms_wanted;
  int         atoms_wanted_cnt;

} XResTopApp;


/* X Error trapping */

static int trapped_error_code = 0;
static int (*old_error_handler) (Display *d, XErrorEvent *e);

static int
error_handler(Display     *display,
	      XErrorEvent *error)
{
   trapped_error_code = error->error_code;
   display = display; /* make compiler happy */
   return 0;
}

static void
trap_errors(void)
{
   trapped_error_code = 0;
   old_error_handler = XSetErrorHandler(error_handler);
}

static int
untrap_errors(void)
{
   XSetErrorHandler(old_error_handler);
   return trapped_error_code;
}


/* Misc util funcs */

static pid_t
window_get_pid(XResTopApp *app, Window win)
{
  Atom  type;
  unsigned long  bytes_after, n_items;
  long *data = NULL;
  pid_t result = -1;
  int   format;

  if (XGetWindowProperty (app->dpy, win, 
			  app->atoms[ATOM_NET_WM_PID],
			  0, 2L,
			  False, XA_CARDINAL,
			  &type, &format, &n_items,
			  &bytes_after, (unsigned char **)&data) == Success
      && n_items && data != NULL)
    {
      result = *data;
    }

  if (data) XFree(data);

  return result;
}

static unsigned char*
window_get_utf8_name(XResTopApp *app, Window win)
{
  Atom type;
  int format;
  unsigned long  bytes_after, n_items;
  unsigned char *str = NULL;
  int result;

  result =  XGetWindowProperty (app->dpy, win, app->atoms[ATOM_NET_WM_NAME],
				0, 1024L,
				False, app->atoms[ATOM_UTF8_STRING],
				&type, &format, &n_items,
				&bytes_after, (unsigned char **)&str);

  if (result != Success || str == NULL)
    {
      if (str) XFree (str);
      return NULL;
    }

  if (type != app->atoms[ATOM_UTF8_STRING] || format != 8 || n_items == 0)
    {
      XFree (str);
      return NULL;
    }

  /* XXX should probably utf8_validate this  */

  return str;
}


static void 
usage(char *progname)
{
  fprintf(stderr, 
          "%s usage:\n"
          "  -d, -display      Specify X Display to monitor.\n"
          "  -a, -atom         Specify X Resource Atom name to report.\n"
          "                    Multiple -a/-atom parameters are accepted.\n"
          "                    The atoms are reported in the order specified.\n"
          "\n"
          "Examples:\n"
          "  %s -a WINDOW -a FONT -a \"PASSIVE GRAB\"\n"
          "\n",
          progname, progname);

  exit(1);
}


/* Client struct stuff */

static XResTopClient*
xrestop_client_new(void)
{
  XResTopClient *client = NULL;

  client = malloc(sizeof(XResTopClient));
  memset(client, 0, sizeof(XResTopClient));

  client->pid = -1;

  return client;
}

static void
xrestop_client_free(XResTopClient *client)
{
  if (client->identifier) XFree (client->identifier);
  free(client);
}

static Bool
check_win_for_info(XResTopApp *app, XResTopClient *client, Window win)
{
  XTextProperty  text_prop;
  XID            match_xid ;

  /* 
   *  Figure out if a window belongs in a XResClients resource range,
   *  and if it does try and get a name for it.
   *
   *  XXX Should also check for CLASS and TRANSIENT props so we 
   *      get the name for top level window. 
   */

  match_xid = (client->resource_base & ~client->resource_mask);

  if ( (win & ~client->resource_mask) == match_xid )
    {
      trap_errors();

      if ((client->identifier = window_get_utf8_name(app, win)) == NULL)
	{
	  if (XGetWMName(app->dpy, win, &text_prop))
	    {
	      client->identifier = (unsigned char *) strdup((char *) text_prop.value);
	      XFree((char *) text_prop.value);
	    }
	  else
	    {
	      XFetchName(app->dpy, win, (char **)&client->identifier);
	    }
	}

      if (untrap_errors())
	{
	  app->n_xerrors++;
	  return False;
	}
    }

  if (client->identifier != NULL)
    return True;

  return False;
}

static XID
recurse_win_tree(XResTopApp *app, XResTopClient *client, Window win_top)
{
  Window       *children, dummy;
  unsigned int  nchildren, i;
  XID           w = 0;
  Status        qtres;
  
  if (check_win_for_info(app, client, win_top))
    return win_top;
  
  trap_errors();

  qtres = XQueryTree(app->dpy, win_top, &dummy, &dummy, &children, &nchildren);

  if (untrap_errors())
    {
      app->n_xerrors++;
      return 0;
    }

  if (!qtres) return 0;

  for (i=0; i<nchildren; i++) 
    {
      if (recurse_win_tree(app, client, children[i]))
	{
	  w = children[i];
	  break;
	}
    }

  if (children) XFree ((char *)children);

  return w;
}

static void 
xrestop_client_get_info(XResTopApp *app, XResTopClient *client)  
{
  Window found = None;

  /* 
   * Try and find out some useful info about an XResClient so user
   * can identify it to a window. 
   * 
   * XXX This uses a bucket load of X traffic - improve !
   */

  /* Check for our own connection */
  if ( (client->resource_base & ~client->resource_mask) 
          == (app->win_dummy & ~client->resource_mask) )
    {
      client->identifier = (unsigned char *) strdup("xrestop");
      return;
    }

  found = recurse_win_tree(app, client, app->win_root);

  if (found)
    {
       client->pid = window_get_pid(app, found);
    }
  else
    {
      client->identifier = (unsigned char *) strdup("<unknown>");
    }
}

static void
xrestop_client_get_stats(XResTopApp *app, XResTopClient *client)
{
  trap_errors();
  
  XResQueryClientResources (app->dpy, client->resource_base,
          &client->n_resources, &client->resources);
  
  XResQueryClientPixmapBytes (app->dpy, client->resource_base, 
			      &client->pixmap_bytes);
  
  if (untrap_errors())
    {
      app->n_xerrors++;
      if (client->resources) {
        XFree(client->resources);
        client->resources = NULL;
        client->n_resources = 0;
      }
    }
}

static void
xrestop_populate_client_data(XResTopApp *app)
{
  int         i;
  XResClient *clients;

  for (i=0; i < app->n_clients; i++)
    xrestop_client_free(app->clients[i]);

  trap_errors();

  XResQueryClients(app->dpy, &app->n_clients, &clients); 

  if (untrap_errors())
    {
      app->n_xerrors++;
      goto cleanup;
    }

  for(i = 0; i < app->n_clients; i++) 
    {
      app->clients[i] = xrestop_client_new();

      app->clients[i]->resource_base = clients[i].resource_base;
      app->clients[i]->resource_mask = clients[i].resource_mask;

      xrestop_client_get_info(app, app->clients[i]); 

      xrestop_client_get_stats(app, app->clients[i]); 
    }

 cleanup:

  if (clients) XFree(clients);
}

/* Iterate over the list of X clients, and collect a set of unique X resource
 * atoms from the ones that we encounter.
 *
 * Then map the atoms (=integers) to human readable resource names.
 */
static void
xrestop_build_atom_list(XResTopApp *app)
{
  int i, j, k;

  for (i=0; i < app->n_clients; ++i)
    {
      for (k=0; k < app->clients[i]->n_resources; ++k)
        {
          Atom a = app->clients[i]->resources[k].resource_type;
          for (j=0; j < app->resource_atoms_cnt; ++j)
            {
              if (a == app->resource_atoms[j]) break;
            }
          if (j == app->resource_atoms_cnt)
            {
              app->resource_atoms_cnt += 1;
              app->resource_atoms = realloc(app->resource_atoms,
                        (app->resource_atoms_cnt)*sizeof(Atom));
              app->resource_atoms[app->resource_atoms_cnt-1] = a;
            }
        }
    }

  app->resource_atom_names = calloc(app->resource_atoms_cnt, sizeof(char*));
  XGetAtomNames(app->dpy, app->resource_atoms, app->resource_atoms_cnt,
                app->resource_atom_names);
}

static void
print_column_titles(XResTopApp *app)
{
  int i, j;
  printf("res-base");
  if (app->atoms_wanted_cnt)
    {
      /* Report the atoms in the exact order the user specified on command
       * line.
       */
      for (i=0; i < app->atoms_wanted_cnt; ++i)
        {
          for (j=0; j < app->resource_atoms_cnt; ++j)
            {
              if (strcmp(app->atoms_wanted[i], app->resource_atom_names[j]) == 0)
                {
                  printf(",%s", app->resource_atom_names[j]);
                  break;
                }
            }
        }
    }
  else
    {
      for (i=0; i < app->resource_atoms_cnt; ++i)
        {
          printf(",%s", app->resource_atom_names[i]);
        }
    }
  printf(",total_resource_count,Pixmap mem,Misc mem,Total mem,PID,Identifier\n");
}

static unsigned
rcount(XResTopClient *client)
{
  int i;
  unsigned cnt = 0;
  for (i=0; i < client->n_resources; ++i)
    {
      cnt += client->resources[i].count;
    }
  return cnt;
}

static unsigned
rcount_for_atom(XResTopClient *client, Atom atom)
{
  int i;
  unsigned cnt = 0;
  for (i=0; i < client->n_resources; ++i)
    {
      if (atom == client->resources[i].resource_type)
        {
          cnt = client->resources[i].count;
          break;
        }
    }
  return cnt;
}

static void
print_client_data(XResTopApp *app, XResTopClient *client)
{
  int i, j;

  printf("%.7x", (unsigned)client->resource_base);

  if (app->atoms_wanted_cnt)
    {
      /* Report the atoms in the exact order the user specified on command
       * line.
       */
      for (i=0; i < app->atoms_wanted_cnt; ++i)
        {
          for (j=0; j < app->resource_atoms_cnt; ++j)
            {
              if (strcmp(app->atoms_wanted[i], app->resource_atom_names[j]) == 0)
                {
                  printf(",%u", rcount_for_atom(client, app->resource_atoms[j]));
                  break;
                }
            }
        }
    }
  else
    {
      for (i=0; i < app->resource_atoms_cnt; ++i)
        {
          printf(",%u", rcount_for_atom(client, app->resource_atoms[i]));
        }
    }

  printf(",%u,%liB,%liB,%liB,%d,%s\n",
      rcount(client),

      client->pixmap_bytes,
      client->other_bytes,
      client->pixmap_bytes + client->other_bytes,

      client->pid,	/* -1 for unknown */
      client->identifier);
}

static void
xrestop_display(XResTopApp *app)
{
  int i;

  print_column_titles(app);

  for (i=0; i < app->n_clients; i++)
    {
      print_client_data(app, app->clients[i]);
    }
}


/* Estimate how many bytes each X client is using.
 *
 * XRes does not give byte values for the resource types (the only exception is
 * pixmaps), so try to guess something.
 */
static void
xrestop_calculate_client_bytes(XResTopApp *app)
{
  int i, j, k;
  for (i=0; i < app->n_clients; ++i)
    {
      for (j=0; j < app->clients[i]->n_resources; ++j)
        {
          unsigned bytes;
          Atom a = app->clients[i]->resources[j].resource_type;
          for (k=0; k < app->resource_atoms_cnt; ++k)
            if (a == app->resource_atoms[k]) break;
          if (strcmp(app->resource_atom_names[k], "PIXMAP") == 0)
            bytes = 0;
          else if (strcmp(app->resource_atom_names[k], "FONT") == 0)
            bytes = app->clients[i]->resources[j].count * 1024;
          else
            bytes = app->clients[i]->resources[j].count * 24;
          app->clients[i]->other_bytes += bytes;
        }
    }
}

static int 
xrestop_sort_compare(const void *a, const void *b)
{
  const XResTopClient *c1 = *(XResTopClient * const *)a;
  const XResTopClient *c2 = *(XResTopClient * const *)b;

  if ((c1->pixmap_bytes + c1->other_bytes) > (c2->pixmap_bytes + c2->other_bytes))
    return -1;

  return 1;
}


static void
xrestop_sort(XResTopApp *app)
{
  qsort((void *)app->clients, app->n_clients, sizeof(app->clients[0]), xrestop_sort_compare);
}


int 
main(int argc, char **argv)
{
  int      i, j, event, error, major, minor;
  XResTopApp *app = NULL;

  app = malloc(sizeof(XResTopApp));
  memset(app, 0, sizeof(XResTopApp));

  app->delay = 2;

  for (i = 1; i < argc; i++) {
    if (!strcmp ("-display", argv[i]) || !strcmp ("-d", argv[i])) {
      if (++i>=argc) usage (argv[0]);
      app->dpy_name = argv[i];
      continue;
    }

    if (!strcmp("-atom", argv[i]) || !strcmp("-a", argv[i])) {
      if (++i>=argc) usage (argv[0]);
      if (!argv[i]) usage (argv[0]);
      if (app->atoms_wanted_cnt)
        {
          for (j=0; j < app->atoms_wanted_cnt; ++j)
            {
              if (strcmp(argv[i], app->atoms_wanted[j]) == 0)
                {
                  fprintf(stderr,
                       "%s: ERROR: -a/-atom '%s' specified multiple times.\n",
                       argv[0], argv[i]);
                  exit(1);
                }
            }
        }
      app->atoms_wanted = realloc(app->atoms_wanted,
                    (app->atoms_wanted_cnt+1)*sizeof(char*));
      if (!app->atoms_wanted)
        {
          fprintf(stderr, "%s: ERROR: realloc() failure.\n", argv[0]);
          exit(1);
        }
      app->atoms_wanted[app->atoms_wanted_cnt] = argv[i];
      app->atoms_wanted_cnt++;
      continue;
    }

    if (!strcmp("--help", argv[i]) || !strcmp("-h", argv[i])) {
      usage(argv[0]);
    }

    usage(argv[0]);
  }

  if ((app->dpy = XOpenDisplay(app->dpy_name)) == NULL)
    {
      fprintf(stderr, "%s: Unable to open display!\n", argv[0]);
      exit(1);
    }

  app->screen = DefaultScreen(app->dpy);
  app->win_root = RootWindow(app->dpy, app->screen); 
    
  XInternAtoms (app->dpy, AtomNames, ATOM_COUNT, False, app->atoms);

  if(!XResQueryExtension(app->dpy, &event, &error)) {
    fprintf(stderr, "%s: XResQueryExtension failed. Display Missing XRes extension ?\n", argv[0]);
    return 1;
  }

  if(!XResQueryVersion(app->dpy, &major, &minor)) {
    fprintf(stderr, "%s: XResQueryVersion failed, cannot continue.\n", argv[0]);
    return 1;
  }

  app->n_clients = 0;

  /* Create our own never mapped window so we can figure out this connection */
  app->win_dummy = XCreateSimpleWindow(app->dpy, app->win_root, 
				       0, 0, 16, 16, 0, None, None); 
  xrestop_populate_client_data(app);
  xrestop_build_atom_list(app);
  xrestop_calculate_client_bytes(app);
  xrestop_sort(app);
  xrestop_display(app);

  return 0;
}

