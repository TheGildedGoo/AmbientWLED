# -*- coding: utf-8 -*-
"""Script entry for settings actions (Test connection, Calibrate sync)."""
from __future__ import annotations

import sys

import xbmc
import xbmcaddon

import service as svc


def main():
    args = [a.lower() for a in sys.argv[1:]]
    if not args or args[0] in ("", "default"):
        xbmcaddon.Addon(svc.ADDON_ID).openSettings()
        return
    if args[0] == "test_connection":
        svc.test_connection()
        return
    if args[0] == "calibrate_sync":
        svc.calibrate_sync()
        return
    xbmc.log("[AmbientWLED] unknown script arg: %s" % args, xbmc.LOGWARNING)


if __name__ == "__main__":
    main()
