#!/home/voron/.KlipperScreen-env/bin/python
"""Screenshot / tap the KlipperScreen display (X :0) from a shell - for remote UI testing.

  ks_shot.py shot OUT.png          save a screenshot
  ks_shot.py tap X Y [OUT.png]     tap (XTest click) at X,Y; optional screenshot 1.5 s later
"""
import ctypes, os, sys, time

os.environ.setdefault("DISPLAY", ":0")
import gi
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk


def shot(path):
    w = Gdk.get_default_root_window()
    g = w.get_geometry()
    Gdk.pixbuf_get_from_window(w, 0, 0, g.width, g.height).savev(path, "png", [], [])


def tap(x, y):
    x11 = ctypes.CDLL("libX11.so.6")
    xt = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    d = x11.XOpenDisplay(None)
    xt.XTestFakeMotionEvent(ctypes.c_void_p(d), -1, int(x), int(y), 0)
    x11.XFlush(ctypes.c_void_p(d))
    time.sleep(0.05)
    xt.XTestFakeButtonEvent(ctypes.c_void_p(d), 1, 1, 0)
    x11.XFlush(ctypes.c_void_p(d))
    time.sleep(0.08)
    xt.XTestFakeButtonEvent(ctypes.c_void_p(d), 1, 0, 0)
    x11.XFlush(ctypes.c_void_p(d))
    x11.XCloseDisplay(ctypes.c_void_p(d))


if __name__ == "__main__":
    if sys.argv[1] == "shot":
        shot(sys.argv[2])
    elif sys.argv[1] == "tap":
        tap(sys.argv[2], sys.argv[3])
        if len(sys.argv) > 4:
            time.sleep(1.5)
            shot(sys.argv[4])
