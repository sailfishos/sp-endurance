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
 *  Copyright (C) 2006,2007 by Nokia Corporation
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
  /* builtin resources */
  ATOM_WINDOW = 0,
  ATOM_PIXMAP,
  ATOM_GC,
  ATOM_FONT,
  ATOM_CURSOR,
  ATOM_COLORMAP,
  ATOM_COLORMAP_ENTRY,
  ATOM_OTHER_CLIENT,
  ATOM_PASSIVE_GRAB,
  /* Render extension */
  ATOM_PICTURE,
  ATOM_PICTFORMAT,
  ATOM_GLYPHSET,
  /* RandR extension */
  ATOM_CRTC,
  ATOM_MODE,
  ATOM_OUTPUT,
  /* Xi extension */
  ATOM_INPUTCLIENT,
  /* non-resource atoms */
  ATOM_NET_CLIENT_LIST,
  ATOM_NET_WM_PID,
  ATOM_NET_WM_NAME,
  ATOM_UTF8_STRING,
  ATOM_COUNT
};

static const char *AtomNames[] =
  {
    "WINDOW",
    "PIXMAP",
    "GC",
    "FONT",
    "CURSOR",
    "COLORMAP",
    "COLORMAP ENTRY",
    "OTHER CLIENT",
    "PASSIVE GRAB",
    "PICTURE",
    "PICTFORMAT",
    "GLYPHSET",
    "CRTC",
    "MODE",
    "OUTPUT",
    "INPUTCLIENT",
    "_NET_CLIENT_LIST",
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
  /* basic types */
  int            n_windows; 
  int            n_pixmaps;
  int            n_gcs;
  int            n_fonts;
  int            n_cursors;
  int            n_colormaps;
  int            n_map_entries;
  int            n_other_clients;
  int            n_passive_grabs;
  /* render extension */
  int            n_pictures;
  int            n_pictformats;
  int            n_glyphsets;
  /* randr extension */
  int            n_crtcs;
  int            n_modes;
  int            n_outputs;
  /* xi */
  int            n_input_clients;
  /* unknown (if any -> update list) */
  int            n_unknown;

} XResTopClient;

#define MAX_CLIENTS 1024  /* XXX find out max connections per server */

typedef struct XResTopApp 
{
  Display    *dpy;
  char       *dpy_name;
  int         screen;
  Window      win_root, win_dummy;
  Atom        atoms[ATOM_COUNT];

  XResTopClient *clients[MAX_CLIENTS];
  int         n_clients;
  
  Bool        want_batch_mode;
  int         delay;
  int         n_xerrors;

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
	  "  -display,     -d        specify X Display to monitor.\n\n",
	  progname);

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
  int               j = 0;
  XResType         *types = NULL;
  int               n_types;

  trap_errors();
  
  XResQueryClientResources (app->dpy, client->resource_base, &n_types, &types);
  
  XResQueryClientPixmapBytes (app->dpy, client->resource_base, 
			      &client->pixmap_bytes);
  
  if (untrap_errors())
    {
      app->n_xerrors++;
      goto cleanup;
    }
  
  for (j=0; j < n_types; j++)
    {
      unsigned int this_type = types[j].resource_type;
      
      if (this_type == app->atoms[ATOM_WINDOW])
	client->n_windows += types[j].count;
      else if (this_type == app->atoms[ATOM_PIXMAP])
	client->n_pixmaps += types[j].count;
      else if (this_type == app->atoms[ATOM_GC])
	client->n_gcs += types[j].count;
      else if (this_type == app->atoms[ATOM_FONT])
	client->n_fonts += types[j].count;
      else if (this_type == app->atoms[ATOM_CURSOR])
	client->n_cursors += types[j].count;
      else if (this_type == app->atoms[ATOM_COLORMAP])
	client->n_colormaps += types[j].count;
      else if (this_type == app->atoms[ATOM_COLORMAP_ENTRY])
	client->n_map_entries += types[j].count;
      else if (this_type == app->atoms[ATOM_OTHER_CLIENT])
	client->n_other_clients += types[j].count;
      else if (this_type == app->atoms[ATOM_PASSIVE_GRAB])
	client->n_passive_grabs += types[j].count;

      else if (this_type == app->atoms[ATOM_PICTURE])
	client->n_pictures += types[j].count;
      else if (this_type == app->atoms[ATOM_PICTFORMAT])
	client->n_pictformats += types[j].count;
      else if (this_type == app->atoms[ATOM_GLYPHSET])
	client->n_glyphsets += types[j].count;

      else if (this_type == app->atoms[ATOM_CRTC])
	client->n_crtcs += types[j].count;
      else if (this_type == app->atoms[ATOM_MODE])
	client->n_modes += types[j].count;
      else if (this_type == app->atoms[ATOM_OUTPUT])
	client->n_outputs += types[j].count;

      else if (this_type == app->atoms[ATOM_INPUTCLIENT])
	client->n_input_clients += types[j].count;

      else
	{
	   client->n_unknown += types[j].count;
	   fprintf(stderr, "WARNING: %d unknown resources of type %d for %s\n", types[j].count, this_type, client->identifier);
	}
    }

  /* All approx currently - same as gnome system monitor */
   client->other_bytes += client->n_windows * 24;
   client->other_bytes += client->n_gcs * 24;
   client->other_bytes += client->n_fonts * 1024;
   client->other_bytes += client->n_cursors * 24;
   client->other_bytes += client->n_colormaps * 24;
   client->other_bytes += client->n_map_entries * 24;
   client->other_bytes += client->n_other_clients * 24;
   client->other_bytes += client->n_passive_grabs * 24;

   client->other_bytes += client->n_pictures * 24;
   client->other_bytes += client->n_pictformats * 24;
   client->other_bytes += client->n_glyphsets * 24;

   client->other_bytes += client->n_crtcs * 24;
   client->other_bytes += client->n_modes * 24;
   client->other_bytes += client->n_outputs * 24;

   client->other_bytes += client->n_input_clients * 24;

   client->other_bytes += client->n_unknown * 24;

 cleanup:
   if (types) XFree(types);

   return;
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

static void
xrestop_display(XResTopApp *app)
{
	int  i;
	
	printf("res-base,Windows,Pixmaps,GCs,Fonts,Cursors,Colormaps,Map entries,Other clients,Grabs,Pictures,Pictformats,Glyphsets,CRTCs,Modes,Outputs,Xi clients,Unknown,Pixmap mem,Misc mem,Total mem,PID,Identifier\n");

	for (i = 0; i < app->n_clients; i++)
	{
		printf("%.7x,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%liB,%liB,%liB,%d,%s\n", 
		       (unsigned int)app->clients[i]->resource_base, 
		       app->clients[i]->n_windows, 
		       app->clients[i]->n_pixmaps,
		       app->clients[i]->n_gcs,
		       app->clients[i]->n_fonts,
		       app->clients[i]->n_cursors,
		       app->clients[i]->n_colormaps,
		       app->clients[i]->n_map_entries,
		       app->clients[i]->n_other_clients,
		       app->clients[i]->n_passive_grabs,

		       app->clients[i]->n_pictures,
		       app->clients[i]->n_pictformats,
		       app->clients[i]->n_glyphsets,

		       app->clients[i]->n_crtcs,
		       app->clients[i]->n_modes,
		       app->clients[i]->n_outputs,

		       app->clients[i]->n_input_clients,

		       app->clients[i]->n_unknown,
		       
		       app->clients[i]->pixmap_bytes,
		       app->clients[i]->other_bytes,
		       app->clients[i]->pixmap_bytes
		       + app->clients[i]->other_bytes,
		       
		       app->clients[i]->pid,	/* -1 for unknown */
		       app->clients[i]->identifier
		       );
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
  int      i, event, error, major, minor;
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
  xrestop_sort(app);
  xrestop_display(app);

  return 0;
}

