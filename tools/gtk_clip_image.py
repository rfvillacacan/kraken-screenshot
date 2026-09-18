#!/usr/bin/env python3
"""Set Wayland/X11 clipboard image via GTK (subprocess helper)."""
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        return 2
    path = sys.argv[1]
    if Gdk.Display.get_default() is None:
        return 3
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
    clip = Gtk.Clipboard.get_default(Gdk.Display.get_default())
    clip.set_image(pixbuf)
    clip.store()
    ctx = GLib.MainContext.default()
    end = GLib.get_monotonic_time() + 500_000
    while GLib.get_monotonic_time() < end:
        ctx.iteration(True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
