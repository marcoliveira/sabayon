/*
 * Copyright (C) 2005 Red Hat, Inc.
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
 * 02111-1307, USA.

 * Authors:
 *      Mark McLoughlin <markmc@redhat.com>
 */

#include <config.h>

#include <Python.h>
#include <pygobject.h>
#include <X11/Xlib.h>
#include <gdk/gdk.h>
#include <gdk/gdkx.h>

static PyObject *
xlib_send_key_event (PyObject *self,
		     PyObject *args)
{
  PyGObject     *window;
  GdkWindow     *gdkwindow;
  GdkScreen     *screen;
  XEvent         xevent;
  int            press;
  unsigned long  time;
  int            state;
  int            hardware_keycode;

  if (!PyArg_ParseTuple (args, "Oilii:xlib.send_event", &window, &press, &time, &state, &hardware_keycode))
    return NULL;

  if (!GDK_IS_WINDOW (window->obj))
    {
      PyErr_SetString (PyExc_TypeError, "window should be a GdkWindow");
      return NULL;
    }

  gdkwindow = GDK_WINDOW (window->obj);

  screen = gdk_drawable_get_screen (gdkwindow);

  xevent.xkey.type        = press ? KeyPress : KeyRelease;
  xevent.xkey.window      = GDK_WINDOW_XWINDOW (gdkwindow);
  xevent.xkey.root        = GDK_WINDOW_XWINDOW (gdk_screen_get_root_window (screen));
  xevent.xkey.subwindow   = None;
  xevent.xkey.time        = time;
  xevent.xkey.x           = 0;
  xevent.xkey.y           = 0;
  xevent.xkey.x_root      = 0;
  xevent.xkey.y_root      = 0;
  xevent.xkey.state       = state;
  xevent.xkey.keycode     = hardware_keycode;
  xevent.xkey.same_screen = True;

  gdk_error_trap_push ();

  XSendEvent (GDK_WINDOW_XDISPLAY (gdkwindow),
	      GDK_WINDOW_XWINDOW (gdkwindow),
	      False,
	      KeyPressMask,
	      &xevent);

  gdk_display_sync (gdk_screen_get_display (screen));
  gdk_error_trap_pop ();

  Py_INCREF (Py_None);
  return Py_None;
}

static struct PyMethodDef xlib_methods[] =
{
  { "send_key_event", xlib_send_key_event, METH_VARARGS },
  { NULL,             NULL,                0            }
};

void initxlib (void);

DL_EXPORT (void)
initxlib (void)
{
  PyObject *mod;

  mod = Py_InitModule4 ("xlib", xlib_methods, 0, 0, PYTHON_API_VERSION);

}
