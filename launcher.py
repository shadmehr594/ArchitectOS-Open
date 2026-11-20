# ==========================================================
# ARCHITECTOS v57 LAUNCHER CORE
# Product Runtime Controller
#
# RUNTIME_FOUNDATION_01
#
# Responsibilities:
#   - select a Python interpreter that actually has the deps
#   - START the ArchitectOS-owned services  (Core API + UI)
#   - VERIFY every runtime dependency:
#         CORE_API, UI, COMFYUI, OLLAMA
#     plus required workflow files and ComfyUI paths
#
# Explicitly NOT done:
#   - ComfyUI and Ollama are EXTERNALLY managed. They are only
#     detected and reported. They are never started or installed.
#   - No render / image generation is triggered by the launcher.
# ==========================================================


import json
import os
import subprocess
import sys
import time
import secrets
import webbrowser


# ==========================================================
# REPO ROOT ON sys.path (so "config" / "core" always resolve)
# ==========================================================

ROOT = os.path.dirname(
    os.path.abspath(__file__)
)

if ROOT not in sys.path:

    sys.path.insert(
        0,
        ROOT
    )


from config import runtime_config as RC

from core.runtime.runtime_preflight import (
    run_preflight,
    format_report,
    probe_http,
)



VERSION = "ARCHITECTOS v57 PRODUCT EDITION"

# One launch, one trust domain. These values are inherited only by the two
# ArchitectOS-owned child processes. The bootstrap is put in a URL fragment
# (never sent in an HTTP request/access log); the proxy secret never enters
# the browser.
_LOCAL_PROXY_SECRET = secrets.token_urlsafe(48)
_LOCAL_BOOTSTRAP_TOKEN = secrets.token_urlsafe(48)


LOG_DIR = os.path.join(
    ROOT,
    "logs",
    "runtime"
)


# ==========================================================
# BOUNDED SERVICE LOG  (LOG_ROTATION_FIX_01)
#
# WHY THIS EXISTS
# ---------------
# start_service() used to hand the child process a bare
#     open(log_path, "ab")
# handle. That handle has no maximum size and is never rotated,
# so any chatty child (notably the Core API, whose Werkzeug
# request logger emits one line per HTTP request) grows its log
# forever. Under UI polling this reached ~4.9 MB/min, i.e.
# hundreds of GB per month, and 4.7 GB of logs/runtime/*.log
# accumulated on disk.
#
# WHERE ROTATION IS ENFORCED (and why not in the launcher)
# --------------------------------------------------------
# The launcher must be able to EXIT while the services keep
# running: _creation_flags() starts every child with
# DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP. A launcher-side
# drain thread therefore cannot be the writer - it dies with the
# launcher, and a launcher-held pipe would close under the
# detached child.
#
# Rotation is consequently enforced INSIDE each service process
# by core/runtime_logging.py (RotatingFileHandler), which is a
# belt-and-braces bound that works no matter how a service was
# launched. The launcher's only logging duty is to hand the child
# an appendable, INHERITABLE handle so its stdout/stderr survive
# the launcher's exit - exactly as before, but the service now
# caps the file itself.
#
# Note the trap this avoids: subprocess.Popen(stdout=<python file
# object>) calls fileno() and passes the RAW OS DESCRIPTOR to the
# child, so Python's write() on such an object is never invoked
# (proved: write() calls == 0). Byte-counting in a wrapper object
# therefore would never fire. That is why the cap lives in the
# child's logging handler, not in a file wrapper here.
# ==========================================================

try:

    from config.runtime_config import (
        LOG_MAX_BYTES,
        LOG_BACKUP_COUNT,
    )

except Exception:

    # Launcher must still run even if config is unavailable.
    LOG_MAX_BYTES = 32 * 1024 * 1024
    LOG_BACKUP_COUNT = 5





# ==========================================================
# BANNER
# ==========================================================

def banner():

    print("=" * 60)
    print("        " + VERSION)
    print("=" * 60)



# ==========================================================
# ENVIRONMENT
# ==========================================================

def localhost_env(pythonpath=None):
    """Environment for child services.

    Localhost traffic must bypass any ambient HTTP_PROXY - otherwise
    UI -> Core API calls get proxied and fail.
    """

    env = os.environ.copy()

    bypass = [
        "127.0.0.1",
        "localhost",
        "::1",
        RC.CORE_API_HOST,
        RC.UI_HOST,
        RC.COMFYUI_HOST,
        RC.OLLAMA_HOST,
    ]

    existing = (
        env.get("NO_PROXY")
        or env.get("no_proxy")
        or ""
    )

    merged = [
        item.strip()
        for item in (
            existing.split(",") + bypass
        )
        if item.strip()
    ]

    # keep order, drop duplicates
    merged = list(
        dict.fromkeys(merged)
    )

    value = ",".join(merged)

    env["NO_PROXY"] = value
    env["no_proxy"] = value

    env["ARCHITECTOS_LOCAL_PROXY_SECRET"] = _LOCAL_PROXY_SECRET
    env["ARCHITECTOS_LOCAL_BOOTSTRAP_TOKEN"] = _LOCAL_BOOTSTRAP_TOKEN

    # ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — when the service runs on the base
    # interpreter (no delegating venv shim) it must still see the venv's
    # packages and the project root.
    if pythonpath:

        merged = [
            item.strip()
            for item in (
                (env.get("PYTHONPATH") or "").split(os.pathsep)
                + str(pythonpath).split(os.pathsep)
            )
            if item.strip()
        ]

        env["PYTHONPATH"] = os.pathsep.join(list(dict.fromkeys(merged)))

    return env



def pick_python():
    """Prefer the project venv interpreter - the system Python may
    not have flask / requests installed at all."""

    candidates = []

    if os.name == "nt":

        candidates.append(
            os.path.join(
                ROOT,
                ".venv",
                "Scripts",
                "python.exe"
            )
        )

    else:

        candidates.append(
            os.path.join(
                ROOT,
                ".venv",
                "bin",
                "python"
            )
        )

    candidates.append(
        sys.executable
    )


    for candidate in candidates:

        if candidate and os.path.isfile(candidate):

            normalized = candidate.replace("\\", "/")

            is_venv = "/.venv/" in normalized

            return candidate, is_venv


    return sys.executable, False


def _venv_root(python_path):
    """The venv directory owning ``python_path`` (<venv>/Scripts/python.exe)."""

    if not python_path:

        return None

    return os.path.dirname(
        os.path.dirname(
            os.path.abspath(python_path)
        )
    )


def _real_interpreter(python_path):
    """Resolve the REAL interpreter behind a delegating venv launcher.

    ARCHITECTOS_LAUNCHER_PERSISTENCE_V1.

    The project venv's ``python.exe`` is a delegating launcher: it re-executes
    the base interpreter as a CHILD with the same argv. Measured on this
    machine: PID 45640 (``.venv\\Scripts\\python.exe``) spawned PID 26548
    (base interpreter), and killing 45640 killed 26548 with it.

    That single hop breaks the launcher three ways:

    * the recorded pid is the launcher shim, not the process holding the port
      (observed: pid files held 14248/43260 while ports were held by their
      children 43108/11100);
    * readiness and death detection watch the shim, so a dead service can look
      healthy for as long as the shim lingers;
    * the service's lifetime is chained to the shim, which is chained to the
      launcher's process tree — so the launcher reports READY and then nothing
      survives.

    Spawning the base interpreter directly removes the hop, so the pid the
    launcher records IS the service.
    """

    venv_root = _venv_root(python_path)

    if not venv_root:

        return None

    cfg = os.path.join(
        venv_root,
        "pyvenv.cfg"
    )

    if not os.path.isfile(cfg):

        return None

    home = None
    executable = None

    try:

        with open(cfg, "r", encoding="utf-8", errors="replace") as handle:

            for line in handle:

                if "=" not in line:

                    continue

                key, _, value = line.partition("=")

                key = key.strip().lower()

                value = value.strip()

                if key == "home":

                    home = value

                elif key == "executable":

                    executable = value

    except OSError:

        return None

    candidates = []

    if executable:

        candidates.append(executable)

    if home:

        candidates.append(
            os.path.join(
                home,
                "python.exe" if os.name == "nt" else "python"
            )
        )

    target = os.path.normcase(os.path.abspath(python_path))

    for candidate in candidates:

        if not candidate or not os.path.isfile(candidate):

            continue

        if os.path.normcase(os.path.abspath(candidate)) == target:

            continue

        return candidate

    return None


def _venv_site_packages(python_path):
    """The venv's site-packages directory, or None."""

    venv_root = _venv_root(python_path)

    if not venv_root:

        return None

    if os.name == "nt":

        candidate = os.path.join(venv_root, "Lib", "site-packages")

    else:

        import glob

        matches = sorted(
            glob.glob(
                os.path.join(venv_root, "lib", "python*", "site-packages")
            )
        )

        candidate = matches[-1] if matches else None

    if candidate and os.path.isdir(candidate):

        return candidate

    return None


def service_interpreter(python_path):
    """(interpreter, PYTHONPATH) used to spawn an ArchitectOS service.

    Prefers the real interpreter so the spawned process is the service itself.
    Falls back to ``python_path`` unchanged when the venv layout cannot be
    resolved, which preserves the previous behaviour rather than guessing.
    """

    real = _real_interpreter(python_path)

    if not real:

        return python_path, None

    parts = []

    site = _venv_site_packages(python_path)

    if site:

        parts.append(site)

    parts.append(ROOT)

    return real, os.pathsep.join(parts)


def _url_port(url):
    """The TCP port named by ``url``, or None."""

    try:

        from urllib.parse import urlparse

        parsed = urlparse(str(url))

        if parsed.port:

            return parsed.port

        return 443 if parsed.scheme == "https" else 80

    except Exception:

        return None


def _listening_pid(port):
    """The PID that actually holds ``port``, or None.

    ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — this is the only trustworthy source
    for "which process is the service". A saved pid file can name a parent, a
    shim, or a recycled pid; the listening socket cannot.
    """

    if os.name != "nt" or not port:

        return None

    try:

        completed = subprocess.run(

            ["netstat", "-ano", "-p", "tcp"],

            capture_output=True,

            text=True,

            timeout=10800

        )

    except Exception:

        return None

    for line in (completed.stdout or "").splitlines():

        parts = line.split()

        if len(parts) < 5:

            continue

        if parts[3].upper() != "LISTENING":

            continue

        if parts[1].rsplit(":", 1)[-1] != str(port):

            continue

        try:

            return int(parts[4])

        except ValueError:

            continue

    return None


def _image_name(pid):
    """The executable image name for ``pid``, or None.

    DIAGNOSTIC ONLY. An image name of ``python.exe`` is NOT proof that a
    process belongs to ArchitectOS — any Python can own the port. Use
    ``_verify_service_identity`` before terminating anything.
    """

    if os.name != "nt":

        return None

    try:

        completed = subprocess.run(

            ["tasklist", "/FI", "PID eq %d" % int(pid), "/FO", "CSV", "/NH"],

            capture_output=True,

            text=True,

            timeout=10800

        )

    except Exception:

        return None

    for line in (completed.stdout or "").splitlines():

        line = line.strip()

        if not line.startswith('"'):

            continue

        return line.split('","')[0].strip('"')

    return None


# ==========================================================
# SERVICE IDENTITY VERIFICATION
#
# ARCHITECTOS_LAUNCHER_IDENTITY_V1 — owning port 3000/5000 with a python.exe
# image is NOT proof that a process belongs to ArchitectOS. Any Python on the
# machine can bind those ports, and a saved pid can be stale or recycled.
# Termination therefore requires positive, independent identity evidence, and
# every unknown fails CLOSED: the process is left alone and the reason is
# printed.
# ==========================================================

#: The entry point each ArchitectOS-owned service must be running.
_SERVICE_ENTRY_POINTS = {
    "CORE_API": "app.py",
    "UI": "ui/app.py",
}


def _powershell_exe():
    """Path to Windows PowerShell, or None."""

    if os.name != "nt":

        return None

    candidate = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32",
        "WindowsPowerShell",
        "v1.0",
        "powershell.exe"
    )

    return candidate if os.path.isfile(candidate) else None


def _process_identity(pid):
    """(exe_path, command_line, creation_epoch) for ``pid``, or None.

    None means "could not establish identity" — callers must fail closed.
    """

    powershell = _powershell_exe()

    if not powershell:

        return None

    script = (
        "$p = Get-CimInstance Win32_Process -Filter 'ProcessId=%d' "
        "-ErrorAction SilentlyContinue; "
        "if ($p) { [pscustomobject]@{ "
        "exe = $p.ExecutablePath; "
        "cmd = $p.CommandLine; "
        "created = ([DateTimeOffset]$p.CreationDate).ToUnixTimeSeconds() "
        "} | ConvertTo-Json -Compress }"
    ) % int(pid)

    try:

        completed = subprocess.run(

            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],

            capture_output=True,

            text=True,

            timeout=10800

        )

    except Exception:

        return None

    raw = (completed.stdout or "").strip()

    if not raw:

        return None

    try:

        import json

        data = json.loads(raw)

    except Exception:

        return None

    if not isinstance(data, dict):

        return None

    exe = data.get("exe")
    cmd = data.get("cmd")
    created = data.get("created")

    try:

        created = int(created)

    except (TypeError, ValueError):

        created = None

    if not exe or not cmd:

        return None

    return str(exe), str(cmd), created


def _allowed_interpreters():
    """Every interpreter an ArchitectOS service may legitimately run on."""

    allowed = set()

    try:

        venv_python, _ = pick_python()

    except Exception:

        venv_python = None

    if venv_python:

        allowed.add(os.path.normcase(os.path.abspath(venv_python)))

        try:

            real, _ = service_interpreter(venv_python)

            if real:

                allowed.add(os.path.normcase(os.path.abspath(real)))

        except Exception:

            pass

    if sys.executable:

        allowed.add(os.path.normcase(os.path.abspath(sys.executable)))

    return allowed


def _cmdline_matches_entry(cmdline, entry):
    """True when ``cmdline`` runs exactly ``entry`` under the project root."""

    if not cmdline or not entry:

        return False

    normalized = str(cmdline).replace("/", "\\").strip().lower()

    wanted = entry.replace("/", "\\").lower()

    if wanted == "app.py":

        # ui\app.py must never satisfy the Core entry point.
        return normalized.endswith("app.py") and not normalized.endswith(
            "ui\\app.py"
        )

    return normalized.endswith(wanted)


def _owner_path(name):
    """Sidecar recording who owned the service when it was started."""

    return _pid_path(name).replace(".pid", ".owner.json")


def _read_recorded_owner(name):
    """The recorded owner record for ``name``, or None."""

    path = _owner_path(name)

    if not os.path.isfile(path):

        return None

    try:

        import json

        with open(path, "r", encoding="utf-8") as handle:

            data = json.load(handle)

    except Exception:

        return None

    return data if isinstance(data, dict) else None


def _verify_service_identity(name, pid):
    """(ok, reason) — positive proof that ``pid`` is the named service.

    Requires, independently of any saved pid file:

    * the process exists and its identity can be read at all;
    * its executable is one of this project's interpreters;
    * its command line runs the expected entry point for that service;
    * its creation time is plausible, and matches the recorded owner when one
      was recorded (a recycled pid cannot match).
    """

    entry = _SERVICE_ENTRY_POINTS.get(name)

    if not entry:

        return False, "unknown service '%s'" % name

    identity = _process_identity(pid)

    if identity is None:

        return False, "process identity could not be established"

    exe, cmdline, created = identity

    allowed = _allowed_interpreters()

    if os.path.normcase(os.path.abspath(exe)) not in allowed:

        return False, "executable '%s' is not a project interpreter" % exe

    if not _cmdline_matches_entry(cmdline, entry):

        return False, "command line does not run '%s'" % entry

    if created is None:

        return False, "creation time unavailable"

    # A plausible creation time rejects impossible/recycled records.
    if created < 1577836800:  # 2020-01-01

        return False, "implausible creation time (%s)" % created

    recorded = _read_recorded_owner(name)

    if isinstance(recorded, dict):

        recorded_pid = recorded.get("pid")

        recorded_created = recorded.get("created")

        if recorded_pid is not None and int(recorded_pid) != int(pid):

            return False, (
                "recorded owner was pid %s, not %s" % (recorded_pid, pid)
            )

        if recorded_created is not None:

            try:

                if abs(int(recorded_created) - created) > 2:

                    return False, (
                        "creation time %s does not match recorded %s "
                        "(recycled pid?)" % (created, recorded_created)
                    )

            except (TypeError, ValueError):

                return False, "recorded creation time unreadable"

    return True, "verified %s pid %s" % (entry, pid)


def python_has_deps(python):


    try:

        result = subprocess.run(

            [
                python,
                "-c",
                "import flask, flask_cors, requests; print('ok')"
            ],

            cwd=ROOT,

            capture_output=True,

            text=True,

            timeout=10800

        )

        return result.returncode == 0, (
            result.stdout + result.stderr
        ).strip()


    except Exception as e:

        return False, str(e)



# ==========================================================
# CHECKS (existing public helpers preserved)
# ==========================================================

def check_python():

    print("\n[1] Checking Python...")

    print(
        "Python:",
        sys.version.split()[0]
    )

    python, is_venv = pick_python()

    print(
        "Interpreter:",
        python
    )

    print(
        "Project venv:",
        "YES" if is_venv else "NO"
    )

    ok, detail = python_has_deps(
        python
    )

    print(
        "Runtime deps (flask/flask_cors/requests):",
        "OK" if ok else "MISSING"
    )

    if not ok:

        print(
            "  ->",
            detail.splitlines()[-1] if detail else "unknown"
        )

    return ok


def check_ollama():
    """Ollama is EXTERNALLY managed: detect + report only."""

    print("\n[2] Checking Ollama (external)...")

    probe = probe_http(
        RC.OLLAMA_URL + RC.OLLAMA_HEALTH_PATH
    )

    if probe["ok"]:

        body = probe.get("body") or {}

        models = [
            m.get("name")
            for m in body.get("models", [])
            if isinstance(m, dict)
        ]

        print("Ollama: ONLINE")
        print("Endpoint:", RC.OLLAMA_URL)

        print("Models:")

        for model in models:

            print(" -", model)

        return True

    print(
        "Ollama: OFFLINE ->",
        RC.OLLAMA_URL,
        probe.get("error")
    )

    return False


def check_comfyui():
    """ComfyUI is EXTERNALLY managed: detect + report only."""

    print("\n[3] Checking ComfyUI (external)...")

    probe = probe_http(
        RC.COMFYUI_URL + RC.COMFYUI_HEALTH_PATH
    )

    if probe["ok"]:

        body = probe.get("body") or {}

        version = (
            body.get("system", {})
            .get("comfyui_version")
        )

        print("ComfyUI: ONLINE")
        print("Endpoint:", RC.COMFYUI_URL)
        print("Root:", RC.COMFYUI_ROOT)
        print("Version:", version)

        return True

    print(
        "ComfyUI: OFFLINE ->",
        RC.COMFYUI_URL,
        probe.get("error")
    )

    return False


def check_bim():

    print("\n[4] Checking BIM Core...")


    try:

        from chatos.bim.bim_final_integration_v109 import BIMFinalIntegrationV109


        pipeline = BIMFinalIntegrationV109()


        print(
            "BIM Core: CONNECTED"
        )


        return True


    except Exception as e:


        print(
            "BIM Core ERROR:",
            e
        )


        return False



# ==========================================================
# SERVICE STARTUP (ArchitectOS-owned services only)
# ==========================================================

def trusted_ui_url(ui_url, token, freshly_started):
    """The one-time trusted-local bootstrap URL, or None.

    The token is this launch's secret. It may only be handed to a browser when
    the Core and UI processes were STARTED BY THIS LAUNCH and therefore share
    it. Reusing already-running services must never produce a URL: their trust
    domain belongs to a different launch, and advertising a fresh token against
    them would fail closed in the browser and look like a product fault.
    """
    if not freshly_started:
        return None
    if not isinstance(token, str) or len(token) < 32:
        return None
    if not isinstance(ui_url, str) or not ui_url.strip():
        return None
    # The fragment is never sent to the server, so the token stays out of
    # access logs and out of the request line.
    return ui_url.rstrip("/") + "/#local-bootstrap=" + token


def _creation_flags():
    """Detach services from this controller.

    Without DETACHED_PROCESS the Core API / UI are attached to the
    launcher's console and die as soon as it exits - so the launcher
    would report READY and leave nothing running.
    """

    if os.name == "nt":

        return (

            subprocess.DETACHED_PROCESS

            | subprocess.CREATE_NEW_PROCESS_GROUP

        )

    return 0



def _pid_path(name):


    return os.path.join(
        LOG_DIR,
        name.lower() + ".pid"
    )


def _launcher_log(message):
    """Append ONE diagnostic line to logs/runtime/launcher.log.

    ARCHITECTOS_LAUNCHER_DIAGNOSTICS_V1 — the launcher used to write its whole
    verdict to the console only. A double-clicked BAT closes that console, so a
    failed launch left no evidence at all: the user saw "nothing happened" and
    there was nothing to inspect afterwards. This keeps a bounded, secret-free
    trace of what the launcher decided.

    NEVER pass a bootstrap URL, a token or the proxy secret here.
    """

    try:

        path = os.path.join(LOG_DIR, "launcher.log")

        if os.path.isfile(path) and os.path.getsize(path) > 2 * 1024 * 1024:

            try:

                os.replace(path, path + ".1")

            except OSError:

                pass

        with open(path, "a", encoding="utf-8", errors="replace") as handle:

            handle.write(
                time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(message) + "\n"
            )

    except Exception:

        # Diagnostics must never break the launch itself.
        pass


def _record_service_pid(name, url, spawned_pid=None):
    """Persist the PID that ACTUALLY holds the service port.

    ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — the saved pid used to be whatever
    Popen returned, which on this machine is a delegating venv shim rather than
    the server (observed: pid files held 14248/43260 while ports were held by
    43108/11100). Recording the socket owner makes shutdown verifiable.
    """

    owner = _listening_pid(_url_port(url))

    chosen = owner or spawned_pid

    if not chosen:

        return None

    try:

        with open(_pid_path(name), "w", encoding="utf-8") as handle:

            handle.write(str(int(chosen)))

    except OSError:

        return chosen

    # ARCHITECTOS_LAUNCHER_IDENTITY_V1 — record enough to detect a recycled
    # pid later. The pid file alone cannot distinguish "still our service"
    # from "an unrelated process that inherited this number".
    try:

        import json

        identity = _process_identity(chosen)

        record = {"pid": int(chosen)}

        if identity is not None:

            record["exe"] = identity[0]
            record["created"] = identity[2]

        with open(_owner_path(name), "w", encoding="utf-8") as handle:

            json.dump(record, handle)

    except OSError:

        pass

    return chosen


def start_service(
    name,
    script
):
    """Start one ArchitectOS-owned service, logging to logs/runtime/."""

    os.makedirs(
        LOG_DIR,
        exist_ok=True
    )

    log_path = os.path.join(
        LOG_DIR,
        name.lower() + ".log"
    )

    python, _ = pick_python()

    # ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — spawn the REAL interpreter, not
    # the venv's delegating launcher, so the pid we record is the process that
    # holds the port and whose lifetime we can actually vouch for.
    python, service_pythonpath = service_interpreter(python)


    # LOG_ROTATION_FIX_01 — the child receives an appendable,
    # INHERITABLE file handle so its stdout/stderr keep working
    # after the launcher exits (services run DETACHED). The size
    # bound itself is enforced inside the child by
    # core/runtime_logging.py, because a launcher-side writer
    # cannot outlive a detached service.
    #
    # A visible marker line records the active rotation policy.
    try:

        with open(
            log_path,
            "ab"
        ) as _marker:

            _marker.write(

                (
                    "\n\n===== "
                    + name
                    + " start @ "
                    + time.strftime("%Y-%m-%d %H:%M:%S")
                    + " (bounded log: "
                    + str(LOG_MAX_BYTES)
                    + " B x "
                    + str(LOG_BACKUP_COUNT)
                    + " backups, enforced in-service) =====\n"
                ).encode("utf-8")

            )

    except OSError:

        pass


    popen_kwargs = dict(

        args=[python, script],

        cwd=ROOT,

        env=localhost_env(service_pythonpath),

        stdin=subprocess.DEVNULL,

        # LOG_ROTATION_FIX_01 — the service writes its own bounded
        # log via core/runtime_logging.py, so the inherited stdout
        # must NOT be a second writer to the same file (that would
        # defeat the size bound). It goes to DEVNULL instead; any
        # output the service produces after logging is configured
        # is re-emitted through the logging system.
        stdout=subprocess.DEVNULL,

        stderr=subprocess.DEVNULL,

    )


    base_flags = _creation_flags()


    # Try to break away from an inherited Windows job object first.
    # When the launcher is itself started inside a job (IDE terminal,
    # CI runner, service wrapper) the services would otherwise be
    # killed the moment the launcher exits. Fall back cleanly when
    # the job does not permit breakaway.
    process = None

    if os.name == "nt" and base_flags:

        try:

            process = subprocess.Popen(

                creationflags=(
                    base_flags
                    | subprocess.CREATE_BREAKAWAY_FROM_JOB
                ),

                **popen_kwargs

            )

        except OSError:

            process = None


    if process is None:

        process = subprocess.Popen(

            creationflags=base_flags,

            **popen_kwargs

        )


    # The service owns its log file outright (bounded by its own
    # logging handler); the launcher holds no handle to it.
    try:

        with open(
            _pid_path(name),
            "w",
            encoding="utf-8"
        ) as f:

            f.write(
                str(process.pid)
            )

    except Exception:

        pass


    print(
        "  "
        + name.ljust(9)
        + "starting -> pid "
        + str(process.pid)
    )

    print(
        "  "
        + name.ljust(9)
        + "log      -> "
        + log_path
    )


    return process, log_path



def tail_log(
    log_path,
    limit=1200
):

    try:

        with open(
            log_path,
            "rb"
        ) as f:

            f.seek(0, os.SEEK_END)

            size = f.tell()

            f.seek(
                max(0, size - limit)
            )

            return f.read().decode(
                "utf-8",
                errors="replace"
            )

    except Exception:

        return ""


def wait_for_http(
    url,
    process=None,
    timeout=None
):
    """Poll a health URL until it answers, the child dies, or timeout."""

    if timeout is None:

        timeout = RC.STARTUP_TIMEOUT

    started = time.time()


    while (
        time.time() - started
    ) < timeout:


        probe = probe_http(
            url
        )

        if probe["ok"]:

            return True, round(
                time.time() - started,
                1
            ), None


        if process is not None and process.poll() is not None:

            return False, round(
                time.time() - started,
                1
            ), (
                "process exited with code "
                + str(process.returncode)
            )


        time.sleep(0.5)


    return False, round(
        time.time() - started,
        1
    ), "timeout"


def ensure_service(
    name,
    script,
    url
):
    """Start a service if needed, then verify it is reachable."""

    probe = probe_http(
        url
    )

    if probe["ok"]:

        # Re-own the pid file: services started by an earlier launch may have
        # a stale or wrong pid recorded.
        owner = _record_service_pid(name, url)

        print(
            "  "
            + name.ljust(9)
            + "already running -> "
            + url
            + ("  (pid " + str(owner) + ")" if owner else "")
        )

        return True, None


    process, log_path = start_service(
        name,
        script
    )

    ok, elapsed, error = wait_for_http(
        url,
        process=process
    )


    if ok:

        owner = _record_service_pid(name, url, spawned_pid=process.pid)

        print(
            "  "
            + name.ljust(9)
            + "ready in "
            + str(elapsed)
            + "s -> "
            + url
            + ("  (pid " + str(owner) + ")" if owner else "")
        )

        return True, process


    print(
        "  "
        + name.ljust(9)
        + "FAILED to become ready ("
        + str(error)
        + ")"
    )

    tail = tail_log(
        log_path
    )

    if tail:

        print(
            "  "
            + name.ljust(9)
            + "last log lines:"
        )

        for line in tail.strip().splitlines()[-12:]:

            print("      | " + line)


    return False, process



# ==========================================================
# SERVICE SHUTDOWN (ArchitectOS-owned services only)
# ==========================================================

def stop_services():
    """Stop ArchitectOS-owned services after verifying who they are.

    ARCHITECTOS_LAUNCHER_PERSISTENCE_V1 — the previous version trusted
    logs/runtime/*.pid and called ``taskkill /T /F`` on whatever it found.
    That was unsafe twice over: the saved pid could name a parent or a
    delegating venv shim instead of the server (observed: 14248/43260 recorded
    while ports 5000/3000 were held by their children 43108/11100), and a
    recycled pid could belong to an unrelated process. ``/T`` also killed the
    service's children, which is exactly how killing a venv shim took the real
    server down with it.

    Now the LISTENING SOCKET decides which process is the candidate. A pid
    file is only a hint: a mismatch is reported, never obeyed. A candidate is
    then rejected unless its executable is one of this project's interpreters,
    its command line runs the expected entry point, its creation time is
    plausible, and it matches the recorded owner when one exists. Anything
    unproven is left running — the launcher fails CLOSED rather than guessing.

    ComfyUI and Ollama are externally managed and are never touched.
    """

    print("Stopping ArchitectOS runtime services...")

    stopped = 0

    targets = (
        ("CORE_API", RC.CORE_API_URL),
        ("UI", RC.UI_URL),
    )

    for name, url in targets:

        port = _url_port(url)

        owner = _listening_pid(port)

        path = _pid_path(name)

        recorded = None

        if os.path.isfile(path):

            try:

                with open(path, "r", encoding="utf-8") as handle:

                    recorded = int(handle.read().strip())

            except Exception:

                recorded = None

        if owner is None:

            print(
                "  " + name.ljust(9) + "not listening on port "
                + str(port) + " (nothing to stop)"
            )

            try:

                if os.path.isfile(path):

                    os.remove(path)

            except OSError:

                pass

            continue

        if recorded is not None and recorded != owner:

            print(
                "  " + name.ljust(9) + "pid file said " + str(recorded)
                + " but port " + str(port) + " belongs to " + str(owner)
                + " -> using the socket owner"
            )

        # ARCHITECTOS_LAUNCHER_IDENTITY_V1 — the socket owner and a python.exe
        # image are not enough: any Python can bind the port, and a pid can be
        # recycled. Require positive identity, and fail CLOSED when any part of
        # it is missing.
        verified, detail = _verify_service_identity(name, owner)

        if not verified:

            print(
                "  " + name.ljust(9) + "REFUSED (pid " + str(owner)
                + " on port " + str(port) + "): " + detail
            )

            print(
                "  " + name.ljust(9)
                + "left untouched; stop it manually if it is not ArchitectOS"
            )

            continue

        try:

            if os.name == "nt":

                completed = subprocess.run(

                    ["taskkill", "/PID", str(owner), "/F"],

                    capture_output=True,

                    timeout=10800

                )

                if completed.returncode != 0:

                    print(
                        "  " + name.ljust(9) + "could not be stopped (pid "
                        + str(owner) + ")"
                    )

                    continue

            else:

                os.kill(owner, 15)

        except Exception as error:

            print(
                "  " + name.ljust(9) + "stop failed: " + str(error)
            )

            continue

        print(
            "  " + name.ljust(9) + "stopped (pid " + str(owner)
            + "; " + detail + ")"
        )

        stopped += 1

        try:

            if os.path.isfile(path):

                os.remove(path)

            owner_record = _owner_path(name)

            if os.path.isfile(owner_record):

                os.remove(owner_record)

        except OSError:

            pass

    print(
        "\nStopped "
        + str(stopped)
        + " service(s). ComfyUI / Ollama untouched (external)."
    )

    _launcher_log(
        "stop_services: stopped=%d (ComfyUI/Ollama untouched)" % stopped
    )

    return 0


def _wait_ports_released(timeout=10800):
    """(released, still_busy) — wait until 3000/5000 are genuinely free.

    ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — ``ensure_service()`` reports
    ``(True, None)`` for a service it found ALREADY listening. ``main()`` then
    computes ``_fresh = core_process is not None and ui_process is not None``,
    which becomes False, and ``trusted_ui_url()`` returns None. The launcher
    prints "TRUSTED LOCAL UI: UNAVAILABLE", opens NO browser, and still exits 0.

    Immediately after an owned restart that is a race: ``taskkill`` has
    returned but the socket may not be released yet, so the very next probe
    can still see the dying service. The user-visible result was a console that
    closed with no browser and no trusted session.

    This makes the post-stop state explicit instead of inferred: either both
    ports are free (so the services really are freshly started) or the restart
    is reported as failed.
    """

    targets = (
        ("CORE_API", RC.CORE_API_URL),
        ("UI", RC.UI_URL),
    )

    deadline = time.time() + max(1.0, float(timeout))

    busy = []

    while True:

        busy = [
            name
            for name, url in targets
            if _listening_pid(_url_port(url)) is not None
        ]

        if not busy:

            return True, []

        if time.time() >= deadline:

            return False, busy

        time.sleep(0.25)


# ==========================================================
# MAIN
# ==========================================================

def main():

    banner()


    # ------------------------------------------------------
    # STATUS-ONLY MODE (no start)
    # ------------------------------------------------------

    if "--status" in sys.argv:

        result = run_preflight()

        print(
            format_report(result)
        )

        return 0 if result["ok"] else 1


    # ------------------------------------------------------
    # STOP MODE
    # ------------------------------------------------------

    if "--stop" in sys.argv:

        return stop_services()


    # ------------------------------------------------------
    # RESTART MODE (explicit consent: stops ArchitectOS-owned
    # services, then starts them again in this launch's trust
    # domain). Project data on disk is untouched.
    # ------------------------------------------------------

    if "--restart" in sys.argv:

        print("\n[*] Restarting ArchitectOS-owned services...")

        _launcher_log("restart requested (--restart)")

        stop_services()

        # Prove the restart really produced a fresh trust domain. Without this
        # the next probe can still see the service being torn down, be treated
        # as "already running", and silently withhold the trusted URL.
        _released, _busy = _wait_ports_released()

        if not _released:

            print(
                "\nERROR: these ports are STILL held after the restart: "
                + ", ".join(_busy)
            )

            print(
                "The launcher did not reuse them and did not open a browser: "
                "a trusted session cannot be issued for services that belong "
                "to another launch's trust domain."
            )

            print("See logs\\runtime\\launcher.log")

            _launcher_log(
                "restart ABORTED: ports still held -> " + ",".join(_busy)
            )

            return 1

        _launcher_log("restart: both ports released, starting fresh services")


    # ------------------------------------------------------
    # ENV / INTERPRETER
    # ------------------------------------------------------

    python_ok = check_python()


    # ------------------------------------------------------
    # EXTERNAL SERVICES (detect only - never auto-started)
    # ------------------------------------------------------

    ollama_ok = check_ollama()

    comfy_ok = check_comfyui()


    # ------------------------------------------------------
    # BIM
    # ------------------------------------------------------

    bim_ok = check_bim()


    # ------------------------------------------------------
    # ARCHITECTOS-OWNED SERVICES (started + verified)
    # ------------------------------------------------------

    print("\n[5] Starting ArchitectOS runtime services...")


    core_ok, core_process = ensure_service(

        "CORE_API",

        "app.py",

        RC.CORE_API_URL + RC.CORE_API_HEALTH_PATH

    )


    ui_ok, ui_process = ensure_service(

        "UI",

        os.path.join("ui", "app.py"),

        RC.UI_URL + RC.UI_STATUS_PATH

    )


    # ------------------------------------------------------
    # FINAL TRUTHFUL PREFLIGHT
    # ------------------------------------------------------

    print("\n[6] Runtime preflight")


    result = run_preflight()


    print(
        format_report(result)
    )


    print(
        "\nBIM Core:",
        "CONNECTED" if bim_ok else "ERROR"
    )

    print(
        "Python runtime deps:",
        "OK" if python_ok else "MISSING"
    )


    overall = (
        result["ok"]
        and python_ok
    )

    # ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — assigned BEFORE the branch so
    # no code path can read an unbound local (AST rule A5).
    _open_failed = False


    print("\n" + "=" * 60)


    if overall:

        print("ARCHITECTOS SYSTEM READY")

        print("STATUS: ONLINE")

        print(
            "CHAT: "
            + ("READY" if result["chat_ready"] else "DEGRADED")
        )

        print(
            "RENDER: "
            + ("READY" if result["render_ready"] else "DEGRADED")
        )

        print("FINAL: RUNTIME_FOUNDATION_01_PASS")

        _fresh = (core_process is not None and ui_process is not None)

        _trusted_url = trusted_ui_url(
            RC.UI_URL, _LOCAL_BOOTSTRAP_TOKEN, _fresh
        )

        if _trusted_url:

            # ARCHITECTOS_LAUNCHER_IDENTITY_V1 — do not echo a live bootstrap
            # token when the browser is the delivery channel: the console is
            # persistent scrollback and often redirected to a file. The URL is
            # printed only when it is the user's ONLY way in.
            if "--open-ui" in sys.argv:

                print(
                    "TRUSTED LOCAL UI: one-time bootstrap token issued and "
                    "delivered to your browser (not printed here)"
                )

            else:

                print("TRUSTED LOCAL UI: " + _trusted_url)

        else:

            # A previously running child did not inherit THIS launch's proxy
            # secret. Advertising the new bootstrap would be misleading and
            # could never authenticate end-to-end. Fail closed and require a
            # deliberate owned-service restart.
            print(
                "TRUSTED LOCAL UI: UNAVAILABLE — these services were already "
                "running and belong to a different launch's trust domain"
            )

            print(
                "To open a trusted session, restart the owned services with: "
                "START_ARCHITECTOS.bat  (or launcher.py --restart --open-ui)"
            )

            _launcher_log(
                "trusted URL UNAVAILABLE (fresh=%s) -> services were reused"
                % _fresh
            )

            # A requested browser session that cannot authenticate is a FAILED
            # launch, not a success. Returning 0 here is what let the BAT print
            # "ready" and close the console while the user got nothing.
            if "--open-ui" in sys.argv:

                _open_failed = True

        if "--open-ui" in sys.argv:

            if _trusted_url:

                print("Opening the trusted local UI in your browser...")

                _opened = False

                try:

                    _opened = bool(webbrowser.open(_trusted_url))

                except Exception as _browser_error:

                    print(
                        "Could not open a browser automatically: "
                        + str(_browser_error)
                    )

                if not _opened:

                    # The token is shown ONLY here: without a browser launch
                    # there is no other way for the user to bootstrap.
                    print("Open this URL manually: " + _trusted_url)

                    # A double-clicked BAT closes its console right after this.
                    # Returning success here would destroy the only copy of the
                    # URL, so a requested-but-failed browser open is reported
                    # as a failure and the caller keeps the window open.
                    _open_failed = True

                _launcher_log(
                    "browser open: "
                    + ("requested" if _opened else "FAILED (URL printed)")
                )

            else:

                # Never open a URL that cannot authenticate: it would look
                # like a broken product instead of a stale trust domain.
                print(
                    "Not opening a browser: no URL from this launch can "
                    "authenticate against services it did not start."
                )

                _launcher_log("browser NOT opened: no trusted URL")


    else:

        print("SYSTEM CHECK FAILED")

        for blocker in result["blockers"]:

            print(" - " + blocker)

        if not python_ok:

            print(" - Python runtime deps missing for this interpreter")

        print("FINAL: RUNTIME_FOUNDATION_01_BLOCKED")


    print("=" * 60)


    # ArchitectOS-owned services were started as separate processes and
    # keep running after this controller exits. START_ARCHITECTOS.bat
    # holds the console open.
    #
    # ARCHITECTOS_LAUNCHER_RESTART_FRESHNESS_V1 — an --open-ui launch that
    # could not issue a trusted session is a FAILURE even when both services
    # answer: the user gets no authenticated UI. The caller (BAT) relies on
    # this exit code instead of guessing from the port.
    _ok = bool(overall) and not _open_failed

    _launcher_log(
        "verdict: %s (overall=%s open_failed=%s)"
        % ("OK" if _ok else "FAILED", overall, _open_failed)
    )

    return 0 if _ok else 1



if __name__ == "__main__":

    sys.exit(
        main()
    )
