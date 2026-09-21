# -*- coding: utf-8 -*-
"""Couch-remote entry: open AmbientWLED settings (stored on the service addon)."""
from __future__ import annotations

import sys

import xbmc
import xbmcaddon
import xbmcplugin

SERVICE_ID = "script.service.ambientwled"
PLUGIN_ID = "plugin.program.ambientwled"


def run(handle):
    # Settings live on the service so one store survives CE updates.
    xbmcaddon.Addon(SERVICE_ID).openSettings()
    xbmcplugin.endOfDirectory(handle, succeeded=True)


if __name__ == "__main__":
    handle = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    try:
        run(handle)
    except Exception as e:
        xbmc.log("[AmbientWLED] plugin openSettings failed: %s" % e, xbmc.LOGERROR)
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)
