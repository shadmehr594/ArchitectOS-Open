# ==========================================================
# ARCHITECTOS_NO_CONSOLE_WINDOW_V1
#
# ArchitectOS services are started DETACHED (no console). On Windows, a
# console-less parent that spawns a console program (python.exe, where.exe,
# a converter ...) makes Windows allocate a BRAND NEW console window for the
# child — a black window that flashes on the user's desktop.
#
# Measured 2026-10-25: Core spawned
#   C:\...\Python311\python.exe -c "import whisper"
# every ~15 s (once per /api/voice/status poll) and every spawn created a
# conhost.exe. Ten occurrences were captured in 150 s.
#
# CREATE_NO_WINDOW tells Windows to create the child WITHOUT a console.
# It does not affect stdout/stderr redirection, exit codes or timeouts, so
# capture_output=True keeps working exactly as before.
# ==========================================================

from __future__ import annotations

import os
import subprocess

CREATE_NO_WINDOW = 0x08000000


def no_window_kwargs():
    """Extra ``subprocess`` kwargs that keep a console child invisible.

    Returns an empty dict off Windows so call sites stay portable.
    """

    if os.name != "nt":

        return {}

    kwargs = {"creationflags": CREATE_NO_WINDOW}

    try:

        startupinfo = subprocess.STARTUPINFO()

        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        startupinfo.wShowWindow = subprocess.SW_HIDE

        kwargs["startupinfo"] = startupinfo

    except Exception:

        # CREATE_NO_WINDOW alone is already sufficient; never fail the call.
        pass

    return kwargs
