# ==========================================================
# ArchitectOS — Runtime Logging Setup  (LOG_ROTATION_FIX_01)
#
# ROOT CAUSE THIS ADDRESSES
# -------------------------
# The Core API (app.py, Flask/Werkzeug) emits one access-log
# line per HTTP request. The launcher previously redirected the
# child's stdout to logs/runtime/core_api.log with a bare
# open(path, "ab") handle: no size limit, no rotation. Combined
# with the UI's 2500 ms /save-state poller (and several tabs left
# open), the file grew ~4.9 MB/min and reached 1.26 GB; 4.7 GB of
# logs/runtime/*.log accumulated on disk.
#
# WHAT THIS MODULE DOES
# ---------------------
# Gives each service ONE writer for its log file: a size-bounded
# RotatingFileHandler attached only to the ROOT logger, with a
# stream handler that re-emits everything into the logging tree.
#
# WHY ROOT-ONLY (no per-logger handlers)
# --------------------------------------
# Werkzeug and Flask already propagate to the root logger. Adding
# the same file handler to "werkzeug", "flask.app" AND root made
# every line land in the file TWICE. Root-only attachment removes
# the duplication while still capturing werkzeug/framework/app
# records, errors and tracebacks.
#
# WHY ROTATION LIVES HERE (in the service process)
# ------------------------------------------------
# start_service() starts services DETACHED, so a launcher-side
# writer cannot outlive the launcher. The bound must therefore be
# enforced inside the service. Subprocess.Popen(stdout=<file>)
# passes the RAW OS descriptor to the child, so Python write()
# wrappers on the launcher side would never count bytes - another
# reason the cap belongs in the logging layer of the service.
#
# ONE WRITER, NO LEAKAGE
# ----------------------
# configure_runtime_logging() also redirects the process's
# OS-level stdout/stderr (sys.stdout, sys.stderr and fd 1/2) into
# the logging system. That keeps assert/print/werkzeug-raw output
# inside the bounded file instead of escaping to an unbounded
# inherited descriptor. The launcher points child stdout at
# DEVNULL for the same reason.
#
# It does NOT disable logging. Errors, tracebacks and warnings are
# all preserved; only the volume of routine access lines is
# bounded by rotation.
# ==========================================================

import logging
import logging.handlers
import os
import sys


# Keep the active file plus this many rotated generations.
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 5


def _policy():
    """Read the canonical policy from runtime config when possible."""

    max_bytes = DEFAULT_MAX_BYTES
    backup_count = DEFAULT_BACKUP_COUNT
    log_dir = None

    try:

        from config import runtime_config as RC

        max_bytes = getattr(RC, "LOG_MAX_BYTES", max_bytes)
        backup_count = getattr(RC, "LOG_BACKUP_COUNT", backup_count)
        log_dir = getattr(RC, "LOG_DIR", None)

    except Exception:

        pass

    if not log_dir:

        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs",
            "runtime"
        )

    return log_dir, int(max_bytes), int(backup_count)


class _LoggingStream:
    """File-like object that forwards writes into a logger.

    Used to replace sys.stdout / sys.stderr so that nothing a
    service prints can bypass the bounded file.
    """

    def __init__(self, logger, level):

        self._logger = logger
        self._level = level
        self._buffer = ""

    def write(self, message):

        # Werkzeug / Flask sometimes write bytes to sys.stdout
        # (e.g. its startup banner). Decode rather than str() so the
        # log never contains b'...' noise.
        if isinstance(message, (bytes, bytearray)):

            message = bytes(message).decode("utf-8", "replace")

        elif not isinstance(message, str):

            message = str(message)

        self._buffer += message

        while "\n" in self._buffer:

            line, self._buffer = self._buffer.split("\n", 1)

            line = line.rstrip("\r")

            if line.strip():

                self._logger.log(self._level, line)

        return len(message)

    def flush(self):

        if self._buffer.strip():

            self._logger.log(self._level, self._buffer.rstrip("\r"))

        self._buffer = ""

    def writable(self):

        return True

    def isatty(self):

        return False


def configure_runtime_logging(service_name="core_api", level=logging.INFO):
    """Attach ONE bounded rotating file handler to the root logger.

    Returns the handler (or None when setup could not be completed,
    in which case logging still works via the existing stdout path).
    """

    log_dir, max_bytes, backup_count = _policy()

    try:

        os.makedirs(log_dir, exist_ok=True)

    except OSError:

        return None

    log_path = os.path.join(log_dir, service_name + ".log")

    try:

        handler = logging.handlers.RotatingFileHandler(

            log_path,

            maxBytes=max_bytes,

            backupCount=backup_count,

            encoding="utf-8",

        )

    except OSError:

        return None

    handler.setFormatter(

        logging.Formatter(

            "%(asctime)s %(levelname)s %(name)s: %(message)s"

        )

    )

    handler.setLevel(level)

    root = logging.getLogger()

    # Avoid stacking duplicate file handlers across repeated calls
    # (e.g. Flask's reloader importing the module twice).
    for existing in list(root.handlers):

        if (
            isinstance(existing, logging.handlers.RotatingFileHandler)
            and getattr(existing, "baseFilename", None) == handler.baseFilename
        ):

            root.removeHandler(existing)

    root.addHandler(handler)

    if root.level == logging.NOTSET or root.level > level:

        root.setLevel(level)

    # Capture the raw OS-level streams so nothing bypasses the file.
    try:

        sys.stdout = _LoggingStream(root, logging.INFO)
        sys.stderr = _LoggingStream(root, logging.ERROR)

    except Exception:

        pass

    return handler
